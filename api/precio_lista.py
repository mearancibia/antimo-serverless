"""POST /api/precio_lista — precio de lista de un producto {key, precio}. Vacío/0 => vuelve al
valor de la hoja del Excel (borra el override)."""
from sl_common import make_handler


def apply(data, sb):
    key = str(data.get("key", "")).strip()
    if not key:
        return "Falta el producto"
    precio = data.get("precio")
    if precio in (None, "", 0, "0"):
        sb.table("precio_lista_override").delete().eq("key", key).execute()
        return None
    try:
        precio = float(precio)
    except (TypeError, ValueError):
        return "Precio inválido"
    if precio < 0:
        return "Precio inválido"
    sb.table("precio_lista_override").upsert({"key": key, "precio": precio}).execute()
    return None


handler = make_handler(apply)
