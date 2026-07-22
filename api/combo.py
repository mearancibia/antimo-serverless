"""POST /api/combo — composición de un combo {producto, componentes:[[insumo,cant,unidad],...]}."""
from sl_common import make_handler


def apply(data, sb):
    producto = str(data.get("producto", "")).strip()
    comp = data.get("componentes") or []
    if not producto:
        return "Falta el producto"
    if not comp:
        return "El combo quedó sin componentes"
    sb.table("combos_extra").upsert(
        {"pos": producto, "componentes": [[x[0], x[1], x[2]] for x in comp]}).execute()
    return None


handler = make_handler(apply)
