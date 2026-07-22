# Verificación final — ANTIMO

**Fecha:** 22-07-2026 · **Datos:** 50 noches (14-05 al 21-07), 116 productos, 120 insumos, 51 cierres de caja

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

### 8.1 18 productos sin costear — $4.903.000 (4,6% de las ventas)

Aparecen en las ventas pero **no aportan margen**, así que la rentabilidad real es distinta de la que muestra el tablero. Los más grandes:

| Producto | Unidades | Facturado | Motivo |
|---|---|---|---|
| GIN TONIC | 153 | $1.533.000 | no está en Maestro |
| ABSOLUT + ENERGIZANTE | 85 | $1.263.000 | no está en Maestro |
| Combo cumpleaños | 12 | $900.000 | falta la composición |
| SMIRNOFF + ENERGIZANTE | 39 | $390.000 | no está en Maestro |
| Combo Cumpleaños Premium | 1 | $220.000 | falta la composición |
| Combo cumpleaños 2 | 1 | $150.000 | falta la composición |

Los tres primeros son productos que **ya existen con otro nombre** en el sistema (hay GIN TONIC con receta, y combos de vodka + energizante): probablemente sea cuestión de mapear el nombre del POS. Los Combos de cumpleaños requieren que el dueño defina qué incluyen.

El tablero ya avisa de esto en la alerta *"18 productos sin costear"* y en la solapa Caja › N/D. **No es un error del sistema: es información que falta cargar.**

### 8.2 Dos productos que venden bajo costo

BAILEYS (−$1.774 por unidad, 142 vendidas) y BUNKER (−$1.150 por unidad, 244 vendidas). El tablero ya los muestra como alerta. Puede ser precio mal cargado en el POS, costo desactualizado, o una decisión comercial.

### 8.3 Gin Aconcagua

El Excel tiene `Gin Aconcagua` ($9.500) y `GIN ACONCAGUA VASO` ($9.000) como líneas separadas, pero el sistema los unifica en un solo producto y hoy toma $9.500. Resolverlo cambia las ventas históricas de ese producto, así que es una decisión del dueño.

---

## Conclusión

**El sistema calcula correctamente.** Los 98 productos costeables coinciden al centavo con el recálculo independiente desde el Excel, las 13 identidades del P&L cierran, las solapas son coherentes entre sí, no hay divisiones por cero ni NaN en ningún caso borde, y el cruce contra una fuente independiente da +0,73%.

Los números que muestra el tablero son confiables **en la medida en que lo sean las recetas y los precios cargados**, que es lo único que no se puede verificar por software.

Antes de entregar, lo que más valor agrega es **cerrar los 18 productos sin costear**: son el 4,6% de las ventas y hoy el margen real del bar es mejor o peor que el que se ve, en una proporción desconocida.
