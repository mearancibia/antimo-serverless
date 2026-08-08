# Prompt para Claude Code — Módulo "Caja de respaldo" (mobile)

> Pegá este archivo como brief. Antes de tocar nada, leé `CLAUDE.md` y `MIGRACION.md`:
> la app **hoy corre en Vercel + Supabase** (fork serverless), no en local. El motor es
> `engine.py` (`compute(src) -> DATA`), los datos salen de `sources.py` (`SupabaseSource` en
> producción, `LocalSource` para verificar), y los endpoints viven en `api/index.py` +
> `sl_common.py` + `handlers.py` + `auth.py`. **Regla de oro: nada de lo que hoy muestra el
> dashboard puede cambiar de número ni romperse.**

---

## 1. Objetivo

Agregar una **segunda caja de cobro** para cuando el cajero de Bistrosoft no da abasto en un
rush. Es una caja **independiente**: lo que se cobra acá se **suma** a lo que trae la API de
Bistrosoft, sin pisarlo ni duplicarlo. En el backend, cada venta se guarda **en el mismo
formato** que ya produce el conector de Bistrosoft (fila(s) de ranking de productos + registro
de caja por noche), para que el motor la sume solo.

Este módulo —y **solo este módulo**— tiene que ser **mobile-first** (se usa desde el celular).
El dashboard grande sigue siendo desktop como está.

## 2. Modelo mental (mantenerlo simple)

Nueva caja → cobra → el backend guarda la venta como la guarda Bistrosoft → `engine.compute`
suma las dos cajas. Son fuentes independientes que se suman. No hay merge complicado ni
recálculo por venta: se guarda el dato y se suma cuando el motor corre.

```
CELULAR (caja.html, mobile, offline-first)
  │  cobra → guarda en IndexedDB → sincroniza
  ▼
POST /api/caja_venta  (Vercel serverless, rol cajero)
  │  escribe ventas_backup + cajas_backup en Supabase → recompute()
  ▼
engine.compute(SupabaseSource)                      Supabase
  │  ventas   = ventas  + ventas_backup   (suma por producto+noche)
  │  cajas    = cajas   ⊕ cajas_backup     (suma por noche, en sources.py)
  ▼
DATA → dashboard (todo ya sumado, sin duplicar)

IMPRESIÓN (aparte del flujo de datos):
CELULAR ──(red local del bar)──► relay print-bridge ──(socket 9100)──► POS80C WiFi
```

## 3. Backend — dónde y cómo se guarda (Supabase)

**No escribir en las tablas `ventas` ni `cajas` existentes.** Dos razones verificadas en el
código:

- `sl_common.write_pull()` hace `ventas.delete().like("iso", ym+"-%")` → **borra el mes
  completo** y reinserta en cada pull. Ventas backup ahí se perderían.
- La tabla `cajas` tiene PK `fecha_key` y el pull hace **upsert por noche** → una caja backup
  de la misma noche pisaría la de Bistrosoft.

**Crear dos tablas nuevas** (agregarlas a `supabase_schema.sql`, idempotente, con RLS activado
igual que el resto):

```sql
-- ventas cargadas por la caja de respaldo (NO las toca el pull de Bistrosoft)
create table if not exists ventas_backup (
  id bigint generated always as identity primary key,
  nombre text not null,       -- nombre CRUDO del producto (el motor lo normaliza al leer)
  fecha text,                 -- "DD-MM"
  iso text,                   -- "YYYY-MM-DD" (noche de caja, corte 08:00, hora LOCAL)
  unidades numeric,
  monto numeric,              -- en PESOS (no centavos)
  ticket text,                -- id del ticket backup (para anular / excluir)
  creado_ts timestamptz not null default now()
);

-- cierres por noche de la caja de respaldo
create table if not exists cajas_backup (
  fecha_key text primary key, -- ISO de la noche
  data jsonb not null         -- MISMA forma que _nuevo_dia() del conector (ver §5)
);
```

**Lectura / suma (en `sources.py`):** `SupabaseSource` (y `LocalSource`, para que el gate de
verificación siga andando) tiene que, al armar `src`:

1. **Ventas:** concatenar las filas de `ventas` + `ventas_backup` en la misma lista `ventas`
   que ya arma. El motor agrupa por `(nombre normalizado, iso)` y **suma solo** → una venta
   backup de un producto que ya vendió Bistrosoft cae en la misma fila y suma. **No** normalizar
   en el cliente/JS: emitir el nombre crudo y dejar que `engine`/`norm()`+`UNIFICAR` lo resuelvan
   (si no, el producto se desdobla).
2. **Cajas:** para cada noche, si hay caja Bistrosoft **y** caja backup, **sumar** los campos
   numéricos (`total_vendido`, `efectivo`, `tarjetas`, `qr`, `otros_pago`, `comensales`,
   `descuentos`, `retiros`, `depositos`) y **concatenar** `detalle_retiros`/`detalle_descuentos`.
   Hacer esta fusión **en la source, antes de pasar al motor**, así el dedupe existente
   (`engine._dedup_cajas`, que se queda con uno preferiendo `archivo=="Bistrosoft API"`) queda
   **intacto y no hay que tocarlo**: recibe una sola caja por noche, ya sumada. La caja fusionada
   debe conservar el `archivo` de la fuente Bistrosoft cuando exista, para no alterar la
   preferencia del dedupe frente al PDF.

**Verificar** que con las tablas backup vacías, `compute(LocalSource())` y
`compute(SupabaseSource())` dan **idéntico** a hoy (los gates de `MIGRACION.md`).

## 4. Endpoint nuevo + auth/RBAC

Agregar `POST /api/caja_venta` como un `apply(data, sb)` nuevo en `handlers.py`, registrado en el
dict `handlers.ROUTES` (mismo patrón que `_dia_cerrado`, `_stock`, etc.). `api/index.py` lo
despacha solo (busca `ROUTES.get(name)`, ejecuta, audita con `audit(sb, user, name, data)` y
llama `recompute(sb)`) — **no** hay que tocar `api/index.py` salvo que necesites lógica especial.
El `apply` recibe una venta ya cerrada (líneas + pago) y escribe: N filas en `ventas_backup` (una
por producto, bruto) + upsert de la noche en `cajas_backup` (sumando sobre lo que ya haya de esa
noche).

- **Rol:** agregar `"caja_venta"` al `frozenset POST_CAJERO` de `auth.py` (el cajero ya tiene la
  solapa Caja). El bloqueo es server-side: `auth.puede_post()` devuelve 403 a quien no
  corresponda y queda auditado como `denegado:caja_venta`.
- **Idempotencia:** cada venta lleva `ticket` único; reintentos desde el celu (mala señal) **no**
  deben duplicar. Upsert/dedupe por `ticket`.
- ⚠️ **No** colgar un recálculo pesado por cada venta si se puede evitar: agrupar. Pero como el
  patrón actual recalcula por POST y en la nube no hay concurrencia de archivos (Supabase
  serializa), es aceptable; priorizar correctness sobre latencia.

## 5. Formato exacto de la venta (espejo del conector) — CRÍTICO (Regla #0)

El POS de referencia (`index.html` subido, base `datos-demo.json`) guarda distinto que ANTIMO.
Al emitir hacia el backend hay que traducir:

- **Plata:** el POS de referencia usa **centavos** (`precio: 1000000` = $10.000). Convertir a
  **pesos** (÷100). Errarle = inflar 100×.
- **Noche de caja:** bucketizar por **fecha de cierre con corte 08:00 en hora LOCAL** (idéntico
  a `business_ddmm_ym` / `bistro.py`). Un cobro de las 2am pertenece a la noche que cerró esa
  madrugada. No usar UTC.
- **Ranking = bruto por ítem; descuento aparte.** Igual que la API: la fila de `ventas_backup`
  lleva el monto bruto del ítem; el descuento va en `cajas_backup.data["descuentos"]` (+ detalle),
  no restado dentro del producto. `total_vendido` de la caja = neto cobrado.
- **Anuladas / cortesías:** excluir líneas anuladas (no van al ranking ni a la caja). La
  cortesía (gratis) cuenta para consumo (unidades) con monto 0.
- **Medios de pago:** mapear los del POS de referencia a los campos de la caja: EFECTIVO→
  `efectivo`, TARJETA→`tarjetas`, QR→`qr`, TRANSFERENCIA y cualquier otro→`otros_pago`. Pagos
  mixtos: repartir el monto por medio.
- **Campos de la caja backup:** misma forma que `_nuevo_dia()`:
  `{total_vendido, efectivo, tarjetas, qr, otros_pago, comensales, descuentos, retiros,
  depositos, detalle_retiros, detalle_descuentos}` + `fecha` (DD-MM), `fecha_iso`, `fecha_key`
  (ISO), `archivo:"Caja respaldo"`.
- **Nombres de producto:** el catálogo de la caja backup se **siembra desde los productos que
  ANTIMO ya conoce** (los de `maestro_productos` / ranking), para que el nombre crudo emitido
  caiga en la misma fila al normalizar. No inventar nombres nuevos que no matcheen.

## 6. Anti doble conteo + válvula

Regla operativa (no de código): una venta se cobra en Bistrosoft **o** en la caja de respaldo,
**nunca en las dos**. Además, construir una **válvula por noche**: un toggle "esta noche ya se
volcó a Bistrosoft → excluir del cómputo" que, al activarse para una noche, hace que el motor
**ignore tanto `ventas_backup` como `cajas_backup` de esa noche** (las dos, no una — si no, los
productos se contarían doble aunque la caja no). Guardar el flag en una tabla/override simple
(ej. `backup_excluido(iso primary key)`) y filtrar en `sources.py`.

## 7. Módulo mobile (`caja.html`)

- Página **propia**, **mobile-first** (no tocar el layout desktop del dashboard). Agregarla a
  `vercel.json` (build estático + ruta, ej. `/caja`). Respetar la identidad visual del dashboard
  (mismos colores/tipografía/tokens).
- **Solo la herramienta de Cobro** del POS de referencia: selector rápido de productos + cobro
  con medios mixtos + vuelto + (opcional) propina. **No** portar turno/arqueo/reportes/gestión de
  productos: eso vive en el dashboard.
- **Login `cajero`** (usa la sesión firmada que ya existe; redirige a `/login` si no hay sesión).
- **Offline-first:** como es una app en la nube, si se cae internet en pleno rush no puede
  trabarse. Bufferear cada cobro en **IndexedDB** y **sincronizar** a `/api/caja_venta` cuando
  vuelva la conexión (cola con reintentos, dedupe por `ticket`). PWA con service worker para que
  cargue sin red.

## 8. Impresión POS80C — la realidad en la nube

Una app servida por Vercel **no puede imprimir directo** en una impresora WiFi del bar: ni el
navegador del celu abre un socket TCP a la impresora, ni las funciones serverless llegan a la
LAN del bar. "Por WiFi" es posible pero necesita **un relay local en la red del bar**. Soportar,
elegible en Ajustes:

- **Modo relay LAN (recomendado para WiFi):** un proceso chico corriendo en el bar en la misma
  red que la impresora (sirve tal cual el `print-bridge.js` de referencia: `POST /print` con
  `{ip, port, dataBase64}` → socket 9100). El celu le manda el ticket **al relay por IP local**,
  el relay lo pasa a la impresora. Requiere IP fija/reserva DHCP de la impresora **y** del relay.
- **Modo WebUSB:** impresora por USB-OTG al celu, impresión directa desde el navegador (sin
  relay, sin LAN) — pero es USB, no WiFi. Requiere contexto seguro (HTTPS de Vercel lo es).
- **Modo navegador:** diálogo de impresión del sistema hacia una impresora que el dispositivo ya
  tenga instalada (respaldo universal).

Reusar los **mismos bytes ESC/POS** del proyecto de referencia (code pages CP858/CP437/CP1252,
degradado sin acentos). **Guardar la venta SIEMPRE pasa primero; imprimir es posterior y nunca
puede bloquear ni revertir un cobro** (igual que el ref): si falla la impresión, la venta ya
quedó, y se ofrece Reimprimir + `.txt` de respaldo.

## 9. Invariantes que NO se pueden romper (de `CLAUDE.md` §3, adaptadas a la nube)

1. Todo POST pasa por el chequeo de origen/sesión existente (`sl_common`/`auth`). No aflojarlo.
2. Todo texto tipeado por el personal (nombre de mesa, concepto, comentarios) va **escapado**
   antes de `innerHTML` en cualquier vista del dashboard que lo muestre (`esc()`).
3. Read-modify-write con lectura estricta (abortar ante dato corrupto, no pisar con vacío).
4. Nunca inventar el año ni la noche: si un dato no resuelve, queda visible sin cruzar, no se
   adivina.
5. Sin dependencias nuevas fuera de lo que ya usa el proyecto (stdlib + `requests` en el back;
   JS vanilla en el front). El relay de impresión es Node puro, sin `npm install`.

## 10. Verificación (obligatoria antes de dar por cerrado)

- **Gate de no-regresión:** con las tablas backup vacías, `compute(LocalSource())` y
  `compute(SupabaseSource())` == DATA de hoy (las 13 secciones), byte a byte donde aplique.
- **Suma correcta:** cargar una venta backup de un producto que Bistrosoft ya vendió esa noche →
  las unidades/monto se **suman** en la misma fila (no aparece duplicado el producto), y la caja
  de esa noche suma ambos totales.
- **Noche solo-backup:** una noche sin datos de Bistrosoft pero con ventas backup aparece como
  noche con datos (completitud/patrón de apertura), con su `dow` y corte 08:00 correctos.
- **Válvula:** activar el toggle de una noche → desaparecen del cómputo **tanto** el ranking
  backup **como** la caja backup de esa noche; los totales vuelven exactamente a lo que da la API
  sola.
- **Plata/hora:** un cobro de $10.000 no aparece como $1.000.000 ni $100; un cobro post-medianoche
  cae en la noche correcta.
- **RBAC:** `cajero` puede `POST /api/caja_venta`; un rol no autorizado recibe 403 y queda
  auditado.
- **Impresión no bloquea:** con la impresora apagada, la venta igual se guarda y sincroniza.
- Correr `scripts/test_rbac.py` y los gates de `MIGRACION.md`; agregar un test del endpoint nuevo
  contra el Supabase falso.

## 11. Fuera de alcance (no hacer)

- No portar del POS de referencia: gestión/creación de productos, turno/arqueo, reportes (ya
  están en el dashboard).
- No tocar el flujo de pull de Bistrosoft ni las tablas `ventas`/`cajas`.
- No cambiar el layout desktop del dashboard.
