"""POST /api/dia_cerrado — marca/desmarca una noche sin apertura {iso, cerrado, motivo}."""
from sl_common import make_handler, ISO_RE


def apply(data, sb):
    iso = str(data.get("iso", "")).strip()
    if not ISO_RE.match(iso):
        return "Fecha inválida"
    if data.get("cerrado"):
        sb.table("dias_cerrados").upsert({"iso": iso, "motivo": data.get("motivo", "") or "Cerrado"}).execute()
    else:
        sb.table("dias_cerrados").delete().eq("iso", iso).execute()
    return None


handler = make_handler(apply)
