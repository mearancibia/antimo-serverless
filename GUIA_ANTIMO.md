# ANTIMO · Guía de uso (Opción 1 — local, gratis)

## Qué hace
Con **un doble clic**, tu computadora se conecta a Bistrosoft, trae las ventas y los cierres, recalcula todo (costos, márgenes, matriz, compras) y abre el tablero actualizado. Todo gratis, corre en tu Mac.

---

## Preparación (una sola vez)

### 1. Tener las credenciales cargadas
Abrí `ANTIMO/datos/bistro_config.json` y confirmá que están tu usuario, contraseña y shopCode reales (ya lo hiciste).

### 2. Habilitar el lanzador
La primera vez, macOS puede bloquear el archivo por seguridad:
- Andá a la carpeta `ANTIMO`.
- **Clic derecho** sobre `actualizar_ANTIMO.command` → **Abrir** → en el aviso, **Abrir** de nuevo.
- (Solo la primera vez. Después es doble clic normal.)

### 3. Python
Si no tenés Python, la primera corrida abre sola la instalación de macOS. Apretá **Instalar**, esperá a que termine y volvé a ejecutar el lanzador. (Las librerías se instalan solas.)

---

## Uso diario
1. **Doble clic en `actualizar_ANTIMO.command`.**
2. Se abre una ventana negra (Terminal) que muestra el avance: trae ventas → calcula → abre el tablero.
3. Cuando termina, el `dashboard_ANTIMO.html` se abre en el navegador, actualizado.

Por defecto trae **desde el 1 del mes pasado hasta hoy**. Cada corrida refresca esos meses.

---

## Importante
- Tenés que estar **conectado a internet**.
- Los datos que trae la API arman archivos `api_ventas_AAAA-MM.xlsx` en `entrada/` (uno por mes, se sobreescriben solos).
- **Archivos viejos:** los Excel que subías a mano (`RankingVentasDiario-...`) van a convivir con los de la API y pueden duplicar períodos. Cuando confirmes que la API trae bien los datos, conviene sacarlos de `entrada/` (movelos a otra carpeta o borralos).

## Si algo falla
- **"ERROR al traer datos"** → revisá internet y las credenciales en `datos/bistro_config.json`.
- **Nombres de productos que caen en "Sin datos (N/D)"** → puede ser que la API los mande con un prefijo distinto al de tu Maestro. Avisame y lo calibro.
- Cualquier cosa rara, mandame captura de la ventana negra.
