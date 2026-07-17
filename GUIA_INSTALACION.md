# ANTIMO · Guía de instalación (para tu Mac)

Bienvenido. ANTIMO es tu panel de gestión: ventas, rentabilidad, compras, caja y costos, en vivo desde Bistrosoft. Corre **100% en tu Mac**, no sube nada a internet salvo consultar tus ventas en Bistrosoft.

## Paso 1 — Poné la carpeta en tu Mac
Copiá la carpeta **ANTIMO** completa a tu Escritorio (o donde prefieras). Que quede junta, sin separar los archivos.

## Paso 2 — Instalá (una sola vez)
1. Abrí la carpeta ANTIMO.
2. **Clic derecho** sobre **`INSTALAR_ANTIMO.command`** → **Abrir** → en el aviso de seguridad, **Abrir** de nuevo.
   *(macOS bloquea la primera vez por seguridad; con clic derecho → Abrir se destraba.)*
3. Se abre una ventana negra. Seguí lo que dice:
   - Si te pide **instalar Python**, apretá **Instalar** en la ventana de Apple, esperá a que termine (varios minutos) y **volvé a abrir `INSTALAR_ANTIMO.command`**.
   - Cuando te pida, escribí tu **usuario, contraseña y código de tienda** de Bistrosoft. *(La contraseña no se ve mientras la escribís, es normal.)*
4. Cuando diga **"Instalación completa"**, ya está.

## Paso 3 — Usá ANTIMO
- **Doble clic en `run_ANTIMO_app.command`.** (La primera vez, igual que antes: clic derecho → Abrir → Abrir.)
- Se abre una **ventana negra** (dejala abierta mientras usás ANTIMO) y **solo el navegador** con el tablero.
- Arriba a la derecha vas a ver **"✏️ Modo edición"**: ahí podés editar recetas, costos y OPEX, y crear productos.
- Botón **🔄 Traer ventas**: trae lo último de Bistrosoft.
- Para **cerrar** ANTIMO: cerrá la ventana negra.

## Cambiar tus datos de Bistrosoft
Si cambiás la contraseña de Bistrosoft, en ANTIMO (con la app abierta) tocá **⚙️ Bistrosoft** arriba a la derecha, actualizá y guardá. No hace falta reinstalar.

## Si algo falla
- **"No se puede abrir porque es de un desarrollador no identificado"** → clic derecho → Abrir → Abrir.
- **No trae ventas** → revisá tu internet y tus datos en ⚙️ Bistrosoft.
- **Se ve raro / vacío** → cerrá la ventana negra y volvé a abrir `run_ANTIMO_app.command`.
- Cualquier otra cosa, sacá una foto de la ventana negra y mandámela.

## Importante
- Tu información vive en la carpeta `datos/`. **No borres esa carpeta.**
- El archivo `datos/bistro_config.json` tiene tu contraseña de Bistrosoft: no lo compartas.
