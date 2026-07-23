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
