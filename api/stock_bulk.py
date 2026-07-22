"""POST /api/stock_bulk — importación masiva de conteos {fecha, items:[{insumo,cantidad,umbral_dias}]}.
Una sola fecha para todo el lote. Filas inválidas se saltean, no aborta el import."""
import datetime
from sl_common import make_handler, ISO_RE


def apply(data, sb):
    fecha = str(data.get("fecha") or "").strip()
    if not ISO_RE.match(fecha):
        fecha = datetime.date.today().isoformat()
    rows = []
    for row in (data.get("items") or []):
        insumo = str(row.get("insumo", "")).strip()
        cant = row.get("cantidad")
        if not insumo or cant in (None, "", 0, "0"):
            continue
        try:
            cant = float(cant)
        except (TypeError, ValueError):
            continue
        if cant <= 0:
            continue
        entry = {"cant": cant, "fecha": fecha}
        umb = row.get("umbral_dias")
        if umb not in (None, "", 0, "0"):
            try:
                entry["umbral_dias"] = float(umb)
            except (TypeError, ValueError):
                pass
        rows.append({"insumo": insumo, "data": entry})
    if rows:
        sb.table("stock").upsert(rows).execute()
    return None


handler = make_handler(apply)
