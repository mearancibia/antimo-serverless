#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tests del relay de impresión: autenticación por token y encolado. Sin red ni Supabase.
Correr: python3 scripts/test_relay.py
"""
import os, sys, base64

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import auth, handlers
from test_caja_backup import FakeSB

FALLAS = []


def check(cond, msg):
    print(("  ok   " if cond else "  FALLA ") + msg)
    if not cond:
        FALLAS.append(msg)


class H(dict):
    """Headers falsos (case-insensitive como los de verdad no hace falta acá)."""
    def get(self, k, d=None):
        return dict.get(self, k, d)


print("\n=== 1. Falla CERRADA: sin token configurado, nadie entra ===")
os.environ.pop("PRINT_RELAY_TOKEN", None)
check(not auth.relay_autorizado(H({"Authorization": "Bearer loquesea"})),
      "sin PRINT_RELAY_TOKEN -> rechaza aunque manden un Bearer")
check(not auth.relay_autorizado(H({})), "sin PRINT_RELAY_TOKEN y sin header -> rechaza")

print("\n=== 2. Con token configurado ===")
os.environ["PRINT_RELAY_TOKEN"] = "s3cr3t0-del-relay"
check(auth.relay_autorizado(H({"Authorization": "Bearer s3cr3t0-del-relay"})), "token correcto -> pasa")
check(auth.relay_autorizado(H({"Authorization": "Bearer  s3cr3t0-del-relay  "})),
      "tolera espacios alrededor del token")
check(not auth.relay_autorizado(H({"Authorization": "Bearer otro"})), "token incorrecto -> rechaza")
check(not auth.relay_autorizado(H({"Authorization": "s3cr3t0-del-relay"})),
      "sin el prefijo Bearer -> rechaza")
check(not auth.relay_autorizado(H({})), "sin header -> rechaza")
check(not auth.relay_autorizado(H({"Authorization": "Bearer "})), "Bearer vacío -> rechaza")
check(not auth.relay_autorizado(H({"Authorization": "Bearer s3cr3t0-del-rela"})),
      "un token que es prefijo del bueno -> rechaza")

print("\n=== 3. El token del relay NO abre nada más ===")
# El relay se autentica aparte; no es un usuario y no debe tener rol ni permisos de la app.
check(not auth.puede_post("cajero", "print_pend"), "print_pend no está entre los POST del cajero")
check("print_pend" not in handlers.ROUTES and "print_ok" not in handlers.ROUTES,
      "los endpoints del relay NO están en ROUTES (no pasan por el flujo de edición)")

print("\n=== 4. Encolado al cobrar ===")
sb = FakeSB()
BYTES = base64.b64encode(b"\x1b@hola").decode()
handlers._caja_venta({"ticket": "t1", "iso": "2026-08-09",
                      "lineas": [{"nombre": "FERNET", "unidades": 1, "monto": 10000}],
                      "pagos": [{"medio": "EFECTIVO", "monto": 10000}],
                      "escpos": BYTES}, sb)
cola = sb.db.get("cola_impresion", [])
check(len(cola) == 1, "se encoló el ticket")
check(cola and cola[0]["escpos"] == BYTES, "los bytes llegan intactos")
check(cola and cola[0]["estado"] == "pendiente", "queda pendiente")
check(cola and cola[0]["iso"] == "2026-08-09", "con la noche correcta")

print("\n=== 5. Sin modo relay NO se encola ===")
sb2 = FakeSB()
handlers._caja_venta({"ticket": "t2", "iso": "2026-08-09",
                      "lineas": [{"nombre": "FERNET", "unidades": 1, "monto": 10000}],
                      "pagos": [{"medio": "EFECTIVO", "monto": 10000}]}, sb2)
check(not sb2.db.get("cola_impresion"), "sin `escpos`, la cola queda vacía")
check(len(sb2.db["ventas_backup"]) == 1, "pero la venta sí se guardó")

print("\n=== 6. Reenviar el mismo ticket no duplica la cola ===")
handlers._caja_venta({"ticket": "t1", "iso": "2026-08-09",
                      "lineas": [{"nombre": "FERNET", "unidades": 1, "monto": 10000}],
                      "pagos": [{"medio": "EFECTIVO", "monto": 10000}],
                      "escpos": BYTES}, sb)
check(len(sb.db["cola_impresion"]) == 1, "sigue habiendo 1 sola fila (upsert por ticket)")

print("\n=== 7. Si encolar falla, el cobro NO se cae ===")
class SBRoto(FakeSB):
    def table(self, name):
        if name == "cola_impresion":
            raise RuntimeError("Supabase caído")
        return FakeSB.table(self, name)

sb3 = SBRoto()
err = handlers._caja_venta({"ticket": "t3", "iso": "2026-08-09",
                            "lineas": [{"nombre": "FERNET", "unidades": 1, "monto": 10000}],
                            "pagos": [{"medio": "EFECTIVO", "monto": 10000}],
                            "escpos": BYTES}, sb3)
check(err is None, "el cobro devuelve OK aunque la cola de impresión explote")
check(len(sb3.db["ventas_backup"]) == 1, "y la venta quedó guardada igual")

print("\n=== 8. Prueba de impresión (sin cobrar) ===")
sb4 = FakeSB()
check(handlers._print_test({}, sb4) is not None, "sin bytes -> error")
handlers._print_test({"escpos": BYTES}, sb4)
t = sb4.db.get("cola_impresion", [])
check(len(t) == 1 and t[0]["ticket"].startswith("test-"), "encola una prueba con id 'test-...'")
check("print_test" in handlers.SIN_RECOMPUTE, "no dispara un recálculo del motor")
check(auth.puede_post("cajero", "print_test"), "el cajero puede probar la impresora")

print("\n" + "=" * 60)
if FALLAS:
    print("❌ %d FALLA(S):" % len(FALLAS))
    for f in FALLAS:
        print("   -", f)
    sys.exit(1)
print("✅ TODO OK")
