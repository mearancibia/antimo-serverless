# Impresión desde la caja de respaldo (`/caja`)

## Qué anda hoy

| Modo | Cómo | Estado |
|---|---|---|
| **No imprimir** | — | ✅ **Es el default** |
| **Impresora del bar** | Relay que consulta al servidor | ✅ Anda — **es el modo para usar** |
| **USB directo** (WebUSB) | La impresora colgada del celu por un cable OTG | ✅ Anda |
| **Diálogo del sistema** | Abre la ventana de impresión del celu | ✅ Anda, pero frena la pantalla |

El default es **no imprimir** a propósito. El modo "diálogo del sistema" usa `window.print()`,
que abre un modal y **bloquea la pantalla hasta que alguien lo cierra**: con eso puesto por
defecto, cada cobro frenaría la caja en pleno rush — exactamente lo contrario de para lo que
existe este módulo. Sirve para una reimpresión suelta, no para cobrar toda una noche.

**Guardar siempre va primero.** La venta se registra (o se encola) y recién después se imprime.
Si la impresora está apagada, el cobro ya quedó igual; se avisa y aparece el botón 🧾 para
reimprimir. Una impresión que falla nunca deshace un cobro.

---

## Por qué la impresora WiFi no se puede usar todavía

El brief planteaba: el celular le manda el ticket por la red local a un relay
(`print-bridge.js`), y el relay lo pasa a la impresora por el puerto 9100. **Eso no funciona
acá**, y no es un problema de código.

La app se sirve por **HTTPS** desde Vercel. Una página HTTPS **no puede** hacer pedidos a una
dirección `http://` — el navegador lo bloquea como *mixed content*, sin opción de permitirlo, y
en el celular no hay forma de saltearlo. El relay en la red del bar sería
`http://192.168.x.x:8765`, o sea justo lo que está prohibido.

> ¿Por qué en el POS de referencia sí anda? Porque **ese** POS se sirve desde
> `http://localhost:8080`, en la misma máquina que el relay. `localhost` es la única excepción
> que el navegador acepta. Acá el celular y el relay son dos equipos distintos, así que la
> excepción no aplica.

Ponerle HTTPS al relay tampoco alcanza: habría que instalar un certificado de confianza en cada
celular, algo que no se sostiene en un bar.

### La solución: dar vuelta la dirección ✅

En vez de que el celular le hable al relay, **el relay le pregunta al servidor**:

```
CELULAR ──HTTPS──► /api/caja_venta ──► Supabase: cola_impresion
                                              ▲
RELAY (PC del bar) ──HTTPS cada 3s────────────┘   GET /api/print_pend
   │                                              POST /api/print_ok
   └──socket 9100──► impresora POS80C
```

El relay abre la conexión **hacia afuera**, que es siempre HTTPS y nunca está bloqueada:

- no hace falta IP fija para la PC del relay (sí para la impresora)
- no hay que abrir ningún puerto en el router
- el celular y la impresora no necesitan verse entre sí

**Los bytes ESC/POS los arma el celular** y viajan en base64 dentro del cobro. Así hay **un solo
codificador** (el de `caja.html`, testeado) y el relay queda tonto: decodifica y escupe al socket.
Un segundo codificador del lado del relay se terminaría desincronizando, y los tickets saldrían
distintos según por dónde se imprimieron.

Como el ticket viaja **dentro** de la venta, un cobro hecho sin señal se guarda en la cola del
celular **con su ticket adentro**: cuando vuelve la red, se sincroniza y se imprime.

---

## Poner en marcha el relay

### 1. Generar el token

```bash
python3 -c "import secrets; print(secrets.token_urlsafe(32))"
```

Ese valor va en **dos lugares, idéntico**:
- En **Vercel** → Settings → Environment Variables → `PRINT_RELAY_TOKEN`
- En la **PC del bar**, al arrancar el relay (abajo)

> Si la variable no está en Vercel, los endpoints del relay quedan **cerrados** (falla cerrada).
> Dejarla vacía desactiva la impresión; nunca la abre a cualquiera.

### 2. Darle IP fija a la impresora

En el router, reserva DHCP para la impresora (o IP fija desde su menú). Si la IP cambia, el relay
deja de encontrarla.

### 3. Arrancar el relay en la PC del bar

Necesita **Node** instalado. No hay `npm install`: es Node puro.

```bash
ANTIMO_URL=https://antimo-develop.vercel.app \
PRINT_RELAY_TOKEN=el-token-generado \
IMPRESORA_IP=192.168.0.50 \
node scripts/print_relay.js
```

Variables opcionales: `IMPRESORA_PUERTO` (default 9100) e `INTERVALO_MS` (default 3000, mínimo 2000).

La ventana tiene que quedar abierta. Si el relay está apagado, **no se pierde nada**: los tickets
se acumulan en la cola y salen todos juntos cuando se prenda.

### 4. Probar

En el celular: ⚙️ → "Impresora del bar" → **Imprimir prueba**. No hace falta cobrar nada.

### Qué pasa si algo falla

| Situación | Qué hace |
|---|---|
| Impresora apagada | Reintenta cada ciclo. A los **5 intentos** abandona ese ticket, para que uno imposible no trabe los que esperan detrás. |
| Se corta internet en la PC | Avisa una vez y sigue intentando. Al volver, imprime lo acumulado. |
| Token mal puesto | **Sale con un mensaje claro.** No se queda girando: reintentar no lo va a arreglar. |
| Relay apagado toda la noche | Los tickets quedan encolados. Sólo se imprimen los de las **últimas 12 horas** — uno de una noche que ya cerró no le sirve a nadie. |

---

## Bytes ESC/POS

Portados tal cual del POS de referencia (`POS-COMANDERA`), que ya se probó contra la OCOM /
POS-80 real: mismas code pages (CP858 / CP437 / CP1252), mismo degradado a ASCII sin tildes
cuando un carácter no se puede representar, mismo ancho de 48 columnas (Font A, 12x24, 203 dpi).

Están testeados en `scripts/test_escpos.js` (25 aserciones, sin navegador ni impresora):
`node scripts/test_escpos.js`. **Se testean porque son bytes** — un ticket mal codificado no se
ve mal en pantalla, se ve mal en el papel, y para cuando alguien lo nota ya se imprimió toda la
noche. Ojo con un detalle que el test cuida: la `Ñ` mayúscula es `0xA5` y la `ñ` minúscula
`0xA4`; confundirlas imprime la letra equivocada, no un error.

Si la impresora saca símbolos raros en vez de tildes, se cambia el juego de caracteres desde
Ajustes (⚙️). El ticket nunca queda ilegible: lo que no se puede representar sale sin tilde.
