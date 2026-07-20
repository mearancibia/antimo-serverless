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
   - Si te pide **usuario, contraseña y código de tienda** de Bistrosoft, escribilos. *(La contraseña no se ve mientras la escribís, es normal.)* Si tu cuenta ya viene configurada, no te va a preguntar nada.
4. Cuando diga **"Instalación completa"**, ya está. La última línea te muestra cuántas noches de ventas quedaron cargadas.

### Si el doble clic no hace nada (o dice "permiso denegado")
Pasa cuando la carpeta viajó por mail, pendrive o ZIP: macOS le saca el permiso de arranque a los archivos. **Se arregla en 20 segundos y una sola vez:**

1. Abrí **Terminal** (apretá `⌘ + barra espaciadora`, escribí `Terminal`, Enter).
2. Escribí `bash` y **una espacio** — sin apretar Enter todavía.
3. **Arrastrá** el archivo `INSTALAR_ANTIMO.command` desde el Finder hasta la ventana de Terminal. Se va a escribir solo.
4. Ahora sí, apretá **Enter**.

El instalador arregla los permisos de toda la carpeta, así que de acá en adelante el doble clic funciona normal.

## Paso 3 — Usá ANTIMO
- **Doble clic en `run_ANTIMO_app.command`.** (La primera vez, igual que antes: clic derecho → Abrir → Abrir.)
- Se abre una **ventana negra** (dejala abierta mientras usás ANTIMO) y **solo el navegador** con el tablero.
- Arriba a la derecha vas a ver **"✏️ Modo edición"**: ahí podés editar recetas, costos y OPEX, y crear productos.
- Botón **🔄 Traer ventas**: trae lo último de Bistrosoft.
- Para **cerrar** ANTIMO: cerrá la ventana negra.

## Cambiar tus datos de Bistrosoft
Si cambiás la contraseña de Bistrosoft, en ANTIMO (con la app abierta) tocá **⚙️ Bistrosoft** arriba a la derecha, actualizá y guardá. No hace falta reinstalar.

## Si algo falla
- **"No se puede abrir porque es de un desarrollador no identificado"** → clic derecho → Abrir → Abrir. Si no aparece la opción "Abrir", usá el truco del Terminal del Paso 2.
- **El doble clic no hace nada / "permiso denegado"** → truco del Terminal del Paso 2.
- **No trae ventas** → revisá tu internet y tus datos en ⚙️ Bistrosoft.
- **Se ve raro / vacío** → cerrá la ventana negra y volvé a abrir `run_ANTIMO_app.command`.
- **"Address already in use" o no abre el navegador** → ANTIMO busca solo un puerto libre entre el 8733 y el 8740. Si ninguno lo está, cerrá otras ventanas de ANTIMO que hayan quedado abiertas.
- Cualquier otra cosa, sacá una foto de la ventana negra y mandámela.

## Importante
- Tu información vive en la carpeta `datos/`. **No borres esa carpeta.**
- El archivo `datos/bistro_config.json` tiene tu contraseña de Bistrosoft: no lo compartas.
