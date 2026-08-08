/* Service worker de la caja de respaldo (/caja).
 *
 * Objetivo: que la pantalla ABRA sin internet. En un rush, si se corta la red, el cajero no
 * puede quedarse mirando el dinosaurio de Chrome — y menos si ya tenía la app abierta y el
 * celular se bloqueó.
 *
 * ⚠️ Alcance acotado a propósito: este SW SOLO maneja /caja y sus archivos. El dashboard
 * (index.html) queda afuera. Cachear el tablero entero sería un problema distinto: muestra
 * plata y una versión vieja servida desde caché haría tomar decisiones con números de ayer.
 * Acá el riesgo no existe: el catálogo se revalida contra la red siempre que haya.
 */
"use strict";

// Subir la versión invalida la caché vieja. Cambiarla en cada deploy que toque caja.html.
const VERSION = "caja-v1";
// Sólo la ruta que la app usa de verdad. No se lista además /caja.html: es el mismo archivo por
// otro nombre y duplicarlo sólo agrega una cosa más que puede fallar.
const SHELL = ["/caja", "/manifest.webmanifest", "/caja-icon.svg"];

self.addEventListener("install", e => {
  // ⚠️ Se cachea de a uno y tolerando fallas, NO con addAll(): addAll es atómico, así que un
  // solo 404 aborta la instalación entera y la app se queda SIN modo offline en silencio. Es
  // preferible arrancar con lo que se pudo guardar (lo que falte se completa en el primer
  // fetch) que quedarse sin nada por un archivo secundario.
  // skipWaiting: al haber versión nueva entra sin esperar a que cierren la pestaña — la app vive
  // abierta toda la noche y si no, nunca se actualizaría.
  e.waitUntil(caches.open(VERSION)
    .then(c => Promise.allSettled(SHELL.map(u => c.add(u))))
    .then(rs => {
      // allSettled se traga los errores: sin este log, un shell que no se cachea deja la app
      // sin modo offline y no hay forma de enterarse. Se ve en DevTools > Application > SW.
      rs.forEach((r, i) => {
        if (r.status === "rejected") console.error("[sw] no pude cachear", SHELL[i], r.reason);
      });
      const ok = rs.filter(r => r.status === "fulfilled").length;
      console.log("[sw] cacheados " + ok + "/" + SHELL.length);
    })
    .then(() => self.skipWaiting()));
});

self.addEventListener("activate", e => {
  e.waitUntil(caches.keys()
    .then(ks => Promise.all(ks.filter(k => k !== VERSION).map(k => caches.delete(k))))
    .then(() => self.clients.claim()));
});

self.addEventListener("fetch", e => {
  const req = e.request;
  const url = new URL(req.url);

  // Nada que no sea GET del mismo origen pasa por acá. En particular los POST de /api/caja_venta:
  // un cobro NO se sirve de caché ni se reintenta desde el SW — de eso se ocupa la cola en
  // IndexedDB, que sabe de idempotencia por ticket. Duplicar esa lógica acá contaría doble.
  if (req.method !== "GET" || url.origin !== location.origin) return;

  // El catálogo: red primero, caché como red de emergencia. Así los precios están al día cuando
  // hay señal, y cuando no hay se puede cobrar igual con los últimos que se vieron.
  if (url.pathname === "/api/data") {
    e.respondWith(
      fetch(req).then(r => {
        if (r.ok) { const copia = r.clone(); caches.open(VERSION).then(c => c.put(req, copia)); }
        return r;
      }).catch(() => caches.match(req).then(r => r || Response.error()))
    );
    return;
  }

  // El resto de /api (me, login) NUNCA se cachea: son sesión y permisos. Servir un /api/me viejo
  // haría creer que hay sesión cuando ya venció.
  if (url.pathname.startsWith("/api/")) return;

  // Archivos de la app: caché primero (arranque instantáneo), y se refresca por atrás.
  e.respondWith(caches.match(req).then(hit => {
    const red = fetch(req).then(r => {
      if (r.ok) { const copia = r.clone(); caches.open(VERSION).then(c => c.put(req, copia)); }
      return r;
    }).catch(() => hit || Response.error());
    return hit || red;
  }));
});
