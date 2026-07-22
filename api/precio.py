"""POST /api/precio — override de precio de insumo {insumo, precio}. Recalcula con el motor."""
from sl_common import make_handler


def apply(data, sb):
    insumo = str(data.get("insumo", "")).strip()
    try:
        precio = float(data.get("precio"))
    except (TypeError, ValueError):
        return "Precio inválido"
    if not insumo or precio < 0:
        return "Datos inválidos"
    sb.table("precios_override").upsert({"insumo": insumo, "precio": precio}).execute()
    return None


handler = make_handler(apply)
