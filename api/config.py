"""GET/POST /api/config — estado de la conexión Bistrosoft.

En la nube, traer ventas de Bistrosoft (POST /api/pull) todavía no está portado: eso requiere
correr el conector server-side contra la API de Bistrosoft y escribir en las tablas ventas/cajas.
Mientras tanto los datos de ventas se actualizan corriendo el conector LOCAL + seed_supabase.py.
Por eso este endpoint no guarda credenciales en la nube (no habría con qué usarlas todavía)."""
import json
from http.server import BaseHTTPRequestHandler

MSG = ("Traer ventas desde la nube todavía no está disponible (Fase 3). Por ahora las ventas se "
       "actualizan corriendo el conector en la Mac y volviendo a subir con seed_supabase.py.")


class handler(BaseHTTPRequestHandler):
    def _send(self, code, payload):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        self._send(200, {"base": "https://ar-api.bistrosoft.com", "username": "", "shopCode": "",
                         "configured": False, "cloud": True, "nota": MSG})

    def do_POST(self):
        self._send(200, {"ok": False, "error": MSG})
