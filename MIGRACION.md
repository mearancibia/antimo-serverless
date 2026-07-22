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

## Lo que queda para una Fase 3 (traer ventas desde la nube)

`/api/pull` y `/api/config` **no** corren el conector de Bistrosoft en la nube todavía (requiere
correr el conector server-side contra la API externa con credenciales, y no se pudo testear contra
la API real). Responden con un mensaje claro. `/api/excel` tampoco aplica (no hay filesystem
persistente). Mientras tanto, **las ventas nuevas se actualizan corriendo el conector en la Mac +
`seed_supabase.py`** — todo lo demás (editar recetas, costos, OPEX, stock, combos, etc.) ya
recalcula al instante en la nube.

## Setup / re-deploy

1. **Schema**: pegar `supabase_schema.sql` en el SQL Editor de Supabase (es idempotente).
2. **Seed**: con `SUPABASE_URL` y `SUPABASE_SERVICE_KEY` (service_role) exportadas:
   `pip install -r requirements.txt && python3 scripts/seed_supabase.py`
   (sube datos maestros, ventas, cajas, overrides y el DATA calculado).
3. **Vercel**: las dos env vars cargadas en el proyecto (Settings → Environment Variables) y deploy.

⚠️ **Tras cambios en el esquema hay que re-correr el seed** para poblar las tablas nuevas, si no
los endpoints que las leen fallan.
