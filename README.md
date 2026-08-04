# Descentralización fiscal en el Perú: ¿cuánto dinero manejan realmente las municipalidades?

**No en la ley, sino en el dinero.** Este proyecto cruza tres fuentes
públicas del MEF y el INEI para medir cuánto de sus ingresos genera cada
municipalidad peruana por sí misma —y cuánto depende de transferencias
desde el gobierno central— entre 2022 y 2025.

El resultado es un pipeline de datos completo sobre 2.7 millones de
registros y las 1,890 municipalidades del país.

> **In brief (EN):** An end-to-end data pipeline analyzing fiscal
> decentralization in Peru. It combines three public datasets from the
> Ministry of Economy (MEF) and the National Statistics Institute (INEI)
> to measure how much revenue each of Peru's 1,890 municipalities
> generates on its own versus how much depends on central government
> transfers, from 2022 to 2025. Built with Python, SQL Server and
> Power BI following a Medallion architecture.

## Las preguntas

El proyecto está construido para responder seis preguntas concretas, cada
una traducida en un dashboard de decisión:

1. **¿Cómo se reparte el dinero público en el territorio?**
   Concentración del presupuesto y la recaudación entre Lima Metropolitana,
   Lima Provincias y las macrorregiones del país (Norte, Centro, Sur,
   Oriente), incluyendo el corte entre gobiernos locales y regionales.

2. **¿Qué tan autónomas son las municipalidades fuera de Lima?**
   Proporción de ingresos que cada municipalidad genera por sí misma
   (recursos directamente recaudados e impuestos municipales) frente a los
   que recibe por transferencias del gobierno central.

3. **¿Quién cumple mejor su meta de impuesto predial?**
   Comparación del cumplimiento entre Lima y las regiones, usando los datos
   del Programa de Incentivos del MEF.

4. **¿El cumplimiento depende de la categoría asignada por el MEF?**
   Las metas del Programa de Incentivos no las define cada municipalidad:
   el MEF las asigna según su clasificación. La pregunta es si esa
   categorización explica las diferencias de desempeño.

5. **¿Cuánto potencial de recaudación queda sin aprovechar?**
   Escenarios de "¿qué pasaría si...?" comparando cada municipalidad contra
   el desempeño de sus pares con características similares.

6. **¿Qué tienen en común las municipalidades que recaudan mejor?**
   Cruce entre estructura municipal (personal, instrumentos de gestión,
   área de administración tributaria) y cumplimiento de la meta predial.

## Alcance

Este proyecto mide la descentralización desde su dimensión
**fiscal-administrativa**: la capacidad de las municipalidades para generar
y gestionar sus propios recursos. No aborda la dimensión política de la
descentralización, que requiere fuentes distintas.

## Los datos

Tres fuentes públicas, unidas por el **UBIGEO** (el código único que
identifica a cada distrito del Perú).

### 1. Presupuesto y Ejecución de Ingreso — MEF
[datosabiertos.mef.gob.pe](https://datosabiertos.mef.gob.pe/dataset/presupuesto-y-ejecucion-de-ingreso)

Ejecución presupuestal de ingresos por entidad. Aporta el presupuesto
inicial (PIA), el modificado (PIM) y lo efectivamente recaudado,
desagregado por rubro —que es lo que permite distinguir recursos propios
de transferencias.

**Cobertura:** 2022–2025 · **Volumen:** 2.7 millones de registros

### 2. Seguimiento de la Meta del Impuesto Predial — MEF
[datosabiertos.mef.gob.pe](https://datosabiertos.mef.gob.pe/dataset/seguimiento-de-la-meta-del-impuesto-predial)

Información que las municipalidades reportan al Programa de Incentivos a
la Mejora de la Gestión Municipal sobre su emisión y recaudación de
impuesto predial, más la clasificación que el MEF asigna a cada una.

**Cobertura:** 2022–2025 · **Volumen:** ~1,000 municipalidades por año

### 3. Registro Nacional de Municipalidades (RENAMU) — INEI
[datosabiertos.gob.pe](https://www.datosabiertos.gob.pe/dataset/registro-nacional-de-municipalidades-renamu-2025-instituto-nacional-de-estad%C3%ADstica-e)

Censo anual a todas las municipalidades del país. Aporta la estructura
institucional: personal por régimen laboral, instrumentos de gestión,
existencia de un área de administración tributaria.

**Cobertura:** 2022–2025 · **Volumen:** ~1,890 municipalidades por año

---

### Sobre la cobertura

Las tres fuentes conectan por UBIGEO, pero no cubren el mismo universo.
RENAMU e Ingreso incluyen la totalidad de municipalidades provinciales y
distritales del país; la fuente de meta predial cubre alrededor de la
mitad, ya que solo registra a las municipalidades que reportaron al
Programa de Incentivos. Los análisis de cumplimiento predial se leen sobre
ese subconjunto, no sobre el total nacional.

## Arquitectura

El proyecto sigue una **arquitectura Medallion**, que separa los datos en
tres capas según su nivel de procesamiento:

<pre>
````
   FUENTES              BRONZE              SILVER               GOLD
  ─────────           ─────────           ─────────           ─────────
   MEF (2)      →     Archivos      →     Datos          →    Tablas
   INEI (1)           crudos              limpios             analíticas
                      sin tocar           en Parquet          en SQL Server
                                                                   ↓
                                                              Power BI
</pre>

| Capa | Qué contiene | Herramienta |
|------|--------------|-------------|
| **Bronze** | Los archivos tal como se descargaron. Nunca se modifican. | Python (`requests`) |
| **Silver** | Datos limpios, tipados y validados. Una tabla por fuente. | Python + pandas → Parquet |
| **Gold** | Tablas agregadas y cruzadas, listas para consumo. | SQL Server (T-SQL) |
| **Visualización** | Dashboards de decisión. | Power BI |

**Por qué este reparto:** la limpieza de Silver (encodings distintos por
fuente, construcción del UBIGEO, recorte de más de 1,300 columnas en
RENAMU) es más natural en pandas; los cruces entre fuentes y las
agregaciones analíticas de Gold son más naturales en SQL. Cada herramienta
en la capa donde rinde mejor.

Bronze se mantiene intacto por diseño: si una regla de negocio cambia,
Silver y Gold se reconstruyen desde el dato original sin volver a
descargar nada.

## Hallazgos en la calidad de los datos

Trabajar con datos públicos peruanos implica encontrarse con
inconsistencias que no están documentadas en ninguna parte. Estos son los
problemas que se detectaron y cómo se resolvieron:

**La misma métrica reportada en formularios distintos.** En la fuente de
meta predial, el monto de emisión de una municipalidad podía aparecer en
más de un formulario dentro del mismo año, y una agregación directa lo
sumaba dos veces. En el caso de San Isidro, la emisión de 2025 saltaba a
S/ 242 millones cuando el valor real era S/ 121 millones. Además, el
identificador de formulario cambia entre rondas del programa, así que no
se podía fijar por número: la regla implementada toma, para cada columna,
el valor de la ronda más reciente que lo reporte, sin sumar entre
formularios.

**Errores de escala en la fuente.** Algunas municipalidades reportan la
misma cifra con una magnitud mil veces menor según la ronda (una emisión
de S/ 1,188,552 aparece como S/ 1,188.55 al año siguiente). Como el monto
de emisión es el denominador del indicador de cumplimiento, estos casos
generaban ratios imposibles. No se corrigen ni se eliminan: se marcan con
banderas (`FLAG_EMISION_SOSPECHOSA`, `FLAG_CUMPLIMIENTO_ATIPICO`) para que
cada análisis decida si incluirlos.

**Totales mezclados con detalle.** El campo de mes en la fuente predial
incluye los doce meses del año y, además, un valor 13 que corresponde al
total anual. Sumar sin filtrar duplicaba todos los montos.

**Variables que dejaron de recolectarse.** El número de predios y de
contribuyentes existe en la fuente solo hasta 2019. RENAMU tampoco lo
registra. En consecuencia, no es posible normalizar la recaudación por
número de predios en el período analizado.

**Catálogos que se contaminan entre sí.** Parte de la información de
arbitrios municipales —un tributo distinto al predial— aparece bajo los
mismos identificadores de formulario. El filtro por título no era una
solución general: la recaudación real de San Isidro en 2024-2025 está
catalogada, por error de la fuente, como "arbitrios". El criterio final
usa el título solo para desempatar cuando dos registros compiten, nunca
como filtro.

Todas las decisiones de tratamiento están documentadas con su
justificación en [`docs/reglas-de-negocio.md`](docs/reglas-de-negocio.md).

## Cómo ejecutar el proyecto

**Requisitos:** Python 3.10+ y SQL Server (para la capa Gold).

```bash
# 1. Clonar el repositorio
git clone https://github.com/Klismann21/[nombre-del-repo].git
cd [nombre-del-repo]

# 2. Instalar dependencias
pip install -r requirements.txt

# 3. Descargar las fuentes a la capa Bronze
python Src/ingesta/descargar_bronze.py

# 4. Construir la capa Silver (una fuente a la vez)
python Src/silver/construir_ingreso.py
python Src/silver/construir_meta_predial.py
python Src/silver/construir_renamu.py
```

Cada script de Silver imprime en consola sus reportes de validación
(cobertura por año, integridad del UBIGEO, valores atípicos) antes de
escribir el Parquet. Las validaciones reportan, no corrigen ni descartan
filas automáticamente.

**Nota sobre los datos:** los archivos de Bronze y Silver no se versionan
en el repositorio por su tamaño. Se regeneran ejecutando los scripts
anteriores, que descargan directamente desde las fuentes oficiales.

## Estructura del repositorio

```
├── Src/
│   ├── ingesta/          # Descarga de fuentes → Bronze
│   └── silver/           # Limpieza y validación → Silver
├── SQL/                  # Transformaciones Silver → Gold
├── Data/
│   ├── bronze/           # Archivos crudos (no versionado)
│   ├── silver/           # Parquet limpios (no versionado)
│   └── gold/             # Tablas analíticas
├── Docs/
│   ├── diccionarios/     # Diccionarios de datos de las fuentes
│   └── reglas-de-negocio.md
├── Power BI/             # Dashboards
└── README.md
```
