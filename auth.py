# -*- coding: utf-8 -*-
"""Autenticación de ANTIMO en la nube: hashing de contraseñas (PBKDF2, stdlib) y sesiones firmadas
con HMAC (cookie HttpOnly). Sin dependencias nuevas.

- Usuarios: tabla `users` en Supabase {username, password_hash}. Un solo nivel de acceso (sin roles).
- Login: /api/login verifica usuario+contraseña y devuelve una cookie de sesión FIRMADA. La firma la
  hace el servidor con un secreto (SESSION_SECRET, o el service key como fallback), así el cliente no
  puede fabricar ni alterar la sesión. La cookie es HttpOnly (el JS del navegador no la lee) → si hay
  un XSS, no se puede robar la sesión leyéndola.
- La contraseña NUNCA se guarda ni se loguea en texto plano. El hash es PBKDF2-SHA256 con sal por
  usuario. Verificación en tiempo constante (hmac.compare_digest).
"""
import os, hmac, hashlib, base64, time

PBKDF2_ITER = 200000
SESSION_TTL = 7 * 24 * 3600  # 7 días
COOKIE_NAME = "antimo_sess"


# ---------------------------------------------------------------- contraseñas
def hash_password(pw, iterations=PBKDF2_ITER):
    salt = os.urandom(16)
    dk = hashlib.pbkdf2_hmac("sha256", pw.encode("utf-8"), salt, iterations)
    return "pbkdf2_sha256$%d$%s$%s" % (iterations, salt.hex(), dk.hex())


def verify_password(pw, stored):
    try:
        algo, iters, salt_hex, hash_hex = stored.split("$")
        if algo != "pbkdf2_sha256":
            return False
        dk = hashlib.pbkdf2_hmac("sha256", pw.encode("utf-8"), bytes.fromhex(salt_hex), int(iters))
        return hmac.compare_digest(dk.hex(), hash_hex)
    except Exception:
        return False


# ---------------------------------------------------------------- sesiones firmadas
def _secret():
    # secreto para firmar. Dedicado si está SESSION_SECRET; si no, el service key (secreto y estable).
    return (os.environ.get("SESSION_SECRET") or os.environ.get("SUPABASE_SERVICE_KEY") or "").encode("utf-8")


def _sign(payload):
    return hmac.new(_secret(), payload.encode("utf-8"), hashlib.sha256).hexdigest()


def make_session(username):
    exp = int(time.time()) + SESSION_TTL
    payload = "%s|%d" % (username, exp)
    token = "%s|%s" % (payload, _sign(payload))
    return base64.urlsafe_b64encode(token.encode("utf-8")).decode("ascii")


def read_session(token):
    """Devuelve el username si el token es válido y no expiró; si no, None."""
    if not token:
        return None
    try:
        raw = base64.urlsafe_b64decode(token.encode("ascii")).decode("utf-8")
        username, exp, sig = raw.rsplit("|", 2)
        payload = "%s|%s" % (username, exp)
        if not hmac.compare_digest(_sign(payload), sig):
            return None
        if int(exp) < int(time.time()):
            return None
        return username
    except Exception:
        return None


# ---------------------------------------------------------------- cookies
def cookie_header(token):
    return ("%s=%s; HttpOnly; Secure; SameSite=Strict; Path=/; Max-Age=%d"
            % (COOKIE_NAME, token, SESSION_TTL))


def cookie_clear():
    return "%s=; HttpOnly; Secure; SameSite=Strict; Path=/; Max-Age=0" % COOKIE_NAME


def session_from_headers(headers):
    """Extrae el token de la cookie del request y devuelve el username (o None)."""
    raw = headers.get("Cookie") or ""
    for part in raw.split(";"):
        part = part.strip()
        if part.startswith(COOKIE_NAME + "="):
            return read_session(part[len(COOKIE_NAME) + 1:])
    return None


VALID_USERNAME = __import__("re").compile(r"^[A-Za-z0-9_.@-]{3,40}$")


# ---------------------------------------------------------------- roles (RBAC)
# FUENTE ÚNICA DE VERDAD del reparto de permisos. El backend la usa para bloquear de verdad
# (403) y el frontend recibe de acá la lista de solapas por /api/me. Si se agrega un endpoint
# o una solapa, se toca ACÁ y los dos lados quedan alineados solos.
#
# ⚠️ El rol NO viaja dentro del token de sesión: se lee de la base en cada request. Así, si a
# alguien lo pasan de admin a cajero (o lo borran), pierde el acceso en el acto y no cuando se
# le venza la cookie 7 días después.
ROL_ADMIN = "admin"
ROL_CAJERO = "cajero"
ROLES = (ROL_ADMIN, ROL_CAJERO)
ROL_DEFAULT = ROL_ADMIN

# Solapas del tablero (los data-t de #tabs en index.html).
TABS_ADMIN = ("resumen", "rent", "recetas", "compras", "caja", "costos", "opex")
TABS_CAJERO = ("compras", "caja", "costos")
TABS_POR_ROL = {ROL_ADMIN: TABS_ADMIN, ROL_CAJERO: TABS_CAJERO}

# GET que puede hacer un cajero. Quedan afuera `config` (credenciales de Bistrosoft) y `audit`
# (registro de actividad de todos los usuarios).
GET_CAJERO = frozenset({"ping", "me", "data"})

# POST que puede hacer un cajero. El cajero SÍ escribe: son las acciones de sus tres solapas.
#   precio / costos_bulk / stock / stock_bulk -> Costos y Compras (precios de insumos y conteos)
#   dia_cerrado                               -> Caja (marcar una noche sin apertura)
#   pull                                      -> traer ventas de Bistrosoft (cerrar la noche)
# Quedan afuera, y son 403 aunque se fuercen a mano desde la consola del navegador:
#   opex_save / opex_vigencia  -> OPEX (incluye sueldos)
#   receta / combo / producto / pour / precio_lista -> Recetas y Rentabilidad
#   sospechoso                 -> marca del dueño sobre precios/costos
#   config                     -> credenciales de Bistrosoft
POST_CAJERO = frozenset({"logout", "precio", "costos_bulk", "stock", "stock_bulk",
                         "dia_cerrado", "pull"})


def normalizar_rol(rol):
    """Cualquier cosa que no sea un rol conocido cae en el default. Nunca devuelve None."""
    return rol if rol in ROLES else ROL_DEFAULT


def es_admin(rol):
    return normalizar_rol(rol) == ROL_ADMIN


def tabs_de(rol):
    return list(TABS_POR_ROL[normalizar_rol(rol)])


def puede_get(rol, name):
    return True if es_admin(rol) else (name in GET_CAJERO)


def puede_post(rol, name):
    return True if es_admin(rol) else (name in POST_CAJERO)


# Campos que NO viajan al navegador de un cajero.
_PROD_OCULTO = ("costo", "receta_ings", "combo_comp", "susp", "susp_motivo")
_BREAKDOWN_OCULTO = ("cxu", "sub")


def filtrar_data(DATA, rol):
    """Recorta el DATA que se le manda a un rol sin acceso total.

    El bloqueo es REAL: lo que el cajero no puede ver NO SALE del servidor, así que no alcanza
    con abrir DevTools y hacer fetch('/api/data'). Se van el OPEX entero (incluye sueldos) y el
    costo/margen por producto.

    Se QUEDAN, porque sus solapas los necesitan: `insumos` (los edita en Costos), `consumo_dia`
    y el `breakdown` sin la parte de plata (Compras los usa para reconstruir el consumo cuando
    hay filtro por categoría) y `cajas` (Caja).

    ⚠️ Honestidad sobre el alcance: con los precios de insumos (que edita) más las cantidades
    del breakdown, un cajero puede DERIVAR el costo de un producto a mano. Eso es inherente a
    darle permiso de tocar costos — no hay forma de que edite precios sin verlos. Lo que sí
    queda realmente fuera de su alcance es el OPEX y la rentabilidad neta del negocio.
    """
    if es_admin(rol) or not isinstance(DATA, dict):
        return DATA
    d = dict(DATA)
    d["opex"] = 0
    d["opex_pend"] = 0
    d["opex_detalle"] = []
    d["opex_periodos"] = []
    prods = []
    for p in (d.get("productos") or []):
        if not isinstance(p, dict):
            continue
        q = {k: v for k, v in p.items() if k not in _PROD_OCULTO}
        bd = q.get("breakdown")
        if isinstance(bd, list):
            q["breakdown"] = [{k: v for k, v in b.items() if k not in _BREAKDOWN_OCULTO}
                              for b in bd if isinstance(b, dict)]
        prods.append(q)
    d["productos"] = prods
    return d
