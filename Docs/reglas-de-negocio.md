# Reglas de negocio y arquitectura del proyecto

Documento principal del proyecto: arquitectura, decisiones de negocio
congeladas y estado actual. Se referencia desde `CLAUDE.md` en la raíz
del repo.

## Proyecto: Análisis de Descentralización Fiscal del Perú

### Qué es
Proyecto de portafolio de análisis de datos sobre la descentralización
fiscal-administrativa del Perú, usando datos públicos. Objetivo: pieza
fuerte de portafolio para conseguir trabajo como analista de datos.

### Arquitectura
Medallion: Bronze (crudo) -> Silver (limpio, tipado, en Parquet) -> Gold
(agregado para dashboards, en Parquet/SQL Server).
- Bronze -> Silver: Python + pandas.
- Silver -> Gold: SQL Server (T-SQL).

### Stack
- Ingesta y capa Silver: Python + pandas
- Transformación Silver->Gold (cruces, autonomía, agregaciones, benchmarks): SQL Server (T-SQL)
- Almacenamiento intermedio: Parquet
- Dashboards: Power BI (conectado a las tablas Gold de SQL Server)

### Fuentes de datos (llave común: UBIGEO)
1. Presupuesto y Ejecución de Ingreso (MEF) - CSVs 2022-2025
2. Seguimiento de la Meta del Impuesto Predial (MEF) - 2022-2025
3. RENAMU (INEI) - años 2022-2025, ZIP con módulos por año

Las decisiones y reglas de negocio del proyecto están congeladas en la
sección "Reglas de negocio (CONGELADAS)" más abajo.

### Estado actual
- Estructura de repo creada y subida a GitHub.
- Script de ingesta (`Src/ingesta/descargar_bronze.py`) descarga a Bronze
  las 3 fuentes (ingreso, meta_predial y RENAMU).
- Las 3 capas Silver están terminadas y verificadas:
  - `Data/silver/ingreso/ingreso.parquet` (2,744,843 filas, 11 columnas)
  - `Data/silver/meta_predial/meta_predial.parquet` (3,943 filas, 22 columnas)
  - `Data/silver/renamu/renamu.parquet` (7,547 filas, 117 columnas)
  - Verificado además el cruce por UBIGEO entre las 3 fuentes.
- Silver ya está cargado en SQL Server (base `GoldFiscal`, esquema
  `silver`), verificado fila por fila y monto por monto contra los 3
  Parquet de origen (ver "Carga de Silver a SQL Server" más abajo).
- La capa Gold ya arrancó: 2 dimensiones (`gold.UBICACION`,
  `gold.RUBRO`) y 2 tablas de hechos (`gold.AUTONOMIA_FISCAL` vía
  `gold.sp_cargar_autonomia_fiscal`; `gold.REPARTO_TERRITORIAL` vía
  `gold.sp_cargar_reparto_territorial`) están construidas y verificadas
  (ver subsecciones "Construcción de Gold" más abajo). Primer número
  real del proyecto: la autonomía fiscal promedio de las
  municipalidades peruanas (Gobiernos Locales, 2022-2025) es **11.75%**.
- Tabla de contexto `gold.REPARTO_NIVEL_GOBIERNO` (12 filas, Nacional/
  Regional/Local × 2022-2025) también construida — es la única pieza
  de Gold que lee Bronze directo, no Silver (ver subsección propia más
  abajo).
- `gold.CUMPLIMIENTO_PREDIAL` (3,943 filas, vía
  `gold.sp_cargar_cumplimiento_predial`) responde las preguntas 3 y 4
  del proyecto (cumplimiento por macrorregión y por categoría MEF).
  Hallazgos: Lima Metropolitana cumple muy por delante del resto
  (73% vs. 30-41%); la categoría MEF "C" tiene el mejor cumplimiento de
  las 7 (70%, más que "A"), rompiendo el patrón esperado A>B>...>G —
  aunque sí hay una caída clara de D a G (45%→22%, mediana de G = 0%).
  Investigado a fondo: "C" corresponde al 100% a Lima Metropolitana
  (P3 y P4 no son hallazgos independientes en el tramo alto); la
  hipótesis de que el canon explica peor cumplimiento se probó y se
  descartó (paradoja de Simpson — el efecto desaparece al controlar
  por categoría).
- `gold.POTENCIAL_RECAUDACION` (3,943 filas, vía
  `gold.sp_cargar_potencial_recaudacion`) responde la pregunta 5
  (benchmark contra pares): si cada municipalidad cobrara como el
  mejor 25% (percentil 75) de sus pares de la misma categoría MEF y
  año, el Perú recaudaría en promedio **S/ 464 millones más al año**
  en impuesto predial (S/ 1,857.6M acumulados 2022-2025). Hallazgo
  aparte, más duro que el número: en la categoría G, en 2022 el 100%
  de los municipios no emitió predial, y en 2024 tres de cada cuatro
  de los que sí emitieron cobraron literalmente cero — para esos
  municipios la pregunta no es "cuánto más podrían cobrar" sino "por
  qué no existe una administración tributaria funcionando" (conecta
  con la pregunta 6).
- `gold.ESTRUCTURA_MUNICIPAL` (7,547 filas, vía
  `gold.sp_cargar_estructura_municipal`) responde la pregunta 6, la
  última del proyecto (estructura municipal vs. cumplimiento predial).
  Con esto, **las 6 preguntas del proyecto están respondidas** — falta
  solo conectar Power BI a las tablas Gold.
  Hallazgo principal: ni tener un área tributaria (sí/no), ni el
  personal absoluto de esa área, ni la proporción de personal
  tributario sobre el total, sostienen una relación limpia con el
  cumplimiento una vez controlado por categoría MEF — en varias
  categorías grandes (E, F, G) el patrón va incluso en dirección
  contraria a lo esperado (más personal, cumplimiento igual o peor).
  Tercera hipótesis estructural que se prueba y no se sostiene (después
  del canon y el área tributaria binaria) — el hallazgo robusto sigue
  siendo el tamaño/categoría del municipio, no ninguna variable
  estructural individual medida hasta ahora.
- Siguiente paso: conectar Power BI a las tablas Gold — la
  construcción de datos del proyecto está completa.

### Cómo quiero trabajar
Explícame cada cambio que propongas antes de aplicarlo. Estoy aprendiendo
y necesito entender el porqué, no solo el código.

## Reglas de negocio (CONGELADAS — no cambiar sin justificar)

### Arquitectura de las capas
- Silver se construye en **Python + pandas**, NO en SQL. Silver limpia,
  tipa, arma UBIGEO, recorta columnas y guarda en Parquet.
- SQL Server entra recién en Silver -> Gold: cruces por UBIGEO entre las
  tres fuentes, cálculo de autonomía, agregaciones y benchmarks.
- Power BI se conecta a las tablas Gold de SQL Server.

### Parámetros de lectura por fuente
- ingreso y meta_predial: encoding UTF-8, separador coma (,).
- RENAMU: encoding utf-8-sig (trae BOM), separador punto y coma (;).

### Filtro de niveles de gobierno
- Existen 3 niveles: GOBIERNO NACIONAL, GOBIERNOS REGIONALES, GOBIERNOS LOCALES.
- En Silver se EXCLUYE solo 'GOBIERNO NACIONAL'.
- Se CONSERVAN Gobiernos Locales y Regionales, manteniendo intacta la
  columna NIVEL_GOBIERNO_NOMBRE.
- El recorte a solo 'GOBIERNOS LOCALES' se aplica por consulta en Gold:
  - Autonomía, predial y cruces con RENAMU -> solo Gobiernos Locales.
  - Vista de reparto (pregunta 1) -> Locales + Regionales.

### UBIGEO (llave común)
- En ingreso NO viene directo: se construye concatenando
  DEPARTAMENTO_EJECUTORA + PROVINCIA_EJECUTORA + DISTRITO_EJECUTORA.
- Estas columnas deben leerse SIEMPRE como texto (str/varchar), nunca como
  entero, para preservar los ceros a la izquierda (ej. '01'). El UBIGEO
  final tiene 6 dígitos.
- En meta_predial (rentas_esat_estadistica_atm) y en RENAMU el UBIGEO ya
  viene como columna directa; no se construye.

### Fórmula de autonomía fiscal
- Se usa MONTO_RECAUDADO (ejecución real), NO MONTO_PIA ni MONTO_PIM
  (que son presupuesto). MONTO_RECAUDADO es una columna anual única.
- numerador = SUM(MONTO_RECAUDADO) donde RUBRO_NOMBRE IN
  ('RECURSOS DIRECTAMENTE RECAUDADOS', 'IMPUESTOS MUNICIPALES')
- denominador = SUM(MONTO_RECAUDADO) de todos los rubros EXCEPTO la deuda.
- La deuda ('RECURSOS POR OPERACIONES OFICIALES DE CREDITO') se EXCLUYE del
  denominador. Justificación: la deuda es un pasivo (plata prestada que hay
  que devolver), no un ingreso; incluirla distorsionaría la autonomía.
  La deuda se conserva como dato, solo queda fuera de esta fórmula.
- El rubro 'FONDO DE COMPENSACION REGIONAL - FONCOR' (nuevo desde 2023) no
  afecta el numerador.

### Fórmula de cumplimiento de meta predial (PROXY, no es una meta oficial del MEF)
- Fuente: rentas_esat_estadistica_atm.csv (meta_predial). No existe en los
  datos una columna de "meta" oficial contra la cual medir cumplimiento
  (TIPO_META no discrimina entre municipalidades, ver más abajo), así que
  esta fórmula es una PROXY construida por nosotros: recaudación real
  sobre lo que se emitió (facturó) a los contribuyentes afectos.
- cumplimiento = (MON_RECAUDACTUAL_ORDIN + MON_RECAUDACTUAL_COAC) /
  MON_EMISIONPREDIAL_AFECTO
- MON_RECAUDACTUAL_ORDIN/COAC = recaudación del año corriente, vías
  ordinaria y coactiva. MON_EMISIONPREDIAL_AFECTO = monto emitido de
  predial a contribuyentes afectos (lo "esperado" a cobrar).
- TIPO_META se conserva como columna en Silver pero NO se usa en ningún
  análisis: es el número de meta del PI (Presupuesto por Resultados), no
  distingue entre municipalidades. La categoría real de cada municipalidad
  es CLASIFICACION (A-G), que viene en rentas_entidad_estado.csv.
- rentas_entidad_estado.csv no tiene diccionario de datos publicado por el
  MEF (se buscó y no existe) — TIPO_META y otras columnas de ese archivo
  quedan sin documentación oficial más allá de lo que se pudo inferir.

### Construcción de Silver de meta_predial
- Silver de meta_predial usa SOLO 2 de los 7 CSV de Bronze:
  rentas_esat_estadistica_atm.csv (montos + UBIGEO) y
  rentas_entidad_estado.csv (CLASIFICACION A-G). Los otros 5 (catálogo de
  formularios/preguntas/respuestas del cuestionario) no se procesan.
- Filtro MES_ESTADISTICA = 13: la columna trae 12 filas mensuales (1-12)
  MÁS una fila adicional 13 con el total anual (verificado: la suma de
  los 12 meses da exactamente el valor de la fila 13). Quedarse solo con
  MES_ESTADISTICA=13 evita contar el año dos veces. Cobertura verificada:
  el 100% de (SEC_EJEC, ANO_ESTADISTICA) tienen esa fila.
- Agregación por columna, NO por FORMULARIO_ID fijo ni por SUMA: se
  verificó que el número de FORMULARIO_ID que representa cada concepto
  (emisión, recaudación, saldos) cambia de ronda en ronda — ej.
  recaudación ordinaria fue FORMULARIO_ID=7 en las rondas 2021-2023, =11
  en la ronda 2024, =12 en la 2025. Por eso NO existe una asignación fija
  "columna X viene siempre de FORMULARIO_ID Y", y sumar montos entre
  formularios de un mismo (SEC_EJEC, ANO_ESTADISTICA) duplica la misma
  cifra reportada en dos rondas distintas (ver el caso de San Isidro más
  abajo). Regla aplicada, igual para las 9 columnas de monto: por cada
  (SEC_EJEC, ANO_ESTADISTICA) y cada columna por separado, se toma el
  valor de la fila con (ANO_APLICACION, PERIODO) más reciente entre las
  que tengan esa columna != 0, sin importar el FORMULARIO_ID. No se suma
  entre formularios.
- Desempate por título, SOLO cuando hay empate real: en 3 columnas
  (MON_RECAUDACTUAL_ORDIN, MON_RECAUDACTUAL_COAC, MON_RECAUDANTER_ORDI)
  hay 459/94/278 casos donde dos filas empatan en el (ANO_APLICACION,
  PERIODO) más reciente con valores distintos. Verificado al 100%: es
  siempre 1 fila cuyo formulario está catalogado como "ARBITRIOS" (otra
  tasa municipal, no predial, cruzando con rentas_formulario.csv por
  ANO_APLICACION+PERIODO+FORMULARIO_ID) + 1 fila de predial real. En el
  desempate se descarta la fila "ARBITRIOS".
  **Por qué el título NO se usa como filtro general** (caso real que lo
  confirma): se probó primero excluir de entrada cualquier fila titulada
  "ARBITRIOS" antes de aplicar la regla, y esto rompió un caso real — la
  recaudación predial 2024 y 2025 de San Isidro (UBIGEO 150131, ~S/ 19.7M
  y ~S/ 20M, verificable en rentas_esat_estadistica_atm.csv) está
  catalogada en rentas_formulario.csv como "4B. EMISIÓN INICIAL DE
  ARBITRIOS MUNICIPALES CORRIENTE" — un error de catalogación del MEF, no
  del dato — y San Isidro no tiene ninguna otra fila predial-titulada con
  valor para esos años. Excluir "arbitrios" a priori borraba por completo
  esa recaudación real. Por eso el título solo interviene para desempatar
  cuando ya hay una ambigüedad real entre dos formularios del mismo año,
  nunca como filtro previo. Si alguien toca esta lógica después, tiene
  que saber que ese es el motivo del diseño.
- Alcance temporal: se filtra por ANO_ESTADISTICA (no ANO_APLICACION) en
  2022-2025, para calzar con el alcance de Ingreso.
- Cruce con CLASIFICACION: se une por SEC_EJEC, buscando primero
  entidad_estado.ANO_APLICACION == esat.ANO_ESTADISTICA (match exacto);
  si no hay match, se prueba ANO_APLICACION = ANO_ESTADISTICA + 1, y si
  tampoco, ANO_APLICACION = ANO_ESTADISTICA + 2. Es un LEFT JOIN: nunca
  se descartan filas de montos por no tener CLASIFICACION.
  Justificación del fallback: se verificó que las municipalidades sin
  match exacto SÍ existen en rentas_entidad_estado.csv, solo que no
  reportaron ese año puntual — su registro más cercano en el tiempo
  suele estar 1 ó 2 años después (no es un desfase fijo, es reporte
  esporádico). Con el fallback, el match exacto cubre 81.6% (3,218 de
  3,943 filas), +1 suma 10.0% adicional (395 filas), +2 suma otro 8.2%
  (322 filas) — sin match queda solo 0.2% (8 filas), bajó de 18.4% con
  el join exacto solo.
- Columna ANO_CLASIFICACION: registra de qué ANO_APLICACION salió la
  CLASIFICACION de cada fila (puede ser igual a ANO_ESTADISTICA, o
  ANO_ESTADISTICA+1, o +2, o nula si no hubo match en ningún caso) —
  existe para que el origen de la categoría sea trazable, no asumido.
- TIPO_META se conserva como columna pero no se usa en ningún cálculo (no
  discrimina entre municipalidades, ver sección de la fórmula arriba).
- NUM_CONTRIPREDIO y NUM_PREDIOTOTAL NO se incluyen en Silver: se
  verificó que el MEF dejó de recolectarlas después de ANO_ESTADISTICA
  2019 (solo 262-263 filas no-cero en las 149,298 del archivo completo,
  todas de 2019) — quedan en 0 para todo el alcance 2022-2025, no hay
  nada que recuperar de esta fuente.
- El número de predios registrados NO está disponible en ninguna de las
  2 fuentes del proyecto: se confirmó que tampoco existe en RENAMU (se
  revisaron los 4 diccionarios de datos 2022-2025 completos, sin ninguna
  coincidencia de "predio"). Conclusión: no se podrá normalizar ningún
  indicador por número de predios — cualquier análisis que lo necesite
  tendrá que usar otra base (población, superficie, etc.) o quedar fuera
  de alcance.

### Hallazgo analítico: denominador cero en cumplimiento de meta predial
- ~34.8% de las filas de Silver meta_predial tienen MON_EMISIONPREDIAL_
  AFECTO = 0 (esa municipalidad no reportó emisión ese año estadístico),
  lo que deja CUMPLIMIENTO_META_PREDIAL en inf/NaN. Se investigó a fondo
  porque no es ruido aleatorio, es un patrón con lectura propia:
  - **Tendencia decreciente año a año**: 47.3% en 2022, 37.8% en 2023,
    30.6% en 2024, 23.5% en 2025. Sugiere mejora real en la tasa de
    reporte del formulario de emisión con el tiempo, no un problema
    puntual de un año — es en sí mismo un dato interesante para el
    análisis de cumplimiento (la cobertura de reporte también es una
    forma de "cumplimiento").
  - **No son siempre las mismas municipalidades**: de 1,056
    municipalidades en el dataset, 629 (59.6%) tienen al menos un año
    en cero, pero solo 102 (9.7% del total) están en cero en los 4 años
    2022-2025 — la mayoría de los ceros son intermitentes (reportan
    unos años sí y otros no), no un grupo fijo que nunca reporta.
  - Los 102 municipios "siempre en cero" son candidatos a investigar
    aparte en el análisis (¿no cobran predial, o simplemente nunca
    llenan ese formulario?) — no se investigó el motivo, solo se
    identificó el patrón.
  - Sigue sin corregirse ni descartarse en Silver: se documenta acá como
    contexto para cuando se use CUMPLIMIENTO_META_PREDIAL en Gold.

### Flags de outliers en meta_predial (se marcan, no se borran)
- FLAG_CUMPLIMIENTO_ATIPICO = CUMPLIMIENTO_META_PREDIAL > 2.0 (False en
  inf/NaN a propósito — esos casos ya son "sin dato", no "cumplimiento
  alto"; se identifican por separado con MON_EMISIONPREDIAL_AFECTO == 0).
- FLAG_EMISION_SOSPECHOSA = 0 < MON_EMISIONPREDIAL_AFECTO < 10,000 (un
  denominador implausible para una municipalidad — para referencia, los
  casos normales del dataset están en el rango de cientos de miles a
  cientos de millones de soles).
- Justificación: se encontró al menos un caso confirmado de corrupción de
  datos en la fuente que ninguna regla de agregación puede arreglar —
  Sapallanga (SEC_EJEC 301027), ANO_ESTADISTICA 2023: la misma emisión
  predial aparece como S/ 1,188,552 en la ronda 2023 y como S/ 1,188.55
  en la ronda 2024 (factor 1000 exacto, error de coma decimal entre
  rondas). Como la regla de agregación usa "la ronda más reciente",
  terminó tomando el valor corrupto — de ahí un CUMPLIMIENTO_META_PREDIAL
  de 665x para esa fila. No hay forma automática confiable de saber cuál
  de las dos cifras es la correcta, así que se marca con ambos flags para
  revisión manual en vez de intentar corregirlo.

### Filtro de partidas sin ejecución (Silver, fuente ingreso)
- En Silver, después de tipar montos, se excluyen las filas donde
  MONTO_PIA = 0 Y MONTO_PIM = 0 Y MONTO_RECAUDADO = 0 simultáneamente
  (partidas presupuestales sin ningún movimiento).
- Justificación: se detectó que, al recortar de 36 a las columnas finales
  de Silver (se pierden GENERICA/SUBGENERICA/ESPECIFICA), muchas filas
  que en Bronze eran partidas distintas-pero-en-cero quedaban idénticas
  entre sí, infladando el conteo de "filas duplicadas" sin ser un error
  real de los datos. Filtrarlas antes de guardar reduce ese ruido.
- Verificado que este filtro NO afecta la fórmula de autonomía fiscal:
  SUM(MONTO_RECAUDADO) es idéntica antes y después del filtro (el filtro
  solo puede excluir una fila si su MONTO_RECAUDADO ya es 0, así que
  nunca descarta un monto que aporte al numerador o denominador).
- Efecto secundario a tener en cuenta: el rubro 'CONTRIBUCIONES A FONDOS'
  desaparece por completo de Silver (todas sus filas eran 0 en los 4
  años). No afecta la fórmula, pero si se necesita el catálogo completo
  de rubros hay que consultarlo en Bronze, no en Silver.

### Construcción de Silver de RENAMU
- Cada año tiene ~1368-1388 columnas. NO se armoniza todo — se recorta a
  las variables relevantes para el proyecto (116 columnas finales, ver
  abajo), no un crosswalk mínimo de 5-10 como se pensaba originalmente:
  al revisar los 4 diccionarios de datos se encontró que los códigos que
  necesitamos son **idénticos en los 4 años** (a diferencia de
  meta_predial, donde el FORMULARIO_ID cambiaba de ronda en ronda), así
  que no hace falta ningún mapeo/crosswalk, solo concatenar y recortar.
- Parámetros de lectura: encoding utf-8-sig, separador `;` (regla ya
  congelada arriba). UBIGEO se lee como texto (dtype forzado), igual que
  en las otras fuentes.
- Columnas seleccionadas (con su justificación):
  - Identidad: `Año` (renombrada `ANO`), `Ubigeo`, `Departamento`,
    `Provincia`, `Distrito`, `Tipomuni`. RENAMU NO tiene una columna de
    nombre de municipalidad (a diferencia de meta_predial) — decisión
    tomada: NO se construye un nombre combinado en Silver, se dejan
    `Distrito`/`Provincia`/`Tipomuni` separados. El cruce entre fuentes
    es por UBIGEO, no por nombre; si se necesita un nombre para mostrar,
    se arma en Gold o en Power BI.
  - Personal: `P19D_T/NM/NH/CM/CH/LM/LH/VM/VH` (9 columnas: total,
    Nombrado D.L.276, Contratado D.L.276, D.L.728, CAS, cada uno por
    sexo) y los totales por categoría de puesto `P19_1_T` … `P19_6_T`
    (Funcionarios, Profesionales, Técnicos, Auxiliares, Obreros
    limpieza, Obreros otros).
  - Instrumentos de gestión: **las 90 columnas `P23_*`** (Plan de
    Desarrollo Municipal Concertado, Plan Estratégico Institucional, PDU,
    ROF, etc. — más de las 9 que se alcanzaron a leer la primera vez del
    PDF, hay 16 instrumentos en total, cada uno con varios sub-campos).
  - Administración tributaria: `P32` (¿tiene personal exclusivo del área
    de administración tributaria?) y `P32_1_T/_M/_H` (personal de esa
    área al 31 de diciembre del año anterior).
  - Catastro: `P17_8` (sistema informático de catastro implementado) —
    es el ÚNICO dato de catastro que existe en todo el proyecto (ni
    RENAMU ni meta_predial tienen si el catastro está digitalizado o
    actualizado), y es débil (mide si tienen un software, no el estado
    del catastro en sí). Se conserva igual porque no hay nada mejor.
- Tipado mixto, no todo a número: `P19D_*`, `P19_x_T` y `P32_1_T/_M/_H`
  se tipan como numérico (son conteos). `P23_*`, `P32`, `P17_8` y
  `Tipomuni` se dejan como texto (dtype `string`, no `str` simple, para
  no convertir los NaN reales en el string `"nan"`) — mezclan flags
  (1/2), texto libre ("¿por qué no tiene?") y números de resolución;
  forzarlos a número habría corrompido los campos de texto libre.
  Nota técnica: al concatenar los 4 años, pandas infiere el tipo de cada
  columna por archivo, y algunas de estas columnas quedan con una mezcla
  de int/str entre años, lo que rompe el guardado a Parquet si no se
  castea explícito a texto después de concatenar.
- Columna calculada: `PCT_PERSONAL_NOMBRADO = (P19D_NM + P19D_NH) /
  P19D_T` (proporción de personal nombrado/permanente sobre el total) —
  mediana real 0.133, la mayoría del personal municipal es contratado,
  no nombrado. División sin forzar: si `P19D_T` es 0 queda inf/NaN, se
  reporta (0.8% de las filas), no se corrige.
- Verificado tras construir: el 100% de los UBIGEO de RENAMU encuentran
  match con Ingreso en los 4 años. El match con meta_predial es más bajo
  (~50-55%), pero NO es un problema de la llave — visto desde el otro
  lado, el 99.7%-100% de los UBIGEO que meta_predial SÍ tiene cada año
  encuentran match en RENAMU; meta_predial simplemente cubre menos
  municipalidades en total (reporte esporádico ya documentado arriba).
- Verificado: no existen filas con `Tipomuni=3` (Centro Poblado) en
  ningún año — el archivo de RENAMU descargado solo trae municipalidades
  Provinciales y Distritales. La columna se conserva por si acaso, pero
  no hace falta filtrar Centros Poblados en este dataset.

### Carga de Silver a SQL Server
- Base de datos **`GoldFiscal`**, esquema **`silver`** (las 3 tablas
  cargadas son copia fiel del Parquet, todavía no son Gold). El esquema
  `gold` con las tablas transformadas se crea recién cuando se construyan
  las transformaciones T-SQL — no se creó antes por no tener aún
  definida su forma real (ver "Fuera de alcance" en
  `Docs/plan-carga-sql.md`).
- Autenticación: **Windows / Trusted Connection**, sin usuario ni
  contraseña — instancia local (`DESKTOP-Q808V1O\SQLEXPRESS`, instancia
  con nombre, no la instancia default). Config en `.env` (no
  versionado): `SQL_SERVER`, `SQL_DATABASE`, `SQL_DRIVER`,
  `SQL_TRUSTED_CONNECTION`.
- `TrustServerCertificate=yes` es obligatorio en la cadena de conexión:
  el driver ODBC 18 cambia el default de `Encrypt` a `yes` respecto al
  17, y sin este parámetro la conexión contra la instancia local (con
  certificado no confiable) falla por SSL.
- Montos en soles: **`DECIMAL(18,2)`**, no `FLOAT`. El Parquet los trae
  en `float64`, pero sumar dinero en punto flotante arrastra error de
  redondeo; `DECIMAL` es exacto para valores que se van a sumar en la
  fórmula de autonomía y en agregaciones de Gold. Verificado: los
  totales de `MONTO_PIA`/`MONTO_PIM`/`MONTO_RECAUDADO` y de las 9
  columnas `MON_*` de meta_predial coinciden exacto (diferencia 0.00)
  entre SQL Server y Parquet.
- Columnas calculadas por división (`CUMPLIMIENTO_META_PREDIAL`,
  `PCT_PERSONAL_NOMBRADO`) quedan como `FLOAT NULL`, con `inf`/`NaN`
  convertidos a `NULL` **solo al insertar** (`df.replace([np.inf,
  -np.inf], np.nan)` seguido de convertir todo `NaN` a `None` de
  Python). No es una corrección de datos: el significado ("sin dato
  para calcular esta métrica") es el mismo que en Silver, y las
  columnas `FLAG_*` que ya marcan estos casos no cambian — es solo un
  ajuste de formato, porque T-SQL `float` no soporta los valores
  especiales IEEE `inf`/`NaN`. Verificado: la cantidad de `NULL` en SQL
  coincide exacto con la cantidad de `inf`/`NaN` del Parquet (1,287 en
  meta_predial).
- Llaves: `silver.ingreso` usa una **llave sustituta**
  (`ID_INGRESO INT IDENTITY`) porque no tiene llave natural — hay
  26,293 filas duplicadas completas en el Parquet, partidas
  presupuestales distintas que quedan iguales tras el recorte de
  columnas de Silver (mismo fenómeno de "Filtro de partidas sin
  ejecución" más arriba). `silver.meta_predial` usa
  `(SEC_EJEC, ANO_ESTADISTICA)` y `silver.renamu` usa `(UBIGEO, ANO)`
  como llave primaria natural — verificado sin duplicados en ambos
  casos antes de cargar.
- Las 90 columnas `P23_*` de `silver.renamu` **no están escritas a mano**
  en el DDL: `SQL/ddl/02_crear_esquema_y_tablas.sql` tiene un marcador
  de texto en su lugar, que `Src/gold/cargar_silver.py` reemplaza en
  tiempo de ejecución leyendo los nombres reales de columna del Parquet
  de renamu (mismo criterio de prefijo `"P23_"` que ya usa
  `Src/silver/construir_renamu.py`), para que la tabla nunca se
  desincronice del dato real.
- Carga por lotes de **50,000 filas** solo para `silver.ingreso` (2.7M
  filas) — `meta_predial` y `renamu` se cargan en una sola pasada por
  ser chicas. `cursor.fast_executemany = True` en las 3 tablas (sin
  esto, cada fila viaja al servidor por separado; con 2.7M filas la
  diferencia es de horas a minutos).
- Carga idempotente: `truncar_tablas()` vacía las 3 tablas (`TRUNCATE
  TABLE`, no `DELETE`, para no arrastrar el costo de borrar fila por
  fila y para que `ID_INGRESO` reinicie su contador `IDENTITY` a 1) antes
  de insertar. Se puede re-ejecutar el proceso de carga las veces que
  haga falta sin duplicar filas ni violar llaves primarias.
- Creación de esquema (`crear_database()` + `rellenar_query()`) queda
  **separada** del flujo de recarga (`truncar_tablas()` + los 3
  `cargar_*()`, agrupados en `main()`): el `CREATE TABLE` no tiene
  resguardo `IF NOT EXISTS`, así que solo se corre una vez (setup
  inicial) o si se necesita rehacer el esquema desde cero — no en cada
  recarga de datos. Ver "Comandos" más abajo.
- Verificado end-to-end tras la carga completa: conteo de filas exacto
  en las 3 tablas, totales de montos exactos, `UBIGEO` conserva los
  ceros a la izquierda (no se corrompió a numérico), y el caso de
  referencia de San Isidro (`UBIGEO 150131`, 2024) coincide con el
  valor ya verificado en Parquet.

### Construcción de Gold: dimensión geográfica (`gold.UBICACION`)
- Grano: **una fila por provincia** (196 filas, verificado contra
  `silver.ingreso`), no por departamento. Se descartó un diseño previo
  de "departamento + provincia opcional (`NULL`)" — con ese diseño, un
  `JOIN` contra `silver.ingreso` con una condición permisiva
  (`CODIGO_PROVINCIA IS NULL OR ...`) hacía que una misma fila de
  `ingreso` (ej. Lima Metropolitana) matcheara **a la vez** contra la
  fila general del departamento Y contra la fila específica de la
  excepción, duplicando el monto en cualquier agregación por
  macrorregión. Se corrigió pasando a grano único (provincia), sin
  mezclar niveles de precisión en la misma tabla.
- `PREFIJO_UBIGEO VARCHAR(4)` (departamento+provincia, los primeros 4
  dígitos del UBIGEO) es la llave primaria natural — no hace falta
  llave sustituta porque, al ser grano único, cada fila es una
  provincia real y `NOMBRE_PROVINCIA` siempre tiene valor (`NOT NULL`).
- Carga: `INSERT ... SELECT DISTINCT` directo desde `silver.ingreso`
  (no valores escritos a mano) — se verificó primero que cada
  `PREFIJO_UBIGEO` tiene siempre el mismo par de nombres
  departamento/provincia en las 4 fuentes/años, sin inconsistencias de
  grafía que pudieran duplicar la llave primaria.
- `MACRO_REGION` se llena con un `UPDATE` + `CASE` por código de
  departamento (`LEFT(PREFIJO_UBIGEO,2)`), con 2 excepciones puntuales
  evaluadas ANTES que la regla general (el orden importa en un
  `CASE`): Lima capital (`1501`) y Callao (`0701`) → "Lima
  Metropolitana"; el resto del departamento Lima (`15`) → "Lima
  Provincias". El resto de los 23 departamentos se clasifica en
  Norte/Centro/Sur/Oriente por código. Verificado: los 24 departamentos
  + Callao quedan cubiertos sin huecos (como `MACRO_REGION` es
  `NOT NULL` y el `CASE` no tiene `ELSE`, cualquier código sin cubrir
  hubiera hecho fallar el `UPDATE` — no falló).
- Distribución final verificada: Norte 59, Sur 59, Centro 35, Oriente
  32, Lima Provincias 9, Lima Metropolitana 2 (196 provincias en total).

### Construcción de Gold: dimensión de rubro (`gold.RUBRO`)
- Clasifica los **7 valores reales** de `RUBRO_NOMBRE` que existen en
  `silver.ingreso` (verificado contra el servidor, no de memoria) en 4
  categorías: `RECURSOS_PROPIOS`, `TRANSFERENCIA`, `CANON`, `DEUDA`. Un
  quinto grupo teórico (`OTROS` / `CONTRIBUCIONES A FONDOS`) no se
  incluyó porque ese rubro no existe en Silver — ya está documentado
  arriba que el "Filtro de partidas sin ejecución" lo elimina por
  completo (todas sus filas eran 0).
- Dos banderas `BIT`, en vez de repetir listas `IN (...)` en cada
  consulta de autonomía: `ES_NUMERADOR_AUTONOMIA` (1 solo para
  `RECURSOS_PROPIOS`) y `ENTRA_EN_DENOMINADOR` (0 solo para `DEUDA`).
  La fórmula de autonomía fiscal queda expresada como dato consultable,
  no como lógica repetida y copiada en cada script.
- Verificado: cobertura 100% contra `silver.ingreso` (ningún
  `RUBRO_NOMBRE` de `ingreso` se queda sin clasificar), y la fórmula de
  autonomía calculada con las banderas reproduce exacto los totales ya
  conocidos: numerador `44,412,227,331.50` (RDR + Impuestos
  Municipales), denominador `228,261,343,063.96` (total recaudado
  menos deuda), autonomía global `19.46%`.

### Construcción de Gold: tabla de hechos de autonomía fiscal (`gold.AUTONOMIA_FISCAL`)
- Grano: **municipalidad-año** (`UBIGEO`, `ANO`), ~7,500 filas — colapsa
  los 12 meses de `MES_DOC` al sumar. Limitación documentada a
  propósito: esta tabla NO sirve para ver estacionalidad dentro de un
  año, solo para el indicador anual de autonomía. Si en algún momento
  hace falta estacionalidad, sería una tabla aparte, no se fuerza acá.
- Filtro: solo `NIVEL_GOBIERNO_NOMBRE = 'GOBIERNOS LOCALES'` (aplica la
  regla ya congelada en "Filtro de niveles de gobierno" más arriba) —
  los Gobiernos Regionales quedan fuera porque, por diseño, casi no
  generan ingresos propios; compararlos con Locales sería injusto.
- Se guardan los **componentes**, no solo el ratio final:
  `MONTO_RECURSOS_PROPIOS`, `MONTO_TRANSFERENCIAS`, `MONTO_CANON`,
  `MONTO_DEUDA`, `MONTO_TOTAL_SIN_DEUDA` — para que un dashboard pueda
  mostrar montos en soles además de porcentajes.
  `MONTO_TOTAL_SIN_DEUDA` NO incluye a `MONTO_DEUDA` (por diseño, la
  deuda queda fuera del denominador — ver "Fórmula de autonomía
  fiscal"); se guardan ambos como columnas separadas para no perder el
  dato de deuda, pero no se suman entre sí.
- `PREFIJO_UBIGEO` (4 dígitos) se guarda precalculado como columna,
  para unir directo con `gold.UBICACION` sin recalcular
  `LEFT(UBIGEO,4)` en cada consulta futura.
- `RATIO_AUTONOMIA = CAST(MONTO_RECURSOS_PROPIOS AS FLOAT) /
  NULLIF(MONTO_TOTAL_SIN_DEUDA, 0)` — queda `NULL`, no se excluye la
  fila, cuando el denominador es 0 (mismo criterio que
  `CUMPLIMIENTO_META_PREDIAL` en `meta_predial`). El `CAST AS FLOAT`
  fuerza división de punto flotante — dividir dos `DECIMAL` en T-SQL
  puede truncar precisión de forma no evidente.
- Se construye con **stored procedure**
  (`gold.sp_cargar_autonomia_fiscal`), no con un script de carga
  suelto — primer procedimiento del proyecto, patrón que se repite para
  el resto de las transformaciones Gold (a diferencia de las
  dimensiones, que son datos fijos cargados con `INSERT` directo). Usa
  un CTE (`WITH AGREGADO AS (...)`) para calcular las sumas una sola
  vez y reutilizarlas tanto en las columnas de monto como en el ratio,
  en vez de repetir la misma expresión `SUM(CASE...)` dos veces.
- Nota técnica: `CREATE OR ALTER PROCEDURE` debe ser la única sentencia
  de su batch (misma restricción que `CREATE SCHEMA`, ver "Carga de
  Silver a SQL Server") — el `.sql` tiene el `CREATE TABLE` y el
  `CREATE OR ALTER PROCEDURE` en el mismo archivo, pero quien lo
  ejecute necesita mandarlos como 2 batches separados, no uno solo.
- **Hallazgo y flag**: `FLAG_DENOMINADOR_NEGATIVO` (mismo espíritu que
  los flags de `meta_predial`) marca 1 sola fila de 7,564 — `UBIGEO
  140203` (Incahuasi, Ferreñafe, Lambayeque), año 2022 — donde el rubro
  Canon tiene montos negativos grandes concentrados en septiembre 2022
  (el mayor, -S/ 6,345,958), consistente con una reversión/corrección
  contable dentro del sistema SIAF del MEF (no es el patrón de
  corrupción de coma decimal visto en Sapallanga). Eso hace que el
  denominador y el ratio den negativos (`-1.45`) para esa fila puntual.
  Se conserva el dato real, marcado con la bandera, no se corrige ni se
  excluye.
- Verificado: 7,564 filas (municipalidad-año, Locales, 2022-2025);
  cobertura 100% de `RUBRO_NOMBRE` contra `gold.RUBRO` (el `INNER JOIN`
  no descarta silenciosamente ningún rubro); `RATIO_AUTONOMIA` nunca
  supera 1.0 fuera de la fila marcada (máximo 0.9869), confirmando que
  ninguna categoría quedó mal clasificada entre numerador y
  denominador; San Isidro con ratio ~0.96-0.98 (alto, coherente con ser
  uno de los distritos con más recaudación propia del país) contra
  distritos rurales de Amazonas con ratios desde ~0 hasta ~0.49.
- **Autonomía fiscal promedio de las municipalidades peruanas**
  (Gobiernos Locales, 2022-2025): **11.75%**, con tendencia levemente
  creciente año a año (11.2% en 2022 → 12.7% en 2025). La **mediana**
  por año, en cambio, ronda solo **6%** (0.058-0.064) — bastante más
  baja que el promedio, señal de asimetría: pocas municipalidades con
  autonomía alta (San Isidro y similares) empujan el promedio hacia
  arriba, mientras la mayoría de municipios queda bastante por debajo
  de esa cifra. Dato a tener en cuenta para cómo se presenta el
  indicador (usar mediana, o mostrar ambas, en vez de solo el promedio).
- El archivo `SQL/gold/02_crear_autonomia_fiscal.sql` termina con un
  tercer batch, `EXEC gold.sp_cargar_autonomia_fiscal;` — corre el
  archivo completo crea la tabla, define el procedimiento, Y lo ejecuta
  una vez, dejando la tabla ya cargada (no solo definida). Quien lo
  ejecute tiene que mandar los 3 bloques como batches separados (ver
  nota técnica de `CREATE OR ALTER PROCEDURE` arriba).

### Construcción de Gold: reparto territorial (`gold.REPARTO_TERRITORIAL`)
- Responde la pregunta de reparto: cómo se concentra el presupuesto y
  la recaudación en el territorio, con el corte entre Gobiernos Locales
  y Regionales. A diferencia de `gold.AUTONOMIA_FISCAL`, **no se filtra
  por nivel de gobierno** — acá interesan ambos, para poder compararlos.
- Grano: `(MACRO_REGION, NOMBRE_DEPARTAMENTO, NIVEL_GOBIERNO_NOMBRE,
  ANO)`, 208 filas. Se agregó `NOMBRE_DEPARTAMENTO` al grano (no solo
  `MACRO_REGION`) a propósito: con `MACRO_REGION` sola la tabla solo
  serviría para un gráfico agregado (~48 filas), pero la pregunta
  también pide un treemap por departamento — agregando por
  departamento, Power BI puede sumar hacia macrorregión desde la misma
  tabla, sin necesitar una segunda. Mismo principio que en Silver:
  agregar solo hasta donde se está seguro de no necesitar más detalle.
- Caso especial verificado: como `MACRO_REGION` se mantiene en el
  `GROUP BY` junto con `NOMBRE_DEPARTAMENTO`, el departamento "LIMA" se
  parte correctamente en sus 2 macrorregiones reales (Metropolitana y
  Provincias) sin mezclar ni perder montos entre ellas — verificado
  fila por fila contra el servidor.
- Columnas: `MONTO_PIA`, `MONTO_PIM` y `MONTO_RECAUDADO` (los 3, a
  diferencia de `AUTONOMIA_FISCAL` que solo necesitaba
  `MONTO_RECAUDADO`) — la pregunta habla de "presupuesto y
  recaudación", no de un ratio único. No se calculó ningún porcentaje
  de participación en SQL: el "% del total" no tiene un único
  significado fijo (¿del total nacional? ¿del año? ¿de Locales?),
  mejor resuelto como medida en Power BI que congelado en la tabla.
- `MACRO_REGION VARCHAR(30)` — ancho igual al de `gold.UBICACION` a
  propósito (estaba en `VARCHAR(20)` en un primer intento; "Lima
  Metropolitana" entra en 20, pero dejar anchos distintos para el mismo
  dato en dos tablas es un riesgo de truncamiento si el valor cambia).
- `JOIN` contra `gold.UBICACION` por `u.PREFIJO_UBIGEO =
  LEFT(i.UBIGEO,4)` — no usa `gold.RUBRO` (no hace falta distinguir
  rubros acá, solo geografía y nivel de gobierno).
- Verificado: cobertura 100% del `JOIN` (ningún prefijo de `ingreso`
  sin match en `gold.UBICACION`); `NIVEL_GOBIERNO_NOMBRE` solo trae
  `GOBIERNOS LOCALES`/`GOBIERNOS REGIONALES`, nada más; `SUM(MONTO_
  RECAUDADO)` de la tabla coincide exacto con `silver.ingreso`
  (`S/ 249,372,977,616.34`, diferencia 0.00) — confirma que
  `gold.UBICACION` funciona como pieza de unión sin perder filas.
- Mismo patrón de `EXEC` al final del archivo que
  `02_crear_autonomia_fiscal.sql` (ver arriba).

### Construcción de Gold: contexto por nivel de gobierno (`gold.REPARTO_NIVEL_GOBIERNO`)
- Objetivo: recuperar, solo como contexto (README + una tarjeta del
  dashboard, NO se integra a ninguna tabla de hechos), el dato de qué
  % del presupuesto/recaudación nacional maneja cada nivel de gobierno
  (Nacional / Regional / Local) — dato que se pierde en el resto del
  proyecto porque Silver excluye `GOBIERNO NACIONAL` a propósito
  ("Filtro de niveles de gobierno", regla ya congelada).
- **Única tabla Gold que lee Bronze directo, no Silver**: lee los
  mismos 4 CSV crudos que `construir_ingreso.py`
  (`Data/bronze/ingreso/*.csv`), pero **sin** aplicar el filtro que
  excluye Nacional — a propósito, porque acá ese nivel es justo el
  dato que se busca. No modifica ni llama a `construir_ingreso.py` ni
  a `cargar_silver.py`, es un script independiente
  (`Src/gold/cargar_reparto_nivel_gobierno.py`), para no arriesgar
  tocar Silver por accidente.
- **Python, no stored procedure** (excepción documentada al patrón
  general de Gold): T-SQL no puede leer un `.csv` sin `BULK INSERT`/
  `OPENROWSET`, que requiere permisos de sistema de archivos para la
  cuenta del servicio de SQL Server — nunca configurados en este
  proyecto, y no se justifican para una tabla de 12 filas de contexto.
  Python + pandas ya sabe leer estos CSV (mismo patrón que toda Silver).
- Grano: `(NIVEL_GOBIERNO_NOMBRE, ANO)`, 12 filas (3 niveles × 4 años,
  verificado sin huecos). Columnas: `MONTO_PIM` y `MONTO_RECAUDADO`
  (sin `MONTO_PIA`, no se pidió). Sin porcentaje guardado como columna
  — mismo criterio que `REPARTO_TERRITORIAL`, el `%` se calcula al
  vuelo (el script lo imprime, y también en Power BI).
- Verificado: 12 filas exactas; chequeo de sentido — el
  `SUM(MONTO_RECAUDADO)` de esta tabla es mayor que el de
  `silver.ingreso` en los 4 años (acá sí incluye Nacional, ~2x más
  grande); se confirmó que ninguna tabla existente (`silver.ingreso`,
  `gold.UBICACION`, `gold.RUBRO`, `gold.AUTONOMIA_FISCAL`,
  `gold.REPARTO_TERRITORIAL`) cambió de conteo ni de total.
- **Hallazgo**: `MONTO_PIM` (presupuesto asignado) y `MONTO_RECAUDADO`
  (ejecución real) cuentan historias distintas. En `MONTO_PIM`, Nacional
  y Locales quedan bastante parejos (~41-45% cada uno, Regionales
  ~14-17%). En `MONTO_RECAUDADO`, Nacional se despega más (hasta 49%
  en 2022) y Locales baja (~37-40%) — consistente con que el recaudado
  nacional incluye impuestos de base amplia y mejor tasa de cobro
  (IGV, renta), no comparable con la recaudación municipal
  (RDR/predial, más difícil de cobrar). Por este motivo se reportan
  las dos tablas de porcentaje por separado, no una combinada — decidir
  cuál usar en el README depende de si se quiere hablar de reparto de
  responsabilidad de gasto (`MONTO_PIM`) o de capacidad de cobro real
  (`MONTO_RECAUDADO`).

### Construcción de Gold: cumplimiento predial (`gold.CUMPLIMIENTO_PREDIAL`)
- Responde las preguntas 3 (¿quién cumple mejor la meta predial, Lima o
  las regiones?) y 4 (¿el cumplimiento depende de la categoría MEF?) con
  **una sola tabla** — comparten el mismo grano (municipalidad-año), es
  "cumplimiento cortado de dos formas distintas", no dos tablas.
- Grano: `(UBIGEO, ANO)`, 3,943 filas — igual a `silver.meta_predial`.
  Verificado antes de construir: `UBIGEO + ANO_ESTADISTICA` ya es único
  en `meta_predial` (0 combinaciones con más de un `SEC_EJEC`), así que
  no hace falta agregar/`GROUP BY`, es un `SELECT` directo con columnas
  calculadas — más simple que `AUTONOMIA_FISCAL` y
  `REPARTO_TERRITORIAL`, que sí necesitaban agregar.
- Es mayormente un **enriquecimiento**, no un cálculo nuevo: casi todo
  ya estaba en Silver (`CUMPLIMIENTO_META_PREDIAL`, `CLASIFICACION`,
  los flags). Lo que se agrega: `PREFIJO_UBIGEO` (para poder unir con
  `gold.UBICACION` en Power BI y sacar macrorregión), `MON_RECAUDACTUAL_
  TOTAL` (ordinaria + coactiva, precalculado), y
  `BRECHA_EMISION_RECAUDACION` (emisión menos recaudado, **en soles**)
  — un indicador derivado más tangible para un dashboard que un ratio
  (ej. San Isidro: "S/ 72.8M emitidos y no cobrados" pega más que
  "37% de cumplimiento").
- Los flags (`FLAG_CUMPLIMIENTO_ATIPICO`, `FLAG_EMISION_SOSPECHOSA`) y
  las filas con `CUMPLIMIENTO_META_PREDIAL = NULL` (denominador cero,
  ~35% de las filas) se **arrastran tal cual desde Silver, sin filtrar
  ni excluir** — mismo criterio de "reportar, no corregir" usado en
  toda la capa Silver y en `FLAG_DENOMINADOR_NEGATIVO` de
  `AUTONOMIA_FISCAL`. Que el dashboard decida qué hacer con ellas.
- **Sin `JOIN` a `gold.UBICACION` en la carga** — decisión deliberada,
  distinta a `REPARTO_TERRITORIAL`. La diferencia: `REPARTO_TERRITORIAL`
  necesitaba columnas que solo existen en la dimensión (`MACRO_REGION`,
  `NOMBRE_DEPARTAMENTO`), así que el `JOIN` era indispensable. Acá
  `PREFIJO_UBIGEO` sale directo de `LEFT(UBIGEO,4)`, no se necesita
  ninguna columna de la dimensión — unir solo para "validar" que exista
  sería usar un `INNER JOIN` como filtro implícito silencioso, el mismo
  patrón peligroso ya identificado con `gold.UBICACION` (ver más
  arriba). En cambio, el procedimiento hace la verificación de
  cobertura como **reporte**, no como filtro: un `PRINT` al final con
  la cantidad de `PREFIJO_UBIGEO` que no encontrarían match en
  `gold.UBICACION` (hoy da 0) — si algún día deja de dar 0, se nota en
  el log de la carga, sin que ninguna fila se pierda calladita.
- Verificado antes de construir: cobertura 100% —
  ningún `UBIGEO` de `meta_predial` se queda sin `PREFIJO_UBIGEO` que
  matchee en `gold.UBICACION`.
- Verificado tras cargar: 3,943 filas (igual a Silver); 1,287 `NULL`
  en `CUMPLIMIENTO_META_PREDIAL`, 58 `FLAG_CUMPLIMIENTO_ATIPICO`, 234
  `FLAG_EMISION_SOSPECHOSA`, 8 `CLASIFICACION` nula — los 4 números
  coinciden exacto con los ya conocidos de Silver; San Isidro 2024
  coincide con los valores ya verificados en sesiones anteriores.
- **Hallazgo P3 (cumplimiento por macrorregión)**: Lima Metropolitana
  muy por delante del resto — 73.1% de cumplimiento promedio, contra
  30.3%-40.6% en las demás 5 macrorregiones (bastante parejas entre
  sí). Coherente con la autonomía fiscal ya vista (Lima Metropolitana
  también lideraba ahí).
- **Hallazgo P4 (cumplimiento por categoría MEF A-G)**: NO sigue el
  patrón limpio A>B>C>D>E>F>G que se esperaba. La categoría **C**
  tiene el mejor cumplimiento de las 7 (70.0% promedio, 72.9% mediana
  — confirmado con ambas medidas, no es un sesgo de outliers en una
  categoría chica de 165 municipios), por encima incluso de A (48.1%).
  Sí hay una caída clara y consistente de D hacia abajo (45.1% → 30.9%
  → 22.5% → 21.7% en promedio; la mediana de la categoría G es
  directamente **0%** — más de la mitad de esos municipios no cobran
  casi nada de lo emitido).
- **Resuelto: por qué la categoría C rompe el patrón** — verificado
  contra el servidor: `CLASIFICACION = 'C'` corresponde al **100%** a
  `MACRO_REGION = 'Lima Metropolitana'` (168 de 168 filas, sin una sola
  excepción; la cifra de 165 de la tabla de arriba es solo por el
  filtro de atípicos/nulos de P4, no una discrepancia real). Es decir:
  **P3 y P4 no son dos hallazgos independientes en el tramo alto** — el
  "70% de la categoría C" y el "73.1% de Lima Metropolitana" son, en
  gran medida, el mismo dato visto por dos caminos. La clasificación
  del MEF no es una escala ordinal pura de tamaño; en el tramo alto se
  mezcla con territorio, y el efecto categoría y el efecto geografía no
  son separables ahí. Sí se verificó que el tramo bajo es distinto: las
  categorías D, E, F y G están genuinamente dispersas por las 6
  macrorregiones (ninguna concentrada en un solo territorio como pasa
  con C — Lima Metropolitana ni siquiera aparece en E, F ni G), así que
  el gradiente D→G sí es un hallazgo propio, no territorio disfrazado.
- **Hipótesis del canon, probada y refutada (paradoja de Simpson)**: se
  probó si la dependencia del canon explica peor cumplimiento predial
  (hipótesis: municipios con mucho canon "cobran menos por costumbre").
  Sin controlar por categoría, hay una diferencia agregada modesta
  (~5.5 puntos). Pero al controlar por `CLASIFICACION` (comparar
  "alta canon" vs. "baja canon" **dentro** de cada categoría, verificado
  con `gold.AUTONOMIA_FISCAL` unida a `gold.CUMPLIMIENTO_PREDIAL` por
  `UBIGEO`+`ANO`), el efecto **desaparece y hasta se invierte** según la
  categoría (A y D: canon alto cumple peor; B y E: canon alto cumple
  mejor; diferencias chicas en ambas direcciones). Conclusión: la
  correlación agregada era un efecto de composición — los municipios
  con mucho canon están sobrerrepresentados en las categorías chicas
  (E/F/G), y es el tamaño del municipio el que arrastra el promedio
  hacia abajo, no el canon en sí. **Hipótesis del canon descartada**;
  el determinante real sigue siendo el tamaño/categoría del municipio,
  no la fuente de sus ingresos.
- **Dato cruzado con autonomía fiscal**: San Isidro tiene 0.97 de
  autonomía fiscal (una de las más altas del país) pero solo 37% de
  cumplimiento predial — incluso el distrito más autónomo deja gran
  parte de lo emitido sin cobrar. Conecta directo con la pregunta 5
  (potencial de recaudación desaprovechado).
- **Valida la decisión de segmentación geográfica**: Lima Provincias
  (36.3%) queda casi idéntica al resto del país (30-41%), muy lejos de
  Lima Metropolitana (73.1%) — el mismo departamento, partido en dos,
  con comportamientos completamente distintos. Confirma que la decisión
  de separar Lima Metropolitana de Lima Provincias en la dimensión
  geográfica (en vez de tratar "Lima" como una sola unidad) era
  correcta: la brecha real es urbano-metropolitano vs. todo lo demás,
  no "capital vs. provincias" — un promedio de "Lima" combinado habría
  escondido esta diferencia.

### Construcción de Gold: potencial de recaudación (`gold.POTENCIAL_RECAUDACION`)
- Responde la pregunta 5, camino A (benchmark contra pares): comparar
  cada municipalidad contra el desempeño de sus pares, no contra un
  ideal absoluto.
- **Par = misma `CLASIFICACION` (A-G) y mismo `ANO`** — no solo misma
  categoría. Comparar contra una mediana/percentil mezclando los 4
  años penalizaría injustamente a los años tempranos si el cumplimiento
  general mejoró con el tiempo (cosa que ya sabíamos que pasa, ver
  "Hallazgo analítico: denominador cero" más arriba). El
  `PARTITION BY (CLASIFICACION, ANO)` en `PERCENTILE_CONT` refleja esto.
- **Percentil 75, no mediana ni promedio**, como referencia del grupo
  (`P75_CUMPLIMIENTO_GRUPO`, guardado como columna explícita, no solo
  calculado y descartado — para que cualquiera pueda auditar contra qué
  se comparó cada fila sin recalcular nada). Se descartó la mediana
  porque en categorías con mediana 0% (como G) generaría potenciales
  negativos sin sentido para casi todos los municipios del grupo — el
  P75 representa "el mejor 25% de tus pares", más ambicioso y evita
  ese caso degenerado (aunque no lo evita del todo, ver hallazgo de la
  categoría G más abajo).
- `POTENCIAL_NO_APROVECHADO = (P75_CUMPLIMIENTO_GRUPO × MON_EMISIONPREDIAL_AFECTO) − MON_RECAUDACTUAL_TOTAL`,
  en soles, no en ratio — mismo criterio que `BRECHA_EMISION_RECAUDACION`
  de `CUMPLIMIENTO_PREDIAL`. **No se fuerza a 0 cuando da negativo**: un
  municipio que ya supera al mejor 25% de sus pares muestra un número
  negativo real (información legítima, no se oculta).
- `NULL` en `POTENCIAL_NO_APROVECHADO` cuando `MON_EMISIONPREDIAL_AFECTO
  = 0` (no hay nada emitido, el concepto no aplica — multiplicar por
  cero daría un número engañoso) o cuando `P75_CUMPLIMIENTO_GRUPO` es
  `NULL` (grupo/año sin ningún dato limpio contra el cual comparar).
  Los 8 registros con `CLASIFICACION NULL` quedan sin grupo de
  referencia por diseño (`P75_CUMPLIMIENTO_GRUPO` forzado a `NULL` con
  un `CASE`, para que no formen su propio "grupo de sin-categoría").
- El percentil de referencia se calcula **solo con filas no atípicas**
  (`FLAG_CUMPLIMIENTO_ATIPICO = 0`) — un caso corrupto tipo Sapallanga
  no debe mover el percentil de nadie. `PERCENTILE_CONT` ignora los
  `NULL` del grupo automáticamente (atípicos marcados + denominador
  cero), sin necesidad de filtrarlos aparte con `WHERE`.
- **`FLAG_GRUPO_SIN_REFERENCIA`** (`P75_CUMPLIMIENTO_GRUPO IS NULL OR
  P75_CUMPLIMIENTO_GRUPO = 0`): se agregó después de encontrar que,
  para la categoría G, el cambio de mediana a P75 **no evitaba del
  todo** el problema que buscaba evitar (ver hallazgo abajo) — se marca
  en vez de excluir la fila o de ocultar el número, mismo criterio de
  "reportar, no corregir" que el resto del proyecto. 670 de 3,943 filas
  quedan marcadas.
- **Hallazgo, categoría G — el más duro del proyecto hasta ahora**: en
  2022, el **100%** de los 143 municipios de categoría G no emitió
  predial (`CUMPLIMIENTO_META_PREDIAL` nulo en todos, de ahí que
  `P75_CUMPLIMIENTO_GRUPO` sea `NULL` ese año — no hay ni un dato limpio
  para calcular nada). En 2024, de los 98 municipios G con dato limpio,
  **75 (77%) tienen `CUMPLIMIENTO_META_PREDIAL` exactamente 0** — por
  eso el propio percentil 75 también da 0, no es un artefacto del
  estadístico elegido, es que ni el mejor 25% de sus pares cobra algo.
  Para estos municipios, la pregunta 5 ("¿cuánto más podrían cobrar?")
  no tiene respuesta significativa — la pregunta real es "¿por qué no
  existe una administración tributaria funcionando?", que conecta
  directo con la pregunta 6 (cruce con estructura municipal de RENAMU:
  `P32`, personal, instrumentos de gestión).
- **Resultado principal**: si cada municipalidad cobrara como el mejor
  25% de sus pares de su misma categoría y año, el Perú recaudaría en
  promedio **S/ 464,409,927.92 más al año** en impuesto predial
  (S/ 1,857,639,711.67 acumulados 2022-2025) — calculado sumando solo
  las brechas positivas, excluyendo filas `FLAG_GRUPO_SIN_REFERENCIA`
  y `FLAG_CUMPLIMIENTO_ATIPICO`. El mayor potencial individual es San
  Isidro 2025 (S/ 57.1M) — el resto del top 10 son casi todos otros
  distritos de Lima Metropolitana, coherente con ser los que más
  emiten en soles absolutos aunque no sean los peores en % relativo.

### Construcción de Gold: estructura municipal (`gold.ESTRUCTURA_MUNICIPAL`)
- Responde la pregunta 6, la última del proyecto: ¿qué tienen en común
  las municipalidades que recaudan mejor? Cruce entre estructura
  (RENAMU: personal, área tributaria, instrumentos de gestión) y
  cumplimiento predial (`meta_predial`).
- **`LEFT JOIN` desde `silver.renamu`, no `INNER`**: RENAMU cubre
  ~1,890 municipios/año, `meta_predial` solo ~1,000 — un `INNER JOIN`
  descartaría justo a los municipios que nunca reportan al MEF, que son
  los más relevantes para "¿por qué no cobran?". Con `LEFT JOIN` se
  conservan las 7,547 filas de RENAMU completas, con `CLASIFICACION`/
  `CUMPLIMIENTO_META_PREDIAL` en `NULL` cuando no hay match.
- `TIENE_DATO_PREDIAL` (bandera de si hubo match en `meta_predial`, sin
  importar si `CUMPLIMIENTO_META_PREDIAL` en sí dio `NULL` por
  denominador cero) — distingue "nunca reportó al MEF" de "reportó pero
  no cobró nada", dos historias distintas que se confirmó que sí tienen
  perfiles diferentes (ver hallazgo abajo).
- **Conteo de instrumentos de gestión sobre 15 columnas, no 16**:
  `P23_4` (Acondicionamiento Territorial de Nivel Provincial) se
  excluye del conteo — verificado contra el diccionario oficial de
  RENAMU ("Sólo Municipalidad Provincial") y contra los datos
  (`Tipomuni=1` siempre responde esa pregunta, `Tipomuni=2` siempre la
  deja en blanco, 100% limpio) — no es un dato faltante, es que la
  pregunta no aplica a distritos. Contarla igual para todos habría
  penalizado injustamente al 90% de las municipalidades (las
  distritales) por algo que no les corresponde tener.
- **`1 = Sí` confirmado contra el diccionario real** (no asumido) para
  `P23_*` y `P32`. Excepción importante para no repetir en otra parte
  del proyecto: **`P17_8` (catastro digital) usa una convención
  distinta** — `0 = No`, `8 = Sí` (el valor "Sí" es el número de la
  pregunta, no `1`). Se guardó tal cual viene en `TIENE_CATASTRO_
  DIGITAL`, sin reinterpretar — cualquier consulta futura sobre esa
  columna tiene que usar `= '8'`, no `= '1'`.
- **Desfase temporal documentado, no corregido**: `P32_1_T` (personal
  del área tributaria) y `PCT_PERSONAL_NOMBRADO` miden personal al 31
  de diciembre del **año anterior** al de la encuesta RENAMU (regla de
  la propia encuesta, confirmado en el diccionario). Es decir, la fila
  con `ANO=2024` describe estructura de personal de 2023. Es
  intencional y hasta conviene para este análisis (la estructura
  instalada precede al resultado de cobranza), pero quien compare
  "estructura vs. cumplimiento del mismo `ANO`" está en realidad
  comparando estructura de un año contra cobranza del siguiente.
- `PCT_PERSONAL_TRIBUTARIO = PERSONAL_AREA_TRIBUTARIA / PERSONAL_TOTAL`
  — variable derivada para normalizar por tamaño de municipio (2
  personas de 200 empleados no es lo mismo que 2 de 20).
- `FLAG_CUMPLIMIENTO_ATIPICO` se arrastra de `meta_predial` — **crítico
  para esta tabla**: sin excluirlo, los 58 casos atípicos (tipo
  Sapallanga) inflan los promedios de categorías chicas hasta valores
  imposibles (se detectó un promedio de 8.66 en una prueba inicial,
  matemáticamente imposible dado que el máximo real es 0.99 — el bug
  fue no incluir esta bandera en la tabla desde el diseño original).
- **Hallazgo 1 (grupos de cobranza)**: los municipios que **nunca
  reportan al MEF** tienen mucha menos área tributaria (43.6%) que
  cualquier otro grupo (76-93% en el resto) — coherente con "no existe
  administración funcionando". Pero entre "cobranza baja" y "cobranza
  aceptable" el `%` con área es casi idéntico (93.2% vs. 92.0%); lo que
  sí difiere fuerte es el personal dentro del área (9.75 vs. 24.67,
  casi el triple) — la existencia formal del área no distingue, el
  tamaño real sí parece importar en este corte sin controlar.
- **Hallazgo 2, tercera hipótesis estructural refutada**: al controlar
  por `CLASIFICACION` (mismo método que con el canon), **ni tener área
  tributaria (sí/no), ni el personal absoluto del área, ni la
  proporción de personal tributario** sostienen una relación limpia y
  consistente con el cumplimiento. En las categorías con muestras
  grandes y confiables (E, F, G), más personal en el área correlaciona
  con cumplimiento **igual o peor**, no mejor (ej. categoría E: 35.3%
  sin área → 27.4% con área de 5+ personas). Solo categoría B muestra
  una tendencia positiva débil. No se sobrevende esta variable como
  explicación — mismo criterio que con el canon: se prueba, no se
  sostiene, se documenta el resultado real, no el esperado.
- **Conclusión acumulada de las preguntas 4-6**: de tres hipótesis
  estructurales probadas con controles apropiados (dependencia del
  canon, existencia de área tributaria, tamaño/proporción de esa área),
  **ninguna sobrevive** de forma limpia. El único patrón robusto en
  todo el proyecto sigue siendo el tamaño/categoría MEF del municipio
  — que en el tramo alto se confunde con geografía (categoría C =
  Lima Metropolitana) y en el tramo bajo (D-G) es un efecto genuino y
  disperso geográficamente. Las variables estructurales medidas hasta
  ahora (personal, área, instrumentos) no explican, por sí solas, la
  diferencia en cumplimiento dentro de un mismo grupo de tamaño.

### Segmentación geográfica
- Una sola columna con: Lima Metropolitana / Lima Provincias / Norte /
  Centro / Sur / Oriente. Cada departamento cae en exactamente una.

### Lecciones aprendidas (qué se haría distinto empezando de nuevo)
- **Llave de `gold.RUBRO` por nombre, no por código**: el `JOIN` entre
  `silver.ingreso` y `gold.RUBRO` compara `RUBRO_NOMBRE` (texto). Funciona
  hoy (cobertura verificada al 100%), pero es una llave frágil — un
  cambio de redacción del MEF en un año futuro (ya pasó con
  `FORMULARIO_ID` en meta_predial) haría caer ese rubro del `JOIN` en
  silencio. Mejor: preservar o generar en Silver un código estable de
  rubro y usarlo como llave; el nombre debería ser solo un atributo
  descriptivo de la dimensión.
- **Grano decidido antes de escribir el `CREATE TABLE`, no durante**: el
  bug de `gold.UBICACION` (ver esa sección) no fue un error de sintaxis,
  fue no responder "¿una fila por departamento o por provincia?" antes de
  diseñar la tabla. Un grano mal definido se propaga como un número
  "razonable pero incorrecto" — el tipo de error más difícil de detectar,
  porque no rompe nada, solo da mal el resultado.
- **Diccionario de datos leído antes de escribir la transformación, no
  después de que algo falle**: los casos de `P23_4` y `P17_8` (ver
  "Construcción de Silver de RENAMU") se resolvieron bien, pero de forma
  reactiva — un resultado raro llevó a revisar el diccionario recién en
  ese momento, cuando ya estaba disponible desde el principio. Leerlo
  completo antes de la primera línea de transformación evita escribir una
  versión con el supuesto equivocado para corregirla después.
- **Convención de "marcar con flag, no corregir en silencio" declarada
  desde el día uno**: terminó siendo uno de los criterios más
  consistentes del proyecto (`FLAG_CUMPLIMIENTO_ATIPICO`,
  `FLAG_EMISION_SOSPECHOSA`, `FLAG_DENOMINADOR_NEGATIVO`,
  `FLAG_GRUPO_SIN_REFERENCIA`), pero se adoptó caso por caso en vez de
  fijarse una sola vez como regla general al inicio del proyecto.

## Comandos

Instalar dependencias:
```
pip install -r requirements.txt
```

Descargar todas las fuentes a la capa Bronze (ingreso, meta_predial y RENAMU):
```
python Src/ingesta/descargar_bronze.py
```

Crear la base de datos `GoldFiscal` y el esquema/tablas `silver.*` (solo la
primera vez, o si hay que rehacer el esquema desde cero):
```
python Src/gold/cargar_silver.py --setup
```

Cargar (o recargar) los 3 Parquet de Silver a SQL Server — vacía las 3
tablas y las vuelve a llenar, se puede correr las veces que haga falta:
```
python Src/gold/cargar_silver.py
```

Cargar (o recargar) la tabla de contexto por nivel de gobierno — antes,
correr una vez `SQL/gold/04_crear_reparto_nivel_gobierno.sql` para crear
la tabla:
```
python Src/gold/cargar_reparto_nivel_gobierno.py
```

Por ahora no hay tests, lint ni build configurados en el repo.

## Arquitectura del código de ingesta

`Src/ingesta/descargar_bronze.py` es el único script de la capa Bronze. Estructura:

- `FUENTES`: diccionario que agrupa las URLs de MEF por categoría (`ingreso`,
  `meta_predial`). Cada categoría se descarga a `Data/bronze/<categoria>/`.
- `RENAMU`: diccionario `año -> URL del ZIP` de INEI (2022-2025). Nota que cada
  año usa una URL con estructura distinta (dominio y ruta cambian entre años).
- `descargar(url, destino)`: helper genérico que hace streaming del archivo y
  lo escribe en disco por chunks; usado tanto para los CSVs de MEF como para
  los ZIPs de RENAMU.
- `descargar_renamu(anio, url)`: descarga el ZIP de un año a una carpeta
  temporal, lo descomprime en `Data/bronze/renamu/<anio>/` y borra el ZIP.
- `main()`: orquesta la descarga de las dos fuentes MEF (`FUENTES`) y luego
  las 4 años de RENAMU. Los errores de descarga por archivo se capturan
  individualmente (no detienen el resto de la ejecución).

## Arquitectura del código de Silver

Tres scripts en `Src/silver/`, uno por fuente, mismo estilo procedural
(prints en español, funciones por paso, `main()` al final):

- `construir_ingreso.py`: arma UBIGEO por concatenación, filtra
  GOBIERNO NACIONAL, tipa montos, filtra partidas sin ejecución, recorta
  columnas, valida (solo reporta) y guarda en
  `Data/silver/ingreso/ingreso.parquet`.
- `construir_meta_predial.py`: filtra MES_ESTADISTICA=13 y 2022-2025,
  agrega por columna con la regla "ronda más reciente gana" (desempate
  por título ARBITRIOS), calcula CUMPLIMIENTO_META_PREDIAL, marca
  outliers, cruza CLASIFICACION con fallback +0/+1/+2 años, valida y
  guarda en `Data/silver/meta_predial/meta_predial.parquet`.
- `construir_renamu.py`: lee los 4 CSV, concatena, recorta a las
  columnas seleccionadas, tipa numéricas vs. texto, calcula
  PCT_PERSONAL_NOMBRADO, valida y guarda en
  `Data/silver/renamu/renamu.parquet`.

## Arquitectura del código de carga a SQL Server

`Src/gold/` tiene el código que conecta y carga Silver a SQL Server:

- `conexion.py`: lee `.env` (vía `python-dotenv`) y arma la cadena de
  conexión ODBC. `obtener_motor(base_datos=None)` devuelve un motor de
  SQLAlchemy (`fast_executemany=True`); sin argumento se conecta a la
  base de `SQL_DATABASE` (`GoldFiscal`), con `"master"` se conecta a la
  base de sistema (necesaria para poder crear `GoldFiscal`, ya que no
  se puede crear una base estando conectado a ella misma).
- `cargar_silver.py`, un `.py` que orquesta todo (no reemplaza al SQL,
  lo ejecuta):
  - `crear_database()`: conecta a `master` en modo `AUTOCOMMIT`
    (`CREATE DATABASE` no puede correr dentro de una transacción) y
    ejecuta `SQL/ddl/01_crear_database.sql`.
  - `rellenar_query()`: lee el Parquet de renamu para sacar los nombres
    reales de las columnas `P23_*`, arma ese bloque de texto, reemplaza
    el marcador dentro de `SQL/ddl/02_crear_esquema_y_tablas.sql` y lo
    ejecuta contra `GoldFiscal` — crea el esquema `silver` y las 3
    tablas.
  - `cargar_meta_predial()` / `cargar_renamu()`: leen su Parquet,
    convierten `inf`/`NaN`/`pd.NA` a `None` de Python
    (`df.replace([np.inf, -np.inf], np.nan)` +
    `df.astype(object).where(pd.notna(df), None)`), arman el `INSERT`
    a partir de las columnas del propio DataFrame, y lo ejecutan de una
    sola vez con `cursor.fast_executemany = True`.
  - `cargar_ingreso()`: mismo patrón, pero en lotes de 50,000 filas —
    un `for` con `range(0, total, tamano_lote)` y slicing de la lista
    de registros, con `commit()` y un `print()` de progreso por lote.
  - `truncar_tablas()`: `TRUNCATE TABLE` de las 3 tablas antes de
    cargar, para que el proceso sea idempotente (re-ejecutable sin
    duplicar filas ni violar llaves primarias) y para que `ID_INGRESO`
    reinicie su `IDENTITY` a 1 en cada recarga.
  - `main()`: agrupa el flujo de recarga —
    `truncar_tablas()` + `cargar_meta_predial()` + `cargar_renamu()` +
    `cargar_ingreso()`, en ese orden. **No** incluye `crear_database()`
    ni `rellenar_query()` (ver más abajo, por qué quedan separados).
  - `if __name__ == "__main__":` con un flag simple por `sys.argv`: con
    `--setup` corre `crear_database()` + `rellenar_query()` (setup
    inicial, una sola vez); sin argumentos corre `main()` (recarga
    normal). Ver comandos exactos en "Comandos" más arriba.
- `SQL/ddl/01_crear_database.sql`: `CREATE DATABASE GoldFiscal` con
  chequeo `IF NOT EXISTS` contra `sys.databases`.
- `SQL/ddl/02_crear_esquema_y_tablas.sql`: `CREATE SCHEMA silver`
  (envuelto en `EXEC(...)`, porque `CREATE SCHEMA` debe ser la única
  sentencia de su batch) y los 3 `CREATE TABLE` (`ingreso`,
  `meta_predial`, `renamu`), este último con el marcador de columnas
  `P23_*` que resuelve `cargar_silver.py`.

## Arquitectura del código de transformaciones Gold

`SQL/gold/` tiene el DDL y la lógica de transformación de la capa Gold
(esquema `gold`, separado de `silver`):

- `01_crear_esquema_gold.sql`: crea el esquema `gold` (mismo patrón
  `IF NOT EXISTS` + `EXEC(...)` que `silver`) y las 2 dimensiones —
  `CREATE TABLE gold.UBICACION` + `INSERT ... SELECT DISTINCT` desde
  `silver.ingreso` + `UPDATE` con el `CASE` de macrorregión;
  `CREATE TABLE gold.RUBRO` + `INSERT` con las 7 filas de clasificación
  y sus 2 banderas. Ver el detalle de cada una en "Reglas de negocio
  (CONGELADAS)" arriba.
- `02_crear_autonomia_fiscal.sql`: `CREATE TABLE gold.AUTONOMIA_FISCAL`
  + `CREATE OR ALTER PROCEDURE gold.sp_cargar_autonomia_fiscal` — el
  procedimiento trunca la tabla y la recarga agregando `silver.ingreso`
  (filtrado a Gobiernos Locales) por `UBIGEO`/año, usando las banderas
  de `gold.RUBRO` para los componentes y el ratio de autonomía. Termina
  con `EXEC gold.sp_cargar_autonomia_fiscal;` como tercer batch, para
  que el archivo cree y cargue la tabla en una sola corrida.
- `03_crear_reparto_territorial.sql`: `CREATE TABLE
  gold.REPARTO_TERRITORIAL` + `CREATE OR ALTER PROCEDURE
  gold.sp_cargar_reparto_territorial` — agrega `silver.ingreso` (sin
  filtrar nivel de gobierno) por macrorregión + departamento + nivel de
  gobierno + año, uniendo contra `gold.UBICACION`. Mismo patrón de
  `EXEC` final que el archivo anterior.
- `04_crear_reparto_nivel_gobierno.sql`: solo la estructura de
  `CREATE TABLE gold.REPARTO_NIVEL_GOBIERNO` — sin procedimiento, la
  carga la hace Python (ver siguiente punto).
- `05_crear_cumplimiento_predial.sql`: `CREATE TABLE
  gold.CUMPLIMIENTO_PREDIAL` + `CREATE OR ALTER PROCEDURE
  gold.sp_cargar_cumplimiento_predial` — `SELECT` directo desde
  `silver.meta_predial` (sin `JOIN`, sin agregar, ver justificación
  arriba), con un `PRINT` de reporte al final que cuenta cuántos
  `PREFIJO_UBIGEO` no encontrarían match en `gold.UBICACION` (no filtra
  nada, solo avisa). Mismo patrón de `EXEC` final que los anteriores.
- `06_crear_potencial_recaudacion.sql`: `CREATE TABLE
  gold.POTENCIAL_RECAUDACION` + `CREATE OR ALTER PROCEDURE
  gold.sp_cargar_potencial_recaudacion` — dos CTE encadenados: uno
  arma la base desde `gold.CUMPLIMIENTO_PREDIAL` (con el cumplimiento
  "limpio" para referencia, excluyendo atípicos), el otro calcula
  `PERCENTILE_CONT(0.75) WITHIN GROUP (...) OVER (PARTITION BY
  CLASIFICACION, ANO)` para el percentil de cada par (categoría, año) y
  lo pega a cada fila. Mismo patrón de `EXEC` final que los anteriores.
- `07_crear_estructura_municipal.sql`: `CREATE TABLE
  gold.ESTRUCTURA_MUNICIPAL` + `CREATE OR ALTER PROCEDURE
  gold.sp_cargar_estructura_municipal` — `LEFT JOIN` desde
  `silver.renamu` hacia `silver.meta_predial` por `UBIGEO+ANO` (ver
  justificación arriba), con el conteo de 15 instrumentos de gestión
  armado a mano (suma de 15 `CASE WHEN P23_N = '1'`, sin despivotar).
  Última tabla Gold del proyecto — cierra las 6 preguntas.

`Src/gold/cargar_reparto_nivel_gobierno.py` es la única excepción al
patrón "Gold = SQL Server": lee Bronze directo con pandas (no Silver,
no SQL), agrega por nivel de gobierno y año, y carga el resultado (12
filas) a `gold.REPARTO_NIVEL_GOBIERNO` reutilizando
`Src/gold/conexion.py`. Es un script independiente — no importa ni
llama a `construir_ingreso.py` ni a `cargar_silver.py`. Ver "Reglas de
negocio (CONGELADAS)" arriba para la justificación completa de por qué
Python y no un stored procedure acá.

Las transformaciones Gold que faltan (cumplimiento predial Lima vs.
regiones, benchmark contra pares, cruce estructura municipal /
cumplimiento) son el siguiente paso, sobre las tablas `silver.*` y
`gold.*` que ya están cargadas y verificadas. Ver "Reglas de negocio
(CONGELADAS)" arriba para los parámetros exactos.
