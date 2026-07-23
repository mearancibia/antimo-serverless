"""ÚNICA función serverless de ANTIMO. Despacha todos los /api/* por ruta (GET y POST), como hacía
app_antimo.py en local. Es una sola función a propósito: Vercel Hobby limita a 12 funciones por
deploy. La lógica de cada endpoint de edición vive en handlers.py.

AUTENTICACIÓN: salvo /api/login (y /api/ping para detección de modo), TODO exige una sesión válida
(cookie firmada). Sin sesión → 401. Así el login protege los DATOS, no solo la pantalla.
AUDITORÍA: cada acción (editar/borrar/pull/config/login/logout) se registra en audit_log con el
usuario (sacado de la sesión verificada, infalsificable), la acción y el payload (password redactado).
"""
import json, os
from http.server import BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

from sl_common import (client, recompute, get_bistro_config, save_bistro_config, write_pull,
                       find_user, audit, recent_audit)
from handlers import ROUTES, NORECOMPUTE
import bistro
import auth

# endpoints que NO requieren sesión
PUBLIC_GET = {"ping"}
PUBLIC_POST = {"login"}

# Entorno: "dev" en el proyecto de desarrollo (env var ANTIMO_ENV=dev), "prod" por defecto.
# El frontend lo usa para mostrar el cartel de DESARROLLO y no confundir los dos tableros.
ENV = os.environ.get("ANTIMO_ENV", "prod")


def _origen_confiable(headers):
    ct = (headers.get("Content-Type") or "").split(";")[0].strip().lower()
    return ct == "application/json"


class handler(BaseHTTPRequestHandler):
    def _send(self, code, payload, extra_headers=None):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        for k, v in (extra_headers or []):
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def _name(self):
        u = urlparse(self.path)
        q = parse_qs(u.query).get("__name")
        if q:
            return q[0]
        p = u.path
        return p[len("/api/"):] if p.startswith("/api/") else p.strip("/")

    def _user(self):
        return auth.session_from_headers(self.headers)

    # -------------------------------------------------- GET
    def do_GET(self):
        name = self._name()
        if name == "ping":
            return self._send(200, {"app": True, "env": ENV})
        user = self._user()
        if name == "me":
            if not user:
                return self._send(401, {"ok": False, "error": "no autenticado", "env": ENV})
            return self._send(200, {"ok": True, "user": user, "env": ENV})
        if not user:
            return self._send(401, {"ok": False, "error": "no autenticado"})
        # --- a partir de acá, autenticado ---
        if name == "data":
            try:
                sb = client()
                r = sb.table("antimo_data").select("data").eq("id", 1).execute()
                return self._send(200, r.data[0]["data"] if r.data else {})
            except Exception as e:
                return self._send(500, {"ok": False, "error": str(e)})
        if name == "config":
            try:
                c = get_bistro_config(client())
                return self._send(200, {"base": c.get("base", "https://ar-api.bistrosoft.com"),
                                        "username": c.get("username", ""), "shopCode": c.get("shopCode", ""),
                                        "configured": bool(c.get("username") and c.get("password")),
                                        "cloud": True})
            except Exception as e:
                return self._send(500, {"ok": False, "error": str(e)})
        if name == "audit":
            try:
                return self._send(200, {"ok": True, "rows": recent_audit(client())})
            except Exception as e:
                return self._send(500, {"ok": False, "error": str(e)})
        return self._send(404, {"ok": False, "error": "not found"})

    # -------------------------------------------------- POST
    def do_POST(self):
        if not _origen_confiable(self.headers):
            return self._send(403, {"ok": False, "error": "origen no permitido"})
        name = self._name()
        try:
            ln = int(self.headers.get("Content-Length") or 0)
            data = json.loads(self.rfile.read(ln) or b"{}")
        except Exception:
            return self._send(400, {"ok": False, "error": "cuerpo inválido"})

        # ---- login (público) ----
        if name == "login":
            return self._login(data)

        # ---- todo lo demás exige sesión ----
        user = self._user()
        if not user:
            return self._send(401, {"ok": False, "error": "no autenticado"})

        if name == "logout":
            try:
                audit(client(), user, "logout", {})
            except Exception:
                pass
            return self._send(200, {"ok": True}, extra_headers=[("Set-Cookie", auth.cookie_clear())])

        try:
            sb = client()
        except Exception as e:
            return self._send(500, {"ok": False, "error": str(e)})

        # ---- Bistrosoft: guardar credenciales ----
        if name == "config":
            try:
                c = get_bistro_config(sb)
                c["base"] = data.get("base") or c.get("base") or "https://ar-api.bistrosoft.com"
                c["username"] = (data.get("username") or "").strip() or c.get("username", "")
                if data.get("password"):
                    c["password"] = data["password"]
                c["shopCode"] = str(data.get("shopCode") or "").strip() or c.get("shopCode", "")
                save_bistro_config(sb, c)
                audit(sb, user, "config", data)   # audit() redacta el password
                return self._send(200, {"ok": True})
            except Exception as e:
                print("ERROR en config ->", repr(e))
                return self._send(500, {"ok": False, "error": str(e)})

        # ---- Bistrosoft: traer ventas ----
        if name == "pull":
            try:
                cfg = get_bistro_config(sb)
                faltan = [k for k in ("base", "username", "password", "shopCode") if not cfg.get(k)]
                if faltan:
                    return self._send(200, {"ok": False,
                        "error": "Falta configurar " + ", ".join(faltan) + " (botón ⚙️ Bistrosoft)."})
                start = str(data.get("start") or "").strip()
                end = str(data.get("end") or "").strip()
                if not start or not end:
                    start, end = bistro.default_range()
                tok = bistro.get_token(cfg["base"], cfg["username"], cfg["password"])
                items = bistro.fetch_all(cfg["base"], tok, cfg["shopCode"], start, end)
                rank, cajas = bistro.parse_items(items)
                nv, nc = write_pull(sb, rank, cajas)
                DATA = recompute(sb)
                audit(sb, user, "pull", {"start": start, "end": end, "ventas": nv, "cajas": nc})
                return self._send(200, {"ok": True, "data": DATA,
                    "log": f"{len(items)} transacciones · {nv} filas de ventas · {nc} noches de caja"})
            except Exception as e:
                print("ERROR en pull ->", repr(e))
                return self._send(200, {"ok": False, "error": str(e)})

        # ---- excel: no aplica en la nube ----
        if name in NORECOMPUTE:
            return self._send(200, {"ok": False, "error": NORECOMPUTE[name]})

        # ---- endpoints de edición (escriben override + recalculan) ----
        apply = ROUTES.get(name)
        if apply is None:
            return self._send(404, {"ok": False, "error": "endpoint desconocido: " + name})
        try:
            err = apply(data, sb)
            if err:
                return self._send(200, {"ok": False, "error": err})
            audit(sb, user, name, data)
            DATA = recompute(sb)
            return self._send(200, {"ok": True, "data": DATA})
        except Exception as e:
            print("ERROR en", name, "->", repr(e))
            return self._send(500, {"ok": False, "error": str(e)})

    # -------------------------------------------------- login
    def _login(self, data):
        username = str(data.get("username") or "").strip()
        password = str(data.get("password") or "")
        if not username or not password:
            return self._send(200, {"ok": False, "error": "Completá usuario y contraseña"})
        try:
            sb = client()
            u = find_user(sb, username)
            ok = bool(u) and auth.verify_password(password, u["password_hash"])
            audit(sb, username, "login" if ok else "login_fallido", {})
            if not ok:
                return self._send(200, {"ok": False, "error": "Usuario o contraseña incorrectos"})
            token = auth.make_session(username)
            return self._send(200, {"ok": True, "user": username},
                              extra_headers=[("Set-Cookie", auth.cookie_header(token))])
        except Exception as e:
            print("ERROR en login ->", repr(e))
            return self._send(500, {"ok": False, "error": str(e)})
