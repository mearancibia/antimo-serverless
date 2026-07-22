"""POST /api/receta — receta nueva o editada {receta, ingredientes:[[nombre,cantidad],...]}.

Misma limitación de fase 1 que api/precio.py: persiste en Supabase (tabla recetas_extra) pero
no recalcula el motor de costeo todavía — ver MIGRACION.md. Respuesta honesta con
"pendiente":true en vez de fingir un recálculo.
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

        nombre = str(data.get("receta", "")).strip()
        ingredientes = data.get("ingredientes") or []
        if not nombre or not ingredientes:
            return self._send(200, {"ok": False, "error": "La receta quedó vacía"})
        ingredientes = [[i[0], i[1]] for i in ingredientes]

        try:
            sb = _client()
            sb.table("recetas_extra").upsert(
                {"nombre": nombre, "ingredientes": ingredientes}
            ).execute()
            res = sb.table("antimo_data").select("data").eq("id", 1).execute()
            current = res.data[0]["data"] if res.data else {}
        except Exception as e:
            return self._send(500, {"ok": False, "error": str(e)})

        return self._send(200, {"ok": True, "data": current, "pendiente": True})
