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

### RENAMU multi-año
- Cada año tiene ~1380 columnas. NO armonizar todo.
- Solo mapear 5-10 variables clave entre los 4 años (crosswalk) para las
  preguntas de tendencia.

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
