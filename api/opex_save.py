"""POST /api/opex_save — guarda los rubros de UNA vigencia de OPEX {desde?, items}.
Sin 'desde' => la vigencia que rige hoy."""
from sl_common import make_handler, opex_periodos, opex_vigente, save_opex


def apply(data, sb):
    ps = opex_periodos(sb)
    desde = str(data.get("desde") or "").strip() or opex_vigente(ps)
    hit = [p for p in ps if str(p.get("desde")) == desde]
    if hit:
        hit[0]["items"] = data.get("items", [])
    else:
        ps.append({"desde": desde, "items": data.get("items", [])})
        ps.sort(key=lambda p: str(p.get("desde")))
    save_opex(sb, ps)
    return None


handler = make_handler(apply)
