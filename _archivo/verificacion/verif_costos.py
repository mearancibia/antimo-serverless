# -*- coding: utf-8 -*-
"""Recalcula el costo de cada producto DESDE EL EXCEL, sin usar el motor, y compara.
Reimplementa la conversion de unidades a proposito: si copiara las funciones del motor,
un error del motor se replicaria y ambos coincidirian estando mal."""
import json, re, openpyxl, sys
sys.path.insert(0,'.')
import actualizar_antimo as M   # solo para leer ALIAS/EQUI/etc, NO para costear

d=json.load(open('datos_dashboard.json'))
app={p['key']:p for p in d['productos']}

wb=openpyxl.load_workbook('datos/datos_general.xlsx',data_only=True)
# --- Costo_Base leido de cero ---
CB={}
for r in list(wb['Costo_Base'].iter_rows(values_only=True))[1:]:
    if r[1] is None: continue
    CB[r[1]]={'precio':r[2],'cant':r[4],'unidad':r[5],'cxu':r[6]}
# overrides de precio
import os
if os.path.exists('datos/precios_override.json'):
    for nm,pr in json.load(open('datos/precios_override.json',encoding='utf-8')).items():
        if nm in CB and CB[nm]['cant']:
            CB[nm]=dict(CB[nm]); CB[nm]['precio']=pr; CB[nm]['cxu']=pr/CB[nm]['cant']
if os.path.exists('datos/insumos_extra.json'):
    for e in json.load(open('datos/insumos_extra.json',encoding='utf-8')):
        c=e.get('cant_base') or 1; p=e.get('precio')
        CB[e['nombre']]={'precio':p,'cant':c,'unidad':e.get('unidad',''),
                         'cxu':e.get('cxu') if e.get('cxu') is not None else (p/c if p and c else None)}

# --- verificacion 1: cxu = precio / cant_base ---
malcxu=[]
for nm,c in CB.items():
    if c['precio'] is None or not c['cant'] or c['cxu'] is None: continue
    esp=c['precio']/c['cant']
    if abs(esp-c['cxu'])>max(0.01,abs(esp)*1e-6): malcxu.append((nm,c['precio'],c['cant'],c['cxu'],esp))

# --- conversion de cantidades, reimplementada ---
EQ={'cucharada':(12,'g'),'bocha':(60,'g'),'hoja':(0.5,'g'),'gajo':(15,'g'),'rodaja':(12,'g'),
    'medida':(60,'ml'),'trago':(60,'ml'),'shot':(45,'ml'),'lata red bull':(250,'ml'),
    'lata speed':(473,'ml'),'poron':(330,'ml'),'a gusto':(15,'g'),'aceituna':(5,'g')}
def qty(q):
    if q is None: return None
    s=str(q).strip().lower()
    for pat,u in [(r'^([\d.,]+)\s*(?:ml|cc)\b','ml'),(r'^([\d.,]+)\s*(?:g|gr|gramos)\b','g'),
                  (r'^([\d.,]+)\s*unidad','u')]:
        m=re.match(pat,s)
        if m: return (float(m.group(1).replace(',','.')),u)
    m=re.match(r'^([\d.,]+)\s*lata',s)
    if m: return ('LATA',float(m.group(1).replace(',','.')))
    for k,(v,ub) in EQ.items():
        if k in s:
            m2=re.match(r'^([\d.,]+)',s); n=float(m2.group(1).replace(',','.')) if m2 else 1.0
            return (n*v,ub)
    m=re.match(r'^([\d.,]+)$',s)
    if m: return (float(m.group(1).replace(',','.')),'u')
    return None
def costo_ing(ing,q):
    ing=str(ing).strip()
    if ing in M.FALTANTES: return None
    ins=M.ALIAS.get(ing) or (ing if ing in CB else None)
    if ins is None or ins not in CB: return None
    p=qty(q)
    if p is None: return None
    c=CB[ins]
    if c['cxu'] is None: return None
    if p[0]=='LATA': return p[1]*c['cant']*c['cxu']
    val,ub=p
    if ub=='u':
        if c['unidad']=='u': return val*c['cxu']
        if ins in M.UNIDAD_G: return val*M.UNIDAD_G[ins]*c['cxu']
        if ins in M.UNIT_TO_G: return val*M.UNIT_TO_G[ins]*c['cxu']
        return None
    if c['unidad']=='u':
        if ins in M.PIECE_G: return val/M.PIECE_G[ins]*c['cxu']
        return None
    return val*c['cxu']

# --- recetas desde el Excel + overrides ---
REC={}
for sh,i0,nc in [('Recetas Bebidas',1,0),('Recetas Comida',2,1)]:
    for r in list(wb[sh].iter_rows(values_only=True))[1:]:
        cells=list(r); nm=cells[nc]
        if not nm: continue
        ings=[]
        for j in range(i0,len(cells)-1,2):
            if cells[j] and str(cells[j]).strip(): ings.append((str(cells[j]).strip(),cells[j+1]))
        REC[M.norm(nm)]=ings
if os.path.exists('datos/recetas_extra.json'):
    for nm,ings in json.load(open('datos/recetas_extra.json',encoding='utf-8')).items():
        REC[M.norm(nm)]=[(i[0],i[1]) for i in ings]

# --- comparar ---
oks=difs=nover=0; detalle=[]
for k,p in app.items():
    if p.get('nd'): continue
    t=p.get('tipo')
    mine=None
    if t in ('receta','promo_2x1'):
        rn=M.norm(str(p.get('receta_nombre') or ''))
        if rn in REC:
            tot=0.0; fallo=False
            for ing,q in REC[rn]:
                c=costo_ing(ing,q)
                if c is None: fallo=True; break
                tot+=c
            if not fallo:
                fac=M.MAESTRO.get(k,{}).get('factor') or 1
                mine=tot*fac
    elif t=='combo':
        comp=p.get('combo_comp') or []
        tot=0.0; fallo=False
        for ins,cant,u in comp:
            if ins not in CB or CB[ins]['cxu'] is None: fallo=True; break
            tot += cant*CB[ins]['cxu'] if u=='ml' else cant*CB[ins]['cant']*CB[ins]['cxu']
        if not fallo: mine=tot
    if mine is None: nover+=1; continue
    dif=abs(mine-p['costo'])
    if dif>max(0.15,abs(p['costo'])*1e-4):
        difs+=1; detalle.append((k,p['costo'],mine,dif))
    else: oks+=1

print(f"cxu incoherente (precio/cant_base): {len(malcxu)}")
for x in malcxu[:5]: print("   ",x)
print(f"costos recalculados que COINCIDEN: {oks}")
print(f"costos que DIFIEREN:               {difs}")
for k,a,b,dd in sorted(detalle,key=lambda x:-x[3])[:10]:
    print(f"    {k[:38]:38} app={a:>10.2f}  recalc={b:>10.2f}  dif={dd:>9.2f}")
print(f"no verificables por esta via (pour/botella/directo): {nover}")
