# -*- coding: utf-8 -*-
"""Común a las funciones serverless de /api. Cliente Supabase, recálculo con el motor, y un
`make_handler(apply)` que arma el BaseHTTPRequestHandler con todo el boilerplate (chequeo de
origen, parseo del body, y el flujo: escribir override -> recalcular -> devolver DATA fresca).

Cada endpoint define `apply(data, sb) -> error|None` (escribe su override) y hace
`handler = make_handler(apply)`. Vercel busca el atributo `handler` en cada archivo.
"""
import os, json, re, datetime
from http.server import BaseHTTPRequestHandler

from supabase import create_client
from engine import compute, OPEX_DESDE_0
from sources import SupabaseSource


def client():
    return create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_KEY"])


def recompute(sb):
    """Corre el motor sobre Supabase, guarda el DATA en antimo_data y lo devuelve. Si el motor
    sembró el OPEX (porque app_meta.opex_json estaba vacío), lo persiste para próximas corridas."""
    src = SupabaseSource(sb).build()
    DATA, seed = compute(src)
    if seed is not None:
        sb.table("app_meta").upsert({"key": "opex_json", "value": seed}).execute()
    sb.table("antimo_data").upsert({"id": 1, "data": DATA, "generado": DATA.get("generado")}).execute()
    return DATA


def _origen_confiable(headers):
    ct = (headers.get("Content-Type") or "").split(";")[0].strip().lower()
    return ct == "application/json"


def make_handler(apply):
    class H(BaseHTTPRequestHandler):
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
                ln = int(self.headers.get("Content-Length") or 0)
                data = json.loads(self.rfile.read(ln) or b"{}")
            except Exception:
                return self._send(400, {"ok": False, "error": "cuerpo inválido"})
            try:
                sb = client()
                err = apply(data, sb)
                if err:
                    return self._send(200, {"ok": False, "error": err})
                DATA = recompute(sb)
                return self._send(200, {"ok": True, "data": DATA})
            except Exception as e:
                print("ERROR endpoint ->", repr(e))
                return self._send(500, {"ok": False, "error": str(e)})
    return H


# ---------------------------------------------------------------- OPEX (app_meta.opex_json)
def opex_periodos(sb):
    """opex.json (guardado en app_meta) normalizado a [{desde,items}] ordenado. Acepta el formato
    viejo (lista plana) leyéndolo como una única vigencia desde siempre."""
    r = sb.table("app_meta").select("value").eq("key", "opex_json").execute().data
    raw = (r[0]["value"] if r else None) or []
    if not raw:
        return [{"desde": OPEX_DESDE_0, "items": []}]
    if isinstance(raw[0], dict) and "items" in raw[0]:
        return sorted([p for p in raw if isinstance(p, dict)],
                      key=lambda p: str(p.get("desde") or OPEX_DESDE_0))
    return [{"desde": OPEX_DESDE_0, "items": raw}]


def opex_vigente(ps):
    hoy = datetime.date.today().isoformat()
    cur = [p for p in ps if str(p.get("desde") or OPEX_DESDE_0) <= hoy]
    return str((cur[-1] if cur else ps[0]).get("desde") or OPEX_DESDE_0)


def save_opex(sb, ps):
    sb.table("app_meta").upsert({"key": "opex_json", "value": ps}).execute()


ISO_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
