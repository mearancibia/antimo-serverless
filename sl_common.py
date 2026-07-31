# -*- coding: utf-8 -*-
"""Común a las funciones serverless de /api. Cliente Supabase, recálculo con el motor, y un
`make_handler(apply)` que arma el BaseHTTPRequestHandler con todo el boilerplate (chequeo de
origen, parseo del body, y el flujo: escribir override -> recalcular -> devolver DATA fresca).

Cada endpoint define `apply(data, sb) -> error|None` (escribe su override) y hace
`handler = make_handler(apply)`. Vercel busca el atributo `handler` en cada archivo.
"""
import os, json, re, datetime
from http.server import BaseHTTPRequestHandler

from supabase import create_client
from engine import compute, OPEX_DESDE_0
from sources import SupabaseSource
import auth


def client():
    return create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_KEY"])


def recompute(sb):
    """Corre el motor sobre Supabase, guarda el DATA en antimo_data y lo devuelve. Si el motor
    sembró el OPEX (porque app_meta.opex_json estaba vacío), lo persiste para próximas corridas."""
    src = SupabaseSource(sb).build()
    DATA, seed = compute(src)
    if seed is not None:
        sb.table("app_meta").upsert({"key": "opex_json", "value": seed}).execute()
    sb.table("antimo_data").upsert({"id": 1, "data": DATA, "generado": DATA.get("generado")}).execute()
    return DATA


def _origen_confiable(headers):
    ct = (headers.get("Content-Type") or "").split(";")[0].strip().lower()
    return ct == "application/json"


def make_handler(apply):
    class H(BaseHTTPRequestHandler):
        def _send(self, code, payload):
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def do_POST(self):
            if not _origen_confiable(self.headers):
                return self._send(403, {"ok": False, "error": "origen no permitido"})
            try:
                ln = int(self.headers.get("Content-Length") or 0)
                data = json.loads(self.rfile.read(ln) or b"{}")
            except Exception:
                return self._send(400, {"ok": False, "error": "cuerpo inválido"})
            try:
                sb = client()
                err = apply(data, sb)
                if err:
                    return self._send(200, {"ok": False, "error": err})
                DATA = recompute(sb)
                return self._send(200, {"ok": True, "data": DATA})
            except Exception as e:
                print("ERROR endpoint ->", repr(e))
                return self._send(500, {"ok": False, "error": str(e)})
    return H


# ---------------------------------------------------------------- OPEX (app_meta.opex_json)
def opex_periodos(sb):
    """opex.json (guardado en app_meta) normalizado a [{desde,items}] ordenado. Acepta el formato
    viejo (lista plana) leyéndolo como una única vigencia desde siempre."""
    r = sb.table("app_meta").select("value").eq("key", "opex_json").execute().data
    raw = (r[0]["value"] if r else None) or []
    if not raw:
        return [{"desde": OPEX_DESDE_0, "items": []}]
    if isinstance(raw[0], dict) and "items" in raw[0]:
        return sorted([p for p in raw if isinstance(p, dict)],
                      key=lambda p: str(p.get("desde") or OPEX_DESDE_0))
    return [{"desde": OPEX_DESDE_0, "items": raw}]


def opex_vigente(ps):
    hoy = datetime.date.today().isoformat()
    cur = [p for p in ps if str(p.get("desde") or OPEX_DESDE_0) <= hoy]
    return str((cur[-1] if cur else ps[0]).get("desde") or OPEX_DESDE_0)


def save_opex(sb, ps):
    sb.table("app_meta").upsert({"key": "opex_json", "value": ps}).execute()


ISO_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


# ---------------------------------------------------------------- auth + auditoría
def find_user(sb, username):
    """{username, password_hash, role} o None si no existe."""
    try:
        r = (sb.table("users").select("username,password_hash,role")
             .eq("username", username).execute().data)
    except Exception as e:
        # La columna `role` recién existe después de correr la migración de supabase_schema.sql.
        # Si todavía no está, se lee como antes y todos quedan con el rol por defecto (admin),
        # que es EXACTAMENTE el comportamiento previo al RBAC: nadie queda afuera y nadie gana
        # permisos que no tuviera. Al correr el ALTER, los roles empiezan a valer solos.
        print("WARN: users.role no disponible (¿falta correr la migración?) ->", repr(e))
        r = (sb.table("users").select("username,password_hash")
             .eq("username", username).execute().data)
    return r[0] if r else None


def user_role(sb, username):
    """Rol vigente del usuario, leído de la BASE (no del token). None si el usuario ya no existe
    — así, borrar un usuario le corta el acceso en el acto aunque tenga una cookie válida."""
    u = find_user(sb, username)
    return None if not u else auth.normalizar_rol(u.get("role"))


# claves sensibles que NUNCA deben quedar en el log de auditoría en texto plano
_REDACT = {"password", "pass", "pw"}


def audit(sb, username, action, detail):
    """Registra una acción en audit_log. Redacta contraseñas. Nunca hace fallar la operación
    principal: si el log falla, se ignora (mejor perder una línea de log que bloquear una edición)."""
    try:
        d = detail
        if isinstance(detail, dict):
            d = {k: ("***" if k.lower() in _REDACT else v) for k, v in detail.items()}
        sb.table("audit_log").insert({"username": username, "action": action, "detail": d}).execute()
    except Exception as e:
        print("WARN: no pude registrar auditoría ->", repr(e))


def recent_audit(sb, limit=300):
    return (sb.table("audit_log").select("ts,username,action,detail")
            .order("ts", desc=True).limit(limit).execute().data or [])


# ---------------------------------------------------------------- Bistrosoft (config + pull)
def get_bistro_config(sb):
    r = sb.table("app_meta").select("value").eq("key", "bistro_config").execute().data
    return (r[0]["value"] if r else None) or {}


def save_bistro_config(sb, cfg):
    sb.table("app_meta").upsert({"key": "bistro_config", "value": cfg}).execute()


def _chunks(lst, n=500):
    for i in range(0, len(lst), n):
        yield lst[i:i + n]


def write_pull(sb, rank, cajas):
    """Escribe el resultado del pull en Supabase, con la MISMA semántica que el conector local:
    - ventas: reemplaza cada MES completo (borra las filas de ese YYYY-MM y reinserta las del pull).
      Por eso el pull arranca en el 1 de un mes (default_range): así los meses del rango se
      reescriben enteros y no se pierde nada.
    - cajas: se FUSIONAN por noche (upsert por fecha_key), no se sobreescriben las viejas."""
    nv = 0
    for ym, cells in rank.items():
        rows = []
        for (ddmm, prod), (q, amt) in cells.items():
            dd, mm = (ddmm.split("-") + ["", ""])[:2]
            iso = f"{ym[:4]}-{mm}-{dd}" if (mm and dd) else ""
            rows.append({"nombre": prod, "fecha": ddmm, "iso": iso,
                         "unidades": int(round(q)), "monto": round(amt)})
        # borrar el mes entero antes de reinsertar (equivale a reescribir api_ventas_YYYY-MM.xlsx)
        sb.table("ventas").delete().like("iso", ym + "-%").execute()
        for ch in _chunks(rows):
            if ch:
                sb.table("ventas").insert(ch).execute()
        nv += len(rows)
    nc = 0
    caja_rows = [{"fecha_key": c.get("fecha_key") or c.get("fecha_iso") or c.get("fecha"), "data": c}
                 for c in cajas if (c.get("fecha_key") or c.get("fecha_iso") or c.get("fecha"))]
    for ch in _chunks(caja_rows):
        if ch:
            sb.table("cajas").upsert(ch).execute()
    nc = len(caja_rows)
    return nv, nc
