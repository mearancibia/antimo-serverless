# Migración a Vercel + Supabase — Fase 1

Este documento vive junto al `CLAUDE.md` original (que describe la versión 100% local del
proyecto). Esta carpeta (`BETA Vercel/INSTALABLE_ANTIMO`) es un fork experimental hacia una
arquitectura serverless: **no reemplaza** la app local todavía, es un primer paso.

## Qué se hizo en esta fase

- `index.html`: copia de `dashboard_tpl.html` con un solo cambio (`let DATA=@@DATA@@;` →
  `let DATA={};`). El resto del JavaScript no se tocó — sigue siendo el mismo frontend vanilla,
  detecta "modo app" pegándole a `/api/ping` y trae los datos de `/api/data`, igual que en local.
- `/api/ping.py`, `/api/data.py`: sirven el DATA calculado, ahora desde una tabla de Supabase
  (`antimo_data`) en vez del archivo `datos_dashboard.json` local.
- `/api/precio.py`, `/api/receta.py`: los dos overrides editables de esta primera etapa
  (precio de insumo, receta). Escriben en Supabase (`precios_override`, `recetas_extra`).
- `supabase_schema.sql`: crea las 3 tablas de arriba, con RLS activado (solo la service_role
  key —usada server-side— puede escribir; la app nunca expone esa key al navegador).
- `scripts/seed_supabase.py`: sube el `datos_dashboard.json` + overrides que ya existen
  localmente a Supabase. Correlo una vez después de aplicar el schema.

## Limitación central de esta fase (léela antes de asumir que "ya funciona todo")

El motor de costeo (`actualizar_antimo.py`, ~800 líneas: Excel con `openpyxl`, PDF con
`pdfplumber`, toda la lógica de recetas/combos/BCG) **no corre dentro de las funciones
serverless**. Guardar un precio o una receta desde el tablero:

1. Persiste el override en Supabase (no se pierde nada).
2. **NO** recalcula costos ni márgenes al instante, a diferencia de la app local.

El tablero avisa esto explícitamente: el toast dice "Guardado (recálculo pendiente — fase 2)"
en vez de fingir un recálculo que no pasó (Regla #0 del proyecto: nunca inventar/ocultar que un
número no está actualizado). Para reflejar un cambio en los números:

```
python3 actualizar_antimo.py          # local, con los overrides ya bajados de Supabase o
                                       # editados a mano en datos/*.json
python3 scripts/seed_supabase.py      # sube el datos_dashboard.json nuevo
```

## Endpoints que YA NO están portados (pendientes de fase 2)

Todo lo demás que la app local expone via POST sigue sin existir acá — clickearlos en el
tablero va a dar un error de red, no un crash de la página:
`/api/opex_save`, `/api/opex_vigencia`, `/api/pour`, `/api/combo`, `/api/producto`,
`/api/sospechoso`, `/api/dia_cerrado`, `/api/stock`, `/api/stock_bulk`, `/api/costos_bulk`,
`/api/precio_lista`, `/api/excel`, `/api/pull`, `/api/config`.

La fase 2 natural es portar `actualizar_antimo.py` para que lea su maestro (hoy el Excel
`datos/datos_general.xlsx`) y sus overrides desde Supabase en vez de archivos locales, y
correrlo desde una función serverless (o un cron) en cada edición — recién ahí "guardar y
recalcular al instante" vuelve a ser real en la nube.

## Setup para desplegar

1. Crear las 3 tablas: pegar `supabase_schema.sql` en el SQL Editor de Supabase.
2. Completar `.env` (nunca commitear) a partir de `.env.example` con `SUPABASE_URL` y
   `SUPABASE_SERVICE_KEY` (la *service role*, no la *anon*).
3. Sembrar los datos: `pip install -r requirements.txt && python3 scripts/seed_supabase.py`
   (con las mismas dos variables exportadas en la shell).
4. En Vercel: importar el repo, cargar `SUPABASE_URL` y `SUPABASE_SERVICE_KEY` como Environment
   Variables del proyecto (Settings → Environment Variables) y deployar.
