# Prompt para Claude Code — Mejorar ANTIMO

> Copiá este texto como primer mensaje en Claude Code (abriendo la carpeta `ANTIMO/`).

---

Estás trabajando en **ANTIMO**, un panel de gestión de bar 100% local. **Leé primero el archivo `CLAUDE.md`** de esta carpeta: tiene el contexto completo, la arquitectura, el modelo de datos, el sistema de overrides y las **reglas de oro** (respetalas siempre).

Recordatorio de lo esencial que NO se rompe:
- Todo **local**: corre con Python del sistema y se usa desde **Chrome en una MacBook** (doble clic → `run_ANTIMO_app.command` → servidor local + navegador). Sin nube, sin frameworks JS, sin dependencias nuevas más allá de `openpyxl/requests/pdfplumber`.
- **Regla #0:** nunca inventar costos ni márgenes. Falta de dato → **N/D**.
- **Nunca** escribir `datos/datos_general.xlsx` por código (rompe las fórmulas de `Costo_Base`). Los cambios van a **archivos override JSON** en `datos/` que el motor fusiona.
- Editá **`dashboard_tpl.html`** (no el HTML generado) y **`actualizar_antimo.py`** (el motor). Validá el JavaScript. El frontend es **JS vanilla en un solo archivo**.

## Cómo verificar cada cambio
1. `python3 actualizar_antimo.py` → debe generar sin errores y crear `dashboard_ANTIMO.html`.
2. `python3 app_antimo.py` → levanta el servidor; probá los endpoints (`/api/data`, ediciones, etc.).
3. Confirmá que el JavaScript no tenga errores (podés extraer el `<script>` y correr `node --check`).

## Tarea: primero un plan
Antes de tocar nada, leé el código, verificá que corre, y **proponeme un plan** con el orden de las mejoras. Después implementamos de a una, probando cada una.

## Backlog de mejoras (priorizado)

**Alta (precisión / lo que confunde):**
1. **Marcar visualmente los precios sospechosos** (ej. Bombay/Brighton/Beefeater+Tónica, Carpano+Sifón que dan 95-98% de margen falso por error de carga en el POS). Que se distingan en Rentabilidad, Recetas y en la matriz BCG, y ojalá poder excluirlos de los "top margen".
2. **OPEX con vigencia por fecha**: que cada valor de OPEX tenga "desde qué fecha rige", para que cada mes/período use el OPEX que correspondía (hoy es una foto única aplicada a todo). Mejora el resultado histórico.
3. **Vista de "control de completitud"**: detectar y mostrar días abiertos sin datos (la API a veces no trae algún día o hay lag), para que el dueño lo note.

**Media (edición más completa):**
4. **Editar el rendimiento de los pours** (ml del vaso) desde el editor de Recetas (hoy el costo de un pour solo se cambia por el precio del insumo).
5. **Agregar/quitar componentes de combos** en el editor (hoy solo se edita la cantidad de los existentes).
6. **Orden por columna** en las tablas (clic en el encabezado para ordenar asc/desc).
7. **Backup/versionado automático** de los archivos override cada vez que se guarda una edición (por las dudas).

**Baja (nice-to-have):**
8. **Punto de equilibrio por día de semana** (findes vs. semana).
9. **Manejo de anulaciones**: el total vendido queda ~0,4% arriba porque no se distinguen comandas anuladas.
10. **Alertas de quiebre de stock** (requiere cargar un inventario inicial — proponé cómo).

## Pendientes de datos (NO son bugs — necesitan info del dueño)
Combo cumpleaños, Combo Premium, Jack Daniels y Rabas están en N/D a la espera de datos. No los fuerces; si querés, mejorá el flujo para cargarlos (ya existe el botón "Nuevo producto").

Arrancá leyendo `CLAUDE.md` y confirmame el plan.
