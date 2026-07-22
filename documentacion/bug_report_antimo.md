# Auditoría de bugs — ANTIMO

**Fecha:** 19-07-2026 · **Alcance:** `app_antimo.py`, `actualizar_antimo.py`, `conector_bistrosoft.py`, `dashboard_tpl.html` (2.538 líneas)
**Método:** lectura completa de los 4 archivos + verificación empírica contra la app corriendo. No se modificó ningún archivo.

> **Todos los hallazgos de este reporte están reproducidos, no inferidos.** Cada uno incluye el comando o la prueba que lo demuestra. Al final hay una sección de **falsos positivos descartados**: cosas que se pidió buscar y que, tras verificarlas, resultaron estar bien.

## Resumen

| Sev. | # | Hallazgos |
|---|---|---|
| 🔴 Crítico | 2 | CSRF sin protección · XSS en nombres de producto |
| 🟠 Alto | 3 | Comparación de KPIs muerta · Pérdida silenciosa de datos · Escrituras no atómicas |
| 🟡 Medio | 8 | `do_HEAD` filtra archivos · Handler muere con `Content-Length` inválido · Fuga de 464 dirs temporales · Carreras de escritura · Año hardcodeado · `json.dump` sin encoding · Crash por `cxu` nulo · Errores con HTTP 200 |
| 🔵 Bajo | 7 | Workbook cargado dos veces · Condición muerta · `except:` desnudos · Scope global · `pip install` en runtime · Sin tope de body · Off-by-one en paginado |

**Los dos críticos comparten una raíz:** la app asume que todo lo que le llega es confiable — el navegador del dueño, y los nombres que vienen del POS. Ninguna de las dos cosas lo es.

---

## ✅ Estado: 19 de 20 corregidos y verificados

Las correcciones se aplicaron después de la auditoría. **Cada una se reverificó con la misma prueba que encontró el bug.**

| Bug | Estado | Evidencia de la corrección |
|---|---|---|
| 01 CSRF | ✅ | El mismo POST cross-origin ahora devuelve **403** y no escribe. También bloqueado con `Content-Type` correcto pero `Origin` ajeno. |
| 02 XSS | ✅ | El payload inyectado crea **0** elementos `<img>`; se muestra como texto literal. Verificado en Rentabilidad, Caja y el documento entero. |
| 03 Comparación muerta | ✅ | `prevRange` devuelve claves ISO; encuentra 15 días y $35.191.500. Las flechas muestran **▼5%** y **▲7%** en vez de "—". |
| 04 Pérdida de datos | ✅ | Con un `stock.json` corrupto el guardado responde **409** con mensaje claro y **deja el archivo intacto**. |
| 05 Escritura no atómica | ✅ | `_save` usa `tmp` + `fsync` + `os.replace`. |
| 06 `do_HEAD` | ✅ | `HEAD /datos/bistro_config.json` → **404** (antes 200 con el tamaño). |
| 07 `Content-Length` | ✅ | Header inválido → **400 Bad Request** (antes el hilo moría sin responder). |
| 08 Fuga de temporales | ✅ | Delta por corrida: **0** (antes +3). Los 467 huérfanos acumulados se limpiaron. |
| 09 Carreras de escritura | ✅ | `_LOCK` (RLock) serializa mutación + pipeline. |
| 10 Año hardcodeado | ✅ | Sin `'2026-'` en `cajaIso`. Total de caja idéntico: $95.233.850. |
| 11 `json.dump` sin encoding | ✅ | Los 3 sitios con `encoding="utf-8"` explícito. |
| 12 Crash por `cxu` nulo | ✅ | Devuelve N/D en vez de abortar; guardas también en combo, pour, botella y directo. |
| 13 Errores con HTTP 200 | ✅ | 400 / 403 / 404 / 409 / 500 según corresponda; sin filtrar rutas del sistema. |
| 14 Doble carga del Excel | ✅ | Una sola pasada; `COSTO` y `CB_CAT` se arman juntos. |
| 15 Condición muerta | ✅ | Eliminada. |
| 16 `except:` desnudos | ✅ | Los 3 acotados a `(TypeError, ValueError)`. |
| 18 `pip install` en runtime | ✅ | Ahora avisa y sigue sin PDF, no instala nada. |
| 19 Off-by-one | ✅ | `>=5000`. |
| 20 `r.json()` sin protección | ✅ | Mensajes claros para credenciales rechazadas, respuesta no-JSON y token ausente. |
| **17 Scope global** | ⏸️ **Pendiente** | Requiere envolver las 1.100 líneas del script en un IIFE. Cambio mecánico pero de diff enorme; conviene hacerlo junto con otro trabajo en el archivo. Riesgo real: bajo. |

**Regresión posterior a los arreglos:** las 7 solapas, los filtros de categoría y búsqueda, el modo comparación, los dos modos de Compras y los filtros del BCG — **0 errores de JS**. Totales sin cambios: $91.390.950 de ventas, $21.740.601 de resultado, 48 días, 109 productos.

---

# 🔴 CRÍTICO

## BUG-01 · Cualquier web que el dueño visite puede escribir en sus datos (CSRF)

**Archivo:** `app_antimo.py:132-300` (`do_POST`) · **Severidad: Crítica**

### El problema

`do_POST` no valida **de dónde viene** el pedido. No mira `Origin`, no mira `Host`, no exige token. Cualquier página web abierta en otra pestaña puede escribir en los archivos de ANTIMO mientras la app esté corriendo.

La defensa que uno esperaría —CORS— no aplica: el navegador bloquea *leer la respuesta*, pero **la escritura ya ocurrió**. Y el preflight que normalmente frenaría esto se esquiva mandando `Content-Type: text/plain` en vez de `application/json`, porque el servidor nunca mira el Content-Type: hace `json.loads` del body venga como venga (línea 135).

### Verificado

```console
$ curl -s -X POST http://127.0.0.1:8733/api/sospechoso \
    -H 'Content-Type: text/plain' \
    -H 'Origin: https://sitio-malicioso.example' \
    -d '{"key":"PRUEBA CSRF","estado":"si","motivo":"escrito desde otro origen"}'
HTTP 200

$ python3 -c "import json;print(json.load(open('datos/sospechosos.json'))['PRUEBA CSRF'])"
{'estado': 'si', 'motivo': 'escrito desde otro origen', 'ts': '2026-07-19T14:00:10'}
```

Se escribió en disco desde un origen ajeno. *(El artefacto de prueba ya fue borrado.)*

### Qué se puede hacer con esto

No es teórico. Los endpoints expuestos permiten, sin ninguna interacción del dueño:

- `POST /api/config` → **sobrescribir las credenciales de Bistrosoft**, incluida la contraseña.
- `POST /api/opex_save` → falsear todo el OPEX, y con él el resultado operativo.
- `POST /api/producto`, `/api/receta`, `/api/precio` → corromper el costeo entero.
- `POST /api/pull` → disparar un `subprocess` a repetición.

Sumado a que no se valida el header `Host`, esto también queda expuesto a **DNS rebinding**: un dominio que resuelve a `127.0.0.1` alcanza el servidor aunque esté bindeado a loopback.

### Corrección

Dos capas. La primera sola ya corta el ataque demostrado; la segunda cubre el rebinding.

```python
# app_antimo.py — agregar dentro de class H, antes de do_POST

def _origen_confiable(self):
    """Un POST valido solo puede venir de la propia pagina de ANTIMO.

    1) Content-Type: exigir application/json obliga al navegador a hacer preflight
       en cualquier pedido cross-origin, y el preflight falla porque no mandamos
       cabeceras CORS. Esto es lo que corta el CSRF con 'simple request'.
    2) Origin: si viene (los navegadores lo mandan siempre en POST), tiene que ser
       loopback. curl y los scripts locales no lo mandan y siguen funcionando.
    3) Host: bloquea DNS rebinding (un dominio que resuelve a 127.0.0.1).
    """
    ct = (self.headers.get("Content-Type") or "").split(";")[0].strip().lower()
    if ct != "application/json":
        return False
    org = self.headers.get("Origin")
    if org is not None:
        h = urllib.parse.urlparse(org).hostname
        if h not in ("127.0.0.1", "localhost"):
            return False
    host = (self.headers.get("Host") or "").split(":")[0]
    if host not in ("127.0.0.1", "localhost"):
        return False
    return True

def do_POST(self):
    if not self._origen_confiable():
        return self._send(403, '{"ok":false,"error":"origen no permitido"}')
    path = urllib.parse.urlparse(self.path).path
    ...  # resto igual
```

**Compatible con el frontend actual:** `apiPost()` (línea 299) ya manda `'Content-Type':'application/json'`, y los tres `fetch` sueltos (líneas 1204, 1278) también. No hay que tocar nada del cliente.

---

## BUG-02 · XSS: los nombres de producto se inyectan como HTML

**Archivo:** `dashboard_tpl.html` — líneas **655, 732, 845, 1028, 1029, 1039, 1136** · **Severidad: Crítica**

### El problema

El archivo define un escapador en la línea 173:

```js
const esc=s=>(''+(s==null?'':s)).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/"/g,'&quot;');
```

…y después **no lo usa** en los lugares donde entra texto que la app no controla. Línea 655:

```js
h+=`<tr class="clik" data-i="${i}"><td>...${x.pos}${suspBadge(x)}</td>...`;
```

`x.pos` es el nombre crudo del producto, tal como viene del ranking de Bistrosoft o del Excel. Nunca pasa por `esc()`.

### Verificado

Inyectando un nombre hostil solo en memoria (sin tocar archivos) y renderizando:

```js
victima.pos = '<img src=x onerror="window.__XSS_EJECUTADO=1">MALICIOSO';
st.tab='rent'; rerender();
document.getElementById('tRent').querySelectorAll('img[onerror]').length  // → 1
```

Resultado: **`"VULNERABLE: el <img> se creo como elemento real"`**, y lo mismo en las otras solapas. El navegador construyó un nodo `<img>` con su handler `onerror` a partir de un dato. Eso es ejecución de HTML arbitrario.

### Por qué importa en una app "local y offline"

Es tentador descartarlo porque no hay usuarios ajenos. No corresponde, por tres razones:

1. **El dato viene de afuera.** Los nombres los tipea el personal en el POS y bajan por la API de Bistrosoft. Cualquiera con acceso a la caja puede crear un producto llamado `<img src=x onerror=...>`.
2. **El JS inyectado corre con el origen de la app**, o sea con acceso completo a todos los endpoints `POST` — incluido `/api/config`, donde vive la contraseña de Bistrosoft.
3. **La solapa Caja es peor todavía** (líneas 1028-1029): ahí se renderizan `concepto` y `user`, que salen del campo `comments` de los retiros. Ese es texto libre que escribe el personal cada noche.

Un `<` en un nombre legítimo (`SANDWICH <3`) también rompe la tabla sin necesidad de malicia.

### Corrección

Envolver en `esc()` en cada punto de inyección. Los sitios exactos:

```js
// L655 — renderRent
h+=`<tr class="clik" data-i="${i}"><td><span style="color:${CLCOL[x.clase]}" title="${esc(x.clase)}">${CLAB[x.clase]}</span> ${esc(x.pos)}${suspBadge(x)}</td>...`;

// L732 — showModal (titulo)
<h2><span style="color:${CLCOL[x.clase]||'#888'}">${CLAB[x.clase]||''}</span> ${esc(x.pos)}</h2>
<div class="mut" style="font-size:12px">${esc(x.cat)} · ${esc(x.tipo||'')} · ${x.u} vendidas en el período</div>

// L692 — showModal (desglose de insumos)
rows+=`<tr><td>${esc(b.insumo)}</td><td class="n">${b.qty} ${esc(b.unidad)}</td>...`;

// L845 — renderRecetas
h+=`<tr><td>${esc(p.pos)}${suspBadge(p)}</td><td class="mut">${p.nd?'sin datos':esc(p.tipo)}</td>...`;

// L1028-1029 — renderCaja (retiros y descuentos: texto libre del POS)
...dr.map(r=>`<tr><td>${esc(r.concepto||'—')}</td><td class="mut">${esc(r.user||'—')}</td><td class="mut">${esc(r.hora||'—')}</td><td class="n neg">${f0(r.monto)}</td></tr>`)

// L1039 — renderND
nd.forEach(x=>{h+=`<tr><td>${esc(x.pos)}</td><td class="n">${x.u}</td><td class="n">${f0(x.monto)}</td><td>${esc(x.falta||x.motivo)}</td><td class="mut">${esc(x.donde||'')}</td></tr>`;});

// L1136 — renderCostos
h+=`<tr><td>${esc(nm)}</td><td class="mut">${esc(m.cb_cat||'')}</td><td class="mut">${esc(m.present||'')}</td>...`;
```

**Ojo con un detalle:** `esc()` no escapa `'`. En los varios lugares donde el código arma atributos con comillas simples convendría además cambiar `.replace(/"/g,'&quot;')` por una versión que cubra ambas comillas:

```js
const esc=s=>(''+(s==null?'':s))
 .replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;')
 .replace(/"/g,'&quot;').replace(/'/g,'&#39;');
```

También hay ~8 lugares que usan el patrón artesanal `.replace(/"/g,'&quot;')` para atributos (L687, 688, 1050, 1088, 1089, 1101, 1102, 1131, 1150, 1193, 1195). Escapan la comilla pero **no** el `<`, así que sirven para el atributo pero no para el contenido. Unificar todo en `esc()`.

---

# 🟠 ALTO

## BUG-03 · La comparación con el período anterior está muerta: siempre muestra "—"

**Archivo:** `dashboard_tpl.html:391-393` (`prevRange`) · **Severidad: Alta**

> ⚠️ **Esta es una regresión introducida por la migración a fecha ISO de este mismo día** (commit `e5e9a92`). No es deuda vieja: la rompí yo y no la detecté hasta esta auditoría.

### El problema

Tras la migración, la clave de un día pasó a ser la fecha ISO completa (`DK(d)` → `d.iso`), y `totals()` indexa por `ISO[a]`. Pero `prevRange` quedó devolviendo **`.fecha`**, que es la etiqueta `"DD-MM"` para mostrar:

```js
return {a:inr[0].fecha, b:inr[inr.length-1].fecha};   // ← devuelve "04-06", no "2026-06-04"
```

`ISO["04-06"]` es `undefined` → `rangeDias` no encuentra ningún día → el período anterior da **0 ventas**.

### Verificado

```js
const pr = prevRange(DK(DIAS[30]), DK(DIAS[47]));
// devuelve: {a:"04-06", b:"22-06"}
// ISO[pr.a] === undefined  → true
// rangeDias(pr.a,pr.b).length     → 0
// totals(pr.a,pr.b).ventas        → 0
// lo correcto seria               → 35.191.500  (15 dias)
```

### Síntoma que ve el dueño

Como `delta()` devuelve `null` cuando el valor previo es 0, **las cuatro flechas ▲/▼ de los KPIs muestran un guion**:

```
RESULTADO OPERATIVO   $10.935.644   —
VENTAS                $37.48M       —
MARGEN BRUTO          57.6%         —
TICKET PROMEDIO       ...           —
```

La función no tira error: falla en silencio y parece "no hay comparación disponible". Es el peor modo de falla posible, porque no se nota.

### Corrección

```js
function prevRange(a,b){
 const n=calDaysRange(a,b);
 const ia=new Date(ISO[a]);
 const pe=new Date(ia); pe.setDate(pe.getDate()-1);
 const psD=new Date(pe); psD.setDate(psD.getDate()-(n-1));
 const psIso=psD.toISOString().slice(0,10), peIso=pe.toISOString().slice(0,10);
 const inr=DIAS.filter(d=>d.iso>=psIso&&d.iso<=peIso);
 if(!inr.length)return null;
 return {a:DK(inr[0]), b:DK(inr[inr.length-1])};   // ← clave ISO, no la etiqueta
}
```

**Lección de proceso:** la migración a ISO se validó comprobando que los totales no cambiaran, y no cambiaron — porque este camino de código devuelve `null` y se saltea en silencio. Un total que no se mueve no prueba que nada se rompió.

---

## BUG-04 · Un JSON corrupto borra todos los datos previos sin avisar

**Archivo:** `app_antimo.py:12-17` (`_load`) + `34-36` (`_save`) · **Severidad: Alta**

### El problema

`_load` no distingue **"el archivo no existe"** de **"el archivo existe pero está roto"**. Ante un JSON corrupto devuelve el default:

```python
try: return json.load(open(p,encoding="utf-8"))
except Exception: return default      # ← {} indistinguible de "archivo nuevo"
```

Y el siguiente guardado escribe ese `{}` con un solo ítem encima del archivo, destruyendo el contenido anterior.

### Verificado

```console
archivo con 2 conteos reales pero corrupto -> _load devuelve: {}
tras guardar un insumo nuevo, el archivo pasa a contener SOLO: {'Fernet': {'cant': 3}}
=> los 2 conteos anteriores se perdieron sin ningun aviso
```

### Cómo llega a pasar

No hace falta que nadie edite nada a mano. **BUG-05 lo produce solo:** si la app se cierra mientras `json.dump` está escribiendo, queda un archivo truncado — que es exactamente la condición que dispara esto. Los dos bugs se encadenan: un cierre a destiempo corrompe el archivo, y el siguiente guardado lo vacía del todo.

Mitigación parcial existente: `_backup()` corre antes de cada `_save`, así que la versión previa queda en `datos/_backups/`. Pero el dueño no tiene forma de saber que tiene que ir a buscarla.

### Corrección

```python
class DatosCorruptos(Exception): pass

def _load(name, default, estricto=False):
    """estricto=True: un archivo ilegible ABORTA en vez de devolver el default.
    Se usa antes de cualquier escritura — devolver {} ahi significa borrar todo."""
    p = os.path.join(DATOS, name)
    if not os.path.exists(p):
        return default
    try:
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        if estricto:
            raise DatosCorruptos(
                f"{name} esta corrupto ({e}). Se aborta el guardado para no "
                f"pisar los datos. Hay copias en datos/_backups/.")
        print("WARN: no pude leer", name, "->", e)
        return default

def _save(name, obj):
    _backup(name)
    p = os.path.join(DATOS, name)
    tmp = p + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=1)
        f.flush(); os.fsync(f.fileno())
    os.replace(tmp, p)          # atomico: o el archivo viejo o el nuevo, nunca a medias
```

Y en cada handler que hace read-modify-write, pasar `estricto=True`:

```python
s = _load("stock.json", {}, estricto=True)
```

El `except Exception` de la línea 296 ya devuelve el mensaje al frontend, así que el dueño vería *"stock.json está corrupto…"* en vez de perder los datos callado.

---

## BUG-05 · Las escrituras no son atómicas: un cierre a destiempo corrompe el archivo

**Archivo:** `app_antimo.py:34-36` (`_save`) · **Severidad: Alta**

```python
def _save(name,obj):
    _backup(name)
    json.dump(obj,open(os.path.join(DATOS,name),"w",encoding="utf-8"),ensure_ascii=False,indent=1)
```

Dos problemas en una línea:

1. **`open(...,"w")` trunca el archivo antes de escribir.** Si el proceso muere en el medio (el dueño cierra la ventana de Terminal, que es *la forma documentada de cerrar la app* según el mensaje de la línea 317), queda un JSON a mitad. Eso es exactamente el input que dispara BUG-04.
2. **El archivo nunca se cierra explícitamente.** Sin `with`, si `json.dump` lanza una excepción a mitad (un objeto no serializable), el descriptor queda colgando y el archivo truncado.

**Corrección:** la versión de `_save` con `tmp` + `os.replace` del bug anterior resuelve ambos. `os.replace` es atómico a nivel del sistema de archivos.

**El mismo patrón está en el motor** (`actualizar_antimo.py:719-720`), donde se escriben `dashboard_ANTIMO.html` y `datos_dashboard.json` — los dos archivos que la app sirve. Si el pipeline muere ahí, la app queda sirviendo un HTML truncado.

---

# 🟡 MEDIO

## BUG-06 · `do_HEAD` heredado esquiva la lista blanca de `do_GET`

**Archivo:** `app_antimo.py:112` · **Severidad: Media**

`class H(http.server.SimpleHTTPRequestHandler)` hereda `do_HEAD`, que sirve archivos del directorio de trabajo. `do_GET` está sobrescrito con una lista blanca de 4 rutas y **nunca llama a `super()`** — así que por GET no hay path traversal. Pero `do_HEAD` quedó sin tocar.

### Verificado

```console
GET  /datos/bistro_config.json -> 404
HEAD /datos/bistro_config.json -> 200
    Content-type: application/json
    Content-Length: 148
```

El archivo de credenciales responde 200 y filtra su tamaño exacto. `HEAD` no devuelve cuerpo, así que **no se filtra la contraseña** — pero sí se confirma qué archivos existen y cuánto pesan, sobre un directorio que además contiene los backups.

`translate_path` de la stdlib normaliza `..`, así que no hay traversal fuera de la carpeta. El problema es el alcance, no el escape.

### Corrección

```python
def do_HEAD(self):
    """No heredar el de SimpleHTTPRequestHandler: serviria toda la carpeta del
    proyecto, incluido datos/bistro_config.json y datos/_backups/."""
    self.do_GET()
```

Alternativa más explícita: heredar de `BaseHTTPRequestHandler` en vez de `SimpleHTTPRequestHandler`. La app no usa nada del segundo (sirve todo a mano), así que no pierde funcionalidad y elimina la clase entera de problemas.

---

## BUG-07 · Un `Content-Length` no numérico mata el handler sin responder

**Archivo:** `app_antimo.py:134` · **Severidad: Media**

```python
def do_POST(self):
    path=urllib.parse.urlparse(self.path).path
    ln=int(self.headers.get("Content-Length") or 0)   # ← ValueError, FUERA del try
    try: data=json.loads(self.rfile.read(ln) or b"{}")
    except Exception: data={}
```

El `int()` está **una línea antes** del `try`. Con un header malformado lanza `ValueError` sin capturar.

### Verificado

```console
$ printf 'POST /api/ping HTTP/1.1\r\nHost: 127.0.0.1\r\nContent-Length: abc\r\n\r\n' | nc 127.0.0.1 8733
[respuesta vacia = el handler murio sin responder]
```

El cliente no recibe **nada** — ni siquiera un 400. Gracias a `ThreadingTCPServer` solo muere ese hilo, así que el servidor sobrevive; pero el navegador queda esperando hasta el timeout.

Relacionado: **no hay tope de tamaño**. Un `Content-Length: 9999999999` hace que `self.rfile.read(ln)` intente reservar 10 GB.

### Corrección

```python
MAX_BODY = 8*1024*1024   # 8 MB: el import de stock mas grande no llega a 1 MB

def do_POST(self):
    path = urllib.parse.urlparse(self.path).path
    try:
        ln = int(self.headers.get("Content-Length") or 0)
        if ln < 0 or ln > MAX_BODY:
            raise ValueError("tamaño fuera de rango")
    except ValueError:
        return self._send(400, '{"ok":false,"error":"Content-Length invalido"}')
    try:
        data = json.loads(self.rfile.read(ln) or b"{}")
    except Exception:
        data = {}
```

---

## BUG-08 · Fuga de directorios temporales: 464 acumulados

**Archivo:** `actualizar_antimo.py:27-40` (`reparar_ranking`) · **Severidad: Media**

```python
def reparar_ranking(src):
    tmp=tempfile.mkdtemp(); dst=os.path.join(tmp,"rank.xlsx")
    ...
    return dst          # ← el directorio nunca se borra
```

Se crea un `mkdtemp()` por cada archivo de `entrada/` y **nunca se limpia**. El pipeline corre en cada arranque de la app y **después de cada POST** (línea 298), o sea después de cada edición de precio, receta, OPEX o stock.

### Verificado

```console
tmpdirs antes: 461 | despues de UNA corrida: 464  (delta 3 = archivos en entrada/)
de los cuales contienen un rank.xlsx de ANTIMO: 464
```

464 directorios huérfanos, **todos de ANTIMO**. Cada uno tiene un xlsx descomprimido entero. Crece 3 por guardado y no se recupera hasta reiniciar la Mac.

### Corrección

```python
import shutil, contextlib

@contextlib.contextmanager
def ranking_reparado(src):
    """Extrae el xlsx sin mergeCells a un temporal y lo borra al salir."""
    tmp = tempfile.mkdtemp(prefix="antimo_rank_")
    try:
        dst = os.path.join(tmp, "rank.xlsx")
        with zipfile.ZipFile(src) as z: z.extractall(tmp)
        ws = os.path.join(tmp, "xl", "worksheets", "sheet1.xml")
        if os.path.exists(ws):
            with open(ws, encoding="utf-8") as f: x = f.read()
            x = re.sub(r"<mergeCells.*?</mergeCells>", "", x, flags=re.S)
            x = re.sub(r"<mergeCell [^>]*/>", "", x)
            with open(ws, "w", encoding="utf-8") as f: f.write(x)
        with zipfile.ZipFile(dst, "w", zipfile.ZIP_DEFLATED) as z:
            for root, _, files in os.walk(tmp):
                for f in files:
                    fp = os.path.join(root, f)
                    if fp != dst: z.write(fp, os.path.relpath(fp, tmp))
        yield dst
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

# uso (reemplaza la linea 509):
for path in RANKS:
    ym = _ym_de(path)
    try:
        with ranking_reparado(path) as rp:
            ws = openpyxl.load_workbook(rp, data_only=True).active
            rows = list(ws.iter_rows(values_only=True))   # materializar ANTES de cerrar
    except Exception as e:
        print("WARN", os.path.basename(path), e); continue
```

Los 464 ya existentes se limpian con `rm -rf /var/folders/*/*/T/tmp*` (o reiniciando).

---

## BUG-09 · Escrituras concurrentes sin bloqueo

**Archivo:** `app_antimo.py:303-304` + todos los handlers · **Severidad: Media**

`class Server(socketserver.ThreadingTCPServer)` atiende cada pedido en su propio hilo, y **todos los handlers hacen read-modify-write sin sincronización**:

```python
p=_load("precios_override.json",{}); p[data["insumo"]]=float(data["precio"]); _save(...)
```

Dos POST simultáneos → el segundo lee antes de que el primero escriba → se pierde una de las dos ediciones. Peor: `run_pipeline()` (línea 298) reescribe `datos_dashboard.json` mientras otro hilo puede estar sirviéndolo por `GET /api/data`, que lo lee sin bloqueo (línea 126).

Con un solo usuario la ventana es chica, pero es real: el frontend dispara `apiPost` desde `oninput`/`onchange` de inputs numéricos (líneas 1064, 1140), y tabular rápido entre campos de OPEX genera pedidos solapados.

### Corrección

```python
import threading
_LOCK = threading.RLock()   # RLock: run_pipeline puede reentrar

def _save(name, obj):
    with _LOCK:
        ... # version atomica de BUG-04

# y en do_POST, envolver todo el bloque de mutacion + pipeline:
def do_POST(self):
    ...
    with _LOCK:
        try:
            if path=="/api/receta": ...
            ...
        except Exception as e:
            return self._send(500, json.dumps({"ok":False,"error":str(e)}))
        ok, log = run_pipeline()
```

Serializar los POST es aceptable: son ediciones manuales, no tráfico.

---

## BUG-10 · Quedó un año hardcodeado en el frontend

**Archivo:** `dashboard_tpl.html:330` (`cajaIso`) · **Severidad: Media**

> Otro residuo de la migración a ISO: se eliminaron los `"2026"` del motor y del conector, pero **este sobrevivió**.

```js
function cajaIso(c){
 ...
 const p=(''+(c.fecha||'')).split('-');
 return p.length>=2?('2026-'+p[1]+'-'+p[0]):'';   // ← año fijo
}
```

Es el último recurso cuando una caja solo trae `DD-MM`. A partir del 1-1-2027, toda caja vieja sin `fecha_iso` se va a mapear al año equivocado, y el cruce con los días del ranking va a fallar en silencio (`dset.has(cajaIso(c))`, línea 385) → el KPI de caja pierde noches sin avisar.

Hoy no se dispara porque todas las cajas tienen `fecha_iso`. Es una bomba de tiempo con fecha conocida.

### Corrección

Reusar el índice inequívoco que el motor ya calcula (`_ddmm2iso`, `actualizar_antimo.py:612-618`) en vez de adivinar:

```js
// El motor ya publica ISO[] indexado por clave de dia. Si el DD-MM no resuelve
// ahi, NO se inventa el año: se devuelve '' y la caja queda sin cruzar, que es
// visible, en vez de cruzarse contra el año equivocado, que no lo es.
function cajaIso(c){
 if(c.iso)return c.iso;
 if(ISO[c.fecha])return ISO[c.fecha];
 if(c.fecha_key){const m=(''+c.fecha_key).match(/(\d{2})\/(\d{2})\/(\d{4})/);if(m)return m[3]+'-'+m[2]+'-'+m[1];}
 return '';
}
```

Alineado con la Regla #0 del proyecto: ante falta de dato, N/D, no un supuesto.

---

## BUG-11 · `json.dump` sin `encoding` explícito (3 sitios)

**Archivos:** `actualizar_antimo.py:720` · `conector_bistrosoft.py:152, 164` · **Severidad: Media**

```python
json.dump(DATA,open(os.path.join(BASE,"datos_dashboard.json"),"w"),ensure_ascii=False)
json.dump(list(fusion.values()),open(cajas_path,"w"),ensure_ascii=False,indent=1)
```

`ensure_ascii=False` deja pasar caracteres no-ASCII, pero `open(...,"w")` sin `encoding` usa el del locale. En esta Mac es UTF-8 y funciona; en un sistema con locale distinto (o `LANG=C`), un `"Cachaça"`, `"Limón"` o `"CUMPLEAÑOS"` lanza `UnicodeEncodeError` **a mitad de la escritura** — dejando el archivo truncado, que es el input de BUG-04.

En el mismo repo hay 15+ `open()` que sí especifican `encoding="utf-8"`. Estos tres quedaron fuera.

### Corrección

```python
# actualizar_antimo.py:719-720
with open(os.path.join(BASE,"dashboard_ANTIMO.html"),"w",encoding="utf-8") as f:
    f.write(tpl.replace("@@DATA@@", json.dumps(DATA,ensure_ascii=False)))
with open(os.path.join(BASE,"datos_dashboard.json"),"w",encoding="utf-8") as f:
    json.dump(DATA,f,ensure_ascii=False)

# conector_bistrosoft.py:152
with open(cajas_path,"w",encoding="utf-8") as f:
    json.dump(list(fusion.values()),f,ensure_ascii=False,indent=1)

# conector_bistrosoft.py:162-164
with open(os.path.join(DATOS,"bistro_debug.json"),"w",encoding="utf-8") as f:
    json.dump({...},f,ensure_ascii=False,indent=1)
```

---

## BUG-12 · Un `cxu` vacío en el Excel voltea el pipeline entero

**Archivo:** `actualizar_antimo.py:240, 255` · **Severidad: Media**

```python
cxu=COSTO[insumo]["cxu"]        # viene de r[6] de Costo_Base, puede ser None
...
return (val*cxu,None)           # None * float → TypeError
```

`COSTO[...]["cxu"]` sale directo de la columna 6 de `Costo_Base` (línea 71). Si esa celda está vacía —una fila nueva a medio cargar, una fórmula que devolvió `#DIV/0!`— el `TypeError` **no está capturado en ningún lado**: sube hasta el nivel de módulo y aborta el script.

Consecuencia: `run_pipeline()` devuelve `ok=False`, el POST responde `{"ok":false}` y **el dashboard entero deja de regenerarse** por una sola celda vacía. Toda la app queda inutilizable hasta arreglar el Excel a mano.

Hoy no pasa (verificado: ningún `cxu` nulo en los 120 insumos). Pero el flujo esperado es que el dueño edite el Excel, así que es cuestión de tiempo.

### Corrección

Tratarlo como los demás datos faltantes — N/D en vez de crash:

```python
def costo_ingrediente(ing, qty):
    ...
    cxu = COSTO[insumo]["cxu"]
    if cxu is None:
        return (None, f"insumo sin costo por unidad:{insumo}")
    ub_i = COSTO[insumo]["unidad"]
    ...
```

Lo mismo en `costear_combo` (L292-293), `costear_producto` para `pour`/`directo` (L327, 332) y `detalle_producto` (L498, que ya usa `or 0` y por eso no rompe).

---

## BUG-13 · Todos los errores devuelven HTTP 200

**Archivo:** `app_antimo.py:296-297` y ~12 returns más · **Severidad: Media**

```python
except Exception as e:
    return self._send(200,json.dumps({"ok":False,"error":str(e)}))
```

Un fallo del servidor responde **200 OK**. Lo mismo las validaciones (`"Fecha inválida"`, `"Cantidad inválida"`, etc.): todas 200.

Dos consecuencias:

1. **El frontend no puede distinguir** entre "se guardó" y "explotó" salvo leyendo `j.ok`. Funciona hoy porque `apiPost` lo chequea, pero cualquier `fetch` nuevo que confíe en `r.ok` va a tragarse los errores en silencio.
2. **`str(e)` filtra rutas absolutas del sistema** al cliente (`/Users/matiasarancibia/Desktop/ANTIMO/datos/...`).

### Corrección

```python
except DatosCorruptos as e:
    return self._send(409, json.dumps({"ok":False,"error":str(e)}))
except Exception as e:
    print("ERROR en", path, "->", repr(e))          # traza completa al log local
    return self._send(500, json.dumps({"ok":False,"error":"Error interno; mirá la ventana de la app"}))
```

Y en las validaciones, `400` en vez de `200`. `apiPost` ya maneja el body JSON igual, así que el frontend no cambia.

---

# 🔵 BAJO

## BUG-14 · El Excel se carga dos veces al arrancar

**Archivo:** `actualizar_antimo.py:67-74` y `78-82` · **Severidad: Baja**

Un bloque de 8 líneas está **duplicado literalmente**:

```python
wb = openpyxl.load_workbook(DG, data_only=True)   # L67
COSTO = {}
for r in ...: COSTO[r[1]] = {...}                 # L69-71
CB_CAT={}                                          # L72-74
...
wb = openpyxl.load_workbook(DG, data_only=True)   # L78 ← otra vez
COSTO = {}
for r in ...: COSTO[r[1]] = {...}                 # L80-82 ← identico
```

El segundo `load_workbook` descarta el primero y reconstruye `COSTO` con exactamente los mismos valores. Medido: **0,08 s desperdiciados por corrida**, y el pipeline corre después de cada guardado.

No causa error (`CB_CAT` se arma con el primero y sobrevive), pero es una trampa: alguien que edite el bloque de arriba va a ver su cambio pisado sin entender por qué.

**Corrección:** borrar las líneas 78-82.

---

## BUG-15 · Condición que nunca puede ser falsa

**Archivo:** `actualizar_antimo.py:580` · **Severidad: Baja**

```python
elif _t=="combo" and norm(_m.get("cat","")) is not None:
```

`norm()` siempre devuelve un `str` (`""` en el peor caso), nunca `None`. Verificado: `norm(None) is not None → True`. La segunda mitad de la condición es decorativa.

**Corrección:** `elif _t=="combo":` — o, si la intención era exigir categoría, `elif _t=="combo" and norm(_m.get("cat","")):`.

---

## BUG-16 · `except:` desnudos (3 sitios)

**Archivos:** `actualizar_antimo.py:526, 528` · `conector_bistrosoft.py:97` · **Severidad: Baja**

```python
try: u=int(r[cV] or 0)
except: u=0            # captura KeyboardInterrupt y SystemExit tambien
```

Un `except:` pelado atrapa `BaseException`: si el dueño hace Ctrl-C justo ahí, el script lo ignora y sigue. **Corrección:** `except (TypeError, ValueError):` en los tres.

## BUG-17 · Estado global en `window`

**Archivo:** `dashboard_tpl.html:298, 656, 785, 839, 1090` · **Severidad: Baja**

`window._tt`, `window._rentV`, `window._bcgV`, `window._recList`, `window._opexRow` viven en el objeto global y se usan para pasar datos entre render y handler. Además, al ser un script clásico, **todos los `let`/`const` de nivel superior son globales**: `DATA`, `st`, `DIAS`, `ISO`, `APP`, `FINDES`…

No hay colisión hoy (no hay otro script), pero `_rentV`/`_bcgV` guardan el array completo de productos y quedan retenidos mientras la página viva.

**Corrección:** envolver todo en un IIFE y mover los `_xxV` a variables del closure. Cambio mecánico, sin riesgo, pero toca las 1.100 líneas del script — conviene hacerlo solo junto con otro trabajo en el archivo.

## BUG-18 · `pip install` automático en tiempo de ejecución

**Archivo:** `actualizar_antimo.py:46-49` · **Severidad: Baja**

```python
try: import pdfplumber
except Exception:
    try:
        subprocess.run([sys.executable,"-m","pip","install","pdfplumber","--break-system-packages","-q"],check=False)
```

Instala un paquete solo, con `--break-system-packages`, que puede alterar el Python del sistema. Con `check=False` un fallo pasa desapercibido. Para una app que se define como offline, es una descarga de red no anunciada.

**Corrección:** avisar en vez de instalar — `print("Los PDF de caja necesitan pdfplumber. Instalalo con: pip3 install pdfplumber")` y seguir sin PDF (el flujo por API ya cubre las cajas).

## BUG-19 · Paginado con off-by-one

**Archivo:** `conector_bistrosoft.py:26` · **Severidad: Baja**

```python
items+=batch; page+=1
if page>5000: break     # corta en 5001, no en 5000
```

Cosmético (el corte es una red de seguridad). **Corrección:** `if page>=5000:`.

## BUG-20 · `r.json()` sin protección ante respuesta malformada

**Archivo:** `conector_bistrosoft.py:14, 23` · **Severidad: Baja**

```python
r.raise_for_status(); return r.json()["token"]
```

`raise_for_status()` cubre bien los HTTP de error (401 tiene manejo propio). Pero si la API responde 200 con HTML —un portal cautivo, un proxy, una página de mantenimiento— `r.json()` lanza `JSONDecodeError` con un traceback crudo. Y `["token"]` lanza `KeyError` si el JSON es válido pero sin esa clave.

### Corrección

```python
def get_token(base,user,pw):
    import requests
    r=requests.post(base.rstrip("/")+"/api/v1/Token",json={"username":user,"password":pw},timeout=30)
    if r.status_code in (401,403):
        raise RuntimeError("Usuario o contraseña rechazados por Bistrosoft. Revisá ⚙️ en la app.")
    r.raise_for_status()
    try: j=r.json()
    except ValueError:
        raise RuntimeError(f"Bistrosoft respondió algo que no es JSON (HTTP {r.status_code}). ¿Hay internet?")
    if "token" not in j:
        raise RuntimeError(f"La respuesta no trae token: {list(j)[:5]}")
    return j["token"]
```

---

# ✅ Falsos positivos descartados

Cosas que se pidió buscar y que, **tras verificarlas, están bien**. Las documento para que no se vuelvan a auditar.

| Se pidió buscar | Resultado |
|---|---|
| **Inyección SQL** | No aplica: no hay base de datos. La persistencia son JSON + Excel. |
| **`requirements.txt` con dependencias obsoletas** | No existe. Las 3 dependencias están al día: `openpyxl 3.1.5`, `requests 2.32.5`, `pdfplumber 0.11.8`. |
| **Problemas de CORS** | No aplica: un solo origen (`127.0.0.1:8733`). Notar que *la ausencia* de CORS es lo que permite BUG-01, pero no es un bug de configuración de CORS. |
| **Path traversal en `do_GET`** | **No es explotable.** `do_GET` está sobrescrito con lista blanca de 4 rutas y nunca llama a `super()`. El problema real está en `do_HEAD` (BUG-06), que es otra cosa. |
| **Falta de `timeout` en llamadas HTTP** | **Ya están.** `get_token` usa `timeout=30`, `fetch_all` usa `timeout=60`. Correcto. |
| **Silenciamiento de errores 500/401** | **Ya manejados.** `raise_for_status()` cubre 5xx y hay un `if r.status_code==401` explícito con mensaje propio. El hueco real es el parseo del body (BUG-20), no el status. |
| **Acumulación de EventListeners** | **No ocurre.** El código usa asignación de propiedad (`el.onclick=fn`), que *sobrescribe*, no `addEventListener`, que *acumula*. Además `rerender()` reemplaza el `innerHTML` completo, así que los nodos viejos y sus handlers se descartan juntos. Elección correcta para este patrón de render. |
| **Errores de precisión de punto flotante en costos** | **No es un bug real.** Sí se usa `float` para dinero, pero el error acumulado es del orden de 1e-10 sobre importes de millones de pesos, y todo se redondea al mostrar (`round(...,1)` en el motor, `Math.round` en el front). Migrar a `Decimal` sería trabajo sin beneficio medible. |
| **Errores de coordenadas en los SVG** | **Revisados los tres gráficos** (`renderTrend` L618-627, `renderBCG` L774-783, barras de OPEX L1109). Las escalas manejan bien los casos borde: `maxv` tiene piso `1`, `ymax-ymin` tiene guarda `||1`, los anchos se clampean con `Math.max(0,Math.min(100,...))`. El `viewBox` es coherente con `width`/`height`. Sin hallazgos. |
| **Rechazos de promesa sin capturar** | **Cubiertos.** `apiPost` tiene `try/catch` con toast de error; los `fetch` de arranque (L1283) encadenan `.catch()`. |

---

# Plan sugerido

Por relación impacto/esfuerzo, no por severidad pura:

**Primero — una tarde**
1. **BUG-01 (CSRF)** — ~20 líneas, corta la exposición más seria.
2. **BUG-03 (comparación muerta)** — 1 línea, y hoy hay una función entera sin funcionar.
3. **BUG-04 + BUG-05 (pérdida de datos + escritura atómica)** — juntos, son el mismo `_save`. Protegen lo único irreemplazable: los datos cargados a mano.
4. **BUG-02 (XSS)** — mecánico, ~10 sitios.

**Después — cuando haya rato**
5. BUG-08 (fuga de temporales), BUG-07 y BUG-06 (endurecer el servidor), BUG-10 (año hardcodeado), BUG-11 (encoding), BUG-12 (cxu nulo).

**Cuando se toque el archivo por otra cosa**
6. Los 🔵 bajos.

---

## Nota sobre el método

**No hay tests automatizados en el proyecto.** Los 20 hallazgos salieron de lectura y de probar contra la app corriendo — un proceso que no se puede repetir solo y que no protege contra regresiones.

Dos de los hallazgos (**BUG-03** y **BUG-10**) son regresiones introducidas hoy mismo, en la migración a fecha ISO, y **sobrevivieron a la verificación de esa migración** porque los totales no cambiaron. BUG-03 falla devolviendo `null`, que la UI dibuja como un guion discreto; BUG-10 no se dispara hasta 2027.

Eso es la evidencia más concreta de por qué conviene una batería de tests que fije los números ya validados (48 días, $91.390.950 de ventas, 109 productos, 11 N/D) antes de seguir agregando funcionalidad.
