#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tests de la caja de respaldo, sin red y sin Supabase (cliente falso en memoria).

Cubre lo que el brief pide verificar: que la venta de respaldo SUME (no duplique) contra lo que
ya trae Bistrosoft, que una noche solo-backup exista, que la válvula saque las dos cosas a la
vez, que la plata no se infle 100x y que el corte de las 08:00 mande la venta a la noche
correcta. Correr: python3 scripts/test_caja_backup.py
"""
import os, sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine import compute, norm
from sources import fusionar_backup
import handlers

FALLAS = []


def check(cond, msg):
    print(("  ok   " if cond else "  FALLA ") + msg)
    if not cond:
        FALLAS.append(msg)


# ---------------------------------------------------------------- Supabase falso
class FakeTable:
    def __init__(self, db, name):
        self.db, self.name = db, name
        self._sel = None; self._filters = []; self._notin = None

    def select(self, *a, **k):
        self._sel = a; return self

    def eq(self, col, val):
        self._filters.append((col, val)); return self

    @property
    def not_(self):
        return self

    def in_(self, col, vals):
        self._notin = (col, set(vals)); return self

    def upsert(self, rows, on_conflict=None):
        rows = rows if isinstance(rows, list) else [rows]
        keys = {"tickets_backup": ("ticket",), "cajas_backup": ("fecha_key",),
                "ventas_backup": ("ticket", "nombre"), "backup_excluido": ("iso",),
                "cola_impresion": ("ticket",)}[self.name]
        t = self.db.setdefault(self.name, [])
        for r in rows:
            kv = tuple(r.get(k) for k in keys)
            for i, ex in enumerate(t):
                if tuple(ex.get(k) for k in keys) == kv:
                    t[i] = dict(r); break
            else:
                t.append(dict(r))
        return self

    def delete(self):
        self._del = True; return self

    def execute(self):
        rows = self.db.setdefault(self.name, [])
        keep = [r for r in rows if all(r.get(c) == v for c, v in self._filters)]
        if self._notin:
            col, vals = self._notin
            keep = [r for r in keep if r.get(col) not in vals]
        if getattr(self, "_del", False):
            for r in keep:
                rows.remove(r)
            return type("R", (), {"data": []})()
        return type("R", (), {"data": [dict(r) for r in keep]})()


class FakeSB:
    def __init__(self):
        self.db = {}

    def table(self, name):
        return FakeTable(self.db, name)


# ---------------------------------------------------------------- datos de prueba
def venta_bistro(nombre, iso, u, m):
    return {"nombre": nombre, "fecha": iso[8:10] + "-" + iso[5:7], "iso": iso,
            "unidades": u, "monto": m}


def caja_bistro(iso, total, efectivo):
    return {"total_vendido": total, "efectivo": efectivo, "tarjetas": 0.0, "qr": 0.0,
            "otros_pago": 0.0, "comensales": 10, "descuentos": 0.0, "retiros": 0.0,
            "depositos": 0.0, "detalle_retiros": [], "detalle_descuentos": [],
            "fecha": iso[8:10] + "-" + iso[5:7], "fecha_dia": iso[8:10] + "-" + iso[5:7],
            "fecha_iso": iso, "fecha_key": iso, "archivo": "Bistrosoft API"}


ISO = "2026-08-08"
OTRA = "2026-08-09"


def ticket(tid, iso, nombre, u, monto, medio="EFECTIVO", desc=0.0, comensales=2):
    return {"ticket": tid, "iso": iso, "comensales": comensales, "descuento": desc,
            "lineas": [{"nombre": nombre, "unidades": u, "monto": monto}],
            "pagos": [{"medio": medio, "monto": monto - desc}]}


print("\n=== 1. La venta de respaldo SUMA en la misma fila (no duplica el producto) ===")
sb = FakeSB()
handlers._caja_venta(ticket("t1", ISO, "FERNET CON COCA", 2, 20000), sb)
vbk = [{"nombre": r["nombre"], "fecha": r["fecha"], "iso": r["iso"],
        "unidades": r["unidades"], "monto": r["monto"]} for r in sb.db["ventas_backup"]]
cbk = [r["data"] for r in sb.db["cajas_backup"]]

ventas = [venta_bistro("FERNET CON COCA", ISO, 5, 50000)]
cajas = [caja_bistro(ISO, 50000, 50000)]
v2, c2 = fusionar_backup(ventas, cajas, vbk, cbk, [])
DATA, _ = compute({"costo_base": {}, "cb_cat": {}, "precio_lista": {}, "recetas": {},
                   "maestro": {}, "ventas": v2, "cajas": c2, "opex_json": [], "opex_base": [],
                   "opex_cero_confirmado": [], "overrides": {}, "logo": ""})
fer = [p for p in DATA["productos"] if norm(p["pos"]) == norm("FERNET CON COCA")]
check(len(fer) == 1, "el producto aparece UNA sola vez (no desdoblado)")
check(fer[0]["byday"][ISO] == [7, 70000], "unidades y monto sumados: 5+2=7 u, $50.000+$20.000")
cj = [c for c in DATA["cajas"] if c["fecha_key"] == ISO][0]
check(cj["total_vendido"] == 70000, "la caja de la noche suma los dos totales")
check(cj["efectivo"] == 70000, "el efectivo suma los dos")
check(cj["archivo"] == "Bistrosoft API", "conserva el archivo de Bistrosoft (dedupe intacto)")
check(len(DATA["cajas"]) == 1, "queda UNA sola caja por noche (no duplicada)")

print("\n=== 2. Idempotencia: reenviar el mismo ticket no cuenta doble ===")
handlers._caja_venta(ticket("t1", ISO, "FERNET CON COCA", 2, 20000), sb)
handlers._caja_venta(ticket("t1", ISO, "FERNET CON COCA", 2, 20000), sb)
check(len(sb.db["ventas_backup"]) == 1, "sigue habiendo 1 fila de venta tras 3 envíos")
check(sb.db["cajas_backup"][0]["data"]["total_vendido"] == 20000,
      "la caja sigue en $20.000 (se recalcula, no acumula)")

print("\n=== 3. Noche SOLO backup (Bistrosoft no tiene nada esa noche) ===")
sb3 = FakeSB()
handlers._caja_venta(ticket("t9", OTRA, "PIZZA MUZZARELLA", 3, 30000), sb3)
vbk3 = [{"nombre": r["nombre"], "fecha": r["fecha"], "iso": r["iso"],
         "unidades": r["unidades"], "monto": r["monto"]} for r in sb3.db["ventas_backup"]]
cbk3 = [r["data"] for r in sb3.db["cajas_backup"]]
v3, c3 = fusionar_backup([], [], vbk3, cbk3, [])
D3, _ = compute({"costo_base": {}, "cb_cat": {}, "precio_lista": {}, "recetas": {}, "maestro": {},
                 "ventas": v3, "cajas": c3, "opex_json": [], "opex_base": [],
                 "opex_cero_confirmado": [], "overrides": {}, "logo": ""})
dia = [d for d in D3["dias"] if d["iso"] == OTRA]
check(len(dia) == 1, "la noche aparece en DATA['dias']")
check(dia[0]["dow"] == "Dom", "el dow es correcto (2026-08-09 = domingo)")
check(len(D3["cajas"]) == 1 and D3["cajas"][0]["total_vendido"] == 30000, "su caja está y suma bien")

print("\n=== 4. Válvula: excluir la noche saca ventas Y caja ===")
v4, c4 = fusionar_backup(ventas, cajas, vbk, cbk, [ISO])
D4, _ = compute({"costo_base": {}, "cb_cat": {}, "precio_lista": {}, "recetas": {}, "maestro": {},
                 "ventas": v4, "cajas": c4, "opex_json": [], "opex_base": [],
                 "opex_cero_confirmado": [], "overrides": {}, "logo": ""})
f4 = [p for p in D4["productos"] if norm(p["pos"]) == norm("FERNET CON COCA")][0]
check(f4["byday"][ISO] == [5, 50000], "las unidades vuelven a ser SOLO las de la API (5 u)")
check([c for c in D4["cajas"] if c["fecha_key"] == ISO][0]["total_vendido"] == 50000,
      "la caja vuelve a ser SOLO la de la API ($50.000)")

print("\n=== 5. Plata: $10.000 es $10.000 (ni 100x ni /100) ===")
sb5 = FakeSB()
handlers._caja_venta(ticket("t5", ISO, "CERVEZA", 1, 10000), sb5)
check(sb5.db["ventas_backup"][0]["monto"] == 10000, "el monto se guarda en PESOS, tal cual")
check(sb5.db["cajas_backup"][0]["data"]["total_vendido"] == 10000, "la caja también")

print("\n=== 6. Medios de pago y descuento ===")
sb6 = FakeSB()
handlers._caja_venta({"ticket": "t6", "iso": ISO, "comensales": 4, "descuento": 1000,
                      "descuento_concepto": "Amigo del dueño",
                      "lineas": [{"nombre": "GIN TONIC", "unidades": 2, "monto": 12000}],
                      "pagos": [{"medio": "TARJETA DEBITO", "monto": 6000},
                                {"medio": "QR MERCADOPAGO", "monto": 3000},
                                {"medio": "TRANSFERENCIA", "monto": 2000}]}, sb6)
c6 = sb6.db["cajas_backup"][0]["data"]
check(c6["tarjetas"] == 6000, "TARJETA DEBITO -> tarjetas")
check(c6["qr"] == 3000, "QR MERCADOPAGO -> qr")
check(c6["otros_pago"] == 2000, "TRANSFERENCIA -> otros_pago")
check(c6["descuentos"] == 1000, "el descuento va al campo descuentos, no restado del producto")
check(sb6.db["ventas_backup"][0]["monto"] == 12000, "el ranking lleva el BRUTO del ítem")
check(c6["total_vendido"] == 11000, "total_vendido es el NETO cobrado (12.000 - 1.000)")
check(c6["comensales"] == 4, "comensales")

print("\n=== 7. Líneas anuladas y cortesías ===")
sb7 = FakeSB()
handlers._caja_venta({"ticket": "t7", "iso": ISO, "comensales": 1, "descuento": 0,
                      "lineas": [{"nombre": "PAPAS", "unidades": 1, "monto": 5000},
                                 {"nombre": "ANULADO", "unidades": 1, "monto": 9999, "anulada": True},
                                 {"nombre": "SHOT CORTESIA", "unidades": 2, "monto": 0}],
                      "pagos": [{"medio": "EFECTIVO", "monto": 5000}]}, sb7)
nombres = {r["nombre"] for r in sb7.db["ventas_backup"]}
check("ANULADO" not in nombres, "la línea anulada NO va al ranking")
check("SHOT CORTESIA" in nombres, "la cortesía SÍ va (consumo real)")
cort = [r for r in sb7.db["ventas_backup"] if r["nombre"] == "SHOT CORTESIA"][0]
check(cort["unidades"] == 2 and cort["monto"] == 0, "la cortesía suma unidades con monto 0")
check(sb7.db["cajas_backup"][0]["data"]["total_vendido"] == 5000, "la anulada no infla la caja")

print("\n=== 8. Validaciones (entradas inválidas no escriben) ===")
sb8 = FakeSB()
check(handlers._caja_venta({"iso": ISO, "lineas": [{"nombre": "X", "unidades": 1, "monto": 1}]}, sb8),
      "sin ticket -> error")
check(handlers._caja_venta({"ticket": "z", "iso": "08/08/2026", "lineas": [{"nombre": "X"}]}, sb8),
      "fecha no ISO -> error")
check(handlers._caja_venta({"ticket": "z", "iso": ISO, "lineas": []}, sb8), "sin líneas -> error")
check(handlers._caja_venta({"ticket": "z", "iso": ISO,
                            "lineas": [{"nombre": "", "unidades": 1, "monto": 1}]}, sb8),
      "producto sin nombre -> error")
check(handlers._caja_venta({"ticket": "z", "iso": ISO,
                            "lineas": [{"nombre": "X", "unidades": -1, "monto": 5}]}, sb8),
      "unidades negativas -> error")
check(not sb8.db.get("ventas_backup"), "ninguna de las inválidas escribió nada")

print("\n=== 9. RBAC ===")
import auth
check(auth.puede_post("cajero", "caja_venta"), "el cajero PUEDE cobrar")
check(not auth.puede_post("cajero", "backup_excluir"), "el cajero NO puede tocar la válvula")
check(auth.puede_post("admin", "backup_excluir"), "el admin sí")
check("caja_venta" in handlers.ROUTES and "backup_excluir" in handlers.ROUTES,
      "los dos endpoints están registrados en ROUTES")

print("\n" + "=" * 60)
if FALLAS:
    print("❌ %d FALLA(S):" % len(FALLAS))
    for f in FALLAS:
        print("   -", f)
    sys.exit(1)
print("✅ TODO OK")
