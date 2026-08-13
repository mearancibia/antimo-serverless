# -*- coding: utf-8 -*-
"""ANTIMO — genera el tablero local. Ejecutable con doble clic vía actualizar_ANTIMO.command.

    python3 actualizar_antimo.py

Este archivo NO tiene lógica de costeo: es el *driver* local del motor único.

    datos/ + entrada/  ──▶  sources.LocalSource.build()  ──▶  engine.compute()  ──▶  DATA
                                                                                      │
                                                                                      ▼
                                                                          datos_dashboard.json

El front (`index.html`, el mismo que sirve Vercel) lee ese JSON por `/api/data`; ya no se genera
ningún HTML con los datos adentro. Hasta el 13-08-2026 acá se escribía además
`dashboard_ANTIMO.html` (plantilla `dashboard_tpl.html` + DATA embebida), un SEGUNDO frontend que
solo veía la app local: los arreglos hechos en uno no aparecían en el otro. Los dos archivos
quedaron en `_archivo/viejo/`.

**Por qué es un driver y no el motor.** Hasta el 13-08-2026 este archivo era un monolito de 797
líneas que duplicaba `engine.py` entero. Los dos motores convivían: la app local corría este, y
el serverless (`api/`) corría `engine.py`. Cada bug había que arreglarlo dos veces, y el día que
alguien se olvidaba de uno, el arreglo quedaba a medias sin que nadie se enterara — pasó: tres
arreglos de matemática se aplicaron a `engine.py` y este siguió con el fallback de OPEX
hardcodeado en $10.460.000, unidades `"3.0"` descartadas en silencio, y tres multiplicaciones por
`cant_base` sin guarda de `None` que volteaban el pipeline entero.

Ahora hay **un solo motor**: `engine.py`. Este archivo solo arma las fuentes, lo llama y escribe
la salida. Es el espejo local exacto de `sl_common.recompute()` (el driver del serverless): si se
toca uno, mirar el otro.

Verificado antes de reemplazar el monolito: sobre los datos reales (64 noches, 133 productos,
121 insumos, 65 cajas) el DATA de `engine.compute(LocalSource())` es **idéntico** campo por campo
al que producía el monolito — la única diferencia es `generado`, que es la fecha del día.

⚠️ **Lo único que se perdió en la unificación: la lectura de PDFs de cierre de caja**
(`parse_caja`/`pdfplumber`). `LocalSource` no los lee. No afecta a los datos actuales — la API de
Bistrosoft ya trae esas noches, el PDF sobrevivía a la deduplicación 0 veces, y los archivos
están en `_archivo/datos_sin_uso/` desde hace rato. Si alguna vez hace falta volver a leerlos, el
monolito completo quedó en `_archivo/viejo/actualizar_antimo_monolito.py` y lo que hay que portar
es `parse_caja()` a `sources.LocalSource.build()`, no resucitar el archivo entero.
"""
import os, sys, json, datetime

from sources import LocalSource
from engine import compute

BASE = os.path.dirname(os.path.abspath(__file__))
DATOS = os.path.join(BASE, "datos")


def _guardar_json(path, data):
    """Escritura atómica: tmp + os.replace (invariante 3 del CLAUDE.md). Sin esto, un corte a
    mitad de escritura deja el archivo truncado y la próxima corrida lo lee corrupto.
    `encoding` explícito porque el del locale revienta con "Cachaça"/"CUMPLEAÑOS"."""
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)
    os.replace(tmp, path)


def main():
    src = LocalSource(BASE).build()
    DATA, seed = compute(src)

    # El motor devuelve `seed` solo si opex.json no existía: es la siembra inicial desde la hoja
    # OPEX del Excel, que el caller persiste. Mismo contrato que sl_common.recompute() en la nube.
    if seed is not None:
        _guardar_json(os.path.join(DATOS, "opex.json"), seed)

    _guardar_json(os.path.join(BASE, "datos_dashboard.json"), DATA)

    productos = DATA["productos"]
    print("OK. Dias:%d Productos:%d (N/D %d) Insumos:%d Cajas:%d OPEX:$%s" % (
        len(DATA["dias"]), len(productos), sum(1 for p in productos if p.get("nd")),
        len(DATA["insumos"]), len(DATA["cajas"]), format(DATA["opex"], ",.0f")))


if __name__ == "__main__":
    main()
