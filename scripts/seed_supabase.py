#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Sube al Supabase de la fase 1 los datos que hoy calcula/edita la app local:
- datos_dashboard.json          -> tabla antimo_data (fila única, id=1)
- datos/precios_override.json   -> tabla precios_override
- datos/recetas_extra.json      -> tabla recetas_extra

Correr DESPUÉS de aplicar supabase_schema.sql y ANTES del primer deploy (o cada vez que se
corra el motor local y se quiera reflejar el resultado en el Vercel). No toca nada local.

Uso:
    export SUPABASE_URL=...
    export SUPABASE_SERVICE_KEY=...
    python3 scripts/seed_supabase.py
"""
import json
import os
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _load(path, default):
    if not os.path.exists(path):
        return default
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def main():
    try:
        from supabase import create_client
    except ImportError:
        sys.exit("Falta el paquete 'supabase'. Corré: pip install -r requirements.txt")

    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_KEY")
    if not url or not key:
        sys.exit("Faltan SUPABASE_URL / SUPABASE_SERVICE_KEY en el entorno (ver .env.example).")

    sb = create_client(url, key)

    data = _load(os.path.join(BASE, "datos_dashboard.json"), None)
    if data is None:
        sys.exit("No encontré datos_dashboard.json — corré antes 'python3 actualizar_antimo.py'.")
    sb.table("antimo_data").upsert(
        {"id": 1, "data": data, "generado": data.get("generado")}
    ).execute()
    print(f"antimo_data: subido ({len(data.get('productos', []))} productos).")

    precios = _load(os.path.join(BASE, "datos", "precios_override.json"), {})
    if precios:
        rows = [{"insumo": k, "precio": float(v)} for k, v in precios.items()]
        sb.table("precios_override").upsert(rows).execute()
        print(f"precios_override: subidas {len(rows)} filas.")

    recetas = _load(os.path.join(BASE, "datos", "recetas_extra.json"), {})
    if recetas:
        rows = [{"nombre": k, "ingredientes": v} for k, v in recetas.items()]
        sb.table("recetas_extra").upsert(rows).execute()
        print(f"recetas_extra: subidas {len(rows)} filas.")

    print("Listo.")


if __name__ == "__main__":
    main()
