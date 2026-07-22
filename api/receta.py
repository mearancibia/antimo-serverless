"""POST /api/receta — receta nueva o editada {receta, ingredientes:[[ing,cant],...]}. Recalcula."""
from sl_common import make_handler


def apply(data, sb):
    nombre = str(data.get("receta", "")).strip()
    ingredientes = data.get("ingredientes") or []
    if not nombre or not ingredientes:
        return "La receta quedó vacía"
    sb.table("recetas_extra").upsert(
        {"nombre": nombre, "ingredientes": [[i[0], i[1]] for i in ingredientes]}).execute()
    return None


handler = make_handler(apply)
