#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Prueba end-to-end del RBAC contra el handler REAL de api/index.py, con un Supabase falso.
Verifica que el bloqueo sea del servidor, no de la pantalla."""
import os, sys, json, types, io

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)
sys.path.insert(0, os.path.join(BASE, "api"))
os.environ["SESSION_SECRET"] = "secreto-de-prueba"
os.environ["SUPABASE_URL"] = "http://fake"
os.environ["SUPABASE_SERVICE_KEY"] = "fake"

# ---- stub de las dependencias pesadas (no hay red ni Supabase real acá) ----
USERS = {"dueño": {"username": "dueño", "password_hash": "x", "role": "admin"},
         "cajero1": {"username": "cajero1", "password_hash": "x", "role": "cajero"}}

DATA_FULL = {
    "generado": "2026-07-30", "opex": 13310000, "opex_pend": 2,
    "opex_detalle": [{"cat": "Sueldos", "item": "Chef", "monto": 900000}],
    "opex_periodos": [{"desde": "2026-01-01", "items": [{"cat": "Sueldos"}]}],
    "dias": [{"fecha": "01-07", "iso": "2026-07-01", "dow": "Mie"}],
    "consumo_dia": {"01-07": {"Hielo": 300}},
    "insumos": {"Hielo": {"cxu": 2.5, "precio": 1000, "cant_base": 400}},
    "cajas": [{"fecha": "01-07", "total_vendido": 500000}],
    "productos": [{"pos": "CUARTO DE LIBRA", "key": "K", "cat": "HAMB", "nd": False,
                   "costo": 7584, "susp": "si", "receta_ings": [["Pan", "1u"]],
                   "byday": {"01-07": [3, 39000]},
                   "breakdown": [{"insumo": "Pan", "qty": 1, "unidad": "u",
                                  "cxu": 178.5, "sub": 178.5}]}]}

ESCRITURAS = []


class _Q:
    def __init__(self, tabla): self.t = tabla; self._eq = {}
    def select(self, *a, **k):
        if self.t == "users" and "role" not in (a[0] if a else ""):
            self._sin_role = True
        return self
    def eq(self, k, v): self._eq[k] = v; return self
    def like(self, *a): return self
    def order(self, *a, **k): return self
    def limit(self, *a): return self
    def insert(self, rows): ESCRITURAS.append((self.t, "insert", rows)); return self
    def upsert(self, rows): ESCRITURAS.append((self.t, "upsert", rows)); return self
    def delete(self): ESCRITURAS.append((self.t, "delete", None)); return self
    def execute(self):
        r = types.SimpleNamespace(data=[])
        if self.t == "users":
            u = USERS.get(self._eq.get("username"))
            r.data = [dict(u)] if u else []
        elif self.t == "antimo_data":
            r.data = [{"data": json.loads(json.dumps(DATA_FULL))}]
        elif self.t == "app_meta":
            r.data = [{"value": {}}]
        return r


class FakeSB:
    def table(self, t): return _Q(t)


fake_supabase = types.ModuleType("supabase")
fake_supabase.create_client = lambda u, k: FakeSB()
sys.modules["supabase"] = fake_supabase

import sl_common
sl_common.client = lambda: FakeSB()
sl_common.recompute = lambda sb: json.loads(json.dumps(DATA_FULL))

import auth
import index as api          # api/index.py

api.client = lambda: FakeSB()
api.recompute = lambda sb: json.loads(json.dumps(DATA_FULL))


# ---- arnés HTTP mínimo ----
class Headers(dict):
    def get(self, k, d=None):
        for kk, vv in self.items():
            if kk.lower() == k.lower():
                return vv
        return d


def pedir(metodo, ruta, usuario=None, body=None, ct="application/json"):
    h = api.handler.__new__(api.handler)
    h.headers = Headers({"Content-Type": ct})
    if usuario:
        h.headers["Cookie"] = "%s=%s" % (auth.COOKIE_NAME, auth.make_session(usuario))
    raw = json.dumps(body or {}).encode()
    h.headers["Content-Length"] = str(len(raw))
    h.rfile = io.BytesIO(raw)
    h.path = ruta
    cap = {}
    h.send_response = lambda c: cap.__setitem__("code", c)
    h.send_header = lambda k, v: None
    h.end_headers = lambda: None
    h.wfile = io.BytesIO()
    (h.do_GET if metodo == "GET" else h.do_POST)()
    return cap.get("code"), json.loads(h.wfile.getvalue().decode() or "{}")


# ---------------------------------------------------------------- pruebas
fallos = []


def ok(nombre, cond, extra=""):
    print(("  ✅ " if cond else "  ❌ ") + nombre + (("  <- " + str(extra)) if (extra and not cond) else ""))
    if not cond:
        fallos.append(nombre)


print("\n=== 1. Sin sesión: nada pasa ===")
c, j = pedir("GET", "/api/data")
ok("GET /api/data sin cookie -> 401", c == 401, (c, j))
c, j = pedir("POST", "/api/precio", body={"insumo": "Hielo", "precio": 1200})
ok("POST /api/precio sin cookie -> 401", c == 401, (c, j))
c, j = pedir("GET", "/api/ping")
ok("GET /api/ping sin cookie -> 200 (detección de modo)", c == 200, (c, j))

print("\n=== 2. /api/me informa el rol y las solapas ===")
c, j = pedir("GET", "/api/me", "dueño")
ok("admin -> 7 solapas", c == 200 and len(j.get("tabs", [])) == 7 and j.get("rol") == "admin", (c, j))
c, j = pedir("GET", "/api/me", "cajero1")
ok("cajero -> compras/caja/costos", c == 200 and j.get("tabs") == ["compras", "caja", "costos"], (c, j))

print("\n=== 3. GET /api/data recortado de verdad (el bloqueo no es de pantalla) ===")
c, adm = pedir("GET", "/api/data", "dueño")
ok("admin ve el costo", adm["productos"][0].get("costo") == 7584, adm["productos"][0])
ok("admin ve el OPEX", adm.get("opex") == 13310000)
c, caj = pedir("GET", "/api/data", "cajero1")
p = caj["productos"][0]
ok("cajero NO recibe costo", "costo" not in p, p.keys())
ok("cajero NO recibe cxu/sub del breakdown",
   "cxu" not in p["breakdown"][0] and "sub" not in p["breakdown"][0], p["breakdown"])
ok("cajero NO recibe receta_ings ni susp", "receta_ings" not in p and "susp" not in p, p.keys())
ok("cajero NO recibe OPEX", caj.get("opex") == 0 and caj.get("opex_detalle") == []
   and caj.get("opex_periodos") == [], (caj.get("opex"), caj.get("opex_detalle")))
ok("cajero SÍ recibe lo suyo (insumos/consumo_dia/cajas/byday/qty)",
   bool(caj.get("insumos")) and bool(caj.get("consumo_dia")) and bool(caj.get("cajas"))
   and bool(p.get("byday")) and p["breakdown"][0].get("qty") == 1)
ok("el JSON del cajero no contiene la palabra 'costo' en ningún lado",
   "costo" not in json.dumps(caj, ensure_ascii=False))

print("\n=== 4. POST: el cajero escribe donde le corresponde ===")
for ep, cuerpo in [("precio", {"insumo": "Hielo", "precio": 1200}),
                   ("stock", {"insumo": "Hielo", "cant": 5}),
                   ("stock_bulk", {"filas": []}),
                   ("costos_bulk", {"filas": []}),
                   ("dia_cerrado", {"iso": "2026-07-05", "motivo": "feriado"})]:
    api.ROUTES[ep] = lambda d, sb: None          # el apply real no importa acá: se prueba el permiso
    c, j = pedir("POST", "/api/" + ep, "cajero1", cuerpo)
    ok("cajero POST /api/%s -> permitido" % ep, c == 200 and j.get("ok") is True, (c, j))

print("\n=== 5. POST: el cajero NO puede forzar rutas de admin (403 del SERVIDOR) ===")
for ep, cuerpo in [("opex_vigencia", {"desde": "2026-08-01"}),
                   ("opex_save", {"items": []}),
                   ("receta", {"nombre": "X", "ings": []}),
                   ("producto", {"pos": "X"}),
                   ("combo", {"pos": "X", "componentes": []}),
                   ("pour", {"key": "X", "ml": 60}),
                   ("precio_lista", {"key": "X", "precio": 1}),
                   ("sospechoso", {"key": "X", "estado": "si"}),
                   ("config", {"username": "u", "password": "p"})]:
    c, j = pedir("POST", "/api/" + ep, "cajero1", cuerpo)
    ok("cajero POST /api/%s -> 403" % ep, c == 403, (c, j))
    c2, _ = pedir("POST", "/api/" + ep, "dueño", cuerpo)
    ok("  ...y el admin SÍ puede (no es 403)", c2 != 403, c2)

print("\n=== 6. GET de admin bloqueados para el cajero ===")
for ep in ("config", "audit"):
    c, j = pedir("GET", "/api/" + ep, "cajero1")
    ok("cajero GET /api/%s -> 403" % ep, c == 403, (c, j))

print("\n=== 7. El intento denegado queda en la auditoría ===")
ESCRITURAS.clear()
pedir("POST", "/api/opex_vigencia", "cajero1", {"desde": "2026-08-01"})
audits = [r for r in ESCRITURAS if r[0] == "audit_log"]
ok("se registró 'denegado:opex_vigencia'",
   any("denegado" in str(r[2].get("action", "")) for r in audits), audits)

print("\n=== 8. El rol sale de la BASE, no del token (revocación inmediata) ===")
tok_admin = auth.make_session("cajero1")          # cookie emitida cuando era... cajero
USERS["cajero1"]["role"] = "admin"                # el dueño lo asciende
c, j = pedir("POST", "/api/opex_vigencia", "cajero1", {"desde": "2026-08-01"})
ok("ascendido a admin -> deja de ser 403 sin volver a loguearse", c != 403, (c, j))
USERS["cajero1"]["role"] = "cajero"               # y lo vuelve atrás
c, j = pedir("POST", "/api/opex_vigencia", "cajero1", {"desde": "2026-08-01"})
ok("degradado a cajero -> vuelve a 403 con la MISMA cookie", c == 403, (c, j))
borrado = USERS.pop("cajero1")
c, j = pedir("GET", "/api/data", "cajero1")
ok("usuario borrado -> 401 aunque la cookie siga firmada y vigente", c == 401, (c, j))
USERS["cajero1"] = borrado

print("\n=== 9. Rol desconocido en la base -> cae al default, no explota ===")
USERS["raro"] = {"username": "raro", "password_hash": "x", "role": "gerente-general"}
c, j = pedir("GET", "/api/me", "raro")
ok("rol inválido -> normaliza a admin (no 500)", c == 200 and j.get("rol") == "admin", (c, j))

print("\n=== 10. Sigue valiendo el chequeo de origen (Content-Type) ===")
c, j = pedir("POST", "/api/precio", "dueño", {"insumo": "Hielo"}, ct="text/plain")
ok("POST sin Content-Type json -> 403", c == 403, (c, j))

print("\n" + "=" * 60)
print("FALLOS: %d" % len(fallos))
for f in fallos:
    print("  - " + f)
sys.exit(1 if fallos else 0)
