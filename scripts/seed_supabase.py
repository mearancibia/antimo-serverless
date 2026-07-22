#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Siembra Supabase con TODO lo que el motor necesita, a partir del Excel base + rankings +
overrides locales (vía LocalSource). Correr una vez tras aplicar supabase_schema.sql, y cada vez
que se quieran reflejar datos locales nuevos (p.ej. tras un pull de Bistrosoft o editar el Excel).

Sube:
  - datos maestros: costo_base, lista_precios, recetas, maestro_productos, opex_base
  - negocio: ventas (rankings), cajas
  - overrides existentes en datos/*.json (precios, recetas, combos, etc.)
  - app_meta: logo (data-URI), opex.json, opex_cero_confirmado
  - antimo_data: el DATA calculado por el motor (idéntico al datos_dashboard.json local)

Uso:
    export SUPABASE_URL=...
    export SUPABASE_SERVICE_KEY=...
    python3 scripts/seed_supabase.py
"""
import os, sys, json

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)


def _chunks(lst, n=500):
    for i in range(0, len(lst), n):
        yield lst[i:i + n]


def main():
    try:
        from supabase import create_client
    except ImportError:
        sys.exit("Falta 'supabase'. Corré: pip install -r requirements.txt")
    from engine import compute, norm
    from sources import LocalSource

    url = os.environ.get("SUPABASE_URL"); key = os.environ.get("SUPABASE_SERVICE_KEY")
    if not url or not key:
        sys.exit("Faltan SUPABASE_URL / SUPABASE_SERVICE_KEY (ver .env.example).")
    sb = create_client(url, key)

    print("Leyendo Excel + rankings + overrides locales…")
    src = LocalSource().build()

    def replace_all(table, rows):
        """Vacía la tabla y reinserta (para tablas sin merge, como ventas/opex_base)."""
        sb.table(table).delete().neq("id", -1).execute()
        for ch in _chunks(rows):
            if ch:
                sb.table(table).insert(ch).execute()

    def upsert(table, rows):
        for ch in _chunks(rows):
            if ch:
                sb.table(table).upsert(ch).execute()

    # ---- datos maestros ----
    upsert("costo_base", [{"nombre": k, "cb_cat": src["cb_cat"].get(k), "precio": v["precio"],
                           "pres": v["pres"], "cant_base": v["cant_base"], "unidad": v["unidad"],
                           "cxu": v["cxu"]} for k, v in src["costo_base"].items()])
    print(f"  costo_base: {len(src['costo_base'])}")

    upsert("lista_precios", [{"nombre": k, "precio": v} for k, v in src["precio_lista"].items()])
    print(f"  lista_precios: {len(src['precio_lista'])}")

    upsert("recetas", [{"nombre": k, "ingredientes": [[i[0], i[1]] for i in ings]}
                       for k, ings in src["recetas"].items()])
    print(f"  recetas: {len(src['recetas'])}")

    upsert("maestro_productos", [{"pos": k, "cat": v["cat"], "canon": v["canon"], "tipo": v["tipo"],
                                  "factor": v["factor"], "rend": v["rend"], "costeo": v["costeo"],
                                  "nota": v["nota"]} for k, v in src["maestro"].items()])
    print(f"  maestro_productos: {len(src['maestro'])}")

    replace_all("opex_base", src["opex_base"])
    print(f"  opex_base: {len(src['opex_base'])}")

    # ---- negocio ----
    replace_all("ventas", src["ventas"])
    print(f"  ventas: {len(src['ventas'])}")

    cajas_rows = []
    for c in src["cajas"]:
        fk = c.get("fecha_key") or c.get("fecha") or c.get("iso") or ""
        if fk:
            cajas_rows.append({"fecha_key": fk, "data": c})
    upsert("cajas", cajas_rows)
    print(f"  cajas: {len(cajas_rows)}")

    # ---- overrides (desde datos/*.json locales) ----
    ovr = src["overrides"]
    upsert("precios_override", [{"insumo": k, "precio": v} for k, v in ovr["precios_override"].items()])
    upsert("recetas_extra", [{"nombre": k, "ingredientes": v} for k, v in ovr["recetas_extra"].items()])
    upsert("precio_lista_override", [{"key": k, "precio": v} for k, v in ovr["precio_lista_override"].items()])
    upsert("pours_extra", [{"key": k, "rend": v} for k, v in ovr["pours_extra"].items()])
    upsert("maestro_extra", [{"pos": norm(e["pos"]), "data": e} for e in ovr["maestro_extra"]])
    upsert("insumos_extra", [{"nombre": e["nombre"], "data": e} for e in ovr["insumos_extra"]])
    upsert("combos_extra", [{"pos": k, "componentes": v} for k, v in ovr["combos_extra"].items()])
    upsert("sospechosos", [{"key": k, "data": v} for k, v in ovr["sospechosos"].items()])
    upsert("dias_cerrados", [{"iso": k, "motivo": v} for k, v in ovr["dias_cerrados"].items()])
    upsert("stock", [{"insumo": k, "data": v} for k, v in ovr["stock"].items()])
    print("  overrides subidos")

    # ---- app_meta ----
    meta = [{"key": "logo", "value": src["logo"]},
            {"key": "opex_json", "value": src["opex_json"]},
            {"key": "opex_cero_confirmado", "value": src["opex_cero_confirmado"]}]
    upsert("app_meta", meta)
    print("  app_meta subido (logo, opex_json, opex_cero_confirmado)")

    # ---- DATA calculado (para /api/data) ----
    DATA, _seed = compute(src)
    sb.table("antimo_data").upsert({"id": 1, "data": DATA, "generado": DATA.get("generado")}).execute()
    print(f"  antimo_data: {len(DATA.get('productos', []))} productos, "
          f"{len(DATA.get('cajas', []))} cajas, OPEX ${DATA.get('opex', 0):,.0f}")
    print("Listo.")


if __name__ == "__main__":
    main()
