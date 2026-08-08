#!/usr/bin/env node
/* Relay de impresión de ANTIMO — corre en una PC del bar, en la misma red que la impresora.
 * Node puro (https, net), sin dependencias, sin npm install. macOS, Windows y Linux.
 *
 *   ANTIMO_URL=https://antimo-develop.vercel.app \
 *   PRINT_RELAY_TOKEN=xxxxx \
 *   IMPRESORA_IP=192.168.0.50 \
 *   node scripts/print_relay.js
 *
 * ── Por qué pregunta en vez de recibir ──────────────────────────────────────────────────────
 * La app se sirve por HTTPS y el navegador bloquea como mixed content cualquier pedido a
 * http://192.168.x.x, así que el celular NO le puede hablar a este proceso. Se da vuelta la
 * dirección: el celular deja el ticket en una cola del servidor, y este relay PREGUNTA por
 * HTTPS cada pocos segundos. La conexión sale hacia afuera, que nunca está bloqueada:
 *   · no hace falta IP fija para esta PC (sí para la impresora)
 *   · no hay que abrir ningún puerto en el router
 *   · el celular y la impresora no necesitan verse entre sí
 *
 * ── Por qué es tan corto ────────────────────────────────────────────────────────────────────
 * Los bytes ESC/POS los arma el celular (caja.html) y viajan en base64. Acá sólo se decodifican
 * y se escupen al socket 9100. Un segundo codificador de este lado se terminaría
 * desincronizando del primero, y los tickets saldrían distintos según por dónde se imprimieron.
 */
"use strict";

const https = require("https");
const http = require("http");
const net = require("net");
const { URL } = require("url");

const BASE = (process.env.ANTIMO_URL || "").replace(/\/+$/, "");
const TOKEN = process.env.PRINT_RELAY_TOKEN || "";
const IP = process.env.IMPRESORA_IP || "";
const PUERTO = Number(process.env.IMPRESORA_PUERTO || 9100);
const CADA_MS = Math.max(2000, Number(process.env.INTERVALO_MS || 3000));
const TCP_TIMEOUT = 8000;

for (const [k, v] of [["ANTIMO_URL", BASE], ["PRINT_RELAY_TOKEN", TOKEN], ["IMPRESORA_IP", IP]]) {
  if (!v) { console.error("Falta la variable " + k + ". Ver documentacion/impresion_caja.md"); process.exit(1); }
}

const log = (...a) => console.log(new Date().toTimeString().slice(0, 8), ...a);

/* ------------------------------------------------------------------ HTTP al servidor */
function pedir(ruta, metodo, cuerpo) {
  return new Promise((ok, fail) => {
    const u = new URL(BASE + ruta);
    const mod = u.protocol === "http:" ? http : https;
    const body = cuerpo ? Buffer.from(JSON.stringify(cuerpo)) : null;
    const req = mod.request({
      hostname: u.hostname, port: u.port || (u.protocol === "http:" ? 80 : 443),
      path: u.pathname + u.search, method: metodo,
      headers: Object.assign({ "Authorization": "Bearer " + TOKEN },
        body ? { "Content-Type": "application/json", "Content-Length": body.length } : {})
    }, res => {
      let d = "";
      res.on("data", c => d += c);
      res.on("end", () => {
        if (res.statusCode === 401) {
          // Se marca aparte de un error de red: son dos problemas distintos y la solución
          // también. Reintentar un token mal puesto no lo va a arreglar nunca.
          const e = new Error("el servidor rechazó el token. Revisá PRINT_RELAY_TOKEN "
            + "(tiene que ser el mismo que está configurado en Vercel).");
          e.auth = true;
          return fail(e);
        }
        try { ok(JSON.parse(d || "{}")); } catch (e) { fail(new Error("respuesta no-JSON: " + d.slice(0, 120))); }
      });
    });
    req.on("error", fail);
    req.setTimeout(15000, () => req.destroy(new Error("timeout hablando con el servidor")));
    if (body) req.write(body);
    req.end();
  });
}

/* ------------------------------------------------------------------ socket 9100 */
function imprimir(buffer) {
  return new Promise((ok, fail) => {
    const s = new net.Socket();
    let listo = false;
    const fin = err => { if (listo) return; listo = true; s.destroy(); err ? fail(err) : ok(); };
    s.setTimeout(TCP_TIMEOUT);
    s.on("timeout", () => fin(new Error("no responde " + IP + ":" + PUERTO)));
    s.on("error", fin);
    s.connect(PUERTO, IP, () => s.write(buffer, () => { s.end(); fin(null); }));
  });
}

/* ------------------------------------------------------------------ ciclo */
let sinRed = false;      // para no llenar la pantalla de errores iguales

async function ciclo() {
  let r;
  try {
    r = await pedir("/api/print_pend", "GET");
    if (sinRed) { log("✅ conexión con el servidor recuperada"); sinRed = false; }
  } catch (e) {
    if (e.auth) {
      // No tiene sentido seguir preguntando cada 3 segundos con un token que no sirve: sale y
      // avisa. Si quedara girando, el error se perdería entre cientos de líneas iguales.
      log("❌ " + e.message);
      process.exit(1);
    }
    if (!sinRed) { log("⚠️  sin conexión con el servidor:", e.message); sinRed = true; }
    return;
  }
  if (!r.ok) return log("⚠️  el servidor respondió:", r.error || "error");

  for (const job of (r.jobs || [])) {
    try {
      await imprimir(Buffer.from(job.escpos, "base64"));
      await pedir("/api/print_ok", "POST", { ticket: job.ticket });
      log("🖨️  impreso", job.ticket.slice(0, 8), "(noche " + job.iso + ")");
    } catch (e) {
      log("❌ no pude imprimir", job.ticket.slice(0, 8) + ":", e.message);
      // Se reporta el fallo para que el servidor cuente el intento. A los 5 lo abandona, así un
      // ticket imposible (impresora rota) no traba los nuevos que esperan detrás.
      try { await pedir("/api/print_ok", "POST", { ticket: job.ticket, error: e.message, intentos: job.intentos }); }
      catch (e2) { /* si tampoco se puede reportar, se reintenta en el próximo ciclo */ }
      break;    // si la impresora falla, no tiene sentido seguir con los demás ahora
    }
  }
}

log("Relay de impresión de ANTIMO");
log("servidor:  " + BASE);
log("impresora: " + IP + ":" + PUERTO);
log("Consultando cada " + (CADA_MS / 1000) + "s. Dejá esta ventana abierta. Ctrl+C para salir.");
ciclo();
setInterval(ciclo, CADA_MS);
