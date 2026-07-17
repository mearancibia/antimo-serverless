#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Conector Bistrosoft -> arma rankings (por mes) + cajas (por NOCHE) que consume el motor ANTIMO.
Config en datos/bistro_config.json: {base,username,password,shopCode}. NUNCA hardcodear credenciales.
Uso:  python3 conector_bistrosoft.py                 (por defecto: del 1 del mes pasado hasta manana)
      python3 conector_bistrosoft.py 2026-06-01 2026-06-30
      python3 conector_bistrosoft.py --mock           (autotest sin API)"""
import json, os, sys, datetime, re, collections
BASE=os.path.dirname(os.path.abspath(__file__)); DATOS=os.path.join(BASE,"datos"); ENTRADA=os.path.join(BASE,"entrada")

def get_token(base,user,pw):
    import requests
    r=requests.post(base.rstrip("/")+"/api/v1/Token",json={"username":user,"password":pw},timeout=30)
    r.raise_for_status(); return r.json()["token"]

def fetch_all(base,token,shop,start,end):
    import requests
    items=[]; page=0; hdr={"Authorization":"Bearer "+token}
    while True:
        params={"startDate":start,"endDate":end,"shopCode":shop,"pageNumber":page}
        r=requests.get(base.rstrip("/")+"/api/v1/TransactionDetailReport",headers=hdr,params=params,timeout=60)
        if r.status_code==401: raise RuntimeError("Token vencido/invalido")
        r.raise_for_status(); batch=r.json().get("items",[])
        if not batch: break
        items+=batch; page+=1
        if page>5000: break
    return items

def clean_product(p):
    p=(p or "").strip()
    p=re.sub(r"^[A-Za-z] - ","",p)   # quita prefijo tipo "E - " si existe (CONFIRMAR con datos reales)
    return p

def business_ddmm_ym(it):
    """Fecha de la NOCHE de caja, rotulada por la fecha de cierre (como el POS). Corte 08:00:
    lo que pasa entre 00:00 y 07:59 cuenta para la noche que cerro esa madrugada."""
    ts=it.get("timestamp")
    try:
        dt=datetime.datetime.fromisoformat(str(ts))
        bd=dt.date() if dt.hour<8 else dt.date()+datetime.timedelta(days=1)
        return bd.strftime("%d-%m"), bd.strftime("%Y-%m")
    except Exception:
        pp=str(it.get("date") or "").split("-")
        if len(pp)<3: return None,None
        try:
            bd=datetime.date(int(pp[2]),int(pp[1]),int(pp[0]))
            return bd.strftime("%d-%m"), bd.strftime("%Y-%m")
        except Exception: return None,None

def _nuevo_dia():
    return {"total_vendido":0.0,"efectivo":0.0,"tarjetas":0.0,"qr":0.0,"otros_pago":0.0,
            "comensales":0,"descuentos":0.0,"retiros":0.0,"depositos":0.0,"detalle_retiros":[],"detalle_descuentos":[]}

def parse_items(items):
    """ranking_por_mes {'YYYY-MM': {(ddmm,prod):[q,amt]}} y cajas[] por NOCHE.
    Comandas anuladas (status VOID): Bistrosoft ya manda la comanda original y su reversa
    (misma comanda y sus '- ITEM', ambas con signo opuesto), asi que sumarlas da neto $0 -
    verificado sobre datos reales. Igual se excluyen por ticketNumber en vez de confiar en esa
    cancelacion implicita: si se corre el conector a mitad de un turno, la reversa de una
    anulacion reciente puede no haber llegado todavia y quedaria plata de mas contada un rato."""
    anuladas={it.get("ticketNumber") for it in items
              if (it.get("transactionType") or "").startswith("Comanda") and it.get("status")=="VOID"}
    if anuladas:
        antes=len(items)
        items=[it for it in items if it.get("ticketNumber") not in anuladas]
        print(f"Anulaciones: {len(anuladas)} comandas excluidas ({antes-len(items)} transacciones).")
    rank=collections.defaultdict(lambda: collections.defaultdict(lambda:[0.0,0.0]))
    dias={}
    for it in items:
        tt=(it.get("transactionType") or "").strip()
        ddmm,ym=business_ddmm_ym(it)
        if ddmm is None: continue
        amt=float(it.get("amount") or 0)
        if tt in ("- ITEM","- COMBO"):
            prod=clean_product(it.get("product"))
            if not prod or prod=="-": continue
            cell=rank[ym][(ddmm,prod)]; cell[0]+=float(it.get("quantity") or 0); cell[1]+=amt
            continue
        v=dias.setdefault(ddmm,_nuevo_dia())
        if tt=="- ITEM DESCUENTO":
            v["descuentos"]+=amt
            v["detalle_descuentos"].append({"concepto":(it.get("comments") or "").strip()[:50],
                "monto":amt,"user":it.get("user") or "","hora":it.get("hour") or ""})
        elif tt.startswith("Comanda"):
            v["total_vendido"]+=amt
            pm=(it.get("paymentMethod") or "").upper()
            if "EFECT" in pm: v["efectivo"]+=amt
            elif "TARJ" in pm: v["tarjetas"]+=amt
            elif "QR" in pm: v["qr"]+=amt
            else: v["otros_pago"]+=amt
            if tt=="Comanda":
                try: v["comensales"]+=int(float(it.get("dinnersQty") or 0))
                except: pass
        elif tt=="CAJA (RETIRO)":
            v["retiros"]+=amt
            v["detalle_retiros"].append({"concepto":(it.get("comments") or "").strip()[:60],
                "monto":amt,"user":it.get("user") or "","hora":it.get("hour") or ""})
        elif tt=="CAJA (DEPOSITO)":
            v["depositos"]+=amt
        # CIERRE / APERTURA / AJUSTE de caja: se ignoran
    cajas=[]
    for f,v in sorted(dias.items()):
        if v["total_vendido"]==0 and v["retiros"]==0 and v["depositos"]==0: continue
        v["fecha"]=f; v["fecha_dia"]=f; v["archivo"]="Bistrosoft API"; v["fecha_key"]=f; cajas.append(v)
    return rank, cajas

def write_outputs(rank, cajas, entrada=None, datos=None):
    """Escribe rankings + cajas. entrada/datos se pueden redirigir: el autotest --mock NO debe
    tocar los datos reales (sus ventas inventadas pisarian el ranking del mes en curso)."""
    import openpyxl
    entrada=entrada or ENTRADA; datos=datos or DATOS
    written=[]
    for ym, cells in rank.items():
        wb=openpyxl.Workbook(); ws=wb.active; ws.title="Ranking de Ventas"
        ws.append(["RANKING DE VENTAS DIARIO"])
        ws.append(["Fecha","Nombre","Sku","Stock","Vendidos","Consumidos","Monto","Categoria"])
        for (ddmm,prod),(q,amt) in cells.items():
            ws.append([ddmm,prod,"",0,int(round(q)),int(round(q)),round(amt),""])
        fn=os.path.join(entrada,f"api_ventas_{ym}.xlsx"); wb.save(fn); written.append(os.path.basename(fn))
    json.dump(cajas,open(os.path.join(datos,"cajas_api.json"),"w"),ensure_ascii=False,indent=1)
    return written

def write_debug(items):
    cnt=collections.Counter((it.get("transactionType") or "") for it in items)
    fechas=sorted({(business_ddmm_ym(it)[0]) for it in items if business_ddmm_ym(it)[0]})
    samples={}
    for it in items:
        tt=it.get("transactionType") or ""
        if tt not in samples: samples[tt]=it
    json.dump({"total_items":len(items),"tipos":dict(cnt),"noches":fechas,
               "ejemplo_por_tipo":samples},
              open(os.path.join(DATOS,"bistro_debug.json"),"w"),ensure_ascii=False,indent=1)
    print("Diagnostico -> datos/bistro_debug.json | noches:",fechas)

def default_range():
    today=datetime.date.today()
    first_prev=(today.replace(day=1)-datetime.timedelta(days=1)).replace(day=1)
    end=today+datetime.timedelta(days=1)
    return first_prev.isoformat(), end.isoformat()

def run(start,end):
    cfg=json.load(open(os.path.join(DATOS,"bistro_config.json"),encoding="utf-8"))
    print(f"Conectando a Bistrosoft ({start} a {end})...")
    tok=get_token(cfg["base"],cfg["username"],cfg["password"])
    items=fetch_all(cfg["base"],tok,cfg["shopCode"],start,end)
    write_debug(items)
    rank,cajas=parse_items(items)
    written=write_outputs(rank,cajas)
    print(f"OK: {len(items)} transacciones -> rankings: {written} | {len(cajas)} noches de caja")

def mock():
    items=[
     {"transactionType":"- ITEM","product":"FERNET","date":"11-07-2026","timestamp":"2026-07-11T22:52:00","quantity":3,"amount":30000,"ticketNumber":1},
     {"transactionType":"Comanda","date":"11-07-2026","timestamp":"2026-07-11T22:52:00","amount":30000,"paymentMethod":"TARJETA","dinnersQty":"2","ticketNumber":1},
     {"transactionType":"- ITEM","product":"COCA","date":"12-07-2026","timestamp":"2026-07-12T02:10:00","quantity":5,"amount":17500,"ticketNumber":2},
     {"transactionType":"Comanda","date":"12-07-2026","timestamp":"2026-07-12T02:10:00","amount":17500,"paymentMethod":"EFECTIVO","dinnersQty":"3","ticketNumber":2},
     {"transactionType":"CAJA (RETIRO)","date":"12-07-2026","timestamp":"2026-07-12T05:09:00","amount":-100000,"comments":"PAGO A PROVEEDORES - dj"},
     {"transactionType":"CAJA (CIERRE DE CAJA)","date":"12-07-2026","timestamp":"2026-07-12T05:10:00","amount":45000,"comments":"CIERRE"},
     # comanda anulada: Bistrosoft manda el original + su reversa, ambas status VOID -> deben desaparecer del todo
     {"transactionType":"- ITEM","product":"CAMPARI","date":"12-07-2026","timestamp":"2026-07-12T03:00:00","quantity":1,"amount":9000,"ticketNumber":9,"status":"VOID"},
     {"transactionType":"Comanda","date":"12-07-2026","timestamp":"2026-07-12T03:00:00","amount":9000,"paymentMethod":"EFECTIVO","status":"VOID","ticketNumber":9},
     {"transactionType":"- ITEM","product":"CAMPARI","date":"12-07-2026","timestamp":"2026-07-12T03:05:00","quantity":-1,"amount":-9000,"ticketNumber":9,"status":"VOID"},
     {"transactionType":"Comanda","date":"12-07-2026","timestamp":"2026-07-12T03:05:00","amount":-9000,"paymentMethod":"EFECTIVO","status":"VOID","ticketNumber":9},
    ]
    rank,cajas=parse_items(items)
    import tempfile
    tmp=tempfile.mkdtemp(prefix="antimo_mock_")   # sandbox: nunca las carpetas reales
    print("MOCK -> archivos:",write_outputs(rank,cajas,entrada=tmp,datos=tmp),"en",tmp)
    print("caja (todo debe caer en la noche 12-07, SIN el ticket 9 anulado):")
    for x in cajas: print("  ",{k:x[k] for k in ("fecha","total_vendido","efectivo","tarjetas","comensales","retiros")})
    campari=any(prod=="CAMPARI" for _,prod in (k for cells in rank.values() for k in cells))
    print("CAMPARI (anulado) aparece en el ranking?",campari,"(debe ser False)")

if __name__=="__main__":
    if len(sys.argv)>1 and sys.argv[1]=="--mock": mock()
    elif len(sys.argv)>=3: run(sys.argv[1],sys.argv[2])
    else:
        s,e=default_range(); run(s,e)
