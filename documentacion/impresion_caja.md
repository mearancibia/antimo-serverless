# Impresión desde la caja de respaldo (`/caja`)

## Qué anda hoy

| Modo | Cómo | Estado |
|---|---|---|
| **No imprimir** | — | ✅ **Es el default** |
| **USB directo** (WebUSB) | La impresora colgada del celu por un cable OTG | ✅ Anda |
| **Diálogo del sistema** | Abre la ventana de impresión del celu | ✅ Anda, pero frena la pantalla |
| **Impresora WiFi del bar** | Relay en la red local | ❌ **Bloqueado por el navegador**, ver abajo |

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

### La salida: dar vuelta la dirección

En vez de que el celular le hable al relay, **que el relay pregunte al servidor**:

```
CELULAR ──HTTPS──► /api/caja_venta ──► Supabase: cola de impresión
                                              ▲
RELAY (PC del bar) ──HTTPS cada 2s────────────┘   pide trabajos pendientes
   │
   └──socket 9100──► impresora POS80C
```

El relay abre la conexión **hacia afuera**, que es siempre HTTPS y nunca está bloqueada. No
necesita IP fija, ni abrir puertos, ni que el celular y la impresora se vean entre sí.

**Lo que hay que construir:** una tabla `cola_impresion` en Supabase, dos endpoints (uno que
encola al cobrar y otro que el relay consulta y marca como impreso), y el relay en Node puro
—reusando el `imprimirPorSocket()` del `print-bridge.js` de referencia, que ya está probado
contra la impresora real—. Es medio día de trabajo y queda pendiente de decisión.

**Mientras tanto**, si hace falta ticket en papel: **USB al celu** (anda hoy, sin nada más), o
bajar el `.txt` desde Ajustes.

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
