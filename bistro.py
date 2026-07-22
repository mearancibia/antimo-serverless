# -*- coding: utf-8 -*-
"""Lógica PURA del conector Bistrosoft (sin I/O de archivos), para correr server-side en /api/pull.
Es el mismo algoritmo que conector_bistrosoft.py (token JWT → TransactionDetailReport paginado →
parse por noche de caja), extraído para que la nube escriba a Supabase en vez de Excel/JSON.

Reglas de oro que se mantienen:
- Noche de caja rotulada por fecha de CIERRE (corte 08:00): lo de 00:00-07:59 cuenta para la noche
  que cerró esa madrugada. `business_ddmm_ym` devuelve (DD-MM, YYYY-MM, YYYY-MM-DD).
- Comandas anuladas (status VOID): se excluyen por ticketNumber (defensivo para pulls a mitad de
  turno; sobre datos históricos ya suman neto $0).
- Nunca inventar el año: el ISO sale del timestamp real de cada transacción.
"""
import datetime, re, collections

REQ_TIMEOUT = 25  # < límite de Vercel; si Bistrosoft tarda, falla claro en vez de colgar la función


def get_token(base, user, pw):
    import requests
    r = requests.post(base.rstrip("/") + "/api/v1/Token",
                      json={"username": user, "password": pw}, timeout=REQ_TIMEOUT)
    if r.status_code in (401, 403):
        raise RuntimeError("Usuario o contraseña rechazados por Bistrosoft. Revisá la configuración.")
    r.raise_for_status()
    try:
        j = r.json()
    except ValueError:
        raise RuntimeError(f"Bistrosoft respondió algo que no es JSON (HTTP {r.status_code}).")
    if "token" not in j:
        raise RuntimeError(f"La respuesta de login no trae token. Claves: {list(j)[:5]}")
    return j["token"]


def fetch_all(base, token, shop, start, end):
    import requests
    items = []; page = 0; hdr = {"Authorization": "Bearer " + token}
    while True:
        params = {"startDate": start, "endDate": end, "shopCode": shop, "pageNumber": page}
        r = requests.get(base.rstrip("/") + "/api/v1/TransactionDetailReport",
                         headers=hdr, params=params, timeout=REQ_TIMEOUT)
        if r.status_code == 401:
            raise RuntimeError("Token vencido/inválido")
        r.raise_for_status()
        try:
            batch = r.json().get("items", [])
        except ValueError:
            raise RuntimeError(f"Bistrosoft devolvió algo que no es JSON en la página {page}.")
        if not batch:
            break
        items += batch; page += 1
        if page >= 5000:
            break
    return items


def clean_product(p):
    p = (p or "").strip()
    p = re.sub(r"^[A-Za-z] - ", "", p)
    return p


def business_ddmm_ym(it):
    ts = it.get("timestamp")
    bd = None
    try:
        dt = datetime.datetime.fromisoformat(str(ts))
        bd = dt.date() if dt.hour < 8 else dt.date() + datetime.timedelta(days=1)
    except Exception:
        pp = str(it.get("date") or "").split("-")
        if len(pp) >= 3:
            try:
                bd = datetime.date(int(pp[2]), int(pp[1]), int(pp[0]))
            except Exception:
                bd = None
    if bd is None:
        return None, None, None
    return bd.strftime("%d-%m"), bd.strftime("%Y-%m"), bd.isoformat()


def _nuevo_dia():
    return {"total_vendido": 0.0, "efectivo": 0.0, "tarjetas": 0.0, "qr": 0.0, "otros_pago": 0.0,
            "comensales": 0, "descuentos": 0.0, "retiros": 0.0, "depositos": 0.0,
            "detalle_retiros": [], "detalle_descuentos": []}


def parse_items(items):
    """Devuelve (rank, cajas). rank = {'YYYY-MM': {(ddmm,prod): [q,amt]}}; cajas = lista por noche."""
    anuladas = {it.get("ticketNumber") for it in items
                if (it.get("transactionType") or "").startswith("Comanda") and it.get("status") == "VOID"}
    if anuladas:
        items = [it for it in items if it.get("ticketNumber") not in anuladas]
    rank = collections.defaultdict(lambda: collections.defaultdict(lambda: [0.0, 0.0]))
    dias = {}
    for it in items:
        tt = (it.get("transactionType") or "").strip()
        ddmm, ym, iso = business_ddmm_ym(it)
        if ddmm is None:
            continue
        amt = float(it.get("amount") or 0)
        if tt in ("- ITEM", "- COMBO"):
            prod = clean_product(it.get("product"))
            if not prod or prod == "-":
                continue
            cell = rank[ym][(ddmm, prod)]
            cell[0] += float(it.get("quantity") or 0); cell[1] += amt
            continue
        v = dias.setdefault(iso, _nuevo_dia()); v["_ddmm"] = ddmm
        if tt == "- ITEM DESCUENTO":
            v["descuentos"] += amt
            v["detalle_descuentos"].append({"concepto": (it.get("comments") or "").strip()[:50],
                "monto": amt, "user": it.get("user") or "", "hora": it.get("hour") or ""})
        elif tt.startswith("Comanda"):
            v["total_vendido"] += amt
            pm = (it.get("paymentMethod") or "").upper()
            if "EFECT" in pm:
                v["efectivo"] += amt
            elif "TARJ" in pm:
                v["tarjetas"] += amt
            elif "QR" in pm:
                v["qr"] += amt
            else:
                v["otros_pago"] += amt
            if tt == "Comanda":
                try:
                    v["comensales"] += int(float(it.get("dinnersQty") or 0))
                except (TypeError, ValueError):
                    pass
        elif tt == "CAJA (RETIRO)":
            v["retiros"] += amt
            v["detalle_retiros"].append({"concepto": (it.get("comments") or "").strip()[:60],
                "monto": amt, "user": it.get("user") or "", "hora": it.get("hour") or ""})
        elif tt == "CAJA (DEPOSITO)":
            v["depositos"] += amt
    cajas = []
    for iso_f, v in sorted(dias.items()):
        if v["total_vendido"] == 0 and v["retiros"] == 0 and v["depositos"] == 0:
            continue
        ddmm = v.pop("_ddmm", iso_f)
        v["fecha"] = ddmm; v["fecha_dia"] = ddmm; v["archivo"] = "Bistrosoft API"
        v["fecha_iso"] = iso_f; v["fecha_key"] = iso_f
        cajas.append(v)
    return rank, cajas


def default_range():
    """Del 1 del mes pasado hasta mañana. Arranca en el 1 de un mes a propósito: el pull reemplaza
    meses COMPLETOS en Supabase, así que un rango que empiece a mitad de mes perdería los primeros
    días de ese mes (mismo criterio que el conector local)."""
    today = datetime.date.today()
    first_prev = (today.replace(day=1) - datetime.timedelta(days=1)).replace(day=1)
    end = today + datetime.timedelta(days=1)
    return first_prev.isoformat(), end.isoformat()
