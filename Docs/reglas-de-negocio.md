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
- Siguiente paso: transformaciones Gold en T-SQL (cruces por UBIGEO
  entre las tres fuentes, cálculo de autonomía fiscal, agregaciones y
  benchmarks), para luego conectar Power BI a las tablas Gold.

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

### Segmentación geográfica
- Una sola columna con: Lima Metropolitana / Lima Provincias / Norte /
  Centro / Sur / Oriente. Cada departamento cae en exactamente una.

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

Las transformaciones Gold en T-SQL (cruces por UBIGEO, autonomía fiscal,
agregaciones, benchmarks) todavía no existen — son el siguiente paso,
sobre las tablas `silver.*` que ya están cargadas y verificadas. Ver
"Reglas de negocio (CONGELADAS)" arriba para los parámetros exactos.
