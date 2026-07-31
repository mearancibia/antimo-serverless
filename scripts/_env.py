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


# Marcadores de los ejemplos de la documentación. Si alguno llega tal cual, es que se copió el
# comando sin reemplazarlo — pasó dos veces y el síntoma era un traceback de 20 líneas.
_PLACEHOLDERS = ("LA-KEY", "TU-PROYECTO", "PEGA_ACA", "eyJ...", "tu-service-role-key",
                 "LA-SERVICE-KEY", "DE-PRODUCCION", "DE-DESARROLLO")


def revisar_placeholders():
    import os
    for var in ("SUPABASE_URL", "SUPABASE_SERVICE_KEY"):
        v = os.environ.get(var, "")
        if any(ph.lower() in v.lower() for ph in _PLACEHOLDERS):
            raise SystemExit(
                f"\n{var} tiene un texto de EJEMPLO, no un valor real:\n"
                f"    {v[:45]}{'...' if len(v) > 45 else ''}\n\n"
                "Reemplazalo por el valor de verdad. La service_role key está en:\n"
                "  Supabase -> Settings -> API -> service_role (empieza con eyJ)\n")


def explicar_error(e):
    """Traduce los errores más comunes de Supabase a algo accionable."""
    import os
    t = str(e)
    if "Invalid API key" in t or "'code': 401" in t:
        url = os.environ.get("SUPABASE_URL", "(sin definir)")
        raise SystemExit(
            "\nSupabase rechazó la clave (Invalid API key).\n"
            f"  Base a la que apuntaste: {url}\n"
            "  Revisá que SUPABASE_SERVICE_KEY sea la 'service_role' DE ESA MISMA BASE\n"
            "  (Settings -> API). Ojo: las claves de desarrollo y produccion no son intercambiables.\n")
    if "does not exist" in t and "role" in t:
        raise SystemExit(
            "\nLa tabla users todavia no tiene la columna 'role'.\n"
            "  Corré la migración en el SQL Editor de ESA base (ver supabase_schema.sql).\n")
    if "Could not find the table" in t:
        raise SystemExit(
            "\nFalta crear las tablas en esa base.\n"
            "  Pegá supabase_schema.sql en el SQL Editor de Supabase y ejecutalo.\n")
    raise
