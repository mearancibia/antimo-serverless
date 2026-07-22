# -*- coding: utf-8 -*-
"""pour = rendimiento_ml * cxu | botella = precio entero | directo = rend*cxu o precio"""
import json,os,sys,openpyxl
sys.path.insert(0,'.'); import actualizar_antimo as M
d=json.load(open('datos_dashboard.json')); app={p['key']:p for p in d['productos']}
CB={}
wb=openpyxl.load_workbook('datos/datos_general.xlsx',data_only=True)
for r in list(wb['Costo_Base'].iter_rows(values_only=True))[1:]:
    if r[1] is not None: CB[r[1]]={'precio':r[2],'cant':r[4],'unidad':r[5],'cxu':r[6]}
if os.path.exists('datos/precios_override.json'):
    for nm,pr in json.load(open('datos/precios_override.json',encoding='utf-8')).items():
        if nm in CB and CB[nm]['cant']: CB[nm]=dict(CB[nm]);CB[nm]['precio']=pr;CB[nm]['cxu']=pr/CB[nm]['cant']
if os.path.exists('datos/insumos_extra.json'):
    for e in json.load(open('datos/insumos_extra.json',encoding='utf-8')):
        c=e.get('cant_base') or 1;p=e.get('precio')
        CB[e['nombre']]={'precio':p,'cant':c,'unidad':e.get('unidad',''),
                         'cxu':e.get('cxu') if e.get('cxu') is not None else (p/c if p and c else None)}
ok=dif=0; det=[]; rends={}
for k,p in app.items():
    if p.get('nd') or p.get('tipo') not in ('pour','botella','directo'): continue
    m=M.MAESTRO.get(k,{})
    ins=str(m.get('costeo') or '').replace('Insumo:','').strip()
    real=M.INSUMO_ALIAS.get(ins,ins)
    if real not in CB: det.append((k,'insumo no hallado: '+ins,None,None)); dif+=1; continue
    c=CB[real]; t=p['tipo']; esp=None
    if t=='botella': esp=c['precio']
    elif t=='pour': esp=(m.get('rend') or 0)*(c['cxu'] or 0); rends[k]=(m.get('rend'),real,c['cant'])
    elif t=='directo': esp=(m.get('rend')*c['cxu']) if m.get('rend') else c['precio']
    if esp is None: det.append((k,'no calculable',None,None)); dif+=1; continue
    if abs(esp-p['costo'])>max(0.15,abs(p['costo'])*1e-4):
        dif+=1; det.append((k,'',p['costo'],esp))
    else: ok+=1
print(f"pour/botella/directo que COINCIDEN: {ok}")
print(f"que DIFIEREN:                      {dif}")
for k,msg,a,b in det[:10]: print(f"    {k[:34]:34} {msg} app={a} recalc={b}")
print()
print("=== control de sensatez: un pour no puede rendir mas que la botella ===")
raros=[(k,r,ins,cb) for k,(r,ins,cb) in rends.items() if r and cb and r>cb]
print(f"  pours con rendimiento > contenido del envase: {len(raros)}")
for x in raros[:5]: print("   ",x)
print()
print("=== control: costo > precio de venta promedio (vende a perdida) ===")
perd=[]
for k,p in app.items():
    if p.get('nd'): continue
    u=sum(x[0] for x in p['byday'].values()); mm=sum(x[1] for x in p['byday'].values())
    if u and mm:
        pv=mm/u
        if p['costo']>pv: perd.append((p['pos'],round(p['costo']),round(pv),u))
for x in sorted(perd,key=lambda y:-(y[1]-y[2]))[:8]:
    print(f"    {x[0][:34]:34} costo=${x[1]:>8,} venta=${x[2]:>8,}  {x[3]}u")
print(f"  total que venden bajo costo: {len(perd)}")
