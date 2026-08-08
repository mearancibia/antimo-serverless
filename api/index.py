"""ÚNICA función serverless de ANTIMO. Despacha todos los /api/* por ruta (GET y POST), como hacía
app_antimo.py en local. Es una sola función a propósito: Vercel Hobby limita a 12 funciones por
deploy. La lógica de cada endpoint de edición vive en handlers.py.

AUTENTICACIÓN: salvo /api/login (y /api/ping para detección de modo), TODO exige una sesión válida
(cookie firmada). Sin sesión → 401. Así el login protege los DATOS, no solo la pantalla.
AUTORIZACIÓN (RBAC): además de estar logueado, cada request se chequea contra el ROL del usuario
(auth.puede_get / auth.puede_post). Un cajero que fuerce a mano una ruta de admin —por ejemplo
POST /api/opex_vigencia desde la consola del navegador— se come un 403 y queda registrado en la
auditoría. Y GET /api/data le vuelve RECORTADO (auth.filtrar_data): lo que no puede ver no viaja.
AUDITORÍA: cada acción (editar/borrar/pull/config/login/logout) se registra en audit_log con el
usuario (sacado de la sesión verificada, infalsificable), la acción y el payload (password redactado).
"""
import json, os, datetime
from http.server import BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

from sl_common import (client, recompute, get_bistro_config, save_bistro_config, write_pull,
                       find_user, user_role, audit, recent_audit)
from handlers import ROUTES, NORECOMPUTE, SIN_RECOMPUTE
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

    def _sb(self):
        """Un solo cliente Supabase por request (el chequeo de rol y el endpoint comparten)."""
        if getattr(self, "_sb_cache", None) is None:
            self._sb_cache = client()
        return self._sb_cache

    def _auth(self):
        """(usuario, rol) de la sesión, o (None, None) si no hay sesión válida.

        El rol sale de la BASE en cada request, no del token: si a alguien lo bajan de admin a
        cajero o lo borran, pierde el acceso en el acto y no cuando se le venza la cookie."""
        user = auth.session_from_headers(self.headers)
        if not user:
            return None, None
        try:
            rol = user_role(self._sb(), user)
        except Exception as e:
            # No se pudo verificar el rol -> se trata como sin sesión. Fallar cerrado: mejor
            # pedir login de nuevo que servir datos con un rol adivinado.
            print("ERROR leyendo el rol ->", repr(e))
            return None, None
        if rol is None:
            return None, None          # el usuario ya no existe
        return user, rol

    # -------------------------------------------------- GET
    def do_GET(self):
        name = self._name()
        if name == "ping":
            return self._send(200, {"app": True, "env": ENV})

        # ---- relay de impresión: trabajos pendientes ----
        # Va ANTES del chequeo de sesión porque el relay es una máquina y no tiene cookie; se
        # autentica con su propio token. No afloja nada: si el token no está configurado o no
        # coincide, es 401 y nunca llega a la base.
        if name == "print_pend":
            if not auth.relay_autorizado(self.headers):
                return self._send(401, {"ok": False, "error": "relay no autorizado"})
            try:
                # Sólo lo reciente: un pendiente de hace días es de una noche que ya cerró y
                # nadie quiere que salga por la impresora al reconectar el relay.
                desde = (datetime.datetime.now(datetime.timezone.utc)
                         - datetime.timedelta(hours=12)).isoformat()
                r = (self._sb().table("cola_impresion")
                     .select("ticket,iso,escpos,intentos")
                     .eq("estado", "pendiente").gte("creado_ts", desde)
                     .order("creado_ts").limit(20).execute().data or [])
                return self._send(200, {"ok": True, "jobs": r})
            except Exception as e:
                return self._send(500, {"ok": False, "error": str(e)})
        user, rol = self._auth()
        if name == "me":
            if not user:
                return self._send(401, {"ok": False, "error": "no autenticado", "env": ENV})
            # `tabs` es lo que el frontend usa para dibujar el menú. Es una comodidad de UI, no
            # la defensa: aunque alguien lo falsee, el backend bloquea igual por rol.
            # `relay` dice sólo SI está configurado el token, nunca su valor. Sin esto, cargar
            # PRINT_RELAY_TOKEN en Vercel es un paso a ciegas: el endpoint del relay responde
            # 401 igual esté configurado o no (falla cerrada), así que desde afuera no hay forma
            # de saber si quedó bien puesto hasta que falla la impresión en pleno servicio.
            # Va en /api/me y no en /api/ping porque ping es público.
            return self._send(200, {"ok": True, "user": user, "rol": rol,
                                    "tabs": auth.tabs_de(rol), "env": ENV,
                                    "relay": bool(os.environ.get("PRINT_RELAY_TOKEN"))})
        if not user:
            return self._send(401, {"ok": False, "error": "no autenticado"})
        if not auth.puede_get(rol, name):
            return self._send(403, {"ok": False, "error": "Tu usuario no tiene acceso a esto."})
        # --- a partir de acá, autenticado Y autorizado ---
        if name == "data":
            try:
                sb = self._sb()
                r = sb.table("antimo_data").select("data").eq("id", 1).execute()
                DATA = r.data[0]["data"] if r.data else {}
                return self._send(200, auth.filtrar_data(DATA, rol))
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

        # ---- relay de impresión: marcar impreso / reportar fallo ----
        # Igual que print_pend: token propio, antes del chequeo de sesión.
        if name == "print_ok":
            if not auth.relay_autorizado(self.headers):
                return self._send(401, {"ok": False, "error": "relay no autorizado"})
            tk = str(data.get("ticket") or "").strip()
            if not tk:
                return self._send(400, {"ok": False, "error": "falta el ticket"})
            try:
                sb = self._sb()
                if data.get("error"):
                    # Falló la impresión: se cuenta el intento y queda pendiente para el próximo
                    # ciclo. A partir de 5 intentos se abandona, para no trabar la cola con un
                    # ticket imposible (impresora rota) mientras los nuevos esperan detrás.
                    n = int(data.get("intentos") or 0) + 1
                    campos = {"intentos": n}
                    if n >= 5:
                        campos["estado"] = "impreso"     # se da por perdido, no bloquea la cola
                        print("WARN: ticket", tk, "abandonado tras 5 intentos de impresión")
                    sb.table("cola_impresion").update(campos).eq("ticket", tk).execute()
                else:
                    sb.table("cola_impresion").update({
                        "estado": "impreso",
                        "impreso_ts": datetime.datetime.now(datetime.timezone.utc).isoformat()
                    }).eq("ticket", tk).execute()
                return self._send(200, {"ok": True})
            except Exception as e:
                return self._send(500, {"ok": False, "error": str(e)})

        # ---- todo lo demás exige sesión ----
        user, rol = self._auth()
        if not user:
            return self._send(401, {"ok": False, "error": "no autenticado"})

        # ---- ...y que el ROL lo habilite. Acá se corta un cajero que fuerce una ruta de admin.
        if not auth.puede_post(rol, name):
            # Se registra: un intento de escribir donde no corresponde es justo lo que el dueño
            # quiere ver en el log. Nunca hace fallar la respuesta (audit ya traga sus errores).
            try:
                audit(self._sb(), user, "denegado:" + name, data)
            except Exception:
                pass
            return self._send(403, {"ok": False,
                                    "error": "Tu usuario no tiene permiso para esta acción."})

        if name == "logout":
            try:
                audit(self._sb(), user, "logout", {})
            except Exception:
                pass
            return self._send(200, {"ok": True}, extra_headers=[("Set-Cookie", auth.cookie_clear())])

        try:
            sb = self._sb()
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
                return self._send(200, {"ok": True, "data": auth.filtrar_data(DATA, rol),
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
            if name in SIN_RECOMPUTE:
                return self._send(200, {"ok": True})
            DATA = recompute(sb)
            # El recálculo devuelve el DATA completo; al cajero le vuelve recortado igual que
            # por GET /api/data (si no, guardar un precio le filtraba todo de rebote).
            return self._send(200, {"ok": True, "data": auth.filtrar_data(DATA, rol)})
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
