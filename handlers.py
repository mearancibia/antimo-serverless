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


# nombre de endpoint -> función apply (todas recalculan tras aplicar)
ROUTES = {
    "precio": _precio, "receta": _receta, "precio_lista": _precio_lista, "pour": _pour,
    "combo": _combo, "sospechoso": _sospechoso, "dia_cerrado": _dia_cerrado, "stock": _stock,
    "stock_bulk": _stock_bulk, "costos_bulk": _costos_bulk, "opex_save": _opex_save,
    "opex_vigencia": _opex_vigencia, "producto": _producto,
}

# POST que NO recalculan (funciones que no corren en la nube todavía): responden un mensaje claro.
MSG_PULL = ("El pull de Bistrosoft todavía no corre en la nube (Fase 3). Actualizá las ventas "
            "corriendo el conector en la Mac (python3 conector_bistrosoft.py) y después "
            "python3 scripts/seed_supabase.py.")
MSG_EXCEL = ("Generar el Excel completo se hace desde la app local (run_ANTIMO_app), no desde la nube.")
MSG_CONFIG = ("Traer ventas desde la nube todavía no está disponible (Fase 3). Las ventas se "
              "actualizan corriendo el conector en la Mac y volviendo a subir con seed_supabase.py.")
NORECOMPUTE = {"pull": MSG_PULL, "excel": MSG_EXCEL, "config": MSG_CONFIG}
