"""POST /api/pull — traer ventas de Bistrosoft. NO portado a la nube todavía (Fase 3): requiere
correr el conector server-side contra la API de Bistrosoft y escribir en ventas/cajas. Por ahora
las ventas se actualizan corriendo el conector local + seed_supabase.py. Responde honestamente."""
import json
from http.server import BaseHTTPRequestHandler

MSG = ("El pull de Bistrosoft todavía no corre en la nube (Fase 3). Actualizá las ventas corriendo "
       "el conector en la Mac (python3 conector_bistrosoft.py) y después python3 scripts/seed_supabase.py.")


class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        body = json.dumps({"ok": False, "error": MSG}, ensure_ascii=False).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)
