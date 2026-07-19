# ANTIMO — Panel de gestión de bar (app local)

> Este archivo es el contexto del proyecto para Claude Code. Estás trabajando dentro de la
> carpeta `ANTIMO/` en una MacBook. **El sistema es 100% local**: corre con Python del sistema
> y se usa desde **Chrome** en la misma Mac. No hay servidor en la nube, no hay frameworks, no
> hay build tools. Mantené SIEMPRE esa premisa: todo tiene que seguir funcionando con doble clic
> y navegador local.

---

## 1. Qué es

Un panel de rentabilidad, compras y gestión para un bar/restaurante (razón social **ANTIMO**).
Toma las ventas del POS **Bistrosoft** (vía su API), las costea contra recetas/insumos, y muestra
rentabilidad por producto, matriz de menú (BCG), lista de compras, control de caja y OPEX. Además
permite **editar recetas, costos, OPEX y crear productos** desde el propio tablero, y recalcula al
instante.

**Objetivo del dueño:** que sea fiel a la realidad, automático y editable, sin depender de nadie,
gratis y local.

---

## 2. Cómo se usa (local, Chrome, MacBook)

- **`run_ANTIMO_app.command`** (doble clic) → arranca `app_antimo.py`, un servidor local con la
  librería estándar de Python (`http.server`) en `http://127.0.0.1:8733` (si está ocupado prueba
  8734…8740), y abre el navegador. **En este modo el tablero es editable** (aparece el badge
  "✏️ Modo edición"). La ventana de Terminal debe quedar abierta; cerrarla apaga la app.
- **`actualizar_ANTIMO.command`** (doble clic) → corre el conector (trae ventas de Bistrosoft) y
  regenera el tablero, sin levantar el servidor. Modo rápido.
- Abrir `dashboard_ANTIMO.html` directo (sin la app) → funciona en **modo lectura** (sin editar).
- Requisitos en la Mac: Python 3 (Command Line Tools) + `pip install --user openpyxl requests
  pdfplumber` (los `.command` lo hacen solos). La API de Bistrosoft necesita internet normal.

**Detección de modo:** el tablero, al cargar, hace `fetch('/api/ping')`. Si responde
`{app:true}` → modo edición y trae datos de `/api/data`. Si falla (archivo abierto directo) →
modo lectura con los datos embebidos.

**Carpeta `_archivo/`:** todo lo que ningún script lee, agrupado y sacado del camino (no se borra
nada, por las dudas). `_archivo/viejo/` = legado de antes de que existiera esta versión de ANTIMO.
`_archivo/docs_superados/` = docs reemplazadas por otras más nuevas (**sí** se versiona en git,
tiene valor histórico). `_archivo/datos_sin_uso/` = Excel manuales y un PDF de caja que ya cubre
la API, más un backup viejo del Excel base (**no** se versiona, son datos/binarios). Verificado
antes de mover: `entrada/archivo_manual/` nunca lo leía el motor (el glob de `entrada/*patrón*`
no entra a subcarpetas); el PDF sobrevivía a la deduplicación 0 veces (su noche ya la trae la API).

---

## 3. Stack y principios (NO romper)

- **Backend:** `app_antimo.py`, solo librería estándar de Python (`http.server`,
  `socketserver`). Sin Flask ni dependencias web.
- **Motor:** `actualizar_antimo.py`, un único script autocontenido (~500 líneas). Usa `openpyxl`
  (Excel), `pdfplumber` (PDF de caja, opcional), `datetime`, `json`, `re`. **Editar este archivo
  directamente.**
- **Conector:** `conector_bistrosoft.py`, usa `requests`.
- **Frontend:** `dashboard_tpl.html` — un solo archivo con HTML + CSS + **JavaScript vanilla**
  (sin React, sin librerías, sin CDN). Se genera `dashboard_ANTIMO.html` reemplazando el token
  `@@DATA@@` por el JSON de datos. **Editar la plantilla `dashboard_tpl.html`, no el HTML
  generado.**
- **Reglas de oro (respetarlas siempre):**
  1. **Regla #0 — honestidad de datos:** nunca inventar costos ni márgenes. Si a un producto le
     falta receta o costo → queda **N/D** (no se fuerza a la matriz, no se recomienda eliminarlo).
  2. **NO escribir `datos/datos_general.xlsx` por código:** al re-guardarlo con openpyxl se
     rompen los valores cacheados de las fórmulas de la hoja `Costo_Base`. Los cambios del usuario
     van a **archivos override JSON** que el motor fusiona (ver sección 6). El "Excel completo"
     se genera aparte (`datos_general_actualizado.xlsx`) aplicando los overrides a una copia.
  3. **Agrupación por noche de caja:** una noche de bar cruza la medianoche. Se agrupa por
     **fecha de cierre** (corte 08:00: lo que pasa entre 00:00 y 07:59 cuenta para la noche que
     cerró esa madrugada). Coincide con cómo rotula Bistrosoft. Ver `business_ddmm_ym` en el
     conector.
     ⚠️ **Corolario: los rótulos van corridos +1 respecto de la noche coloquial.** El bar abre de
     miércoles a domingo a la noche, pero esas noches figuran como **Jue, Vie, Sáb, Dom y Lun**
     (la noche del sábado cierra el domingo → figura "Dom"). Verificado en los datos: Lun 5/5 y
     Dom 5/5 con datos, Mar 0/5 y Mie 1/5. **Nunca hardcodear los días de apertura** — se infieren
     del histórico con `patronApertura()` en el front (dow con datos en ≥50% de sus fechas).
     Por el mismo corrimiento, "findes" (Resumen → tarjeta Findes vs. Semana) **no** se define
     hardcodeando las etiquetas Sáb/Dom/Lun: se calcula restando 1 día a la fecha etiquetada
     (`nocheReal()` en el front) y comparando contra Vie/Sáb/Dom reales. Así el código no depende
     de que el lector recuerde el corrimiento — es autoexplicativo. **Ojo con tildes:** `DOWN`
     usa `'Sab'` sin tilde; un `Set` con `'Sáb'` (con tilde) no matchea nunca y rompe la
     clasificación en silencio (pasó una vez en desarrollo — visible sólo comparando contra los
     números reales, no a simple vista).
  4. **Comandas anuladas (status VOID):** Bistrosoft ya manda la comanda anulada y su reversa
     (mismo monto, signo opuesto, mismo `ticketNumber`) — verificado sobre datos reales: siempre
     suman neto $0, nunca cruzan de una noche a otra. Por eso el total vendido **nunca estuvo
     inflado** por anulaciones en los datos históricos (a diferencia de lo que se sospechaba
     originalmente). Aun así, `parse_items` en el conector excluye explícitamente por
     `ticketNumber` en vez de confiar en la cancelación implícita: si se corre el conector a
     mitad de un turno, la reversa de una anulación reciente puede no haber llegado todavía y
     quedaría plata de más contada un rato. `--mock` ejercita este camino con un ticket anulado.
  4. **Todo local y sin dependencias nuevas** salvo openpyxl/requests/pdfplumber. Nada de npm,
     bundlers, ni servicios externos.

---

## 4. Flujo de datos

```
Bistrosoft API ──(conector_bistrosoft.py)──▶ entrada/api_ventas_YYYY-MM.xlsx  (ranking de ventas)
                                          └─▶ datos/cajas_api.json            (cierres de caja)

datos/datos_general.xlsx (maestro: recetas, costos, OPEX base)
        + overrides JSON (ediciones del usuario)
        + entrada/api_ventas_*.xlsx + datos/cajas_api.json
                          │
                          ▼
              actualizar_antimo.py  (motor de costeo)
                          │
          ┌───────────────┴───────────────┐
          ▼                               ▼
  datos_dashboard.json            dashboard_ANTIMO.html
  (DATA calculada)                (plantilla + DATA embebida)
```

`app_antimo.py` orquesta: sirve el HTML, expone la API de edición, y cada edición **escribe el
override correspondiente y vuelve a correr `actualizar_antimo.py`** (subproceso), devolviendo la
DATA nueva.

---

## 5. Modelo de datos (`datos_dashboard.json` / objeto `DATA` en el front)

```jsonc
{
  "generado": "2026-07-14",
  "logo": "data:image/png;base64,…",        // logo embebido si existe datos/logo.png o ANTIMO/logo.png
  "opex": 13310000,                          // total OPEX mensual
  "opex_pend": 0,                            // rubros en $0 no confirmados
  "opex_detalle": [ {"cat","item","cantidad","unitario","monto","confirmado_cero"} ],
  "dias": [ {"fecha":"DD-MM","iso":"YYYY-MM-DD","dow":"Mie"} ],   // ordenados
  "productos": [
    {
      "pos": "CUARTO DE LIBRA", "key": "CUARTO DE LIBRA",   // key = identidad estable (ver abajo)
      "cat": "HAMBURGUESAS Y SANDWICH", "grupo": "COMIDA",
      "nd": false, "tipo": "receta", "costo": 7584, "nota": "",
      "precio_lista": 13000,                                // null si no matchea, ver más abajo
      "susp": "si", "susp_motivo": "…",                     // solo si el dueño lo marcó
      "breakdown": [ {"insumo","qty","unidad","cxu","sub"} ],     // desglose por unidad
      "byday": { "DD-MM": [unidades, monto] },                    // ventas por día
      "receta_nombre": "CUARTO DE LIBRA",                          // solo receta/promo
      "receta_ings": [ ["Ingrediente","115g"] ],                  // receta cruda editable
      "combo_comp": [ ["Insumo", 700, "ml"] ],                    // solo combo
      "editable": true
      // si nd:true → { "nd":true, "motivo", "falta", "donde" } en vez de costo/breakdown
    }
  ],
  "insumos": { "Nombre": {"cxu","precio","cant_base","present","unidad","cb_cat","grupo","compartido"} },
  "consumo_dia": { "DD-MM": { "Insumo": cantidad_base } },        // para compras/reposición
  "cajas": [ {"fecha","iso","total_vendido","efectivo","tarjetas","qr","descuentos","retiros",
              "comensales","detalle_retiros":[{"concepto","monto","user","hora"}],
              "detalle_descuentos":[…],"fecha_dia","fecha_key"} ],
  "dias_cerrados": { "YYYY-MM-DD": "motivo" }          // noches que el dueño marcó sin apertura
}
```

Cada producto lleva `key` (nombre normalizado + unificado): es su **identidad estable** para guardar
marcas del dueño, porque `pos` es la grafía cruda del POS y puede variar. Cada caja lleva `iso`: las
cajas se **deduplican por fecha** (un cierre puede llegar por PDF y por API a la vez; gana la de la
API, que trae comensales y detalle por operador).

**`precio_lista`:** viene de la hoja **"Lista de Precios"** de `datos/datos_general.xlsx` (existe en
el Excel base desde siempre, nadie la usaba). Es el precio **oficial** — el verdadero "PVP" en el
sentido comercial habitual (Precio de Venta al Público) — complementario al **promedio real de
venta** que se calcula de las ventas (`byday`, columna "Prom. venta" en las tablas) — no lo
reemplaza.

**Match en dos pasos** (`precio_lista_de()` en `actualizar_antimo.py`), **nunca fuzzy** (Regla #0
— no adivinar a qué producto corresponde un precio):
1. Por nombre normalizado **exacto**.
2. Si no hay, por nombre **aplanado** (`_aplanar()`): mismas letras y dígitos ignorando espacios,
   puntuación y tildes. La cadena resultante tiene que ser **idéntica**, así que solo cubre
   diferencias de tipeo del POS: `"2 x 1 APEROL"`↔`"2 X 1.  APEROL"`, `"FERNET + COCA"`↔
   `"FERNET+COCA"`, `"CUMPLEANOS"`↔`"CUMPLEAÑOS"`. Si dos filas del Excel se aplanan al mismo
   texto con **precios distintos**, se descarta el match (ambiguo) en vez de elegir uno.

3. Si tampoco, por **equivalencia explícita** (`PRECIO_LISTA_ALIAS`): casos donde el nombre cambia
   de verdad y ningún algoritmo puede resolverlos sin adivinar — typos del POS (`"CORONA 33O"` con
   letra O en vez de cero, `"HEINIKEN CHICA"`) o el Excel detalla el envase y el POS no
   (`"COCA 600CC"`↔`"COCA"`). **Cada entrada fue confirmada por el dueño y contrastada contra el
   precio realmente cobrado** antes de agregarla; la evidencia quedó en el comentario del dict.
   Para agregar una nueva, hacer lo mismo: comparar `precio_lista` contra el promedio real de
   venta. Si coinciden (0-7%), es el mismo producto; si no, preguntar antes de mapear.

Resultado sobre los datos reales: **96 de 109** productos con precio (79 solo con match exacto,
90 sumando el aplanado, 96 con las equivalencias). Lo que queda sin precio son productos que
nunca estuvieron en la hoja (shots, Redbull, Speed, Tónica, Rabas) o los N/D.

⚠️ Caso especial sin resolver: el Excel tiene `Gin Aconcagua` ($9.500) **y** `GIN ACONCAGUA VASO`
($9.000) como líneas separadas, pero `UNIFICAR` fusiona ambos en un producto — hoy gana $9.500.
Resolverlo implica dejar de unificarlos, lo que cambiaría las ventas históricas de ese producto:
es una decisión del dueño, no un bug.

Ojo con no confundir dos cosas: **mapear** (decidir que dos nombres son el mismo producto) es
distinto de que **los precios coincidan**. `HEINIKEN CHICA` está bien mapeado y aun así muestra
−33% — vendió sus 13 unidades una sola noche a precio promocional. Esa brecha es exactamente lo
que la columna "Lista" está para mostrar, no un error de mapeo.

En Rentabilidad y Recetas se muestra junto al promedio real (`fPrecioLista()`),
resaltado en naranja cuando difiere más de `PRECIO_LISTA_UMBRAL` (5%) — eso puede señalar un
descuento, un cambio de precio a mitad de período, o algo mal cargado en el POS. Ya reveló algo
interesante: BEEFEATER + TONICA (lista $80.000, promedio real $50.000, -37.5%) es uno de los
productos marcados como "sospechoso" por margen falso (Fase 1) — además del costo mal mapeado, el
precio real vendido también se aleja bastante del oficial.

⚠️ **Ojo con la terminología:** antes de este cambio, la columna que hoy dice "Prom. venta" decía
"PVP"/"PV" a secas en los encabezados de tabla — comercialmente ambiguo, porque "PVP" en español
significa "Precio de Venta al Público" (el precio oficial), no un promedio. Se renombró para que
no quede ambigüedad ahora que conviven las dos columnas: "Prom. venta" = promedio real calculado
de las ventas; "Lista" = el verdadero PVP oficial. El campo interno `p.pv`/`x.pv` en el código
sigue llamándose así por compatibilidad — solo cambió la etiqueta visible.

**Editor de precio de lista:** `precio_lista` se puede editar desde la app (Rentabilidad y
Recetas, columna "Lista", `fPrecioLista()`), mismo patrón que el resto de los overrides —
`datos/precio_lista_override.json` (`{key: precio}`), pisa el valor de la hoja sin tocar el
Excel, `POST /api/precio_lista`. Vacío o `0` al guardar **vuelve al valor del Excel** (no lo
borra del producto), mismo criterio que `/api/stock`. También sirve para cargar un precio de
lista en productos que **nunca** tuvieron uno en la hoja (los inputs quedan vacíos con
placeholder "—", no bloqueados). Como los `<tr>` de Rentabilidad tienen `onclick` propio (abren
el modal), el input hace `stopPropagation()` en su handler de click — si se toca esa tabla y algo
dispara el modal al tocar el precio, revisar que ese `stopPropagation` siga ahí.

---

## 6. Sistema de overrides (dónde se guardan las ediciones) — carpeta `datos/`

`datos_general.xlsx` es la **base** (no se toca). El motor la carga y **fusiona por encima**:

| Archivo | Qué guarda | Se edita desde |
|---|---|---|
| `maestro_extra.json` | productos nuevos / remapeos (POS→tipo, factor, rend, costeo, nota) | "Nuevo producto" |
| `recetas_extra.json` | recetas nuevas o editadas `{nombre: [[ing, cant],…]}` | editor de recetas |
| `insumos_extra.json` | insumos nuevos `[{nombre,precio,pres,cant_base,unidad,cxu,cb_cat}]` | (manual / crear) |
| `precios_override.json` | precios de insumos cambiados `{insumo: precio}` (recalcula cxu) | solapa Costos |
| `combos_extra.json` | composición de combos `{POS: [[insumo,cant,unidad],…]}` | editor de combos |
| `opex.json` | OPEX editable `[{cat,item,cantidad,unitario,confirmado_cero}]` (monto = cant×unit) | solapa OPEX |
| `opex_cero_confirmado.json` | rubros OPEX confirmados en $0 (no cuentan como pendientes) | — |
| `sospechosos.json` | marca de precio/costo mal cargado `{key: {estado:"si"\|"no", motivo, ts}}` | modal de producto |
| `dias_cerrados.json` | noches sin apertura `{"YYYY-MM-DD": motivo}` (no cuentan como dato faltante) | tarjeta Completitud |
| `pours_extra.json` | rendimiento (ml) de pours editado `{key: ml}`, override parcial sobre `MAESTRO[key]["rend"]` | modal de producto (Recetas) |
| `stock.json` | conteos manuales de insumos vigilados `{insumo: {cant, fecha, umbral_dias?}}` — **no** es inventario perpetuo, ver más abajo | modal Stock (Costos / tarjeta Resumen) |
| `bistro_config.json` | credenciales Bistrosoft `{base,username,password,shopCode}` (**sensible**) | manual |
| `cajas_api.json`, `bistro_debug.json` | los genera el conector | — |
| `_backups/` | copias automáticas de cada override antes de pisarlo (últimas 20 c/u) | — |

**Backups:** `app_antimo._save()` respalda la versión previa en `datos/_backups/<archivo>.<YYYYMMDD-HHMMSS>.json`
antes de sobreescribir, conservando las últimas `BACKUP_KEEP` (20). `bistro_config.json` está **excluido a
propósito** (`NO_BACKUP`): es el único archivo con credenciales en claro y no conviene multiplicar copias.
Si el respaldo falla, avisa por Terminal pero nunca bloquea el guardado.

**Precios sospechosos:** el tablero **sugiere** revisar todo producto con margen ≥ `SUSP_THR` (90%, constante en
`dashboard_tpl.html`), pero solo el dueño **confirma** (`estado:"si"`) o **descarta** (`estado:"no"`) desde el modal.
Coherente con la Regla #0: la marca **no altera ningún costo, margen, KPI ni el P&L** — solo etiqueta y, con el
toggle "⚠️ Sin sospechosos", saca los confirmados de la tabla de Rentabilidad, la matriz BCG y las alertas
(se excluyen *antes* de `classify()` para no correr los promedios del BCG). La causa puede ser el precio del POS
**o** el costo del insumo desactualizado/proxy.

`opex.json` se **siembra automáticamente** de la hoja OPEX del Excel la primera vez, preservando el
total. Desde ahí, es la fuente editable del OPEX.

**Stock (alertas de quiebre):** decisión de diseño explícita, no un inventario perpetuo. Un inventario
perpetuo (restar cada venta, sumar cada compra) da un saldo exacto solo si **todas** las compras se
cargan siempre — si se salta una, el número queda mal y lo sigue estando hasta el próximo conteo manual
(peor que no tener alerta: una que dice "hay stock" cuando no hay). En cambio: el dueño carga un conteo
puntual (`stock.json`), y `stockCalc()` en el front resta el **consumo real** (`consumo_dia`, ya exacto)
desde esa fecha — sin necesidad de registrar compras. Eso nunca es una estimación.

Lo que SÍ es una estimación es "cuánto va a durar", y ahí se pondera por dos cosas (`ritmosRecientes()`):
1. **Ventana reciente** (`STOCK_VENTANA_DIAS`=21, ~3 semanas) en vez de toda la historia: un trago que
   se puso de moda o dejó de pedirse hace poco se refleja rápido, no diluido por meses de historia vieja.
   Si la ventana no tiene noches de algún tipo (findes o semana), cae al promedio de *toda* la historia
   para ese tipo — nunca deja el ritmo en 0 por falta de muestra.
2. **Findes vs. semana** (reusa `FINDES`/`nocheReal()` de la Fase 7a): findes vende ~el doble que semana
   en este bar, un ritmo único no sirve igual un martes que un sábado.

Con esos dos ritmos, `proyectarQuiebre()` simula **noche por noche** desde mañana (usando
`patronApertura()` + `dias_cerrados.json`, saltea las noches que no abren) hasta que el stock cruza
cero, devolviendo una **fecha de quiebre** ("se agota el jueves 24/07") en vez de un "X noches"
abstracto — más accionable: de un vistazo se sabe si alcanza hasta la próxima compra o no. Tope de
seguridad: 180 noches simuladas: si no se agota en ese horizonte, muestra "sin quiebre a la vista".

Como el `restante` se desactualiza si compran sin recontar, siempre se muestra "hace cuántas noches
fue el último conteo". Ver `STOCK_UMBRAL_DEFAULT` (3 noches) en `dashboard_tpl.html`, ajustable por
insumo — `critico` compara contra las noches simuladas hasta el quiebre, no contra un cociente plano.

**`stock.json["cant"]` está en UNIDADES DE PRESENTACIÓN, no en la unidad base con la que se
costea.** Ej.: "Cerveza Corona Porrón 710ml" — 1 unidad = 1 botella (710ml), `cant:7` significa
7 botellas, no 7 ml. La conversión usa `insumos[x].cant_base` (la misma que ya usa Compras para
decir "comprá 3 botellas" en vez de "comprá 2130 ml") — `stockCalc()` multiplica por `cant_base`
para restar contra `consumo_dia` (que sí está en unidad base) y divide de vuelta para mostrar.
El ratio "noches restantes" no cambia con esta conversión (el `cant_base` se cancela). **Ojo si
se toca este código:** los 119 insumos tienen `cant_base`/`present` válidos, verificado — no hay
casos especiales que rompan la conversión, pero cualquier insumo nuevo sin esos campos sí la
rompería (división por 1 por defecto, silenciosa).

**Exportar/importar stock en bloque:** botones en Costos (`stkExport`/`stkImport`), APP-only.
Exporta los 119 insumos completos (no solo los vigilados) como CSV con columnas
`Insumo;Presentacion;Cantidad_actual;Umbral_noches` — así el dueño hace un conteo físico general
una vez y decide ahí mismo cuáles vigilar. El import usa una **sola fecha para todo el lote**
(un `prompt()`, default hoy), no una por fila. Fila vacía **o con 0 explícito** → no se toca ese
insumo (decisión explícita: un 0 accidental en la planilla — autocompletado, arrastre de fórmula —
no debe borrar un insumo que sí se estaba vigilando; para dejar de vigilar hay que usar el botón
"Dejar de vigilar" del modal individual). Endpoint `/api/stock_bulk`, separado de `/api/stock`
(que sigue sirviendo para cargar/recontar un insumo a la vez). El parser de CSV (`parseCSV()`)
espera el mismo formato que ya generan `exportCSV()`/`exportStockCSV()`: BOM + `;` + comillas.

## 7. Motor de costeo (dentro de `actualizar_antimo.py`)

Cada producto vendido se busca en el Maestro por su nombre POS → `Tipo_venta`:
- **receta**: suma ingredientes × costo por unidad base (convierte unidades no métricas).
- **promo_2x1**: receta base × `factor` (2 → consume doble).
- **pour**: `rendimiento_ml / contenido_botella × precio` (X ml del insumo).
- **botella**: costo 1:1 de la botella entera.
- **directo**: costo del insumo por porción.
- **combo**: mini-receta (botella + N latas) — vive en un dict `COMBOS` en el código + `combos_extra.json`.
- **sin_datos** / sin mapear → **N/D**.

Detalles: hay un diccionario `ALIAS` que mapea nombres de ingredientes de receta a insumos de
`Costo_Base`; si un ingrediente ya es un nombre exacto de `Costo_Base`, se usa directo (fallback).
`parse_qty` interpreta cantidades (`120g`, `60 ml`, `1 unidad`, `4 lata`, `A gusto`, `1 cucharada`,
etc.) usando la hoja de Equivalencias. Hay **supuestos documentados** (pesos de pieza para
panes/medallón/masa/aceitunas, proxies como gin tonic con Gin Brighton, aguas 500ml). La
clasificación BCG (estrella/vaca/interrogante/perro) se calcula en el **frontend** sobre el rango
de fechas elegido.

---

## 8. Conector Bistrosoft (`conector_bistrosoft.py`)

- API: `POST /api/v1/Token` (JWT) → `GET /api/v1/TransactionDetailReport?startDate&endDate&shopCode&pageNumber`.
  Es un reporte de **detalle de transacciones** (una fila por movimiento), no un resumen ya
  sumarizado — separado del sistema que genera el PDF de cierre de caja en el momento.
- ⚠️ **Desfasaje de sincronización conocido:** este reporte puede tardar varias horas en reflejar
  la noche más reciente, aunque la caja ya haya cerrado. Si un número de ANTIMO no coincide con
  Bistrosoft para la noche más reciente (y solo para esa), **antes de sospechar de un bug**
  revisar el último `timestamp` que trae la API para esa fecha (`fetch_all` + tomar el máximo) y
  compararlo contra la hora de cierre real de esa noche. Si el timestamp más reciente es anterior
  al cierre, es sync lag de Bistrosoft — probar de nuevo más tarde, no hay nada para arreglar del
  lado de ANTIMO. Paginación: confirmado que no es un bug propio (se probó página por página, la
  API misma devuelve una página vacía cuando no hay más datos). Page size observado: 5000 items.
- Tipos de transacción reales: `- ITEM` / `- COMBO` (productos → ranking), `Comanda`/`Comanda (Multipago)`/
  `(Pago parcial)` (venta con medio de pago y comensales → caja), `- ITEM DESCUENTO`, `CAJA (RETIRO)`,
  `CAJA (DEPOSITO)`. Se ignoran `CAJA (CIERRE/APERTURA/AJUSTE)`.
- Agrupa por **noche de caja** (fecha de cierre, corte 08:00) y escribe `entrada/api_ventas_YYYY-MM.xlsx`
  (uno por mes, **se sobreescriben**) + `datos/cajas_api.json`.
- Rango por defecto: del 1 del mes anterior a mañana. `--mock` autotest sin API: escribe en un
  directorio temporal (`write_outputs(entrada=,datos=)`), **nunca** en las carpetas reales.
- ⚠️ **Estos archivos son los únicos sin backup automático** (los escribe el conector, no
  `app_antimo._save()`). Si se pierden, se recuperan corriendo el conector con el rango deseado:
  `python3 conector_bistrosoft.py 2026-06-01 2026-07-16`. Son datos de la API, no ediciones del dueño.
- ✅ **`datos/cajas_api.json` se FUSIONA por noche (`fecha_key`), no se sobreescribe entero**
  (`write_outputs` en el conector). Antes, un pull de rango angosto (el default, "1ro del mes
  pasado a mañana") corrido *después* de un backfill largo hacía desaparecer las cajas de los
  meses viejos — pasó una vez en desarrollo (backfill 30/4→hoy dio 48 noches, un pull posterior
  con rango default lo bajó a 32, perdiendo mayo). Ahora las noches que trae el pull actual se
  actualizan (por si había sync parcial), y las que quedan fuera de su rango se conservan tal
  cual estaban. Verificado: reproducido el escenario exacto (backfill 30/4→hoy, después pull
  default) y las 48 noches sobrevivieron.

---

## 9. Endpoints de la app (`app_antimo.py`)

`GET /` (dashboard), `GET /api/data`, `GET /api/ping`, `GET /api/config`.
`POST`: `/api/receta`, `/api/precio`, `/api/pour`, `/api/combo`, `/api/producto`, `/api/sospechoso`,
`/api/dia_cerrado`, `/api/stock`, `/api/opex_save`, `/api/opex_vigencia`, `/api/config`,
`/api/pull` (trae de Bistrosoft), `/api/excel` (genera `datos_general_actualizado.xlsx`). Cada POST escribe el
override (con backup previo) y re-corre el motor.
⚠️ `/api/opex` (escribe `opex_override.json`) quedó **sin uso** desde que se agregaron las vigencias
de OPEX — el frontend ya solo llama `/api/opex_save`/`/api/opex_vigencia`. No se borró todavía.

---

## 10. Solapas del tablero

Resumen (KPIs con delta vs período anterior, alertas automáticas, punto de equilibrio, cascada
P&L, tendencia por día), Rentabilidad (tabla + heatmap de margen + matriz BCG scatter, click =
desglose de lectura), **Recetas** (editor: crear/editar recetas, combos; filtros grupo/categoría/
tipo/buscar), Compras (consumo histórico vs reposición, exportable), Caja (por noche, con
detalle de retiros/descuentos), Costos (precios de insumos editables), OPEX (CRUD con
cantidad×unitario, filtros). Selector de fechas Desde/Hasta (calendario), comparar dos rangos,
persistencia en localStorage, botón imprimir/PDF.

### Filtros globales (barra superior) — alcance

El filtro **Categoría/Grupo** y el **buscador** afectan **todo el tablero**, incluido Resumen
(KPIs, P&L, punto de equilibrio, gráfico por día, findes/semana). Hasta que se corrigió, `totals()`
los ignoraba explícitamente y solo las alertas los respetaban — o sea que filtrar cambiaba una sola
caja y parecía roto.

⚠️ **OPEX con filtro activo:** el OPEX es del bar entero, no de una categoría. Si se filtra
"PIZZAS" y se resta el OPEX completo, el resultado da siempre negativo y no dice nada. Por eso
`totals()` lo **prorratea** por el peso que la selección tiene sobre las ventas totales (`share`),
y devuelve `opexProrrateado:true` para que la UI lo aclare (lo hacen el pie del KPI, una nota bajo
el P&L y el punto de equilibrio). **Es una asignación, no un costo medido** — si alguien toca esto,
mantener el cartel: sin él, el número parece un dato duro y no lo es. Sin filtro, `share`=1 y todo
queda idéntico a antes.

**Filtros de Rentabilidad** (`st.mgF` por tramo de margen, `st.claseF` por cuadrante BCG): la
leyenda "pierde/bajo/alto" y las cajas de cuadrante son clickeables y filtran tabla + matriz +
categorías a la vez. Umbral `MG_BAJO`=40% (el mismo que ya usaban las alertas de VACA, antes
implícito). Ojo con `curItemsBase()` vs `curItems()`: los cuadrantes y la escala del scatter usan
**base** (sin filtro de clase) a propósito — si usaran el filtrado, al seleccionar "Perros" los
otros cuadrantes quedarían en 0 (imposible cambiar de selección) y los puntos saltarían de lugar.

**Modo comparación:** el P&L se dibuja como tabla A vs B con diferencia por línea; la tarjeta de
indicadores muestra solo lo que el P&L no (margen %, ticket, unidades, comensales) para no repetir
números. Completitud, Stock y Findes/Semana **se ocultan** (muestran "estado de hoy" o un solo
período, no comparan); el gráfico por día y el punto de equilibrio se quedan pero rotulados
"solo período A".

**Compras — dos modos que NO son lo mismo:** `real` = consumo histórico del período (NO es una
lista de compras: con 66 días seleccionados, "477 Stella" es lo consumido en 66 días); `repo` =
cuánto comprar para cubrir un ciclo de apertura, **restando el stock cargado** (`stockCalc`) de los
insumos vigilados, con columnas Necesito / Tengo / Comprar. El CSV exportado refleja el modo activo
y en `real` no incluye columna "Comprar", para que nadie lo lea como una orden de compra.

---

## 11. Estado actual y pendientes

**N/D (faltan datos del dueño, confirmado que no hay info — dejar así):** Combo cumpleaños,
Combo Cumpleaños Premium, Jack Daniels, Rabas.

**Resuelto:** RED LABEL / BLACK LABEL costeaban como *Whisky Ballantines* vía alias — la propia
nota del Excel ya decía "Costeado con Ballantines; falta precio real". El dueño dio los precios
reales de botella (Red Label $36.615, Black Label $64.000, ambas 750ml). Se agregaron como
insumos nuevos en `insumos_extra.json` y se redirigió el `costeo` de ambos productos vía
`maestro_extra.json` (mismo cat/canon/tipo/factor/rend que el Excel, solo cambia el insumo).
Margen real: Red Label 63.4%, Black Label 36.7% (antes ~93% falso, ya no aparecen como
sospechosos por umbral).

**Resuelto:** "Gin Brighton" y "GIN BRIGTON" eran el mismo trago con dos grafías (el dueño lo
confirmó). Se unificaron en `UNIFICAR` (clave `norm("GIN BRIGTON") → norm("Gin Brighton")`),
igual que ya se hacía con "speed"/"redbull"/limonadas. De paso se sacó una entrada duplicada de
`UNIFICAR` que quedaba pisada sin efecto (dos definiciones idénticas, solo la segunda contaba) y
la fila de "GIN BRIGTON" en `maestro_extra.json`, que quedó inalcanzable tras la unificación
(esa clave nunca vuelve a aparecer en `prods`, se resuelve todo bajo "Gin Brighton").

**Roadmap del backlog original — completo:**
- ✅ Backups automáticos de overrides (§6).
- ✅ Precios sospechosos: umbral sugiere, dueño confirma (`sospechosos.json`).
- ✅ Control de completitud de datos + noches cerradas (`dias_cerrados.json`).
- ✅ OPEX con vigencia por fecha (`opex_periodos`, §5).
- ✅ Rendimiento de pours editable (`pours_extra.json`).
- ✅ Agregar/quitar componentes de combos (con guardia server-side contra insumo inexistente:
  `costear_combo`/`explotar_producto` dan N/D en vez de crashear el pipeline entero).
- ✅ Orden por columna en Recetas, Compras, Costos, OPEX (Rentabilidad ya lo tenía).
- ✅ Manejo de anulaciones: el conector excluye por `ticketNumber` los `status:"VOID"` — **verificado
  que Bistrosoft ya manda pares que se cancelan solos** (no había overcounting real en los datos
  históricos, a diferencia de lo que se sospechaba originalmente; el filtro es defensivo para
  pulls a mitad de turno, no una corrección de un bug existente).
- ✅ Punto de equilibrio por día de semana (findes vs. semana, tarjeta en Resumen).
- ✅ Alertas de quiebre de stock: conteo periódico + proyección por consumo real, **no** inventario
  perpetuo (decisión de diseño explícita, ver §6).
- ✅ `git init` + carpeta reorganizada (`_archivo/`, ver sección 2).

**Pendiente:** nada de código. Solo decisiones/datos del dueño (ver "N/D" arriba) y una limpieza
menor ya sugerida como tarea aparte: el endpoint `/api/opex` sin uso (§9).

---

## 12. Qué necesito de vos (Claude Code)

Mantené y extendé este sistema **sin romper las reglas de oro** (sección 3). Cualquier cambio debe
seguir funcionando **local, con doble clic y Chrome en la MacBook**, sin dependencias nuevas ni
servicios en la nube. Cuando edites el tablero, tocá `dashboard_tpl.html` (no el HTML generado) y
validá el JavaScript. Cuando edites el motor, tocá `actualizar_antimo.py`. Después de cualquier
cambio, corré `python3 actualizar_antimo.py` para verificar que genera bien, y probá los endpoints
levantando `python3 app_antimo.py`. Nunca escribas `datos/datos_general.xlsx` por código.
