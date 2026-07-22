"""POST /api/precio — override de precio de insumo {insumo, precio}.

Fase 1: persiste en Supabase (tabla precios_override) pero NO vuelve a correr el motor de
costeo (eso vive en actualizar_antimo.py, que depende de openpyxl + el Excel base — portarlo a
una función serverless queda para la fase 2, ver MIGRACION.md). Por eso la respuesta marca
"pendiente":true en vez de fingir un recálculo que no pasó — Regla #0 del proyecto: nunca
mostrar un número como recalculado si no lo está.
"""
import json
import os
from http.server import BaseHTTPRequestHandler

from supabase import create_client


def _client():
    url = os.environ["SUPABASE_URL"]
    key = os.environ["SUPABASE_SERVICE_KEY"]
    return create_client(url, key)


def _origen_confiable(headers):
    ct = (headers.get("Content-Type") or "").split(";")[0].strip().lower()
    return ct == "application/json"


class handler(BaseHTTPRequestHandler):
    def _send(self, code, payload):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        if not _origen_confiable(self.headers):
            return self._send(403, {"ok": False, "error": "origen no permitido"})
        try:
            length = int(self.headers.get("Content-Length") or 0)
            data = json.loads(self.rfile.read(length) or b"{}")
        except Exception:
            return self._send(400, {"ok": False, "error": "cuerpo inválido"})

        insumo = str(data.get("insumo", "")).strip()
        try:
            precio = float(data.get("precio"))
        except (TypeError, ValueError):
            return self._send(200, {"ok": False, "error": "Precio inválido"})
        if not insumo or precio < 0:
            return self._send(200, {"ok": False, "error": "Datos inválidos"})

        try:
            sb = _client()
            sb.table("precios_override").upsert({"insumo": insumo, "precio": precio}).execute()
            res = sb.table("antimo_data").select("data").eq("id", 1).execute()
            current = res.data[0]["data"] if res.data else {}
        except Exception as e:
            return self._send(500, {"ok": False, "error": str(e)})

        return self._send(200, {"ok": True, "data": current, "pendiente": True})
