# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

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
- Script de ingesta (Src/ingesta/descargar_bronze.py) descarga a Bronze.
- Siguiente paso: capa Silver (limpieza de encoding y tipos).

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

Por ahora no hay tests, lint ni build configurados en el repo.

## Arquitectura del código de ingesta

`Src/ingesta/descargar_bronze.py` es el único script del proyecto por ahora. Estructura:

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

Todavía no existe código para las capas Silver ni Gold. Silver se construye
en Python + pandas (siguiente paso, ver "Estado actual" arriba); Gold se
construye en SQL Server a partir de las tablas Silver en Parquet. Ver
"Reglas de negocio (CONGELADAS)" arriba para los parámetros exactos.
