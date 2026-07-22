"""POST /api/sospechoso — marca de precio/costo mal cargado {key, estado:"si"|"no"|"", motivo}.
Estado vacío o inválido => limpia la marca. NO altera ningún costo/margen (solo etiqueta)."""
import datetime
from sl_common import make_handler


def apply(data, sb):
    key = str(data.get("key", "")).strip()
    if not key:
        return "Falta el producto"
    est = str(data.get("estado", "") or "")
    if est not in ("si", "no"):
        sb.table("sospechosos").delete().eq("key", key).execute()
        return None
    entry = {"estado": est, "motivo": data.get("motivo", "") or "",
             "ts": datetime.datetime.now().isoformat(timespec="seconds")}
    sb.table("sospechosos").upsert({"key": key, "data": entry}).execute()
    return None


handler = make_handler(apply)
