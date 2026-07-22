# Verificación final — ANTIMO

**Fecha:** 22-07-2026 · **Datos:** 50 noches (14-05 al 21-07), 116 productos al momento de verificar (109 tras unificar nombres), 120 insumos, 51 cierres de caja

**Alcance:** fórmulas del tablero, costeo de los 116 productos, cruce contra Bistrosoft, casos borde y coherencia entre solapas.

---

## Resultado

| Verificación | Resultado |
|---|---|
| Costos recalculados desde el Excel | **98 de 98 coinciden** (0 diferencias) |
| Identidades del P&L y KPIs | **13 de 13 pasan** |
| Coherencia entre solapas | **11 de 11 pasan** |
| Casos borde | **7 de 7 sin NaN ni error** |
| Cruce contra la caja de Bistrosoft | **+0,73%** |

**No se encontró ningún error de cálculo.** Las dos únicas diferencias detectadas son de redondeo, ambas por debajo del 0,03%, y están explicadas abajo.

---

## 1. Costeo — recalculado desde cero

Recalculé el costo de **cada producto directamente desde `datos_general.xlsx`**, con una implementación independiente de la conversión de unidades. Esto es deliberado: si hubiera copiado las funciones del motor, un error del motor se habría replicado y ambos habrían coincidido estando mal.

| Tipo de producto | Verificados | Coinciden | Difieren |
|---|---|---|---|
| Receta y promo 2x1 | 61 | 61 | 0 |
| Combo | 4 | 4 | 0 |
| Pour, botella y directo | 33 | 33 | 0 |
| **Total** | **98** | **98** | **0** |

Coincidencia **al centavo** en los 98. Los 18 restantes son los productos sin costear (ver más abajo).

**Controles adicionales:**

- **Coherencia `precio ÷ cantidad = costo por unidad`** en los 120 insumos: 0 incoherencias.
- **Ningún pour rinde más que su envase** (un trago no puede servir más de lo que entra en la botella): 0 casos.
- **Productos que venden por debajo del costo:** 2 — BAILEYS (cuesta $10.506, se vende a $8.732, 142 unidades) y BUNKER (cuesta $14.170, se vende a $13.020, 244 unidades). **No es un error de cálculo**, es información real que el tablero ya muestra como alerta.

---

## 2. Fórmulas del tablero

Recalculé cada indicador por fuera de la app y comparé contra lo que muestra.

| Identidad verificada | Resultado |
|---|---|
| Ventas − costo de insumos = margen bruto | ✅ |
| Margen bruto − OPEX = resultado operativo | ✅ |
| Margen % = margen ÷ ventas | ✅ |
| Suma de ventas noche por noche = KPI de ventas | ✅ |
| Suma de unidades noche por noche = KPI de unidades | ✅ |
| Suma del gráfico diario = total de ventas | ✅ |
| El gráfico tiene exactamente una barra por noche | ✅ |
| OPEX = suma de (mensual ÷ 30) por día | ✅ |
| Ticket promedio = caja ÷ comensales | ✅ |
| Vender el punto de equilibrio da resultado exactamente 0 | ✅ |
| Noches de findes + noches de semana = total de noches | ✅ |
| Sin filtro, el prorrateo (`share`) vale 1 | ✅ |

### Prorrateo de OPEX con filtro activo

Es la parte más delicada del cálculo, porque el OPEX es del bar entero y no de una categoría. Verificado con PIZZAS:

| | Resultado |
|---|---|
| `share` = ventas filtradas ÷ ventas totales | ✅ |
| OPEX filtrado = OPEX total × share | ✅ |
| Resultado filtrado = margen − OPEX filtrado | ✅ |
| El % que representa el OPEX da igual con y sin filtro | ✅ |

Lo último es la prueba de que el prorrateo es proporcional y no distorsiona: cada categoría carga su parte exactamente según lo que vende.

---

## 3. Coherencia entre solapas

Que Resumen, Rentabilidad, Compras y Caja no se contradigan con los mismos filtros.

| Verificación | Resultado |
|---|---|
| Σ montos de Rentabilidad = KPI de ventas del Resumen | ✅ |
| Σ márgenes de Rentabilidad = KPI de margen | ✅ (dif. de redondeo, ver §5) |
| Matriz BCG: cada producto en uno y solo un cuadrante | ✅ |
| Tramos de margen (pierde/bajo/alto): partición completa, sin solapamiento | ✅ |
| Total de caja de la solapa = el usado en los KPIs | ✅ |
| Compras: consumo reconstruido con filtro = el del motor | ✅ (dif. 0,02%, ver §5) |

---

## 4. Casos borde

Donde suelen esconderse los errores. Ninguno produjo `NaN`, `Infinity` ni excepción:

| Caso | Resultado |
|---|---|
| Un solo día seleccionado | ✅ todos los valores numéricos |
| Filtro que no devuelve ningún producto | ✅ devuelve 0, no NaN |
| Punto de equilibrio con margen 0 (división por cero) | ✅ sin NaN |
| Matriz BCG sin productos | ✅ no rompe |
| Comparar un rango largo contra uno de un solo día | ✅ sin NaN en el P&L |
| Productos con 0 unidades vendidas | ✅ no aparecen |
| Última noche del historial, sola | ✅ |

---

## 5. Las dos diferencias encontradas (ambas de redondeo)

### 5.1 Margen bruto: $262 sobre $59.468.040 (**0,0004%**)

La app calcula el margen como `(precio promedio redondeado − costo) × unidades`, mientras que el cálculo exacto sería `monto − costo × unidades`.

Ejemplo real: STELLA 1L se vendió 569 veces a un promedio de $9.916,52. La app redondea a $9.917 y multiplica → $273 de diferencia sobre ese producto.

**No es un defecto.** El tablero muestra "Prom. venta $9.917" y el margen que informa es **coherente con ese número en pantalla**. Si calculara el exacto, el margen no cerraría con la multiplicación que cualquiera haría a mano mirando la tabla.

### 5.2 Lista de compras con filtro: $9.696 sobre $41.859.376 (**0,023%**)

Cuando hay un filtro activo, Compras reconstruye el consumo desde el desglose de cada producto, y ese desglose se publica redondeado a 2 decimales. El peor caso individual es el Medallón de Carne Vacuna, con 0,28% de desvío.

Sobre una lista de compras que se redondea a envases enteros, es irrelevante.

---

## 6. Cruce contra Bistrosoft

La verificación más fuerte, porque compara **dos caminos independientes** al mismo número: la suma de productos vendidos contra los cierres de caja del POS.

| | |
|---|---|
| Suma de productos | $106.230.450 |
| Suma de cierres de caja | $105.460.350 |
| **Diferencia** | **+0,73%** |

Consistente con el histórico (+0,74%). La diferencia se explica por descuentos e invitaciones, que la caja registra y el ranking de productos no.

**50 de 51 cajas cruzan** con un día del tablero. La que no cruza es un registro viejo del 01-06 por $28.000, de una noche que no existe en el ranking de ventas — no se contaba antes tampoco, así que no afecta ningún número.

> ⚠️ **Nota metodológica:** en un primer intento este cruce me dio **+27%** y estuve a punto de reportarlo como un problema grave. Estaba mal medido: usé un campo (`fecha_iso`) que 16 cajas antiguas no tienen. Con el campo correcto (`iso`, el que calcula el motor) da +0,73%. Lo dejo anotado porque es la trampa exacta en la que puede caer quien repita esta verificación.

---

## 7. Lo que esta verificación NO cubre

Es importante que quede explícito antes de la entrega. Todo lo anterior confirma que **las cuentas están bien hechas**, no que **los datos de entrada sean ciertos**.

Queda fuera del alcance de cualquier verificación automática:

- **Si las recetas reflejan lo que realmente se sirve.** Si el trago lleva 70 ml y la receta dice 60, todos los números van a cerrar perfecto y estar mal. Solo lo puede confirmar quien está detrás de la barra.
- **Si los precios de los insumos están al día.** Un gin que subió y no se cargó da un margen optimista, sin ninguna señal de error.
- **Si los nombres del POS apuntan al producto correcto.**
- **Si los datos que entrega Bistrosoft son correctos.**

---

## 8. Pendientes reales (no son errores de cálculo)

### 8.1 Productos sin costear: de 18 a 5 (resuelto el 22-07)

Tras esta verificación se mapearon 8 de los 18. **Ninguno era un producto nuevo**: el POS había
empezado a mandar otro nombre para productos que ya estaban costeados.

| Nombre del POS | Se unificó con | Evidencia |
|---|---|---|
| COCA 600CC | COCA | promedio de venta −0% |
| SPRITE 600CC | SPRITE | −3% |
| COCA ZERO 600CC | Coca Zero | −4% |
| FANTA 600CC | FANTA | −5% |
| POMELADA | LIMONADA POMELADA | 0% |
| SMIRNOFF + ENERGIZANTE | Smirnoff + Speed | −1%, confirmado por el dueño |
| ABSOLUT + ENERGIZANTE | Absolut + Speed | +6%, confirmado por el dueño |
| GIN TONIC | receta propia con Gin Brighton | confirmado por el dueño |

Las cuatro gaseosas ya figuraban como equivalencias confirmadas por el dueño en
`PRECIO_LISTA_ALIAS` (ahí en el sentido inverso: el nombre corto tomaba el precio de lista del
largo), así que el mapeo no es una suposición nueva.

`GIN TONIC` es el único que necesitó receta propia: la del Excel usa el ingrediente genérico
`Gin (Brighton/Beefeater)`, que resuelve al gin más barato. Se fijó Gin Brighton explícito, mismo
criterio que el resto de la familia (ver §7 de CLAUDE.md).

**Impacto:** $3.364.500 de ventas que antes no entraban en ningún cálculo ahora sí. Los productos
sin costear pasaron de **$4.903.000 (4,6%)** a **$1.538.500 (1,4%)**.

Después se cargaron dos más con datos del dueño:

| Producto | Cómo se resolvió | Resultado |
|---|---|---|
| COPA DE VINO | pour de **150 ml** de la misma botella de 750 ml que `BOTELLA VINO` | costo $1.200, margen 70% |
| JACK DANIELS | insumo nuevo (**750 ml a $55.000**) + pour de **60 ml** | costo $4.400, margen 48% |

La copa de vino tiene un control de sensatez que cierra: 5 copas de 150 ml cuestan $6.000 y la
botella entera $5.999.

⚠️ **JACK DANIELS queda con 48% de margen, muy por debajo del resto de los destilados** (Jagger
80%, Tanqueray 80%, Brighton 91%). No es un error de cálculo: se vende a $8.500, casi lo mismo
que el Gin Brighton ($8.837), pero el insumo cuesta 5,7 veces más. Vale la pena revisar el precio
de venta.

Por último se cargaron los tres combos de cumpleaños, que eran el 93% de lo que faltaba:

| Combo | Composición | Costo | Precio | Margen |
|---|---|---|---|---|
| Cumpleaños (10 pers.) | 5 pizzas + 2 papas | $40.283 | $75.000 | 46% |
| Cumpleaños 2 (20 pers.) | 10 pizzas + 4 papas | $80.566 | $150.000 | 46% |
| Cumpleaños Premium | 5 pizzas + degustación + picada Dorrego + 2 nuggets + 1 botella + 3 Speed | $79.473 | $220.000 | 64% |

Para cargarlos hubo que **extender el motor**: los combos solo aceptaban insumos crudos (botellas,
latas) y estos se componen de **productos** (pizzas, papas, picada). Ahora un componente puede ser
otro producto ya costeado, lo que mantiene el vínculo — si cambia la receta de la pizza, los tres
combos se actualizan solos. Multiplicar los ingredientes a mano habría dado el mismo número hoy y
habría quedado desactualizado a la primera modificación.

**Controles que cierran:**
- El Combo 2 es exactamente el doble del Combo 1: $80.566,293333 contra $80.566,293333, idénticos
  al sexto decimal (la diferencia de 10 centavos que aparece en el JSON es el redondeo a 1 decimal
  con que se publica el costo).
- Los componentes por separado suman el combo, en los tres casos.
- Un combo que se referencia a sí mismo da N/D en vez de colgar el pipeline (probado).

**Dos detalles del Premium, ambos confirmados por el dueño el 22-07:**
- "degustaciones de papas" (venía en plural y sin número) es **1 sola** `DEGUSTACION DE PAPAS`.
- La botella es a elección del cliente (gin Brighton o vodka Smirnoff) y se costea con la **más
  cara** — Brighton, $8.990 contra $8.800 — para no subestimar el costo. Diferencia real: $190.

**Quedan 5, todos de monto muy chico:**

| Producto | Unidades | Facturado | Qué falta |
|---|---|---|---|
| fernet botella | 1 | $50.000 | ver abajo |
| RABAS | 1 | $13.500 | receta |
| SPEED CHICO | 2 | $10.000 | si es la lata chica o el mismo Speed |
| ALBA | 1 | $8.000 | qué es |
| cuba libre | 1 | $8.000 | receta |

Total: **$89.500 (0,08% de las ventas)**, contra los $4.903.000 (4,6%) del inicio.

⚠️ **`fernet botella` merece una mirada:** ya existen `BOTELLA FERNET` ($70.000) y
`BOTELLA DE FERNET` ($65.000). Son tres nombres para lo que parece el mismo producto, a tres
precios distintos ($50.000 el tercero). Puede ser un descuento, una botella más chica, o algo mal
cargado en el POS — no se unificó porque la diferencia de precio es demasiado grande para asumir
que son lo mismo.


### 8.2 Dos productos que venden bajo costo

BAILEYS (−$1.774 por unidad, 142 vendidas) y BUNKER (−$1.150 por unidad, 244 vendidas). El tablero ya los muestra como alerta. Puede ser precio mal cargado en el POS, costo desactualizado, o una decisión comercial.

### 8.3 Gin Aconcagua

El Excel tiene `Gin Aconcagua` ($9.500) y `GIN ACONCAGUA VASO` ($9.000) como líneas separadas, pero el sistema los unifica en un solo producto y hoy toma $9.500. Resolverlo cambia las ventas históricas de ese producto, así que es una decisión del dueño.

---

## Conclusión

**El sistema calcula correctamente.** Los 98 productos costeables coinciden al centavo con el recálculo independiente desde el Excel, las 13 identidades del P&L cierran, las solapas son coherentes entre sí, no hay divisiones por cero ni NaN en ningún caso borde, y el cruce contra una fuente independiente da +0,73%.

Los números que muestra el tablero son confiables **en la medida en que lo sean las recetas y los precios cargados**, que es lo único que no se puede verificar por software.

Tras la verificación se cerraron 13 de los 18 productos sin costear (ver §8.1): quedan 5, que suman **$89.500 — el 0,08% de las ventas**, contra el 4,6% del inicio. A esta altura el tablero refleja el negocio prácticamente completo.
