"""POST /api/costos_bulk — importación masiva de precios y/o stock en una sola pasada
{precios:[{insumo,precio}], stock:[{insumo,cantidad,umbral_dias}], fecha}.
Precio <=0 se rechaza (falsea márgenes); stock <=0 se saltea. El frontend ya mostró la vista
previa obligatoria, pero acá se revalida todo porque el endpoint es alcanzable sin pasar por ahí."""
import datetime
from sl_common import make_handler, ISO_RE


def apply(data, sb):
    pv = data.get("precios") or []
    sk = data.get("stock") or []
    if not pv and not sk:
        return "No vino ningún cambio"
    if pv:
        rows = []
        for e in pv:
            nm = str(e.get("insumo", "")).strip()
            try:
                val = float(e.get("precio"))
            except (TypeError, ValueError):
                continue
            if not nm or val <= 0:
                continue
            rows.append({"insumo": nm, "precio": val})
        if rows:
            sb.table("precios_override").upsert(rows).execute()
    if sk:
        fecha = str(data.get("fecha") or "").strip()
        if not ISO_RE.match(fecha):
            fecha = datetime.date.today().isoformat()
        rows = []
        for e in sk:
            nm = str(e.get("insumo", "")).strip()
            try:
                cant = float(e.get("cantidad"))
            except (TypeError, ValueError):
                continue
            if not nm or cant <= 0:
                continue
            entry = {"cant": cant, "fecha": fecha}
            try:
                u = float(e.get("umbral_dias"))
                if u > 0:
                    entry["umbral_dias"] = u
            except (TypeError, ValueError):
                pass
            rows.append({"insumo": nm, "data": entry})
        if rows:
            sb.table("stock").upsert(rows).execute()
    return None


handler = make_handler(apply)
