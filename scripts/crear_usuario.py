#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Crea (o actualiza) un usuario de ANTIMO en Supabase. La contraseña se TIPEA acá (no se ve en
pantalla, no queda en el historial) y se guarda HASHEADA — nunca en texto plano.

Uso (con SUPABASE_URL y SUPABASE_SERVICE_KEY exportadas):
    python3 scripts/crear_usuario.py
    python3 scripts/crear_usuario.py jazzarelli      # pre-carga el usuario, pide solo la contraseña

Corré este script una vez por cada usuario que quieras dar de alta. Para cambiar una contraseña,
volvé a correrlo con el mismo usuario.
"""
import os, sys, getpass

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)


def main():
    try:
        from supabase import create_client
    except ImportError:
        sys.exit("Falta 'supabase'. Corré: pip install -r requirements.txt")
    from auth import hash_password, VALID_USERNAME

    url = os.environ.get("SUPABASE_URL"); key = os.environ.get("SUPABASE_SERVICE_KEY")
    if not url or not key:
        sys.exit("Faltan SUPABASE_URL / SUPABASE_SERVICE_KEY en el entorno (ver .env.example).")
    sb = create_client(url, key)

    username = (sys.argv[1] if len(sys.argv) > 1 else input("Usuario: ")).strip()
    if not VALID_USERNAME.match(username):
        sys.exit("Usuario inválido (3-40 caracteres: letras, números, . _ - @).")

    pw1 = getpass.getpass("Contraseña (no se muestra): ")
    if len(pw1) < 4:
        sys.exit("La contraseña es demasiado corta (mínimo 4 caracteres).")
    pw2 = getpass.getpass("Repetir contraseña: ")
    if pw1 != pw2:
        sys.exit("Las contraseñas no coinciden.")

    sb.table("users").upsert({"username": username, "password_hash": hash_password(pw1)}).execute()
    print(f"Usuario '{username}' guardado (contraseña hasheada). Listo.")


if __name__ == "__main__":
    main()
