# -*- coding: utf-8 -*-
"""ANTIMO — motor de costeo PURO (sin I/O). `compute(src) -> DATA`.

Refactor de `actualizar_antimo.py` para que corra igual en local (Excel + archivos) o en
serverless (Supabase): toda la lógica de costeo vive acá, y las FUENTES de datos llegan ya
parseadas en `src` (ver sources.py para las dos implementaciones — LocalSource / SupabaseSource).

Los diccionarios grandes (ALIAS, EQUI, UNIFICAR, COMBOS por defecto, INSUMO_ALIAS, PIECE_G,
UNIDAD_G, PRECIO_LISTA_ALIAS, FALTANTES, FOOD_CATS, DOW) son **lógica de negocio**, no datos del
usuario: se quedan como código, igual que estaban en el motor original.

`src` es un dict con estas claves (todo ya parseado a estructuras Python):
  costo_base:  {nombre: {precio,pres,cant_base,unidad,cxu}}
  cb_cat:      {nombre: categoria_de_insumo}
  precio_lista:{norm(nombre): precio}      # hoja "Lista de Precios" (ya normalizada)
  recetas:     {norm(nombre): [(ing, qty), ...]}   # Recetas Bebidas + Comida
  maestro:     {norm(pos): {cat,canon,tipo,factor,rend,costeo,nota}}
  ventas:      [{nombre, fecha("DD-MM"), iso("YYYY-MM-DD" o ""), unidades, monto}]
  cajas:       [ ... cajas_api.json ... ]
  opex_json:   contenido de opex.json (lista de vigencias o lista plana) o None
  opex_base:   [{cat,item,cantidad,unitario,monto}]  # hoja OPEX del Excel, para sembrar
  opex_cero_confirmado: set/list de items confirmados en $0
  overrides:   maestro_extra(list), pours_extra(dict), recetas_extra(dict), insumos_extra(list),
               precios_override(dict), combos_extra(dict), precio_lista_override(dict),
               sospechosos(dict), dias_cerrados(dict), stock(dict)
  logo:        data-URI del logo (o "")

Devuelve el mismo objeto DATA que producía actualizar_antimo.py, y además `opex_seed`: si
`opex_json` venía vacío, acá se calcula la siembra inicial para que el caller la persista
(en local iba a opex.json; en Supabase va a la tabla opex).
"""
import re, datetime, math
import unicodedata as _ud


# ---------------------------------------------------------------- helpers de texto/números
def norm(s):
    return " ".join(str(s).strip().upper().split()) if s is not None else ""


def _aplanar(s):
    s = _ud.normalize("NFD", str(s).upper())
    s = "".join(c for c in s if _ud.category(c) != "Mn")   # saca tildes/diéresis
    return re.sub(r"[^A-Z0-9]", "", s)


# ---------------------------------------------------------------- tablas de negocio (CÓDIGO)
EQUI = {"cucharada": (12, "g"), "bocha": (60, "g"), "hoja": (0.5, "g"), "gajo": (15, "g"),
        "rodaja": (12, "g"), "medida": (60, "ml"), "trago": (60, "ml"), "shot": (45, "ml"),
        "lata red bull": (250, "ml"), "lata speed": (473, "ml"), "poron": (330, "ml"),
        "a gusto": (15, "g"), "aceituna": (5, "g")}

ALIAS = {
 "Fernet Branca": "Fernet Branca", "Arroz para Sushi": "Arroz base para Sushi", "Salmón Fresco": "Proteína para Poke Bowl Salmón", "Queso Crema": "Queso Crema con hierbas", "Alga Nori": "Alga Nori", "Coca Cola (Insumo Barra)": "Coca Cola / Coca Zero",
 "Hielo": "Hielo / Hielo Picado", "Hielo picado": "Hielo / Hielo Picado",
 "Gin (Brighton/Beefeater)": "Gin Brighton", "Gin": "Gin Brighton", "Agua Tónica": "Agua Tónica",
 "Rodaja de Limón": "Limas y Limones (Gajos/Rodajas/Jugos)", "Ron Blanco": "Ron Blanco",
 "Soda o Sprite": "Sprite 3L", "Sprite": "Sprite 3L", "Soda": "Soda fresca", "Soda fresca": "Soda fresca",
 "Hojas de Menta": "Menta fresca (Hojas)", "Hojas de Menta fresca": "Menta fresca (Hojas)",
 "Lima en gajos": "Limas y Limones (Gajos/Rodajas/Jugos)", "Limas en gajos": "Limas y Limones (Gajos/Rodajas/Jugos)",
 "Jugo de Lima": "Limas y Limones (Gajos/Rodajas/Jugos)", "Jugo de Limón": "Limas y Limones (Gajos/Rodajas/Jugos)",
 "Azúcar": "Azúcar (Blanca/Almíbar simple)", "Azúcar blanca": "Azúcar (Blanca/Almíbar simple)",
 "Almíbar simple": "Azúcar (Blanca/Almíbar simple)", "Ron Malibu": "Ron Malibu",
 "Whisky": "Whisky Ballantines", "Whisky Red Label": "Whisky Ballantines",
 "Almíbar de Miel": "Almíbar de Miel / Jengibre", "Almíbar de Jengibre": "Almíbar de Miel / Jengibre",
 "Cerveza Corona (Porón)": "Cerveza Corona Porroncito 330ml", "Tequila": "Tequila", "Triple Sec": "Triple Sec",
 "Blue Curaçao": "Blue Curaçao", "Vodka Smirnoff": "Vodka Smirnoff", "Vodka": "Vodka Smirnoff",
 "Vodka Absolut": "Vodka Absolut", "Energizante Speed": "Energizante Speed",
 "Energizante (Speed/Red Bull)": "Energizante Speed", "Pulpa de Fruta": "Pulpa / Fruta para Daikiri",
 "Aperol": "Aperol", "Espumante (Champagne)": "Espumante / Champagne Chandon",
 "Rodaja de Naranja": "Limas y Limones (Gajos/Rodajas/Jugos)", "Cerveza de Jengibre": "Cerveza de Jengibre (Ginger Beer)",
 "Baileys": "Baileys", "Helado de crema americana": "Helado (Crema Americana)", "Campari": "Campari",
 "Vermouth Rosso": "Vermouth Rosso Cinzano", "Vermouth Rosso (Cinzano/Carpano)": "Vermouth Rosso Cinzano",
 "Cachaça": "Cachaça", "Cynar": "Cynar", "Jugo de Pomelo": "Jugo de Pomelo", "Jugo de Naranja o Tónica": "Jugo de Naranja fresco",
 "Lechuga Romana": "Lechuga (Romana/Capuchina)", "Lechuga Capuchina picada": "Lechuga (Romana/Capuchina)",
 "Pechuga de Pollo Grillé": "Pechuga de Pollo (Grillé/Crispy)", "Pechuga de Pollo Crispy Frito": "Pechuga de Pollo (Grillé/Crispy)",
 "Crotones de Pan": "Crotones de Pan", "Queso Parmesano en Hebras": "Queso Parmesano (Hebras/Escamas)",
 "Queso Parmesano rallado": "Queso Parmesano (Hebras/Escamas)", "Queso Parmesano en escamas": "Queso Parmesano (Hebras/Escamas)",
 "Aderezo César": "Aderezo César", "Arroz base para Sushi": "Arroz base para Sushi",
 "Proteína (Salmón/Pollo)": "Proteína para Poke Bowl Salmón", "Palta fresca": "Palta fresca",
 "Pepino japonés": "Pepino (Japonés/Pepinillos en Vinagre)", "Pepinillos en vinagre": "Pepino (Japonés/Pepinillos en Vinagre)",
 "Semillas de Sésamo": "Semillas de Sésamo", "Salsa de Soja / Teriyaki": "Salsa de Soja / Teriyaki",
 "Pan Baguette Rústico": "Pan Baguette Rústico", "Lomito Vacuno o Pechuga": "Lomito Vacuno",
 "Queso Danbo / Muzarella": "Queso Danbo", "Tomate en rodajas": "Tomate redondo",
 "Mayonesa clásica": "Mayonesa clásica / Mayonesa base Coleslaw", "Mayonesa base Coleslaw": "Mayonesa clásica / Mayonesa base Coleslaw",
 "Mayonesa / Aderezo": "Mayonesa clásica / Mayonesa base Coleslaw", "Medallón de Carne Vacuna": "Medallón de Carne Vacuna (Hamburguesas)",
 "Medallón de Carne Vacuna 1": "Medallón de Carne Vacuna (Hamburguesas)", "Medallón de Carne Vacuna 2": "Medallón de Carne Vacuna (Hamburguesas)",
 "Pan con Sésamo": "Pan de Hamburguesa (Sésamo/Brioche/Clásico)", "Pan Brioche de Hamburguesa": "Pan de Hamburguesa (Sésamo/Brioche/Clásico)",
 "Pan Brioche": "Pan de Hamburguesa (Sésamo/Brioche/Clásico)", "Pan de Hamburguesa Clásico": "Pan de Hamburguesa (Sésamo/Brioche/Clásico)",
 "Queso Cheddar en Fetas": "Queso Cheddar (Fetas/Salsa Fundida)", "Salsa Cheddar fundido": "Queso Cheddar (Fetas/Salsa Fundida)",
 "Salsa Cheddar Fundido": "Queso Cheddar (Fetas/Salsa Fundida)", "Panceta Ahumada crocante": "Panceta Ahumada",
 "Panceta Ahumada picada": "Panceta Ahumada", "Panceta picada crocante": "Panceta Ahumada", "Panceta Ahumada": "Panceta Ahumada",
 "Huevo frito": "Huevo fresco", "Huevo fresco": "Huevo fresco", "Cebolla blanca picada": "Cebolla blanca",
 "Cebolla Blanca en juliana": "Cebolla blanca", "Ketchup": "Ketchup", "Mostaza": "Mostaza",
 "Carne Desmechada (Tapa/Bondiola)": "Carne Desmechada (Tapa de asado/Bondiola)", "Pan Ciabatta o Flat": "Pan Ciabatta / Flat / Francés",
 "Pan Francés rústico": "Pan Ciabatta / Flat / Francés", "Queso Muzarella fundido": "Queso Muzarella (Barra/Premium)",
 "Queso Muzarella": "Queso Muzarella (Barra/Premium)", "Queso Muzarella Premium": "Queso Muzarella (Barra/Premium)",
 "Queso Muzarella en cubos": "Queso Muzarella (Barra/Premium)", "Cebolla Caramelizada": "Cebolla Caramelizada",
 "Salsa Especial Park": "Salsa Especial Park", "Tapa de Asado Horneada": "Tapa de Asado", "Queso Provoleta fundido": "Queso Provoleta",
 "Chimichurri artesanal": "Chimichurri artesanal", "Papas Bastón Prefritas": "Papas Fritas (Bastón/Rústicas Prefritas)",
 "Papas Fritas Rústicas": "Papas Fritas (Bastón/Rústicas Prefritas)", "Papas Fritas Bastón": "Papas Fritas (Bastón/Rústicas Prefritas)",
 "Ragú de Carne estofada": "Ragú de Carne Estofada", "Estofado / Ragú de Carne": "Ragú de Carne Estofada",
 "Aceite de Girasol (absorción)": "Aceite de Girasol (Freír)", "Aceite de Girasol (freír)": "Aceite de Girasol (Freír)",
 "Masa de Pizza (bollo)": "Masa de Pizza (Bollos de media masa)", "Salsa de Tomate base": "Tomate redondo",
 "Orégano seco": "Orégano seco", "Aceitunas Verdes": "Aceitunas (Verdes/Negras)", "Aceitunas Verdes y Negras": "Aceitunas (Verdes/Negras)",
 "Aceite de Oliva": "Aceite de Oliva (Común/Extra Virgen)", "Aceite de Oliva Extra Virgen": "Aceite de Oliva (Común/Extra Virgen)",
 "Jamón Cocido en fetas": "Jamón Cocido", "Jamón Cocido feteado": "Jamón Cocido", "Morrones en tiras": "Morrón Rojo",
 "Morrón rojo asado": "Morrón Rojo", "Hojas de Albahaca Fresca": "Hojas de Albahaca Fresca", "Hojas de Rúcula Fresca": "Hojas de Rúcula Fresca",
 "Jamón Crudo en fetas": "Jamón Crudo", "Jamón Crudo feteado": "Jamón Crudo", "Cuadrado de Brownie": "Cuadrado de Brownie Chocolate",
 "Bocha de Helado Americana": "Helado (Crema Americana)", "Salsa de Chocolate cobertura": "Salsa de Chocolate cobertura",
 "Nueces picadas": "Nueces picadas", "Pan Integral / Sin TACC": "Pan Integral / Sin TACC", "Zucchini asado": "Zucchini",
 "Berenjena asada": "Berenjena", "Hummus (garbanzos)": "Hummus (Garbanzos)", "Queso Cream con hierbas": "Queso Crema con hierbas",
 "Sal Fina": "Sal Fina", "Sal fina": "Sal Fina", "Salsa Barbacoa": "Salsa Barbacoa", "Cebolla de Verdeo picada": "Cebolla de Verdeo",
 "Zanahoria rallada": "Zanahoria", "Nuggets de Pollo": "Nuggets de Pollo", "Repollo blanco y morado": "Repollo (Blanco/Morado)",
 "Maní Salado": "Maní Salado", "Queso Pategrás": "Queso Pategrás", "Salame tipo Milán": "Salame tipo Milán",
 "Queso Azul": "Queso Azul", "Panera (Pancitos variados)": "Panera (Pancitos variados)",
}
FALTANTES = {"Tubos de Calamar", "Harina de Trigo"}

# g/ml que representa "1 unidad" para insumos precificados por g/ml (SUPUESTOS)
UNIDAD_G = {"Pan Baguette Rústico": 200, "Pan Ciabatta / Flat / Francés": 150,
            "Pan de Hamburguesa (Sésamo/Brioche/Clásico)": 210, "Pan Integral / Sin TACC": 90,
            "Cerveza Corona Porroncito 330ml": 330,
            "Limas y Limones (Gajos/Rodajas/Jugos)": 12, "Nuggets de Pollo": 20}
UNIT_TO_G = {"Aceitunas (Verdes/Negras)": 5}
PIECE_G = {"Medallón de Carne Vacuna (Hamburguesas)": 115, "Masa de Pizza (Bollos de media masa)": 250,
           "Cuadrado de Brownie Chocolate": 120, "Palta fresca": 200}

PRECIO_LISTA_ALIAS = {
    norm("CORONA 33O"):     norm("CORONA 330"),
    norm("COCA"):           norm("COCA 600CC"),
    norm("SPRITE"):         norm("SPRITE 600CC"),
    norm("COCA ZERO"):      norm("COCA ZERO 600CC"),
    norm("FANTA"):          norm("FANTA 600CC"),
    norm("HEINIKEN CHICA"): norm("HEINEKEN CHICA"),
}

INSUMO_ALIAS = {"Gin Beefeater": "Gin Beefeater", "Gin Aconcagua": "Gin Aconcagua", "Aperol": "Aperol",
 "Whisky Ballantines": "Whisky Ballantines", "Jagger": "Jagger", "Cerveza Stella 1L": "Cerveza Stella 1L",
 "Cerveza Corona (Porón/Poroncitó)": "Cerveza Corona Porroncito 330ml", "Cerveza Corona (proxy)": "Cerveza Corona Porron 710ml",
 "Cerveza Patagonia 730": "Cerveza Patagonia 730", "Coca Cola / Coca Zero 600cc": "Coca Cola / Coca Zero 600cc",
 "Sprite 600cc": "Sprite 600cc", "Agua Con Gas / Sin Gas": "Agua Con Gas / Sin Gas", "Agua Saborizada": "Agua Saborizada",
 "Limonada base": "Limonada base (Clásica/Frutos Rojos/Pomelada)", "Energizante Speed": "Energizante Speed",
 "Energizante Red Bull": "Energizante Red Bull", "Agua Tónica": "Agua Tónica"}

# COMBOS por defecto (código). Se extienden/pisan con combos_extra (override del usuario).
COMBOS_DEFAULT = {
    norm("SMIRNOFF + 4 ENERGIZANTES"): [("Vodka Smirnoff", 700, "ml"), ("Energizante Speed", 4, "lata")],
    norm("ABSOLUT + 4 ENERGIZANTES"): [("Vodka Absolut", 700, "ml"), ("Energizante Speed", 4, "lata")],
    norm("BARON B + ENERGIZANTE"): [("Espumante / Champagne Baron B", 750, "ml"), ("Energizante Speed", 2, "lata")],
    norm("SERNOVA + 4 ENERGIZANTES"): [("Vodka Sernova", 700, "ml"), ("Energizante Speed", 4, "lata")]}

UNIFICAR = {norm("speed"): norm("SPEED"), norm("redbull"): norm("REDBULL"),
 norm("Gin aconcagua vaso"): norm("Gin Aconcagua"),
 norm("VASO LIMONADA FRUTOS ROJOS"): norm("LIMONADA FRUTOS ROJOS"),
 norm("VASO LIMONADA FR"): norm("LIMONADA FRUTOS ROJOS"),
 norm("GIN BRIGTON"): norm("Gin Brighton"),
 norm("COCA 600CC"):      norm("COCA"),
 norm("SPRITE 600CC"):    norm("SPRITE"),
 norm("COCA ZERO 600CC"): norm("COCA ZERO"),
 norm("FANTA 600CC"):     norm("FANTA"),
 norm("POMELADA"):        norm("LIMONADA POMELADA"),
 norm("SMIRNOFF + ENERGIZANTE"): norm("Smirnoff + Speed"),
 norm("ABSOLUT + ENERGIZANTE"):  norm("Absolut + Speed")}

FOOD_CATS = {"HAMBURGUESAS Y SANDWICH", "PARA PICAR Y PAPAS", "PIZZAS", "ENSALADAS", "SIN TACC Y VEGGIE", "POSTRES"}
DOW = ["Lun", "Mar", "Mie", "Jue", "Vie", "Sab", "Dom"]
OPEX_DESDE_0 = "2000-01-01"


def _grupo_cat(cat):
    return "COMIDA" if str(cat).upper() in FOOD_CATS else "BEBIDA"


def parse_qty(qty):
    if qty is None:
        return None
    s = str(qty).strip().lower()
    m = re.match(r"^([\d.,]+)\s*(ml|cc)\b", s)
    if m:
        return (float(m.group(1).replace(",", ".")), "ml")
    m = re.match(r"^([\d.,]+)\s*(g|gr|gramos)\b", s)
    if m:
        return (float(m.group(1).replace(",", ".")), "g")
    m = re.match(r"^([\d.,]+)\s*unidad", s)
    if m:
        return (float(m.group(1).replace(",", ".")), "u")
    m = re.match(r"^([\d.,]+)\s*lata", s)
    if m:
        return ("LATA", float(m.group(1).replace(",", ".")))
    for key, (val, ub) in EQUI.items():
        if key in s:
            m2 = re.match(r"^([\d.,]+)", s)
            n = float(m2.group(1).replace(",", ".")) if m2 else 1.0
            return (n * val, ub)
    m = re.match(r"^([\d.,]+)$", s)
    if m:
        return (float(m.group(1).replace(",", ".")), "u")
    return None


# ================================================================ COMPUTE
def compute(src):
    """Motor puro: recibe todas las fuentes ya parseadas en `src`, devuelve (DATA, opex_seed)."""
    # ---- base: costos e insumos (con overrides fusionados encima) ----
    COSTO = {k: dict(v) for k, v in (src.get("costo_base") or {}).items()}
    CB_CAT = dict(src.get("cb_cat") or {})
    PRECIO_LISTA = dict(src.get("precio_lista") or {})
    RECETAS = {k: list(v) for k, v in (src.get("recetas") or {}).items()}
    MAESTRO = {k: dict(v) for k, v in (src.get("maestro") or {}).items()}
    COMBOS = {k: list(v) for k, v in COMBOS_DEFAULT.items()}

    # alias de maestro para dos grafías del POS que el Excel resolvía a mano
    if norm("Cerveza Corona Porroncito 330ml") in MAESTRO:
        MAESTRO[norm("CORONA 33O")] = dict(MAESTRO[norm("Cerveza Corona Porroncito 330ml")])
    if norm("Cerveza Corona Porron 710ml") in MAESTRO:
        MAESTRO[norm("CORONA 730")] = dict(MAESTRO[norm("Cerveza Corona Porron 710ml")])

    ov = src.get("overrides") or {}

    # maestro_extra: productos nuevos / remapeos (fila entera)
    for e in (ov.get("maestro_extra") or []):
        MAESTRO[norm(e["pos"])] = {"cat": e["cat"], "canon": e["canon"], "tipo": e["tipo"],
            "factor": e.get("factor") or 1, "rend": e.get("rend"), "costeo": e.get("costeo"), "nota": e.get("nota", "")}
    # pours_extra: override parcial de rend
    for k, rend in (ov.get("pours_extra") or {}).items():
        if k in MAESTRO:
            MAESTRO[k] = dict(MAESTRO[k]); MAESTRO[k]["rend"] = rend
    # recetas_extra
    for nm, ings in (ov.get("recetas_extra") or {}).items():
        RECETAS[norm(nm)] = [(i[0], i[1]) for i in ings]
    # insumos_extra
    for e in (ov.get("insumos_extra") or []):
        nm = e["nombre"]; base = dict(COSTO.get(nm, {}))
        cant = e.get("cant_base", base.get("cant_base")) or 1
        precio = e.get("precio", base.get("precio"))
        cxu = e.get("cxu")
        if cxu is None and precio is not None and cant:
            cxu = precio / cant
        COSTO[nm] = {"precio": precio, "pres": e.get("pres", base.get("pres", "")),
                     "cant_base": cant, "unidad": e.get("unidad", base.get("unidad", "")), "cxu": cxu}
        CB_CAT[nm] = e.get("cb_cat", CB_CAT.get(nm, "Comidas - Sushi"))
    # precios_override
    for nm, precio in (ov.get("precios_override") or {}).items():
        if nm in COSTO and COSTO[nm].get("cant_base"):
            COSTO[nm] = dict(COSTO[nm]); COSTO[nm]["precio"] = precio
            COSTO[nm]["cxu"] = precio / COSTO[nm]["cant_base"]
    # combos_extra
    for kpos, comp in (ov.get("combos_extra") or {}).items():
        COMBOS[norm(kpos)] = [(c[0], c[1], c[2]) for c in comp]
    # precio_lista_override
    for k, precio in (ov.get("precio_lista_override") or {}).items():
        PRECIO_LISTA[k] = precio

    SOSP = ov.get("sospechosos") or {}
    CERRADOS = ov.get("dias_cerrados") or {}
    STOCK = ov.get("stock") or {}

    # ---- precio de lista aplanado (para match inequívoco) ----
    _PL_APL = {}; _apl_dup = set()
    for nm_norm, precio in PRECIO_LISTA.items():
        a = _aplanar(nm_norm)
        if a in _PL_APL and _PL_APL[a] != precio:
            _apl_dup.add(a)
        _PL_APL[a] = precio
    for a in _apl_dup:
        _PL_APL.pop(a, None)

    def precio_lista_de(k):
        if k in PRECIO_LISTA:
            return PRECIO_LISTA[k]
        al = PRECIO_LISTA_ALIAS.get(k)
        if al is not None and al in PRECIO_LISTA:
            return PRECIO_LISTA[al]
        return _PL_APL.get(_aplanar(k))

    # ---- costeo de ingredientes ----
    def costo_ingrediente(ing, qty):
        ing = str(ing).strip()
        if ing in FALTANTES:
            return (None, f"insumo faltante:{ing}")
        insumo = ALIAS.get(ing) or (ing if ing in COSTO else None)
        if insumo is None:
            return (None, f"sin alias:{ing}")
        if insumo not in COSTO:
            return (None, f"no en Costo_Base:{insumo}")
        p = parse_qty(qty)
        if p is None:
            return (None, f"cant no parseada:{qty}")
        cxu = COSTO[insumo]["cxu"]; ub_i = COSTO[insumo]["unidad"]
        if cxu is None:
            return (None, f"insumo sin costo por unidad:{insumo}")
        if p[0] == "LATA":
            if COSTO[insumo]["cant_base"] is None:
                return (None, f"insumo sin cantidad base:{insumo}")
            return (p[1] * COSTO[insumo]["cant_base"] * cxu, None)
        val, ub = p
        if ub == "u":
            if ub_i == "u":
                return (val * cxu, None)
            if insumo in UNIDAD_G:
                return (val * UNIDAD_G[insumo] * cxu, None)
            if insumo in UNIT_TO_G:
                return (val * UNIT_TO_G[insumo] * cxu, None)
            return (None, f"unidad sin peso:{ing}")
        if ub_i == "u":
            if insumo in PIECE_G:
                return (val / PIECE_G[insumo] * cxu, None)
            return (None, f"pieza sin peso:{ing}")
        return (val * cxu, None)

    def costear_receta(rn, factor=1.0):
        ings = RECETAS.get(rn)
        if ings is None:
            return (None, [f"receta no hallada:{rn}"])
        total = 0.0; errs = []
        for ing, qty in ings:
            c, e = costo_ingrediente(ing, qty)
            if e:
                errs.append(e)
            elif c:
                total += c
        if errs:
            return (None, errs)
        return (total * factor, [])

    def _insumo_pour(c):
        return c.replace("Insumo:", "").strip()

    def costear_combo(k, _visitados=None):
        _visitados = (_visitados or set()) | {k}
        t = 0.0; errs = []
        for ins, cant, u in COMBOS[k]:
            if u == "producto":
                pk = norm(ins)
                if pk in _visitados:
                    errs.append(f"combo circular:{ins}"); continue
                sub = costear_producto(pk, _visitados)
                if sub.get("nd"):
                    errs.append(f"componente sin costo:{ins} ({sub.get('motivo','')})"); continue
                t += cant * sub["costo"]; continue
            if ins not in COSTO:
                errs.append(f"insumo no encontrado:{ins}"); continue
            if COSTO[ins]["cxu"] is None:
                errs.append(f"insumo sin costo por unidad:{ins}"); continue
            if u == "ml":
                t += cant * COSTO[ins]["cxu"]
            elif u == "lata":
                if COSTO[ins]["cant_base"] is None:
                    errs.append(f"insumo sin cantidad base:{ins}"); continue
                t += cant * COSTO[ins]["cant_base"] * COSTO[ins]["cxu"]
            elif u == "unidad":
                if COSTO[ins]["cant_base"] is None:
                    errs.append(f"insumo sin cantidad base:{ins}"); continue
                t += cant * COSTO[ins]["cant_base"] * COSTO[ins]["cxu"]
            else:
                errs.append(f"unidad no soportada:{u}")
        return (None, errs) if errs else (t, [])

    def costear_producto(k, _visitados=None):
        m = MAESTRO.get(k)
        if not m:
            return {"nd": True, "motivo": "no está en Maestro"}
        t = m["tipo"]
        if t == "sin_datos":
            return {"nd": True, "motivo": "sin_datos"}
        if t == "combo":
            if k in COMBOS:
                c, errs = costear_combo(k, _visitados)
                if c is None:
                    return {"nd": True, "motivo": "; ".join(errs[:2])}
                return {"costo": c, "tipo": t}
            return {"nd": True, "motivo": "combo sin composición"}
        if t in ("receta", "promo_2x1"):
            rec = str(m["costeo"] or "").replace("Receta:", "").strip()
            f = (m.get("factor") or 1)
            c, errs = costear_receta(norm(rec), f)
            if c is None:
                return {"nd": True, "motivo": "; ".join(errs[:2])}
            return {"costo": c, "tipo": t}
        if t == "botella":
            ins = _insumo_pour(str(m["costeo"])); real = INSUMO_ALIAS.get(ins, ins)
            if real in COSTO and COSTO[real]["precio"] is not None:
                return {"costo": COSTO[real]["precio"], "tipo": t}
            return {"nd": True, "motivo": f"botella sin precio:{ins}" if real in COSTO else f"botella no hallada:{ins}"}
        if t == "pour":
            ins = _insumo_pour(str(m["costeo"])); real = INSUMO_ALIAS.get(ins, ins)
            if real in COSTO and m["rend"] and COSTO[real]["cxu"] is not None:
                return {"costo": m["rend"] * COSTO[real]["cxu"], "tipo": t}
            return {"nd": True, "motivo": f"pour sin insumo/rend/costo:{ins}"}
        if t == "directo":
            ins = _insumo_pour(str(m["costeo"])); real = INSUMO_ALIAS.get(ins, ins)
            if real in COSTO:
                if m["rend"] and COSTO[real]["cxu"] is not None:
                    return {"costo": m["rend"] * COSTO[real]["cxu"], "tipo": t}
                if not m["rend"] and COSTO[real]["precio"] is not None:
                    return {"costo": COSTO[real]["precio"], "tipo": t}
                return {"nd": True, "motivo": f"directo sin costo:{ins}"}
            return {"nd": True, "motivo": f"directo sin insumo:{ins}"}
        return {"nd": True, "motivo": f"tipo desconocido:{t}"}

    # ---- explosión de consumo (reposición) ----
    def qty_ingrediente(ing, qty):
        ing = str(ing).strip()
        if ing in FALTANTES:
            return (None, None, None, f"faltante:{ing}")
        insumo = ALIAS.get(ing) or (ing if ing in COSTO else None)
        if insumo is None or insumo not in COSTO:
            return (None, None, None, f"sin insumo:{ing}")
        p = parse_qty(qty)
        if p is None:
            return (None, None, None, f"cant:{qty}")
        ub_i = COSTO[insumo]["unidad"]
        if p[0] == "LATA":
            return (insumo, p[1] * COSTO[insumo]["cant_base"], ub_i, None)
        val, ub = p
        if ub == "u":
            if ub_i == "u":
                return (insumo, val, "u", None)
            if insumo in UNIDAD_G:
                return (insumo, val * UNIDAD_G[insumo], ub_i, None)
            if insumo in UNIT_TO_G:
                return (insumo, val * UNIT_TO_G[insumo], ub_i, None)
            return (None, None, None, f"unidad sin peso:{ing}")
        if ub_i == "u":
            if insumo in PIECE_G:
                return (insumo, val / PIECE_G[insumo], "u", None)
            return (None, None, None, f"pieza sin peso:{ing}")
        return (insumo, val, ub_i, None)

    def explotar_producto(k, _visitados=None):
        m = MAESTRO.get(k)
        if not m:
            return None
        t = m["tipo"]; out = []
        if t == "sin_datos":
            return None
        if t == "combo":
            if k not in COMBOS:
                return None
            _visitados = (_visitados or set()) | {k}
            for ins, cant, u in COMBOS[k]:
                if u == "producto":
                    pk = norm(ins)
                    if pk in _visitados:
                        return None
                    sub = explotar_producto(pk, _visitados)
                    if sub is None:
                        return None
                    for i2, q2, u2 in sub:
                        out.append((i2, q2 * cant, u2))
                    continue
                if ins not in COSTO:
                    return None
                if u == "ml":
                    out.append((ins, cant, COSTO[ins]["unidad"]))
                elif u in ("lata", "unidad"):
                    out.append((ins, cant * COSTO[ins]["cant_base"], COSTO[ins]["unidad"]))
            return out
        if t in ("receta", "promo_2x1"):
            rec = norm(str(m["costeo"] or "").replace("Receta:", "").strip())
            ings = RECETAS.get(rec)
            if ings is None:
                return None
            f = (m.get("factor") or 1)
            for ing, qty in ings:
                insumo, qb, ub, err = qty_ingrediente(ing, qty)
                if err:
                    return None
                out.append((insumo, qb * f, ub))
            return out
        if t == "botella":
            ins = _insumo_pour(str(m["costeo"])); real = INSUMO_ALIAS.get(ins, ins)
            if real not in COSTO:
                return None
            return [(real, COSTO[real]["cant_base"], COSTO[real]["unidad"])]
        if t == "pour":
            ins = _insumo_pour(str(m["costeo"])); real = INSUMO_ALIAS.get(ins, ins)
            if real not in COSTO or not m["rend"]:
                return None
            return [(real, m["rend"], COSTO[real]["unidad"])]
        if t == "directo":
            ins = _insumo_pour(str(m["costeo"])); real = INSUMO_ALIAS.get(ins, ins)
            if real not in COSTO:
                return None
            q = m["rend"] if m["rend"] else COSTO[real]["cant_base"]
            return [(real, q, COSTO[real]["unidad"])]
        return None

    def detalle_producto(k):
        exp = explotar_producto(k)
        if not exp:
            return []
        out = []
        for insumo, qb, ub in exp:
            cxu = COSTO.get(insumo, {}).get("cxu", 0) or 0
            out.append({"insumo": insumo, "qty": round(qb, 2), "unidad": ub,
                        "cxu": round(cxu, 3), "sub": round(qb * cxu, 1)})
        return out

    def nd_guia(nombre, motivo):
        up = re.sub(r"[^A-Z0-9 ]", "", str(nombre).upper())
        toks = [x for x in up.split() if len(x) > 3]
        if "combo" in motivo:
            return ("Falta definir la composición (qué botellas/unidades incluye).",
                    "Confirmámelo y lo cargo en Maestro_Productos.")
        if motivo.startswith("no está en Maestro"):
            cost_hit = None
            for name in COSTO:
                words = set(re.sub(r"[^A-Z0-9 ]", " ", name.upper()).split())
                if toks and any(t in words for t in toks):
                    cost_hit = name; break
            rec_hit = any(toks and (set(rn.split()) & set(toks)) for rn in RECETAS)
            if rec_hit or cost_hit:
                base = "su " + ("receta ya existe" if rec_hit else ("costo ya existe: " + cost_hit))
                return ("No está en Maestro_Productos (" + base + ").",
                        "Agregá una fila en Maestro_Productos de datos_general.xlsx.")
            return ("No está en Maestro_Productos y no encuentro su costo/receta.",
                    "Cargá el insumo en 'Costo items' y agregá la fila en Maestro_Productos.")
        if "faltante" in motivo or "sin_datos" in motivo or "receta no" in motivo:
            return ("Falta la receta y/o el costo de algún insumo.",
                    "Cargá los insumos que faltan en 'Costo items'.")
        return (motivo, "Revisar en datos_general.xlsx.")

    # ---- recolectar ventas en una línea de tiempo día a día ----
    prods = {}; dias = {}; consumo_dia = {}; split = {}
    for v in (src.get("ventas") or []):
        nombre = v.get("nombre")
        if nombre is None:
            continue
        try:
            u = int(v.get("unidades") or 0)
        except (TypeError, ValueError):
            u = 0
        try:
            monto = float(v.get("monto") or 0)
        except (TypeError, ValueError):
            monto = 0.0
        if u == 0 and monto == 0:
            continue
        fecha = str(v.get("fecha") or "s/f")
        iso = str(v.get("iso") or "")
        dkey = iso or fecha
        if dkey not in dias:
            try:
                dow = DOW[datetime.date.fromisoformat(iso).weekday()]
            except Exception:
                dow = ""
            dias[dkey] = {"fecha": fecha, "iso": iso, "dow": dow}
        k = norm(nombre); k = UNIFICAR.get(k, k)
        p = prods.setdefault(k, {"raw": nombre, "byday": {}})
        bd = p["byday"].setdefault(dkey, [0, 0.0]); bd[0] += u; bd[1] += monto
        exp = explotar_producto(k)
        if exp:
            g = _grupo_cat(MAESTRO.get(k, {}).get("cat", ""))
            cd = consumo_dia.setdefault(dkey, {})
            for insumo, qb, ub in exp:
                cd[insumo] = cd.get(insumo, 0.0) + qb * u
                s = split.setdefault(insumo, {"BEBIDA": 0.0, "COMIDA": 0.0}); s[g] += qb * u

    # ---- costear cada producto ----
    productos = []
    for k, p in prods.items():
        cc = costear_producto(k)
        cat = MAESTRO.get(k, {}).get("cat", "(sin cat)"); grupo = _grupo_cat(cat)
        byday = {f: [bd[0], round(bd[1])] for f, bd in p["byday"].items()}
        base = {"pos": p["raw"], "key": k, "cat": cat, "grupo": grupo, "byday": byday,
                "precio_lista": precio_lista_de(k)}
        _sp = SOSP.get(k) or {}
        if _sp.get("estado"):
            base["susp"] = _sp["estado"]; base["susp_motivo"] = _sp.get("motivo", "") or ""
        if cc.get("nd"):
            fa, do = nd_guia(p["raw"], cc["motivo"])
            base.update({"nd": True, "motivo": cc["motivo"], "falta": fa, "donde": do})
        else:
            base.update({"nd": False, "tipo": cc["tipo"], "costo": round(cc["costo"], 1),
                         "nota": MAESTRO.get(k, {}).get("nota", "") or "", "breakdown": detalle_producto(k)})
            _m = MAESTRO.get(k, {}); _t = cc["tipo"]
            if _t in ("receta", "promo_2x1"):
                _rn = str(_m.get("costeo") or "").replace("Receta:", "").strip()
                base["receta_nombre"] = _rn
                base["receta_ings"] = [[i[0], i[1]] for i in RECETAS.get(norm(_rn), [])]
            elif _t == "combo":
                _cc = COMBOS.get(k)
                if _cc:
                    base["combo_comp"] = [[x[0], x[1], x[2]] for x in _cc]
            base["editable"] = _t in ("receta", "promo_2x1", "combo")
        productos.append(base)

    # ---- metadata de insumos (para compras) ----
    insumos_meta = {}
    for insumo in sorted(set(i for cd in consumo_dia.values() for i in cd)):
        c = COSTO.get(insumo, {}); s = split.get(insumo, {"BEBIDA": 0, "COMIDA": 0})
        insumos_meta[insumo] = {"cxu": c.get("cxu", 0), "precio": c.get("precio", 0),
            "cant_base": c.get("cant_base", 0), "present": c.get("pres", ""),
            "unidad": c.get("unidad", ""), "cb_cat": CB_CAT.get(insumo, "Otros"),
            "grupo": "COMIDA" if s["COMIDA"] > s["BEBIDA"] else "BEBIDA",
            "compartido": s["BEBIDA"] > 0 and s["COMIDA"] > 0}
    consumo_dia = {f: {i: round(q, 2) for i, q in cd.items()} for f, cd in consumo_dia.items()}
    dias_list = sorted(dias.values(), key=lambda d: d["iso"] or d["fecha"])

    # ---- cajas (ya vienen de src, deduplicadas por noche) ----
    cajas = _dedup_cajas(list(src.get("cajas") or []), dias)

    # ---- OPEX ----
    opex_total, opex_pend, opex_detalle, opex_periodos, opex_seed = _compute_opex(
        src.get("opex_json"), src.get("opex_base") or [], src.get("opex_cero_confirmado") or [])

    DATA = {"generado": datetime.date.today().isoformat(), "logo": src.get("logo") or "",
            "opex": opex_total, "opex_pend": opex_pend, "opex_detalle": opex_detalle,
            "dias": dias_list, "productos": productos, "insumos": insumos_meta,
            "consumo_dia": consumo_dia, "cajas": cajas, "dias_cerrados": CERRADOS,
            "stock": STOCK, "opex_periodos": opex_periodos}
    return DATA, opex_seed


# ---------------------------------------------------------------- cajas: dedup por noche
def _dedup_cajas(cajas, dias):
    _ddmm2iso = {}; _ddmm_amb = set()
    for _d in dias.values():
        _f = _d.get("fecha"); _i = _d.get("iso")
        if not _f or not _i:
            continue
        if _f in _ddmm2iso and _ddmm2iso[_f] != _i:
            _ddmm_amb.add(_f)
        _ddmm2iso[_f] = _i
    for _f in _ddmm_amb:
        _ddmm2iso.pop(_f, None)

    def _caja_iso(c):
        fi = str(c.get("fecha_iso") or "")
        if re.match(r"^\d{4}-\d{2}-\d{2}$", fi):
            return fi
        m = re.search(r"(\d{2})/(\d{2})/(\d{4})", str(c.get("fecha_key") or "") or str(c.get("fecha") or ""))
        if m:
            return "%s-%s-%s" % (m.group(3), m.group(2), m.group(1))
        f = str(c.get("fecha") or "")
        if f in _ddmm2iso:
            return _ddmm2iso[f]
        return ""

    _uni = {}; _sin = []
    for c in cajas:
        c = dict(c)
        c["iso"] = _caja_iso(c)
        if not c["iso"]:
            _sin.append(c); continue
        prev = _uni.get(c["iso"])
        if prev is None or (c.get("archivo") == "Bistrosoft API" and prev.get("archivo") != "Bistrosoft API"):
            _uni[c["iso"]] = c
    return sorted(_uni.values(), key=lambda c: c["iso"]) + _sin


# ---------------------------------------------------------------- OPEX
def _compute_opex(opex_json, opex_base, cero_confirmado):
    """Devuelve (total, pend, detalle, periodos, seed). `seed` != None solo si opex_json venía
    vacío: es la siembra que el caller debe persistir (en local iba a opex.json)."""
    _cero_ok = {str(x).strip().lower() for x in (cero_confirmado or [])}
    seed = None
    raw = opex_json

    if not raw:
        # sembrar de la hoja OPEX del Excel (una vez), preservando el total mensual estimado
        seed_items = []
        for r in (opex_base or []):
            cat = r.get("cat"); item = r.get("item")
            if item is None:
                continue
            if str(cat or "").upper().startswith("TOTAL") or str(item or "").upper().startswith("TOTAL"):
                continue
            cant = r.get("cantidad"); unit = r.get("unitario"); monto = r.get("monto") or 0
            key = str(item).strip().lower()
            if cant and unit and abs((cant or 0) * (unit or 0) - monto) < 1 and monto:
                cantidad = cant; unitario = unit
            else:
                cantidad = 1; unitario = monto
            seed_items.append({"cat": cat, "item": item, "cantidad": cantidad, "unitario": unitario,
                               "confirmado_cero": key in _cero_ok})
        seed = [{"desde": OPEX_DESDE_0, "items": seed_items}]
        raw = seed

    def _opex_calc(items):
        det = []; tot = 0; pend = 0
        for e in (items or []):
            cantidad = e.get("cantidad", 1) or 0; unitario = e.get("unitario", 0) or 0
            monto = round(cantidad * unitario)
            key = str(e.get("item", "")).strip().lower()
            cz = bool(e.get("confirmado_cero")) or (key in _cero_ok)
            det.append({"cat": e.get("cat", "(sin cat)"), "item": e.get("item", ""),
                        "cantidad": cantidad, "unitario": unitario, "monto": monto, "confirmado_cero": cz})
            if monto == 0:
                if not cz:
                    pend += 1
            else:
                tot += monto
        return det, tot, pend

    if raw and isinstance(raw[0], dict) and "items" in raw[0]:
        _pers = [p for p in raw if isinstance(p, dict)]
    elif raw:
        _pers = [{"desde": OPEX_DESDE_0, "items": raw}]
    else:
        _pers = []
    _pers.sort(key=lambda p: str(p.get("desde") or OPEX_DESDE_0))

    periodos = []
    for p in _pers:
        det, tot, pend = _opex_calc(p.get("items"))
        periodos.append({"desde": str(p.get("desde") or OPEX_DESDE_0), "opex": tot,
                         "opex_pend": pend, "opex_detalle": det})

    _hoy = datetime.date.today().isoformat(); _vig = None
    for p in periodos:
        if p["desde"] <= _hoy:
            _vig = p
    if _vig is None and periodos:
        _vig = periodos[0]
    opex_total = _vig["opex"] if _vig else 0
    opex_pend = _vig["opex_pend"] if _vig else 0
    opex_detalle = _vig["opex_detalle"] if _vig else []
    if not opex_detalle:
        opex_total = 10460000
    return opex_total, opex_pend, opex_detalle, periodos, seed
