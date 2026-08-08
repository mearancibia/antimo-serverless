/* Tests del codificador ESC/POS de caja.html. Corre en Node, sin navegador ni impresora:
 *   node scripts/test_escpos.js
 *
 * Se testea porque son BYTES: un ticket mal codificado no se ve mal en pantalla, se ve mal en
 * el papel, y para entonces ya se imprimió toda la noche. Los valores esperados salen de la
 * especificación ESC/POS y del POS de referencia, que ya se probó contra la impresora real.
 */
"use strict";
const fs = require("fs"), path = require("path"), vm = require("vm");

// --- levantar el <script> de caja.html en un sandbox con lo mínimo del DOM ---
const html = fs.readFileSync(path.join(__dirname, "..", "caja.html"), "utf8");
const js = html.match(/<script>\n([\s\S]*)<\/script>/)[1];
const noop = () => {};
const elem = () => new Proxy({}, { get: (t, k) => (k in t ? t[k] : noop), set: (t, k, v) => (t[k] = v, true) });
const sandbox = {
  document: { querySelector: elem, createElement: elem, getElementById: elem,
              addEventListener: noop, hidden: false },
  localStorage: { getItem: () => null, setItem: noop },
  navigator: { onLine: true }, location: { href: "" }, crypto: {},
  indexedDB: { open: () => ({}) }, console,
  addEventListener: noop, setInterval: noop, setTimeout: noop, clearTimeout: noop,
  fetch: () => Promise.reject(new Error("sin red en los tests")),
  URL: { createObjectURL: () => "", revokeObjectURL: noop }, Blob: function () {}, print: noop
};
sandbox.window = sandbox;
vm.createContext(sandbox);
// El init del final toca la red/DOM: se corta ahí, ya están todas las funciones definidas.
// Y se exportan a mano: las declaradas con `const` (a diferencia de `function`) NO quedan
// colgando del objeto global, así que desde afuera del sandbox no se ven.
const cortado = js.replace(/\nred\(\);[\s\S]*$/, "") +
  "\n;globalThis.__api = { encodeEscPos, docABytes, docATexto, docTicket, nuevoDoc, ESC_COLS };";
vm.runInContext(cortado, sandbox, { timeout: 5000 });

let fallas = 0;
const check = (cond, msg) => { console.log((cond ? "  ok    " : "  FALLA ") + msg); if (!cond) fallas++; };
const hex = a => [...a].map(b => b.toString(16).padStart(2, "0")).join(" ");

const { encodeEscPos, docABytes, docATexto, docTicket, nuevoDoc, ESC_COLS } = sandbox.__api;

console.log("\n=== 1. Cabecera: reset + code page ===");
let b = docABytes(nuevoDoc(), "CP858");
check(hex(b).startsWith("1b 40 1b 74 13"), "CP858 -> ESC @ + ESC t 19  (" + hex(b.slice(0, 5)) + ")");
check(hex(docABytes(nuevoDoc(), "CP437")).startsWith("1b 40 1b 74 00"), "CP437 -> ESC t 0");
check(hex(docABytes(nuevoDoc(), "CP1252")).startsWith("1b 40 1b 74 10"), "CP1252 -> ESC t 16");
check(hex(docABytes(nuevoDoc(), "INVENTADA")).startsWith("1b 40 1b 74 13"),
      "code page desconocida cae en CP858, no rompe");

console.log("\n=== 2. Acentos y ñ (lo que más se rompe en térmicas) ===");
check(hex(encodeEscPos("ñ", "CP858")) === "a4", "ñ en CP858 -> 0xA4");
check(hex(encodeEscPos("ñ", "CP1252")) === "f1", "ñ en CP1252 -> 0xF1");
check(hex(encodeEscPos("áéíóú", "CP858")) === "a0 82 a1 a2 a3", "áéíóú en CP858");
// Ojo: la Ñ mayúscula es 0xA5, distinta de la ñ minúscula (0xA4). Confundirlas imprime
// la letra equivocada, no un error.
check(hex(encodeEscPos("PEÑA", "CP858")) === "50 45 a5 41", "PEÑA usa la Ñ mayúscula (0xA5)");
check(hex(encodeEscPos("peña", "CP858")) === "70 65 a4 61", "peña usa la ñ minúscula (0xA4)");
check(hex(encodeEscPos("ASCII puro", "CP858")) === hex(Buffer.from("ASCII puro", "ascii")),
      "el ASCII pasa igual");

console.log("\n=== 3. Degradado: nunca sale basura ===");
// CP1252 no tiene 'â'; tiene que degradar a 'a', no a un byte cualquiera.
check(hex(encodeEscPos("â", "CP1252")) === "e2", "â existe en CP1252 -> 0xE2");
check(hex(encodeEscPos("ă", "CP858")) === "3f", "un carácter sin equivalente -> '?' (0x3F)");
check(hex(encodeEscPos("好", "CP858")) === "3f", "un ideograma -> '?' , no un byte al azar");
// SIN_ACENTO cubre lo que la code page no tiene
check(hex(encodeEscPos("¿", "CP858")) === "a8", "¿ en CP858");

console.log("\n=== 4. Comandos ===");
const d = nuevoDoc();
d.align(1).bold(true).size(1, 1).line("X").bold(false).feed(3).cut();
b = docABytes(d, "CP858");
const h = hex(b);
check(h.includes("1b 61 01"), "align centro -> ESC a 1");
check(h.includes("1b 45 01") && h.includes("1b 45 00"), "bold on/off -> ESC E 1 / ESC E 0");
check(h.includes("1d 21 11"), "size(1,1) -> GS ! 0x11 (doble ancho y alto)");
check(h.includes("1b 64 03"), "feed 3 -> ESC d 3");
check(h.endsWith("1d 56 42 00"), "corte al final -> GS V B 0");
check(h.includes("58 0a"), "el texto lleva su salto de línea");

console.log("\n=== 5. El ticket ===");
const venta = {
  ticket: "abcdef12-3456", iso: "2026-08-09", hora: "03:15",
  descuento: 4000, descuento_pct: 20,
  lineas: [{ nombre: "FERNET CON COCA", unidades: 2, monto: 20000 },
           { nombre: "AGUA CON GAS", unidades: 1, monto: 3000 }],
  pagos: [{ medio: "EFECTIVO", monto: 15000 }, { medio: "QR", monto: 4000 }]
};
const txt = docATexto(docTicket(venta, false));
check(/TOTAL\s+\$19\.000/.test(txt), "el TOTAL es bruto - descuento = $19.000");
check(txt.includes("Descuento 20%"), "muestra el % del descuento");
check(txt.includes("2 x FERNET CON COCA") && txt.includes("$20.000"), "la línea lleva unidades y bruto");
check(txt.includes("Noche 2026-08-09"), "la noche de caja");
check(txt.includes("Ticket abcdef12"), "el id de ticket recortado a 8");
check(!txt.includes("*** COPIA ***"), "el original no dice COPIA");
check(docATexto(docTicket(venta, true)).includes("*** COPIA ***"), "la reimpresión SÍ dice COPIA");
const anchos = txt.split("\n").filter(l => l.includes("=") || l.includes("---"))
  .map(l => l.length);
check(anchos.every(w => w === ESC_COLS), "las líneas separadoras miden 48 columnas");
const totLine = txt.split("\n").find(l => l.startsWith("TOTAL"));
check(totLine.length === ESC_COLS, "la línea del TOTAL ocupa exactamente 48 columnas");

console.log("\n=== 6. Un ticket sin descuento no imprime la línea ===");
const sinD = docATexto(docTicket(Object.assign({}, venta, { descuento: 0, descuento_pct: 0 }), false));
check(!sinD.includes("Descuento"), "sin descuento, no aparece el renglón");
check(/TOTAL\s+\$23\.000/.test(sinD), "y el total es el bruto entero");

console.log("\n" + "=".repeat(60));
if (fallas) { console.log("❌ " + fallas + " FALLA(S)"); process.exit(1); }
console.log("✅ TODO OK");
