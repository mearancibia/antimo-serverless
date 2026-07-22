"""POST /api/excel — generar el Excel completo con overrides aplicados. No aplica en la nube: no
hay filesystem persistente para dejar el archivo. Se genera corriendo la app local. Responde claro."""
import json
from http.server import BaseHTTPRequestHandler

MSG = ("Generar el Excel completo se hace desde la app local (run_ANTIMO_app), no desde la nube: "
       "toma la copia del Excel base y le aplica los overrides.")


class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        body = json.dumps({"ok": False, "error": MSG}, ensure_ascii=False).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)
