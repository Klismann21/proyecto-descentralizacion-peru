# Diagnóstico de calidad de datos — capa Gold

Diagnóstico sistemático de las 6 tablas de Gold, hecho antes de construir
los dashboards en Power BI, para dejar de corregir reactivamente cada vez
que un visual mostraba algo raro (así se encontraron, por accidente, los
casos de Sapallanga, Incahuasi y Jayanca — ver `Docs/reglas-de-negocio.md`).
Corrido contra el servidor real (`GoldFiscal`), solo lectura. Para cada
tabla se revisó: rangos imposibles, outliers extremos, saltos
interanuales >10x, nulos/ceros por columna y año, cobertura entre años, y
consistencia de montos compartidos entre tablas.

Estado de cada hallazgo: **implementado** (se agregó un flag),
**documentado como esperado** (se decidió no marcarlo, es comportamiento
legítimo del negocio), o **documentado, no corregido** (es un patrón real
pero no amerita una regla nueva todavía).

## Hallazgos críticos

### 1. Emisión predial implausiblemente alta — IMPLEMENTADO

`FLAG_EMISION_SOSPECHOSA` (ya existente) solo detecta emisión **baja**
(S/0–10,000). No había ningún chequeo para emisión anormalmente **alta**
respecto al propio historial del municipio. Caso extremo: Jayanca
(140304), 2024 — emisión salta de S/1.1M a **S/203.7M** en un año, con
recaudación de solo S/118K → cumplimiento de 0.00058 (prácticamente 0%),
sin que ningún flag se activara.

**Metodología del umbral**: se probaron tres criterios (salto respecto a
la **mediana del propio municipio**, entre sus años con emisión > 0, no
respecto al año anterior — un municipio grande y uno chico no pueden
compararse contra el mismo umbral en soles):

| Umbral | Filas marcadas |
|---|---|
| >20x | 4 |
| >50x | 4 (mismas filas — el ratio máximo real es 84.6x) |
| >100x | 0 (ninguna fila real llega a esa magnitud) |

Se eligió **>20x** (mismo resultado que 50x hoy, pero deja margen para
casos futuros de menor magnitud).

**Columna agregada**: `FLAG_EMISION_ATIPICA_ALTA BIT NOT NULL` en
`gold.CUMPLIMIENTO_PREDIAL` (calculada con `PERCENTILE_CONT(0.5)` sobre
`MON_EMISIONPREDIAL_AFECTO` particionado por `UBIGEO`, solo entre años con
emisión > 0) y en `gold.POTENCIAL_RECAUDACION` (heredada de
`CUMPLIMIENTO_PREDIAL`, no recalculada — mismo criterio que
`FLAG_CUMPLIMIENTO_ATIPICO`).

**Verificado tras cargar**: 4 filas marcadas en ambas tablas —

| UBIGEO | Municipalidad | Año | Emisión | Cumplimiento |
|---|---|---|---|---|
| 021701 | Recuay | 2024 | S/41,780 | 0.0% |
| 140304 | Jayanca | 2024 | S/203,745,074 | 0.00058% |
| 150716 | San Antonio | 2023 | S/16,465,963 | 20.0% |
| 151004 | Ayaviri | 2022 | S/6,430 | 0.0% |

Ninguna tenía `FLAG_CUMPLIMIENTO_ATIPICO` activo para ese año específico
(Ayaviri 2022 sí tenía `FLAG_EMISION_SOSPECHOSA` por su lado de emisión
baja en términos absolutos — ambos flags conviven sin contradicción, uno
mira el valor absoluto y el otro el salto relativo al propio historial).

**Caso límite verificado, deliberadamente sin marcar**: Municipalidad
Distrital de Chilca, Cañete (150505 — uno de los dos homónimos del
hallazgo #10) — la emisión sube de S/35.2M (2023) a S/85.5M (2024), 2.4x
respecto a su propia mediana (S/33.8M), con el cumplimiento cayendo de
21.9% a 1.3%. Está muy por debajo del umbral de 20x, así que
`FLAG_EMISION_ATIPICA_ALTA` no se activa — correctamente: un salto de
2.4x es sustancial pero no está en el rango de implausibilidad que
motivó el flag (los 4 casos marcados van de 53x a 85x). Se deja como
ejemplo explícito de "cerca del umbral, pero no cruza" para que quede
claro que el diseño no captura cualquier salto grande, solo los
extremos — casos como este quedan a criterio de un análisis manual, no
del flag automático.

### 2. `PERSONAL_AREA_TRIBUTARIA > PERSONAL_TOTAL` — IMPLEMENTADO

El personal del área tributaria es, lógicamente, un subconjunto del
personal total — no puede ser mayor. **52 filas** de `RENAMU` violan esto
(dato auto-reportado por la municipalidad, no es un bug del pipeline).
Consecuencia: **38 filas** con `PCT_PERSONAL_TRIBUTARIO > 100%` (caso
extremo: 44 personas en el área tributaria contra 1 persona de personal
total → 4400%).

**Columna agregada**: `FLAG_PERSONAL_INCONSISTENTE BIT NOT NULL` en
`gold.ESTRUCTURA_MUNICIPAL`, `CASE WHEN P32_1_T > P19D_T THEN 1 ELSE 0
END` — NULL en cualquiera de los dos lados nunca dispara el `CASE`, queda
en 0 por diseño (mismo criterio de no inventar un valor cuando falta
dato). No se corrigió `PCT_PERSONAL_TRIBUTARIO` — sigue calculándose
igual, ahora con el flag al lado para que el dashboard decida si lo
excluye.

**Verificado tras cargar**: 52 de 7,547 filas marcadas — coincide exacto
con el conteo del diagnóstico.

### 3. Cumplimiento entre 100% y 200% — DOCUMENTADO COMO ESPERADO, NO SE MARCA

`FLAG_CUMPLIMIENTO_ATIPICO` se activa recién sobre 2.0 (200%). Entre 1.0 y
2.0 hay **128 filas** (3.2% de `CUMPLIMIENTO_PREDIAL`) sin flag. **Decisión:
no se marca.** Cobrar más de lo emitido en el año es plausible cuando la
recaudación incluye cobro coactivo de deuda de años anteriores — no es un
error de dato, es un mecanismo de cobranza legítimo del sistema
municipal. Queda documentado para que quien construya un visual con techo
en 100% (un gauge, una barra de progreso) sepa que estos casos existen y
por qué no están marcados como atípicos.

### 10. Municipios homónimos sin desambiguar — IMPLEMENTADO

No salió del diagnóstico sistemático original — lo encontró el usuario
directamente en el dashboard: dos "MUNICIPALIDAD DISTRITAL DE CHILCA"
(UBIGEO 120107 en Huancayo, Junín, y 150505 en Cañete, Lima) aparecían
indistinguibles en un ranking por nombre. Cuantificado contra
`gold.CUMPLIMIENTO_PREDIAL`: **30 nombres de municipalidad** se repiten
con distinto UBIGEO (Santa Rosa aparece 6 veces, Pueblo Nuevo y San
Antonio 5 veces cada uno), afectando **79 municipios distintos** y
**299 filas** (7.6% de la tabla) — no es un caso aislado, es sistémico:
el Perú reutiliza nombres de distrito entre departamentos con
frecuencia.

**Columna agregada**: `MUNICIPIO_ETIQUETA VARCHAR(180) NULL` en
`gold.CUMPLIMIENTO_PREDIAL` (calculada) y `gold.POTENCIAL_RECAUDACION`
(mismo criterio, tomando `PROVINCIA_NOMBRE` del `LEFT JOIN` a
`silver.meta_predial` que esa tabla ya tenía para `MUNICIPALIDAD_NOMBRE`)
— concatena `MUNICIPALIDAD_NOMBRE + ' (' + PROVINCIA_NOMBRE + ')'`, ej.
`"MUNICIPALIDAD DISTRITAL DE CHILCA (CAÑETE)"`. Si `PROVINCIA_NOMBRE` es
`NULL` se deja el nombre solo, sin inventar un `"(SIN PROVINCIA)"` — en
la práctica no ocurre (`PROVINCIA_NOMBRE` tiene 0 nulos en
`silver.meta_predial`), pero la regla queda explícita por si cambia en
una recarga futura. No se tocó `MUNICIPALIDAD_NOMBRE` — se agregó una
columna nueva al lado, para que Power BI elija cuál mostrar según el
visual (un filtro puede seguir usando el nombre solo; un ranking o
leyenda debería usar la etiqueta).

**Verificado tras cargar**: 3,943 filas en ambas tablas (igual que
antes), 0 nulos en `MUNICIPIO_ETIQUETA`. Caso de control confirmado:
120107 → `"MUNICIPALIDAD DISTRITAL DE CHILCA (HUANCAYO)"`, 150505 →
`"MUNICIPALIDAD DISTRITAL DE CHILCA (CAÑETE)"`.

### 11. `PCT_CANON` cruzado desde `AUTONOMIA_FISCAL` — IMPLEMENTADO

Columna nueva pedida directamente (no salió del diagnóstico original):
`PCT_CANON` en `gold.ESTRUCTURA_MUNICIPAL`, canon sobre el total sin
deuda, tomado de `gold.AUTONOMIA_FISCAL` por `UBIGEO+ANO` (no
recalculado — `CAST(MONTO_CANON AS FLOAT) / NULLIF(MONTO_TOTAL_SIN_DEUDA,
0)`, `LEFT JOIN`, `NULL` si no hay match).

Al cargarlo por primera vez apareció un valor fuera de `[0,1]`: **7.17**
(717%) en Incahuasi (140203), 2022 — la misma fila que ya tiene
`FLAG_DENOMINADOR_NEGATIVO = 1` en `AUTONOMIA_FISCAL` (canon negativo
sobre denominador también negativo → cociente positivo pero sin
significado de negocio, la reversión contable de canon en SIAF ya
documentada). Se corrigió antes de cerrar la tarea: `PCT_CANON` queda en
`NULL` cuando `FLAG_DENOMINADOR_NEGATIVO = 1`, mismo criterio de fondo
que ya se aplica en el resto del proyecto — un denominador que no tiene
sentido de negocio no debe producir un ratio derivado con apariencia de
válido. (Nota: `RATIO_AUTONOMIA`, en `AUTONOMIA_FISCAL`, no sigue este
mismo tratamiento — ahí se dejó el valor real, -1.45, visible y marcado
con el flag en vez de en `NULL`, siguiendo el criterio general de
"marcar, no ocultar". Son dos decisiones distintas y ambas documentadas
donde corresponden — la de acá aplica solo a este ratio derivado
específico.)

**Verificado tras cargar**: 7,547 filas (sin cambio), 1 `NULL` (Incahuasi
2022), rango del resto en `[0.00007%, 98.9%]` — limpio.

## Hallazgos moderados (documentados, no corregidos)

### 4. `MONTO_DEUDA` negativo en `AUTONOMIA_FISCAL`
6 filas (200301, 080401, 190108, 101103, 150130, 150117), entre -S/4,019 y
-S/4M. No afecta `RATIO_AUTONOMIA` (la deuda está excluida del
denominador por diseño). Sin flag — no se implementó, queda como
candidato para una futura iteración si un visual de "deuda por
municipio" lo necesita.

### 5. Sobrecobro (`BRECHA_EMISION_RECAUDACION` negativa) — DOCUMENTADO, NO SE CORRIGE
521 filas (13.2%) de `CUMPLIMIENTO_PREDIAL` donde lo recaudado supera lo
emitido ese año — mismo mecanismo del punto 3 (cobro coactivo de deuda
antigua), visto en soles en vez de en ratio. Casos grandes: Callao
-S/27.5M (2025), San Román-Juliaca -S/13.5M, Chaclacayo -S/8.8M. **No es
un error, es cobranza legítima** — si Power BI muestra "brecha en soles"
como gráfico de barras, estas aparecerán negativas y necesitan una
nota/tooltip explicando el mecanismo, no un flag ni una exclusión.

### 6. `MONTO_RECAUDADO > MONTO_PIM` — DOCUMENTADO, NO SE CORRIGE
Patrón sistémico, no un caso aislado: 123 de 208 filas (59%) en
`REPARTO_TERRITORIAL`, y 11 de 12 (92%) en `REPARTO_NIVEL_GOBIERNO`
—incluido a nivel nacional. Es comportamiento esperado del sistema SIAF
(lo recaudado no está topado por el presupuesto modificado). **No
requiere flag** — requiere una nota explicativa fija en el dashboard,
dado que es la norma, no la excepción, para cualquier % de ejecución
presupuestal que se muestre.

### 7. Saltos de personal >10x en `ESTRUCTURA_MUNICIPAL`
10+ municipios con personal total saltando 13x-31x de un año a otro, pero
en conteos absolutos chicos (de 1-27 personas a 14-434). Parece
inconsistencia de auto-reporte en RENAMU (a veces cuentan solo planta
nombrada, a veces incluyen CAS/terceros). Sin flag — bajo impacto en
soles, no se implementó.

### 8. La categoría F también colapsó en 2022 — hallazgo de documentación, no de datos
`FLAG_GRUPO_SIN_REFERENCIA` marca correctamente el 100% de la categoría F
en 2022 (142/142 filas), un colapso tan severo como el de la categoría G
ya documentado. El flag funciona bien — era un vacío de documentación en
`Docs/reglas-de-negocio.md`, que solo mencionaba a G.

### 9. Cobertura incompleta entre años
- `CUMPLIMIENTO_PREDIAL` / `POTENCIAL_RECAUDACION`: 226 de 1,056
  municipios (21%) no tienen los 4 años completos (17 con 1 solo año, 21
  con 2, 188 con 3).
- `AUTONOMIA_FISCAL`: 2 municipios con cobertura parcial (130112: solo
  2023-2025; 160405: solo 2025).
- `ESTRUCTURA_MUNICIPAL`: 17 municipios ausentes en 2022 específicamente
  (1,874 filas vs 1,891 en los otros 3 años).

Cualquier comparación año contra año debe filtrar explícitamente por
"municipios presentes en todos los años" si quiere comparar el mismo
conjunto — de lo contrario compara poblaciones distintas sin decirlo.

## Hallazgos cosméticos (sin acción)

- `MONTO_PIA > MONTO_PIM` en 1 sola fila de 208 (Piura, Gobiernos
  Regionales, 2025) — un recorte presupuestal real (PIM 7.2% menor que
  PIA), plausible y aislado.
- Saltos interanuales de miles de veces en `AUTONOMIA_FISCAL`
  (`MONTO_RECURSOS_PROPIOS`, `MONTO_CANON`, `MONTO_DEUDA`) que son ruido
  estadístico de denominadores casi cero (ej. de S/0.12 a S/3,640 = ratio
  30,341x, diferencia real S/3,639 soles) — no material.
- Outliers en montos absolutos (Lima, San Isidro, Miraflores, Espinar con
  5,485 personas en planilla municipal) son escala genuina, no errores.

## Lo que se verificó limpio (no re-auditar)

Consistencia cruzada perfecta (0 diferencias) en los 4 cruces entre
tablas verificados:

- `POTENCIAL_RECAUDACION` ↔ `CUMPLIMIENTO_PREDIAL` (mismo
  `CUMPLIMIENTO_META_PREDIAL` y `CLASIFICACION` para cada UBIGEO-año).
- `ESTRUCTURA_MUNICIPAL` ↔ `CUMPLIMIENTO_PREDIAL` (mismo indicador y
  flag de atípico).
- `REPARTO_TERRITORIAL` ↔ `REPARTO_NIVEL_GOBIERNO` ↔ `silver.ingreso`
  (suma exacta al centavo, por nivel de gobierno y año).
- `AUTONOMIA_FISCAL` (sin `JOIN` a `gold.UBICACION`) ↔
  `REPARTO_TERRITORIAL` Locales (con `INNER JOIN` a `gold.UBICACION`) —
  confirma que ese `INNER JOIN` **no pierde ninguna fila** (0 UBIGEO sin
  match), el riesgo estructural que más preocupaba en este proyecto tras
  el bug de `gold.UBICACION` (ver `Docs/reglas-de-negocio.md`).

Además: `RATIO_AUTONOMIA` sin casos fuera de `[0,1]` sin flaggear (el
único caso, Incahuasi, ya cubierto); `CANTIDAD_INSTRUMENTOS_GESTION`
siempre en `[0,15]`; `PCT_PERSONAL_NOMBRADO` y `P75_CUMPLIMIENTO_GRUPO`
sin valores fuera de rango.

## Tabla resumen de flags en Gold (estado tras este diagnóstico)

| Flag | Tabla(s) | Qué marca | Filas |
|---|---|---|---|
| `FLAG_CUMPLIMIENTO_ATIPICO` | CUMPLIMIENTO_PREDIAL, POTENCIAL_RECAUDACION, ESTRUCTURA_MUNICIPAL | Cumplimiento > 2.0 | 58 |
| `FLAG_EMISION_SOSPECHOSA` | CUMPLIMIENTO_PREDIAL | Emisión entre 0 y 10,000 | — |
| `FLAG_DENOMINADOR_NEGATIVO` | AUTONOMIA_FISCAL | Denominador de autonomía negativo | 1 |
| `FLAG_GRUPO_SIN_REFERENCIA` | POTENCIAL_RECAUDACION | P75 del grupo NULL o 0 | 670 |
| `FLAG_EMISION_ATIPICA_ALTA` | CUMPLIMIENTO_PREDIAL, POTENCIAL_RECAUDACION | Emisión > 20x la mediana propia del municipio | 4 |
| `FLAG_PERSONAL_INCONSISTENTE` | ESTRUCTURA_MUNICIPAL | Personal área tributaria > personal total | 52 |
| `FLAG_SIN_REPORTE_RECAUDACION` | CUMPLIMIENTO_PREDIAL | Emitió (>0) pero recaudación total registrada en exactamente 0 | 46 / 35 / 259 / 262 (2022-2025) |

## Quiebre de recaudación 2024 — investigación cerrada

Hallazgo detectado por el usuario al revisar la serie nacional de
cumplimiento predial, no por el diagnóstico sistemático original.
Investigación completa, con las cuatro verificaciones que la sostienen.

### El patrón

La recaudación predial nacional se estancó/cayó justo cuando la emisión
seguía creciendo — el cumplimiento agregado (`SUM(MON_RECAUDACTUAL_TOTAL)
/ SUM(MON_EMISIONPREDIAL_AFECTO)` sobre toda `gold.CUMPLIMIENTO_PREDIAL`,
sin filtrar nada) cae de golpe en 2024 y no se recupera del todo en 2025:

| Año | Emitido | Recaudado | Cumplimiento |
|---|---|---|---|
| 2022 | S/2,674.0M | S/1,696.2M | **63.4%** |
| 2023 | S/2,898.2M | S/2,049.7M | **70.7%** |
| 2024 | S/3,266.0M | S/1,667.1M | **51.0%** |
| 2025 | S/3,154.8M | S/1,763.3M | **55.9%** |

### Verificación 1 — descarta efecto de composición

Se repitió la misma consulta restringida a los **830 municipios
presentes en los 4 años** (panel balanceado, excluye a los 226 con
cobertura parcial ya documentados en el hallazgo #9). El patrón es
prácticamente idéntico: 63.5% / 70.6% / **51.2%** / 56.1%. No son
municipios nuevos entrando al sistema los que arrastran el promedio —
son los mismos municipios de siempre, cayendo.

### Verificación 2 — descarta datos corruptos

Se repitió excluyendo las filas con `FLAG_CUMPLIMIENTO_ATIPICO` o
`FLAG_EMISION_ATIPICA_ALTA` activos (que incluye a Jayanca, cuya emisión
de S/203.7M en 2024 podría haber inflado artificialmente el "emitido"
nacional de ese año). El quiebre se mantiene: 63.4% / 70.5% / **54.5%** /
56.0% — la caída es un poco menos pronunciada sin esos casos (54.5% en
vez de 51.2%), pero sigue siendo una caída real de ~16 puntos frente a
2023, no un artefacto de un puñado de filas corruptas.

### La explicación — municipios que emiten pero no reportan cobranza

Se contó, por año, cuántos municipios tienen `MON_EMISIONPREDIAL_AFECTO
> 0` (sí emitieron) pero `MON_RECAUDACTUAL_TOTAL = 0` (recaudación
registrada en exactamente cero, no `NULL`, no denominador-cero — un
registro explícito de cero cobranza):

| Año | Emitió y no reportó cobranza | Emitió y sí reportó cobranza |
|---|---|---|
| 2022 | 46 | 475 |
| 2023 | **35** | **637** |
| 2024 | **259** | **482** |
| 2025 | 262 | 460 |

El grupo que "emite pero no reporta cobranza" pasa de 35 a 259
municipios entre 2023 y 2024 (7.4x) y se mantiene en 262 en 2025, y no
por incorporación de municipios nuevos al sistema (verificado con el
panel balanceado de la Verificación 1) — son municipios que ya estaban,
y que en 2024 dejaron de tener un registro de recaudación distinto de
cero. El grupo que sí reporta cobranza cae en paralelo, de 637 (2023) a
482 (2024) y 460 (2025).

### Conclusión — salvedad obligatoria para leer 2024-2025

**Los datos disponibles en este proyecto no permiten distinguir entre
una caída real de cobranza y un cambio en el registro/reporte del MEF.**
Ambos escenarios producen exactamente la misma huella en los datos: una
fila con emisión positiva y recaudación en cero. No hay ninguna columna
en `meta_predial` que indique "esta municipalidad no reportó" de forma
distinta a "esta municipalidad reportó cero" — es la misma ambigüedad ya
documentada para el denominador-cero de emisión (hallazgo "denominador
cero en cumplimiento de meta predial"), ahora del lado de la
recaudación.

**Implicación práctica**: cualquier indicador de cumplimiento predial
para 2024 y 2025 debe leerse con esta salvedad — la caída nacional no se
puede presentar como "los municipios dejaron de cobrar" sin la
advertencia de que podría ser, en la misma medida, "el MEF dejó de
recibir/consolidar el reporte de esos municipios". Se agregó
`FLAG_SIN_REPORTE_RECAUDACION` a `gold.CUMPLIMIENTO_PREDIAL` (marca,
no corrige) para que cualquier análisis o visual pueda excluir o
resaltar estos casos explícitamente en vez de mezclarlos en silencio con
cumplimiento genuinamente bajo.
