"""POST /api/pour — rendimiento (ml) de un pour {key, rend}. Vacío/0 => vuelve al valor del Excel."""
from sl_common import make_handler


def apply(data, sb):
    key = str(data.get("key", "")).strip()
    if not key:
        return "Falta el producto"
    rend = data.get("rend")
    if rend in (None, "", 0, "0"):
        sb.table("pours_extra").delete().eq("key", key).execute()
        return None
    try:
        rend = float(rend)
    except (TypeError, ValueError):
        return "Rendimiento inválido"
    if rend <= 0:
        return "Rendimiento inválido"
    sb.table("pours_extra").upsert({"key": key, "rend": rend}).execute()
    return None


handler = make_handler(apply)
