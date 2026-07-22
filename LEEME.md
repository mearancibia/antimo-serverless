# ANTIMO — qué es cada cosa

Panel de gestión del bar: ventas, rentabilidad, compras, caja y costos.
Corre **entero en esta Mac**. No sube nada a internet salvo cuando le pedís las ventas a Bistrosoft.

---

## Para usarlo (es lo único que necesitás tocar)

| Doble clic en… | Qué hace |
|---|---|
| **`run_ANTIMO_app.command`** | **Abre ANTIMO.** Es el de todos los días. Se abre una ventana negra (dejala abierta) y el tablero en el navegador. Para cerrar, cerrás la ventana negra. |
| `actualizar_ANTIMO.command` | Trae las ventas nuevas y actualiza el tablero, sin abrir la app. Modo rápido. |
| `INSTALAR_ANTIMO.command` | Solo la primera vez, en una Mac nueva. |

> La primera vez que abrís cualquiera de los tres, macOS los bloquea por seguridad:
> **clic derecho → Abrir → Abrir**. Después ya funciona con doble clic.

---

## Las carpetas

| Carpeta | Qué tiene |
|---|---|
| **`datos/`** | **Todo tu trabajo.** Precios, recetas, stock, OPEX, el Excel de costos y tus cierres de caja. **Es la carpeta que no hay que borrar.** Adentro, `_backups/` guarda copias automáticas de cada cambio. |
| `entrada/` | Las ventas que baja el sistema de Bistrosoft. Se llena solo. |
| `documentacion/` | Guía de instalación y los informes técnicos. |
| `_archivo/` | Cosas viejas que ya no se usan, guardadas por las dudas. |
| `SISTEMITA_LISTO/` | El paquete armado para instalar en otra Mac. |

---

## Los archivos sueltos

**No hace falta que los toques, pero por si te los cruzás:**

*El programa en sí:*
- `app_antimo.py` — el que abre el tablero
- `actualizar_antimo.py` — el que calcula los costos y márgenes
- `conector_bistrosoft.py` — el que trae las ventas
- `dashboard_tpl.html` — el diseño del tablero
- `logo.png` — tu logo

*Se generan solos, no los edites:*
- `dashboard_ANTIMO.html` — el tablero ya armado. Se puede abrir directo, sin la app, pero queda en **modo lectura** (se ve todo, no se edita nada). Sirve para mandárselo a alguien.
- `datos_dashboard.json` — los números calculados
- `datos_general_actualizado.xlsx` — se crea cuando apretás "Excel completo"

*Documentación:*
- `CLAUDE.md` — el detalle técnico del proyecto

---

## Si algo sale mal

- **El tablero abre en negro o no abre** → suele ser que quedó otra ventana negra abierta de antes. Cerrá todas y volvé a abrir.
- **Faltan las últimas noches** → apretá 🔄 Traer ventas. Bistrosoft a veces tarda unas horas en publicar la noche anterior.
- **Me equivoqué y guardé algo mal** → mirá en `datos/_backups/`, están las últimas 20 versiones de cada archivo.
- **Cualquier otra cosa** → sacale una foto a la ventana negra.

---

## Lo único importante que tenés que saber

Los números del tablero son tan buenos como **las recetas y los precios cargados**.

Si un trago lleva 70 ml y la receta dice 60, todas las cuentas van a cerrar perfecto y estar mal.
Cada tanto conviene revisar que las recetas reflejen lo que realmente se sirve, y que los precios
de los insumos estén al día.
