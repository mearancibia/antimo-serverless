"""POST /api/opex_vigencia — crea o borra una vigencia de OPEX {desde, borrar?, copiar_de?}.
Una vigencia nueva arranca como copia de otra (o de la última); después se editan solo los
rubros que variaron."""
from sl_common import make_handler, opex_periodos, save_opex, ISO_RE


def apply(data, sb):
    desde = str(data.get("desde") or "").strip()
    if not ISO_RE.match(desde):
        return "Fecha inválida"
    ps = opex_periodos(sb)
    if data.get("borrar"):
        if len(ps) <= 1:
            return "No se puede borrar la única vigencia"
        ps = [p for p in ps if str(p.get("desde")) != desde]
    else:
        if any(str(p.get("desde")) == desde for p in ps):
            return "Ya existe una vigencia desde esa fecha"
        src = str(data.get("copiar_de") or "")
        base = [p for p in ps if str(p.get("desde")) == src] or ps[-1:]
        ps.append({"desde": desde, "items": [dict(e) for e in (base[0].get("items") or [])]})
        ps.sort(key=lambda p: str(p.get("desde")))
    save_opex(sb, ps)
    return None


handler = make_handler(apply)
