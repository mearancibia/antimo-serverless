"""ÚNICA función serverless de ANTIMO. Despacha todos los /api/* por ruta (GET y POST), como hacía
app_antimo.py en local. Es una sola función a propósito: Vercel Hobby limita a 12 funciones por
deploy, y un archivo por endpoint daban 18. La lógica de cada endpoint vive en handlers.py.
"""
import os, json
from http.server import BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

from sl_common import client, recompute
from handlers import ROUTES, NORECOMPUTE


def _origen_confiable(headers):
    ct = (headers.get("Content-Type") or "").split(";")[0].strip().lower()
    return ct == "application/json"


class handler(BaseHTTPRequestHandler):
    def _send(self, code, payload, is_json=True):
        body = (json.dumps(payload, ensure_ascii=False) if is_json else payload).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _name(self):
        # el rewrite de vercel.json pasa el nombre del endpoint en ?__name=... (determinístico,
        # no depende de si self.path preserva la ruta original tras el rewrite). Fallback al path.
        u = urlparse(self.path)
        q = parse_qs(u.query).get("__name")
        if q:
            return q[0]
        p = u.path
        return p[len("/api/"):] if p.startswith("/api/") else p.strip("/")

    def do_GET(self):
        name = self._name()
        if name == "ping":
            return self._send(200, {"app": True})
        if name == "data":
            try:
                sb = client()
                r = sb.table("antimo_data").select("data").eq("id", 1).execute()
                data = r.data[0]["data"] if r.data else {}
                return self._send(200, data)
            except Exception as e:
                return self._send(500, {"ok": False, "error": str(e)})
        if name == "config":
            return self._send(200, {"base": "https://ar-api.bistrosoft.com", "username": "",
                                    "shopCode": "", "configured": False, "cloud": True,
                                    "nota": NORECOMPUTE["config"]})
        return self._send(404, {"ok": False, "error": "not found"})

    def do_POST(self):
        if not _origen_confiable(self.headers):
            return self._send(403, {"ok": False, "error": "origen no permitido"})
        name = self._name()
        try:
            ln = int(self.headers.get("Content-Length") or 0)
            data = json.loads(self.rfile.read(ln) or b"{}")
        except Exception:
            return self._send(400, {"ok": False, "error": "cuerpo inválido"})

        # POST que no recalculan (pull/excel/config): mensaje claro, sin tocar datos.
        if name in NORECOMPUTE:
            return self._send(200, {"ok": False, "error": NORECOMPUTE[name]})

        apply = ROUTES.get(name)
        if apply is None:
            return self._send(404, {"ok": False, "error": "endpoint desconocido: " + name})
        try:
            sb = client()
            err = apply(data, sb)
            if err:
                return self._send(200, {"ok": False, "error": err})
            DATA = recompute(sb)
            return self._send(200, {"ok": True, "data": DATA})
        except Exception as e:
            print("ERROR en", name, "->", repr(e))
            return self._send(500, {"ok": False, "error": str(e)})
