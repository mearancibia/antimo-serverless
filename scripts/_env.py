# -*- coding: utf-8 -*-
"""Carga SUPABASE_URL / SUPABASE_SERVICE_KEY desde un archivo .env si no están en el entorno.

Las variables exportadas con `export` se pierden al cerrar la Terminal, así que había que
volver a tipearlas en cada sesión (y con eso venía el riesgo de pegar la key en el lugar
equivocado). Con esto se escriben UNA vez en .env — que está en .gitignore y nunca se sube.

Sólo lo usan los scripts que corren en la Mac. En Vercel no hace falta: las variables las
inyecta la plataforma, y este módulo ni siquiera viaja con la función.

Precedencia: lo que ya esté exportado en el entorno GANA sobre el .env, para poder apuntar a
otra base en una corrida puntual sin editar el archivo:
    SUPABASE_URL=... python3 scripts/seed_supabase.py
"""
import os

CLAVES = ("SUPABASE_URL", "SUPABASE_SERVICE_KEY", "SESSION_SECRET")


def cargar(base=None):
    """Lee .env de la raíz del proyecto y completa lo que falte. Devuelve las claves cargadas."""
    base = base or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    ruta = os.path.join(base, ".env")
    if not os.path.exists(ruta):
        return []
    puestas = []
    try:
        with open(ruta, encoding="utf-8") as f:
            for linea in f:
                linea = linea.strip()
                if not linea or linea.startswith("#") or "=" not in linea:
                    continue
                k, v = linea.split("=", 1)
                k = k.strip()
                v = v.strip().strip('"').strip("'")      # tolera comillas alrededor del valor
                if k and v and not os.environ.get(k):     # no pisar lo ya exportado
                    os.environ[k] = v
                    puestas.append(k)
    except Exception as e:
        print("Aviso: no pude leer .env ->", e)
    return puestas


def exigir(*claves):
    """Carga el .env y corta con un mensaje claro si sigue faltando algo."""
    cargar()
    faltan = [c for c in (claves or ("SUPABASE_URL", "SUPABASE_SERVICE_KEY")) if not os.environ.get(c)]
    if faltan:
        raise SystemExit(
            "Faltan " + ", ".join(faltan) + ".\n"
            "Escribilas UNA vez en el archivo .env de la carpeta del proyecto:\n"
            "    SUPABASE_URL=https://tu-proyecto.supabase.co\n"
            "    SUPABASE_SERVICE_KEY=eyJ...\n"
            "(ver .env.example · el .env no se sube a git)")
