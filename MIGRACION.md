# Migración a Vercel + Supabase

Fork serverless de ANTIMO (la app local sigue existiendo sin cambios). Vive en
`BETA Vercel/INSTALABLE_ANTIMO/`.

## Arquitectura

```
Navegador (index.html, JS vanilla)
   │  fetch /api/*
   ▼
Funciones serverless Python (/api/*.py)  ──►  engine.compute(SupabaseSource)  ──►  Supabase
   ping/data (GET)                              (motor de costeo puro)              (datos + overrides)
   precio/receta/… (POST): escriben override → recalculan → devuelven DATA fresca
```

- **`engine.py`** — el motor de costeo, refactor de `actualizar_antimo.py` a una **función pura**
  `compute(src) -> (DATA, opex_seed)`. Los diccionarios grandes (ALIAS, EQUI, UNIFICAR, COMBOS,
  INSUMO_ALIAS, PIECE_G, etc.) son lógica de negocio y viven acá como código. Solo usa stdlib.
- **`sources.py`** — capa de datos con dos implementaciones que arman el mismo `src`:
  `LocalSource` (Excel + rankings + `datos/*.json`, para la app local y para verificar) y
  `SupabaseSource` (lee de las tablas de Supabase; **no** necesita openpyxl).
- **`sl_common.py`** — cliente Supabase + `recompute()` + `make_handler(apply)` (boilerplate de los
  endpoints: chequeo de origen, parseo, escribir override → recalcular → devolver DATA).
- **`/api/*.py`** — un archivo por endpoint, mínimos (definen `apply(data, sb)` y
  `handler = make_handler(apply)`).

## Verificación (Regla #0: el refactor no cambia ningún número)

Dos gates que corren sin Supabase real y dieron **idéntico** al `datos_dashboard.json` original:
1. `compute(LocalSource())` == `datos_dashboard.json` (las 13 secciones).
2. Round-trip completo: LocalSource → filas del seed → SupabaseSource → `compute` == local.
3. Endpoints end-to-end contra un cliente Supabase falso (cambiar precio recalcula costos, OPEX,
   sospechosos, pours). Todo OK.

## Endpoints portados (Fase 2 — recálculo REAL en la nube)

GET: `/api/ping`, `/api/data`.
POST (escriben override + recalculan): `/api/precio`, `/api/receta`, `/api/precio_lista`,
`/api/pour`, `/api/combo`, `/api/sospechoso`, `/api/dia_cerrado`, `/api/stock`, `/api/stock_bulk`,
`/api/costos_bulk`, `/api/opex_save`, `/api/opex_vigencia`, `/api/producto`.

## Fase 3 — traer ventas desde la nube (HECHA)

- **`bistro.py`** — lógica pura del conector (token JWT → TransactionDetailReport paginado →
  `parse_items`), extraída de `conector_bistrosoft.py`. Solo usa `requests` + stdlib.
- **`POST /api/config`** — guarda las credenciales de Bistrosoft en Supabase (`app_meta.bistro_config`).
  GET nunca devuelve el password. Las credenciales las ingresa el dueño desde el modal ⚙️ del tablero.
- **`POST /api/pull`** — lee las credenciales, trae las transacciones de Bistrosoft, y con
  `write_pull()` escribe en Supabase: `ventas` (reemplaza cada MES completo — por eso el rango
  arranca el 1 de un mes) y `cajas` (fusiona por noche con upsert). Después recalcula y devuelve DATA.
  Acepta `{start,end}` opcional; por defecto usa el rango del conector (1 del mes pasado a mañana).
- `requirements.txt` suma `requests`. `maxDuration:60` en vercel.json para pulls largos.

`/api/excel` sigue sin aplicar en la nube (no hay filesystem persistente para dejar el archivo).

⚠️ Backfills muy largos pueden superar el tope de tiempo de la función: para esos, correr el
conector local + `seed_supabase.py`. El pull incremental (rango por defecto) anda bien.

## Autenticación + auditoría

- **Usuarios individuales, un solo nivel de acceso** (sin roles). Tabla `users` en Supabase con el
  password HASHEADO (PBKDF2-SHA256 + sal, `auth.py`). Nunca en texto plano.
- **Login** (`/login`): `POST /api/login` verifica y devuelve una **cookie de sesión firmada**
  (HMAC, HttpOnly). Todos los `/api/*` exigen sesión válida → 401 si no (salvo `/api/ping` y
  `/api/login`). El tablero redirige a `/login` si no hay sesión. Botón "🚪 Salir" (`/api/logout`).
- **Auditoría** (`/actividad`): tabla `audit_log`. Cada acción (editar/borrar/pull/config/login/
  logout) registra usuario + timestamp + acción + payload (con el password **redactado**). El
  usuario sale de la sesión verificada, no de lo que manda el cliente (infalsificable).
- **Crear usuarios**: `python3 scripts/crear_usuario.py [usuario]` — pide la contraseña por
  teclado (getpass, no se ve ni queda en el historial) y la guarda hasheada. Uno por usuario.
- Secreto de firma: env var `SESSION_SECRET` (si no está, usa el service key como fallback).

## Dos entornos: desarrollo y producción

| | Producción | Desarrollo |
|---|---|---|
| Rama de git | `main` | `desarrollo` |
| Supabase | `guufxgjvvtyaiwyprkgl` | `ldubhqrxawwcsbehctso` |
| `ANTIMO_ENV` | (sin definir) | `dev` |
| Cartel en pantalla | — | ⚠️ ENTORNO DE DESARROLLO |

**El mismo código sirve para los dos**: la conexión sale de las env vars (`SUPABASE_URL`,
`SUPABASE_SERVICE_KEY`), así que cada proyecto de Vercel apunta a su propia base. No hay ramas de
código con credenciales ni condicionales por entorno.

**Flujo de trabajo:** se desarrolla y prueba en `desarrollo` (que deploya al Vercel de desarrollo contra la
base de desarrollo). Cuando el cambio está verificado, se mergea a `main` → producción.

```
git checkout desarrollo     # trabajar acá
...cambios...
git push origin desarrollo  # deploya a desarrollo, se prueba
git checkout main && git merge desarrollo && git push origin main   # recién ahí, a producción
```

⚠️ Cada entorno necesita su propio `SESSION_SECRET` y sus propios usuarios (`crear_usuario.py`
apuntando a esa base): las sesiones de uno NO valen en el otro, que es justamente lo que se busca.

## Setup / re-deploy

1. **Schema**: pegar `supabase_schema.sql` en el SQL Editor de Supabase (es idempotente).
2. **Seed**: con `SUPABASE_URL` y `SUPABASE_SERVICE_KEY` (service_role) exportadas:
   `pip install -r requirements.txt && python3 scripts/seed_supabase.py`
   (sube datos maestros, ventas, cajas, overrides y el DATA calculado).
3. **Vercel**: las dos env vars cargadas en el proyecto (Settings → Environment Variables) y deploy.

⚠️ **Tras cambios en el esquema hay que re-correr el seed** para poblar las tablas nuevas, si no
los endpoints que las leen fallan.
