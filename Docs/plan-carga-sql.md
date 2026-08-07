# Plan: Cargar Silver a SQL Server (esquema `silver`, base `GoldFiscal`)

> Este documento es la referencia de diseño para implementar la carga de
> Silver a SQL Server. La implementación queda a cargo del usuario (para
> aprender); este archivo documenta las decisiones ya tomadas para que
> el código que se escriba sea consistente con ellas.

## Contexto
Las 3 capas Silver están terminadas y verificadas en Parquet
(`Data/silver/ingreso`, `.../meta_predial`, `.../renamu`). Siguiente paso
del proyecto (según `Docs/reglas-de-negocio.md`): mover Silver a SQL
Server para que las transformaciones Gold (cruces por UBIGEO, autonomía
fiscal, agregaciones, benchmarks) se hagan en T-SQL, no en Python. Este
plan cubre solo la carga Silver -> SQL Server (no las transformaciones
Gold, que son un paso posterior).

Decisiones ya confirmadas:
- Autenticación: **Windows / Trusted Connection** (sin usuario/contraseña).
- Servidor: **localhost**, instancia default.
- Base de datos: nueva, **`GoldFiscal`**.
- Se cargan las 3 tablas completas, incluidas las 2.7M filas de ingreso.

Investigación ya hecha (no hace falta repetirla al implementar):
- `pyodbc` 5.3.0 y `SQLAlchemy` 2.0.50 **ya están instalados** en el
  entorno; ya se agregaron a `requirements.txt` junto con
  `python-dotenv` (recién instalado, no estaba antes).
- Drivers ODBC disponibles en la máquina (`Get-OdbcDriver`): `ODBC Driver
  17 for SQL Server` y `ODBC Driver 18 for SQL Server`, ambos 64-bit.
  Se usará el **18** (el más nuevo). Driver 18 cambia el default de
  `Encrypt` a `yes` respecto al 17 — contra una instancia local con
  certificado no confiable hay que agregar `TrustServerCertificate=yes`
  a la cadena de conexión o la conexión falla.
- `.env` ya está en `.gitignore` (no hay que tocarlo). Ya se creó
  `.env` local y `.env.example` versionado con las claves esperadas
  (ver sección de variables de entorno abajo).
- Tipos y anchos de texto reales medidos sobre los 3 Parquet (ver
  esquema abajo) — evita adivinar tamaños de VARCHAR.
- Llaves naturales verificadas: `meta_predial` es única por
  `(SEC_EJEC, ANO_ESTADISTICA)` (0 duplicados), `renamu` es única por
  `(Ubigeo, ANO)` (0 duplicados). `ingreso` **no tiene llave natural**:
  26,293 filas duplicadas completas y 2,358,207 duplicadas en
  `(ANO_DOC, MES_DOC, UBIGEO, RUBRO_NOMBRE)` — son partidas
  presupuestales distintas que, tras el recorte de columnas de Silver,
  se ven iguales (mismo fenómeno ya documentado en
  `Docs/reglas-de-negocio.md`, sección "Filtro de partidas sin
  ejecución"). `ingreso` necesita **llave sustituta** (`IDENTITY`).
- **Hallazgo importante para la carga**: `CUMPLIMIENTO_META_PREDIAL`
  (meta_predial) y `PCT_PERSONAL_NOMBRADO` (renamu) son columnas
  calculadas por división que ya contienen `inf`/`NaN` a propósito
  (denominador cero, ya documentado y flageado con
  `FLAG_CUMPLIMIENTO_ATIPICO` / el propio `P19D_T==0`). T-SQL `float`
  **no soporta los valores especiales IEEE `inf`/`NaN`** — insertarlos
  tal cual falla. Hace falta convertir `inf`/`NaN` a `NULL` **solo al
  momento de insertar en SQL** (no se toca el Parquet ni la lógica de
  Silver). Esto es un ajuste de formato de almacenamiento, no una
  corrección de datos: el significado ("sin dato para calcular esta
  métrica") es el mismo, y las columnas `FLAG_*` que ya existen para
  marcar estos casos no cambian.
- **Cuidado con tipos al insertar por ODBC**: varias columnas vienen en
  `float64` desde Parquet (por NaN o por división) pero el esquema SQL
  las define como enteras (`ANO_DOC`, `MES_DOC`, `ANO_ESTADISTICA`,
  `TIPO_META`, `ANO_CLASIFICACION` en meta_predial; `ANO` y todos los
  conteos de personal en renamu). Conviene castear esas columnas a
  `Int64` (entero nullable de pandas) antes de insertar, para no
  mandarle un `float` de Python a una columna `INT`/`SMALLINT` vía
  ODBC.

## Estado actual de archivos (ya creados, no hace falta rehacerlos)
- `requirements.txt` — ya tiene `pyodbc`, `SQLAlchemy`, `python-dotenv`.
- `.env` (no versionado) y `.env.example` (versionado) — ya existen en
  la raíz del repo con las 4 claves de la sección siguiente.
- **`Sql/ddl/` está vacío** — el DDL que yo había escrito
  (`001_crear_base_datos.sql`, `002_crear_esquema_y_tablas_silver.sql`)
  fue borrado por el usuario a propósito. Queda **todo** el DDL
  pendiente de escribir, no solo el código Python de `Src/carga/`.
  Idea que había usado para las 90 columnas `P23_*` de `renamu` (libre
  de reusar o no): en vez de escribirlas a mano en el `CREATE TABLE`,
  generarlas en tiempo de ejecución leyendo los nombres reales del
  propio Parquet (mismo criterio que ya usa
  `Src/silver/construir_renamu.py`: `sorted(c for c in df.columns if
  c.startswith("P23"))`), para que la tabla nunca se desincronice del
  dato real. También es válido escribirlas a mano si se prefiere tener
  el DDL como `.sql` estático y legible de punta a punta.
- **Pendiente de escribir (a cargo del usuario), todo**: el DDL en
  `Sql/ddl/` (creación de base de datos, esquema y las 3 tablas) y el
  código en `Src/carga/` que arma la conexión, ejecuta el DDL, trunca
  las tablas, carga los datos por lotes y corre las verificaciones. No
  existe ningún archivo de este paso todavía.

## Variables de entorno (`.env`, no versionado)
```
SQL_SERVER=localhost
SQL_DATABASE=GoldFiscal
SQL_DRIVER=ODBC Driver 18 for SQL Server
SQL_TRUSTED_CONNECTION=yes
```
Con Trusted Connection no hace falta usuario/contraseña. Si en el futuro
se cambia a login SQL, se agregarían `SQL_UID`/`SQL_PWD` sin tocar el
resto del código (el módulo de conexión debería armar la cadena leyendo
estas variables).

## Esquema de las 3 tablas (`silver.*`)

Reglas generales aplicadas a las 3 tablas:
- Todo código geográfico (`UBIGEO`, `SEC_EJEC`) es **VARCHAR**, nunca
  numérico — regla ya congelada para Silver, se mantiene igual en SQL.
- Los montos en soles se guardan como **DECIMAL(18,2)**, no `FLOAT`:
  Parquet los trae en `float64`, pero sumar dinero en punto flotante
  arrastra error de redondeo; `DECIMAL` es exacto y es el tipo correcto
  para valores monetarios que después se van a sumar en la fórmula de
  autonomía y en agregaciones de Gold.
- Las columnas calculadas por división (`CUMPLIMIENTO_META_PREDIAL`,
  `PCT_PERSONAL_NOMBRADO`) quedan como `FLOAT NULL`, con `inf`/`NaN`
  convertidos a `NULL` al cargar (ver justificación arriba).
- Los anchos de `VARCHAR` se fijan con margen sobre el máximo real
  medido en el Parquet (no ajustados al límite exacto), para no romper
  si una carga futura trae un nombre un poco más largo.

### `silver.ingreso` (2,744,843 filas esperadas)
| Columna | Tipo | Notas |
|---|---|---|
| `ID_INGRESO` | `INT IDENTITY(1,1) PRIMARY KEY` | Llave sustituta — no hay llave natural (ver hallazgo arriba) |
| `ANO_DOC` | `SMALLINT NOT NULL` | |
| `MES_DOC` | `TINYINT NOT NULL` | |
| `UBIGEO` | `VARCHAR(6) NOT NULL` | máx. real 6 |
| `DEPARTAMENTO_EJECUTORA_NOMBRE` | `VARCHAR(50) NULL` | máx. real 35 |
| `PROVINCIA_EJECUTORA_NOMBRE` | `VARCHAR(50) NULL` | máx. real 25 |
| `DISTRITO_EJECUTORA_NOMBRE` | `VARCHAR(50) NULL` | máx. real 35 |
| `NIVEL_GOBIERNO_NOMBRE` | `VARCHAR(30) NULL` | máx. real 20 |
| `RUBRO_NOMBRE` | `VARCHAR(100) NULL` | máx. real 64 |
| `MONTO_PIA` | `DECIMAL(18,2) NOT NULL` | |
| `MONTO_PIM` | `DECIMAL(18,2) NOT NULL` | |
| `MONTO_RECAUDADO` | `DECIMAL(18,2) NOT NULL` | |

Ya se verificó (sobre el Parquet) que ninguna de estas columnas tiene
nulos reales hoy — los `NULL` en el esquema son margen de seguridad, no
porque se hayan encontrado nulos.

Índice no-clúster sobre `(UBIGEO, ANO_DOC)` después de la carga (se usa
para los cruces con las otras 2 fuentes en Gold). Ya incluido en el DDL.

### `silver.meta_predial` (3,943 filas esperadas)
| Columna | Tipo | Notas |
|---|---|---|
| `ANO_ESTADISTICA` | `SMALLINT NOT NULL` | |
| `SEC_EJEC` | `VARCHAR(6) NOT NULL` | |
| `UBIGEO` | `VARCHAR(6) NOT NULL` | |
| `DEPARTAMENTO_NOMBRE` | `VARCHAR(50) NULL` | |
| `PROVINCIA_NOMBRE` | `VARCHAR(50) NULL` | |
| `DISTRITO_NOMBRE` | `VARCHAR(50) NULL` | |
| `MUNICIPALIDAD_NOMBRE` | `VARCHAR(120) NULL` | máx. real 63 |
| `MON_EMISIONPREDIAL_AFECTO` | `DECIMAL(18,2) NULL` | 0 nulos reales hoy |
| `MON_EMISIONPREDIAL_EXON` | `DECIMAL(18,2) NULL` | |
| `MON_BASEIMPONIBLE_AFECTO` | `DECIMAL(18,2) NULL` | |
| `MON_RECAUDACTUAL_ORDIN` | `DECIMAL(18,2) NULL` | |
| `MON_RECAUDACTUAL_COAC` | `DECIMAL(18,2) NULL` | |
| `MON_RECAUDANTER_ORDI` | `DECIMAL(18,2) NULL` | |
| `MON_RECAUDANTER_COAC` | `DECIMAL(18,2) NULL` | |
| `MON_SALDOPREDIAL_ORD` | `DECIMAL(18,2) NULL` | |
| `MON_SALDOPREDIAL_COAC` | `DECIMAL(18,2) NULL` | |
| `CUMPLIMIENTO_META_PREDIAL` | `FLOAT NULL` | `inf`/`NaN` -> `NULL` al cargar (34.8% de las filas) |
| `FLAG_CUMPLIMIENTO_ATIPICO` | `BIT NOT NULL` | |
| `FLAG_EMISION_SOSPECHOSA` | `BIT NOT NULL` | |
| `CLASIFICACION` | `VARCHAR(1) NULL` | |
| `TIPO_META` | `SMALLINT NULL` | 8 nulos reales |
| `ANO_CLASIFICACION` | `SMALLINT NULL` | 8 nulos reales |

`PRIMARY KEY (SEC_EJEC, ANO_ESTADISTICA)` — llave natural verificada sin
duplicados.

### `silver.renamu` (7,547 filas esperadas, 117 columnas)
| Columna(s) | Tipo | Notas |
|---|---|---|
| `ANO` | `SMALLINT NOT NULL` | |
| `UBIGEO` | `VARCHAR(6) NOT NULL` | Parquet trae `Ubigeo`, renombrar a `UBIGEO` para consistencia |
| `DEPARTAMENTO` | `VARCHAR(30) NULL` | Parquet trae `Departamento`, renombrar |
| `PROVINCIA` | `VARCHAR(50) NULL` | Parquet trae `Provincia`, renombrar |
| `DISTRITO` | `VARCHAR(60) NULL` | Parquet trae `Distrito`, renombrar |
| `TIPOMUNI` | `VARCHAR(2) NULL` | Parquet trae `Tipomuni`, renombrar. Flag de 1 char |
| `P19D_T, P19D_NM, P19D_NH, P19D_CM, P19D_CH, P19D_LM, P19D_LH, P19D_VM, P19D_VH` | `INT NULL` (9 columnas) | conteos de personal, 268 nulos reales cada una |
| `P19_1_T … P19_6_T` | `INT NULL` (6 columnas) | conteos por categoría, 268 nulos reales cada una |
| `P23_*` | `VARCHAR(100) NULL` (90 columnas) | mezcla flags 1/2, texto libre ("_O", máx. real 94) y n° de resolución — se tipan todas igual, uniforme, como ya se decidió en Silver |
| `P32` | `VARCHAR(2) NULL` | flag de 1 char |
| `P32_1_T, P32_1_M, P32_1_H` | `INT NULL` (3 columnas) | conteos, 2,616 nulos reales cada una |
| `P17_8` | `VARCHAR(2) NULL` | flag de 1 char |
| `PCT_PERSONAL_NOMBRADO` | `FLOAT NULL` | `inf`/`NaN` -> `NULL` al cargar (0.8% de las filas) |

`PRIMARY KEY (UBIGEO, ANO)` — llave natural verificada sin duplicados.

## Estrategia de carga por lotes

- **`meta_predial` y `renamu`** (3,943 y 7,547 filas): se cargan en una
  sola pasada con `pyodbc` `fast_executemany`, no hace falta loteo — el
  volumen es trivial.
- **`ingreso`** (2,744,843 filas): el DataFrame completo cabe en memoria
  sin problema (ya se maneja así en `construir_ingreso.py`), así que no
  hace falta leer el Parquet en streaming. La carga sí conviene hacerla
  **en lotes de 50,000 filas** con un cursor `pyodbc`
  (`cursor.fast_executemany = True`, que arma la inserción como un solo
  round-trip por lote en vez de fila por fila) para:
  - evitar una transacción gigante de 2.7M filas,
  - poder reportar progreso por consola (lote N/M, filas insertadas,
    tiempo transcurrido) — mismo criterio de "reportar todo" del resto
    del proyecto,
  - poder reintentar un lote puntual sin perder todo el trabajo si algo
    falla a mitad de carga.
- **Idempotencia**: antes de insertar, conviene hacer `TRUNCATE TABLE`
  sobre las 3 tablas (no `DROP`, para no perder índices/constraints
  entre corridas). Así el script de carga se puede re-ejecutar tantas
  veces como haga falta sin acumular duplicados — mismo espíritu que los
  scripts de Silver, que también se re-ejecutan libremente.
- **Nota técnica sobre `fast_executemany`**: si se usa una conexión
  "cruda" de pyodbc obtenida a partir de un engine de SQLAlchemy (por
  ejemplo con `engine.raw_connection()`), el flag `fast_executemany=True`
  pasado a `create_engine()` no se propaga solo — hay que setear
  explícitamente `cursor.fast_executemany = True` en ese cursor crudo
  para que realmente aplique.
- **CREATE DATABASE requiere autocommit**: `CREATE DATABASE` no puede
  ejecutarse dentro de una transacción explícita en SQL Server. La
  conexión que la ejecuta (contra `master`, ya que no se puede crear una
  base estando conectado a ella misma) necesita `isolation_level =
  "AUTOCOMMIT"` en SQLAlchemy.
- **`CREATE SCHEMA` debe ser la única sentencia del batch** en T-SQL —
  si se quiere tener esa sentencia en el mismo script/batch que el resto
  del DDL (en vez de mandarla suelta aparte), hay que envolverla en
  `EXEC('CREATE SCHEMA silver')` (SQL dinámico) para que la restricción
  no rompa la ejecución.

## Verificación post-carga

Se recomienda que el propio script de carga corra e imprima estas
verificaciones al final (solo reporta, mismo criterio que las
validaciones de Silver):

1. **Conteo de filas**: `SELECT COUNT(*)` de cada tabla en SQL Server vs.
   `len(df)` del Parquet correspondiente — deben coincidir exacto.
2. **Totales de montos**: `SUM(MONTO_PIA)`, `SUM(MONTO_PIM)`,
   `SUM(MONTO_RECAUDADO)` en `silver.ingreso`, y `SUM(...)` de las 9
   columnas `MON_*` en `silver.meta_predial`, comparados contra
   `df[...].sum()` en pandas (tolerancia mínima, ej. diferencia <
   0.01, por el paso de `float64` a `DECIMAL(18,2)`).
3. **Conteo de NULLs por conversión inf/NaN**: cuántos `NULL` quedaron en
   `CUMPLIMIENTO_META_PREDIAL` y `PCT_PERSONAL_NOMBRADO` en SQL vs.
   cuántos `inf`/`NaN` había en el Parquet original — tienen que
   coincidir exacto, para confirmar que la conversión no generó ni un
   `NULL` de más ni de menos.
4. **Caso conocido**: la fila de San Isidro (UBIGEO `150131`) en
   `silver.meta_predial` para 2024 y 2025, comparando
   `MON_RECAUDACTUAL_ORDIN`/`COAC` contra los valores ya verificados en
   el Parquet en la sesión anterior.
5. **UBIGEO no se corrompió a número**: `SELECT TOP 5 UBIGEO FROM
   silver.ingreso WHERE UBIGEO LIKE '0%'` — confirma que los ceros a la
   izquierda sobrevivieron la carga (si `UBIGEO` se hubiera cargado como
   entero por error, estas filas no existirían con ese formato).
6. **Tipo de columna real en SQL**: consulta a `sys.columns` /
   `INFORMATION_SCHEMA.COLUMNS` para las 3 tablas, confirmando que
   `UBIGEO`/`SEC_EJEC` quedaron como `varchar` y no como tipo numérico.

## Cambios en `Docs/reglas-de-negocio.md` (después de implementar)
Cuando la carga esté lista y verificada, agregar una subsección "Carga
de Silver a SQL Server" documentando: base `GoldFiscal` / esquema
`silver`, Trusted Connection, DECIMAL(18,2) para montos (no FLOAT), la
conversión inf/NaN -> NULL en las columnas calculadas y por qué no es
una corrección de datos, la llave sustituta de `ingreso` y las llaves
naturales de las otras 2 tablas, y el criterio de carga por lotes de
50,000 para `ingreso`.

## Fuera de alcance de este plan
Las transformaciones Gold en T-SQL (cruces, autonomía fiscal,
agregaciones, benchmarks) son el siguiente paso, después de que esta
carga esté implementada y verificada.
