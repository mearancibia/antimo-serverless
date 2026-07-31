#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Crea (o actualiza) un usuario de ANTIMO en Supabase. La contraseña se TIPEA acá (no se ve en
pantalla, no queda en el historial) y se guarda HASHEADA — nunca en texto plano.

Uso (con SUPABASE_URL y SUPABASE_SERVICE_KEY exportadas):
    python3 scripts/crear_usuario.py
    python3 scripts/crear_usuario.py jazzarelli                  # pregunta el rol
    python3 scripts/crear_usuario.py juan --rol cajero           # sin preguntar

Roles:
    admin   acceso total al tablero.
    cajero  sólo Compras, Caja y Costos (puede editar ahí adentro). No ve OPEX, márgenes,
            matriz BCG, punto de equilibrio ni el resumen.

Corré este script una vez por cada usuario que quieras dar de alta. Para cambiar una contraseña
o el rol, volvé a correrlo con el mismo usuario.
"""
import os, sys, getpass

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _env


def main():
    try:
        from supabase import create_client
    except ImportError:
        sys.exit("Falta 'supabase'. Corré: pip install -r requirements.txt")
    from auth import hash_password, VALID_USERNAME, ROLES, ROL_ADMIN, ROL_CAJERO

    _env.exigir()          # toma el .env si las variables no están exportadas
    url = os.environ["SUPABASE_URL"]; key = os.environ["SUPABASE_SERVICE_KEY"]
    sb = create_client(url, key)

    # --rol <valor> en cualquier posición; el resto de los argumentos es el usuario.
    argv = sys.argv[1:]
    rol = None
    if "--rol" in argv:
        i = argv.index("--rol")
        if i + 1 >= len(argv):
            sys.exit("Falta el valor de --rol (admin | cajero).")
        rol = argv[i + 1].strip().lower()
        del argv[i:i + 2]

    username = (argv[0] if argv else input("Usuario: ")).strip()
    if not VALID_USERNAME.match(username):
        sys.exit("Usuario inválido (3-40 caracteres: letras, números, . _ - @).")

    if rol is None:
        r = input(f"Rol [{ROL_ADMIN}/{ROL_CAJERO}] (Enter = {ROL_ADMIN}): ").strip().lower()
        rol = r or ROL_ADMIN
    if rol not in ROLES:
        sys.exit(f"Rol inválido: '{rol}'. Tiene que ser uno de: {', '.join(ROLES)}.")

    pw1 = getpass.getpass("Contraseña (no se muestra): ")
    if len(pw1) < 4:
        sys.exit("La contraseña es demasiado corta (mínimo 4 caracteres).")
    pw2 = getpass.getpass("Repetir contraseña: ")
    if pw1 != pw2:
        sys.exit("Las contraseñas no coinciden.")

    sb.table("users").upsert({"username": username, "password_hash": hash_password(pw1),
                              "role": rol}).execute()
    print(f"Usuario '{username}' guardado con rol '{rol}' (contraseña hasheada). Listo.")


if __name__ == "__main__":
    main()
