"""GET /api/data — sirve el DATA calculado (equivalente a datos_dashboard.json) desde Supabase.

Fase 1 de la migración: este endpoint es SOLO LECTURA. El DATA se sube a Supabase con
scripts/seed_supabase.py a partir del datos_dashboard.json que ya genera el motor local
(actualizar_antimo.py). Recalcular el motor completo dentro de una función serverless
(openpyxl + pdfplumber + Excel base) queda pendiente para una fase 2 — ver MIGRACION.md.
"""
import json
import os
from http.server import BaseHTTPRequestHandler

from supabase import create_client


def _client():
    url = os.environ["SUPABASE_URL"]
    key = os.environ["SUPABASE_SERVICE_KEY"]
    return create_client(url, key)


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            sb = _client()
            res = sb.table("antimo_data").select("data").eq("id", 1).execute()
            data = res.data[0]["data"] if res.data else {}
            body = json.dumps(data, ensure_ascii=False).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)
        except Exception as e:
            payload = json.dumps({"ok": False, "error": str(e)}).encode("utf-8")
            self.send_response(500)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(payload)
