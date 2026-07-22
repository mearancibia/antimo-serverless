"""POST /api/producto — crea un producto nuevo desde la app {pos, cat, canon, tipo, factor, rend,
insumo, ingredientes, componentes, nota}. Escribe en maestro_extra (+ recetas_extra o combos_extra
según el tipo). La PK de maestro_extra es el pos normalizado, así que recrear el mismo lo reemplaza."""
from engine import norm
from sl_common import make_handler


def apply(data, sb):
    pos = str(data.get("pos", "")).strip()
    if not pos:
        return "Falta el nombre"
    tipo = data.get("tipo", "receta")
    entry = {"pos": pos, "cat": data.get("cat") or "GENERICO", "canon": data.get("canon") or pos,
             "tipo": tipo, "factor": float(data.get("factor") or (2 if tipo == "promo_2x1" else 1)),
             "rend": (float(data["rend"]) if data.get("rend") not in (None, "", "0", 0) else None),
             "costeo": "", "nota": data.get("nota", "") or "Creado desde la app"}
    if tipo in ("receta", "promo_2x1"):
        entry["costeo"] = "Receta: " + pos
        sb.table("recetas_extra").upsert(
            {"nombre": pos, "ingredientes": [[i[0], i[1]] for i in data.get("ingredientes", [])]}).execute()
    elif tipo in ("botella", "pour", "directo"):
        entry["costeo"] = "Insumo: " + str(data.get("insumo", "")).strip()
    elif tipo == "combo":
        entry["costeo"] = "Combo definido en app"
        sb.table("combos_extra").upsert(
            {"pos": pos, "componentes": [[x[0], float(x[1]), x[2]] for x in data.get("componentes", [])]}).execute()
    sb.table("maestro_extra").upsert({"pos": norm(pos), "data": entry}).execute()
    return None


handler = make_handler(apply)
