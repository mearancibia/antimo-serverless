# -*- coding: utf-8 -*-
"""Lógica de todos los endpoints POST que escriben un override y recalculan. Un solo módulo con un
dict ROUTES {nombre: apply(data, sb) -> error|None}, para que la ÚNICA función serverless
(api/index.py) despache por acá. Consolidar todo en una función es necesario en Vercel Hobby, que
limita a 12 funciones por deploy (un archivo por endpoint daban 18).
"""
import datetime, re
from engine import norm
from sl_common import opex_periodos, opex_vigente, save_opex

ISO_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _precio(data, sb):
    insumo = str(data.get("insumo", "")).strip()
    try:
        precio = float(data.get("precio"))
    except (TypeError, ValueError):
        return "Precio inválido"
    if not insumo or precio < 0:
        return "Datos inválidos"
    sb.table("precios_override").upsert({"insumo": insumo, "precio": precio}).execute()


def _receta(data, sb):
    nombre = str(data.get("receta", "")).strip()
    ingredientes = data.get("ingredientes") or []
    if not nombre or not ingredientes:
        return "La receta quedó vacía"
    sb.table("recetas_extra").upsert(
        {"nombre": nombre, "ingredientes": [[i[0], i[1]] for i in ingredientes]}).execute()


def _precio_lista(data, sb):
    key = str(data.get("key", "")).strip()
    if not key:
        return "Falta el producto"
    precio = data.get("precio")
    if precio in (None, "", 0, "0"):
        sb.table("precio_lista_override").delete().eq("key", key).execute()
        return
    try:
        precio = float(precio)
    except (TypeError, ValueError):
        return "Precio inválido"
    if precio < 0:
        return "Precio inválido"
    sb.table("precio_lista_override").upsert({"key": key, "precio": precio}).execute()


def _pour(data, sb):
    key = str(data.get("key", "")).strip()
    if not key:
        return "Falta el producto"
    rend = data.get("rend")
    if rend in (None, "", 0, "0"):
        sb.table("pours_extra").delete().eq("key", key).execute()
        return
    try:
        rend = float(rend)
    except (TypeError, ValueError):
        return "Rendimiento inválido"
    if rend <= 0:
        return "Rendimiento inválido"
    sb.table("pours_extra").upsert({"key": key, "rend": rend}).execute()


def _combo(data, sb):
    producto = str(data.get("producto", "")).strip()
    comp = data.get("componentes") or []
    if not producto:
        return "Falta el producto"
    if not comp:
        return "El combo quedó sin componentes"
    sb.table("combos_extra").upsert(
        {"pos": producto, "componentes": [[x[0], x[1], x[2]] for x in comp]}).execute()


def _sospechoso(data, sb):
    key = str(data.get("key", "")).strip()
    if not key:
        return "Falta el producto"
    est = str(data.get("estado", "") or "")
    if est not in ("si", "no"):
        sb.table("sospechosos").delete().eq("key", key).execute()
        return
    entry = {"estado": est, "motivo": data.get("motivo", "") or "",
             "ts": datetime.datetime.now().isoformat(timespec="seconds")}
    sb.table("sospechosos").upsert({"key": key, "data": entry}).execute()


def _dia_cerrado(data, sb):
    iso = str(data.get("iso", "")).strip()
    if not ISO_RE.match(iso):
        return "Fecha inválida"
    if data.get("cerrado"):
        sb.table("dias_cerrados").upsert({"iso": iso, "motivo": data.get("motivo", "") or "Cerrado"}).execute()
    else:
        sb.table("dias_cerrados").delete().eq("iso", iso).execute()


def _stock(data, sb):
    insumo = str(data.get("insumo", "")).strip()
    if not insumo:
        return "Falta el insumo"
    cant = data.get("cantidad")
    if cant in (None, "", 0, "0"):
        sb.table("stock").delete().eq("insumo", insumo).execute()
        return
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


def _stock_bulk(data, sb):
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


def _costos_bulk(data, sb):
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


def _opex_save(data, sb):
    ps = opex_periodos(sb)
    desde = str(data.get("desde") or "").strip() or opex_vigente(ps)
    hit = [p for p in ps if str(p.get("desde")) == desde]
    if hit:
        hit[0]["items"] = data.get("items", [])
    else:
        ps.append({"desde": desde, "items": data.get("items", [])})
        ps.sort(key=lambda p: str(p.get("desde")))
    save_opex(sb, ps)


def _opex_vigencia(data, sb):
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


def _producto(data, sb):
    pos = str(data.get("pos", "")).strip()
    if not pos:
        return "Falta el nombre"
    tipo = data.get("tipo", "receta")
    entry = {"pos": pos, "cat": data.get("cat") or "GENERICO", "canon": data.get("canon") or pos,
             "tipo": tipo, "factor": float(data.get("factor") or (2 if tipo == "promo_2x1" else 1)),
             "rend": (float(data["rend"]) if data.get("rend") not in (None, "", "0", 0) else None),
             "costeo": "", "nota": data.get("nota", "") or "Creado desde la app"}
    if tipo in ("receta", "promo_2x1"):
        entry["costeo"] = "Receta: " + pos
        sb.table("recetas_extra").upsert(
            {"nombre": pos, "ingredientes": [[i[0], i[1]] for i in data.get("ingredientes", [])]}).execute()
    elif tipo in ("botella", "pour", "directo"):
        entry["costeo"] = "Insumo: " + str(data.get("insumo", "")).strip()
    elif tipo == "combo":
        entry["costeo"] = "Combo definido en app"
        sb.table("combos_extra").upsert(
            {"pos": pos, "componentes": [[x[0], float(x[1]), x[2]] for x in data.get("componentes", [])]}).execute()
    sb.table("maestro_extra").upsert({"pos": norm(pos), "data": entry}).execute()


# ---------------------------------------------------------------- caja de respaldo
# Medios de pago del POS -> campos de la caja (mismo criterio que bistro.parse_items, que
# clasifica por subcadena sobre el paymentMethod de Bistrosoft).
def _campo_pago(medio):
    pm = str(medio or "").upper()
    if "EFECT" in pm:
        return "efectivo"
    if "TARJ" in pm or "DEBITO" in pm or "CREDITO" in pm:
        return "tarjetas"
    if "QR" in pm:
        return "qr"
    return "otros_pago"          # transferencia y cualquier otro


def _num(x, default=0.0):
    try:
        v = float(x)
    except (TypeError, ValueError):
        return default
    return default if v != v or v in (float("inf"), float("-inf")) else v


def _caja_vacia():
    """Misma forma que bistro._nuevo_dia(). Se replica en vez de importar bistro para no
    arrastrar `requests` a este módulo; si allá se agrega un campo, agregarlo acá."""
    return {"total_vendido": 0.0, "efectivo": 0.0, "tarjetas": 0.0, "qr": 0.0, "otros_pago": 0.0,
            "comensales": 0, "descuentos": 0.0, "retiros": 0.0, "depositos": 0.0,
            "detalle_retiros": [], "detalle_descuentos": []}


def _derivar_caja(iso, tickets):
    """Arma la caja de la noche sumando TODOS sus tickets. Se recalcula entera en cada POST en
    vez de acumular: así reintentar un ticket (mala señal desde el celu) no cuenta doble."""
    v = _caja_vacia()
    for t in tickets:
        d = t.get("data") or {}
        for linea in (d.get("lineas") or []):
            if linea.get("anulada"):
                continue
            v["total_vendido"] += _num(linea.get("monto"))
        # el descuento va aparte, NO restado dentro del producto (igual que "- ITEM DESCUENTO")
        desc = _num(d.get("descuento"))
        if desc:
            v["descuentos"] += desc
            v["detalle_descuentos"].append({
                "concepto": str(d.get("descuento_concepto") or "")[:50], "monto": desc,
                "user": str(d.get("user") or ""), "hora": str(d.get("hora") or "")})
        v["total_vendido"] -= desc          # total_vendido = neto cobrado
        for p in (d.get("pagos") or []):
            v[_campo_pago(p.get("medio"))] += _num(p.get("monto"))
        try:
            v["comensales"] += int(_num(d.get("comensales")))
        except (TypeError, ValueError):
            pass
    v["fecha"] = _ddmm(iso); v["fecha_dia"] = v["fecha"]
    v["fecha_iso"] = iso; v["fecha_key"] = iso
    v["archivo"] = "Caja respaldo"
    return v


def _ddmm(iso):
    try:
        return datetime.date.fromisoformat(iso).strftime("%d-%m")
    except Exception:
        return iso


def _caja_venta(data, sb):
    """Registra una venta cobrada por la caja de respaldo.

    Escribe el ticket entero (fuente de verdad) + su espejo plano en ventas_backup, y RECALCULA
    la caja de esa noche sobre todos sus tickets. Idempotente por `ticket`: un reintento desde el
    celular reescribe lo mismo y la caja da igual, no suma dos veces.
    """
    ticket = str(data.get("ticket") or "").strip()
    if not ticket:
        return "Falta el id del ticket"
    iso = str(data.get("iso") or "").strip()
    if not ISO_RE.match(iso):
        return "Fecha de la noche inválida"

    lineas = data.get("lineas") or []
    vivas = [l for l in lineas if not l.get("anulada")]
    if not vivas:
        return "El ticket no tiene líneas"

    # una fila por producto (agregando si el mismo producto vino en dos líneas del ticket):
    # ventas_backup tiene unique(ticket, nombre) y un upsert con dos filas iguales se pisa a sí mismo
    agg = {}
    for l in vivas:
        nombre = str(l.get("nombre") or "").strip()   # CRUDO: lo normaliza el motor
        if not nombre:
            return "Una línea vino sin nombre de producto"
        u, m = _num(l.get("unidades")), _num(l.get("monto"))
        if u < 0 or m < 0:
            return "Cantidades o montos negativos"
        a = agg.setdefault(nombre, [0.0, 0.0])
        a[0] += u; a[1] += m

    ddmm = _ddmm(iso)
    sb.table("tickets_backup").upsert({"ticket": ticket, "iso": iso, "data": data}).execute()
    sb.table("ventas_backup").upsert(
        [{"ticket": ticket, "nombre": n, "fecha": ddmm, "iso": iso,
          "unidades": u, "monto": round(m, 2)} for n, (u, m) in agg.items()],
        on_conflict="ticket,nombre").execute()

    # sobran las filas de un producto que ya no está (ticket corregido y reenviado)
    vivos = list(agg)
    sb.table("ventas_backup").delete().eq("ticket", ticket).not_.in_("nombre", vivos).execute()

    tickets = sb.table("tickets_backup").select("data").eq("iso", iso).execute().data or []
    sb.table("cajas_backup").upsert({"fecha_key": iso, "data": _derivar_caja(iso, tickets)}).execute()


def _backup_excluir(data, sb):
    """Válvula anti doble conteo: marca una noche como 'ya volcada a Bistrosoft'. Saca del
    cómputo las ventas Y la caja de respaldo de esa noche (las dos, ver fusionar_backup)."""
    iso = str(data.get("iso") or "").strip()
    if not ISO_RE.match(iso):
        return "Fecha inválida"
    if data.get("excluir"):
        sb.table("backup_excluido").upsert(
            {"iso": iso, "motivo": str(data.get("motivo") or "") or "Volcado a Bistrosoft"}).execute()
    else:
        sb.table("backup_excluido").delete().eq("iso", iso).execute()


# nombre de endpoint -> función apply (todas recalculan tras aplicar)
ROUTES = {
    "precio": _precio, "receta": _receta, "precio_lista": _precio_lista, "pour": _pour,
    "combo": _combo, "sospechoso": _sospechoso, "dia_cerrado": _dia_cerrado, "stock": _stock,
    "stock_bulk": _stock_bulk, "costos_bulk": _costos_bulk, "opex_save": _opex_save,
    "opex_vigencia": _opex_vigencia, "producto": _producto,
    "caja_venta": _caja_venta, "backup_excluir": _backup_excluir,
}

# POST que NO recalcula y no aplica en la nube (no hay filesystem persistente donde dejar el Excel).
MSG_EXCEL = ("Generar el Excel completo se hace desde la app local (run_ANTIMO_app), no desde la nube.")
NORECOMPUTE = {"excel": MSG_EXCEL}
