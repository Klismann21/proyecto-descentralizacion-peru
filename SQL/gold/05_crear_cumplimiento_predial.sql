IF OBJECT_ID('gold.CUMPLIMIENTO_PREDIAL', 'U') IS NOT NULL DROP TABLE gold.CUMPLIMIENTO_PREDIAL;
CREATE TABLE gold.CUMPLIMIENTO_PREDIAL (
    UBIGEO                      VARCHAR(6)    NOT NULL,
    ANO                          SMALLINT      NOT NULL,
    PREFIJO_UBIGEO               VARCHAR(4)    NOT NULL,
    MUNICIPALIDAD_NOMBRE         VARCHAR(120)  NULL,
    MUNICIPIO_ETIQUETA           VARCHAR(180)  NULL,
    CLASIFICACION                VARCHAR(1)    NULL,
    MON_EMISIONPREDIAL_AFECTO    DECIMAL(18,2) NOT NULL,
    MON_RECAUDACTUAL_ORDIN       DECIMAL(18,2) NOT NULL,
    MON_RECAUDACTUAL_COAC        DECIMAL(18,2) NOT NULL,
    MON_RECAUDACTUAL_TOTAL       DECIMAL(18,2) NOT NULL,
    BRECHA_EMISION_RECAUDACION   DECIMAL(18,2) NOT NULL,
    CUMPLIMIENTO_META_PREDIAL    FLOAT         NULL,
    FLAG_CUMPLIMIENTO_ATIPICO    BIT           NOT NULL,
    FLAG_EMISION_SOSPECHOSA      BIT           NOT NULL,
    FLAG_EMISION_ATIPICA_ALTA    BIT           NOT NULL,
    FLAG_SIN_REPORTE_RECAUDACION BIT           NOT NULL,
    CONSTRAINT PK_cumplimiento_predial PRIMARY KEY (UBIGEO, ANO)
);

CREATE OR ALTER PROCEDURE gold.sp_cargar_cumplimiento_predial
AS
BEGIN
    SET NOCOUNT ON;

    TRUNCATE TABLE gold.CUMPLIMIENTO_PREDIAL;

    -- Mediana de emision de cada municipio (solo entre sus propios años
    -- con emision > 0), para detectar emisiones implausiblemente altas
    -- respecto al propio historial del municipio -- no contra un umbral
    -- fijo en soles, que no serviria igual para una capital que para un
    -- distrito chico.
    WITH medianas AS (
        SELECT UBIGEO,
            PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY MON_EMISIONPREDIAL_AFECTO)
                OVER (PARTITION BY UBIGEO) AS MEDIANA_EMISION
        FROM silver.meta_predial
        WHERE MON_EMISIONPREDIAL_AFECTO > 0
    ),
    medianas_unicas AS (
        SELECT DISTINCT UBIGEO, MEDIANA_EMISION FROM medianas
    )
    INSERT INTO gold.CUMPLIMIENTO_PREDIAL (
        UBIGEO, ANO, PREFIJO_UBIGEO, MUNICIPALIDAD_NOMBRE, MUNICIPIO_ETIQUETA, CLASIFICACION,
        MON_EMISIONPREDIAL_AFECTO, MON_RECAUDACTUAL_ORDIN, MON_RECAUDACTUAL_COAC,
        MON_RECAUDACTUAL_TOTAL, BRECHA_EMISION_RECAUDACION,
        CUMPLIMIENTO_META_PREDIAL, FLAG_CUMPLIMIENTO_ATIPICO, FLAG_EMISION_SOSPECHOSA,
        FLAG_EMISION_ATIPICA_ALTA, FLAG_SIN_REPORTE_RECAUDACION
    )
    SELECT
        m.UBIGEO,
        m.ANO_ESTADISTICA AS ANO,
        LEFT(m.UBIGEO, 4) AS PREFIJO_UBIGEO,
        m.MUNICIPALIDAD_NOMBRE,
        -- Desambigua homonimos (30 nombres repetidos en el pais, ej. dos
        -- "MUNICIPALIDAD DISTRITAL DE CHILCA" en Junin y Cañete) para
        -- mostrar en Power BI en vez del UBIGEO. Sin provincia, se deja
        -- el nombre solo -- no se inventa un "(SIN PROVINCIA)".
        CASE WHEN m.PROVINCIA_NOMBRE IS NOT NULL
             THEN m.MUNICIPALIDAD_NOMBRE + ' (' + m.PROVINCIA_NOMBRE + ')'
             ELSE m.MUNICIPALIDAD_NOMBRE END AS MUNICIPIO_ETIQUETA,
        m.CLASIFICACION,
        m.MON_EMISIONPREDIAL_AFECTO,
        m.MON_RECAUDACTUAL_ORDIN,
        m.MON_RECAUDACTUAL_COAC,
        m.MON_RECAUDACTUAL_ORDIN + m.MON_RECAUDACTUAL_COAC AS MON_RECAUDACTUAL_TOTAL,
        m.MON_EMISIONPREDIAL_AFECTO - (m.MON_RECAUDACTUAL_ORDIN + m.MON_RECAUDACTUAL_COAC) AS BRECHA_EMISION_RECAUDACION,
        m.CUMPLIMIENTO_META_PREDIAL,
        m.FLAG_CUMPLIMIENTO_ATIPICO,
        m.FLAG_EMISION_SOSPECHOSA,
        CASE WHEN med.MEDIANA_EMISION IS NOT NULL
                  AND m.MON_EMISIONPREDIAL_AFECTO * 1.0 / med.MEDIANA_EMISION > 20
             THEN 1 ELSE 0 END AS FLAG_EMISION_ATIPICA_ALTA,
        -- Quiebre 2024: marca, no corrige -- ver investigacion completa
        -- en Docs/diagnostico-calidad-gold.md ("Quiebre de recaudacion
        -- 2024"). Emitio pero registro CERO de cobranza (no NULL, no
        -- denominador-cero) -- distinto de "no emitio" (ya cubierto por
        -- CUMPLIMIENTO_META_PREDIAL en NULL).
        CASE WHEN m.MON_EMISIONPREDIAL_AFECTO > 0
                  AND (m.MON_RECAUDACTUAL_ORDIN + m.MON_RECAUDACTUAL_COAC) = 0
             THEN 1 ELSE 0 END AS FLAG_SIN_REPORTE_RECAUDACION
    FROM silver.meta_predial m
    LEFT JOIN medianas_unicas med ON med.UBIGEO = m.UBIGEO;

    PRINT 'Filas insertadas: ' + CAST(@@ROWCOUNT AS VARCHAR);

    -- Reporte, no filtro: PREFIJO_UBIGEO no depende de gold.UBICACION
    -- para cargarse (ver mas arriba), pero se avisa si algun dia deja
    -- de encontrar match, para no descubrirlo recien en Power BI.
    DECLARE @sin_dimension INT = (
        SELECT COUNT(*) FROM gold.CUMPLIMIENTO_PREDIAL c
        LEFT JOIN gold.UBICACION u ON u.PREFIJO_UBIGEO = c.PREFIJO_UBIGEO
        WHERE u.PREFIJO_UBIGEO IS NULL
    );
    PRINT 'Prefijos sin match en gold.UBICACION: ' + CAST(@sin_dimension AS VARCHAR);
END;

EXEC gold.sp_cargar_cumplimiento_predial;
