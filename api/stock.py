"""POST /api/stock — conteo manual de un insumo vigilado {insumo, cantidad, fecha, umbral_dias}.
Cantidad vacía/0 => dejar de vigilarlo (borra la fila)."""
import datetime
from sl_common import make_handler, ISO_RE


def apply(data, sb):
    insumo = str(data.get("insumo", "")).strip()
    if not insumo:
        return "Falta el insumo"
    cant = data.get("cantidad")
    if cant in (None, "", 0, "0"):
        sb.table("stock").delete().eq("insumo", insumo).execute()
        return None
    try:
        cant = float(cant)
    except (TypeError, ValueError):
        return "Cantidad inválida"
    if cant < 0:
        return "Cantidad inválida"
    fecha = str(data.get("fecha") or "").strip()
    if not ISO_RE.match(fecha):
        fecha = datetime.date.today().isoformat()
    entry = {"cant": cant, "fecha": fecha}
    umb = data.get("umbral_dias")
    if umb not in (None, "", 0, "0"):
        try:
            entry["umbral_dias"] = float(umb)
        except (TypeError, ValueError):
            pass
    sb.table("stock").upsert({"insumo": insumo, "data": entry}).execute()
    return None


handler = make_handler(apply)
