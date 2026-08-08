-- Nota de desfase temporal: P32_1_T (personal del area tributaria) y
-- PCT_PERSONAL_NOMBRADO miden personal al 31 de diciembre del AÑO
-- ANTERIOR al de la encuesta RENAMU (regla de la propia encuesta). Es
-- decir, la fila con ANO=2024 describe la estructura de personal de
-- 2023. Esto es intencional y no se corrige -- de hecho conviene para
-- este analisis, porque la estructura instalada precede logicamente al
-- resultado de cobranza. Pero quien compare "estructura 2024 vs
-- cumplimiento 2024" esta en realidad comparando estructura de 2023
-- contra cobranza de 2024, no del mismo año -- ver documentacion.

IF OBJECT_ID('gold.ESTRUCTURA_MUNICIPAL', 'U') IS NOT NULL DROP TABLE gold.ESTRUCTURA_MUNICIPAL;
CREATE TABLE gold.ESTRUCTURA_MUNICIPAL (
    UBIGEO                          VARCHAR(6)    NOT NULL,
    ANO                              SMALLINT      NOT NULL,
    PREFIJO_UBIGEO                   VARCHAR(4)    NOT NULL,
    TIPOMUNI                         VARCHAR(2)    NOT NULL,
    TIENE_AREA_TRIBUTARIA            VARCHAR(2)    NULL,
    PERSONAL_AREA_TRIBUTARIA         INT           NULL,
    PERSONAL_TOTAL                   INT           NULL,
    PCT_PERSONAL_TRIBUTARIO          FLOAT         NULL,
    PCT_PERSONAL_NOMBRADO            FLOAT         NULL,
    TIENE_CATASTRO_DIGITAL           VARCHAR(2)    NULL,
    CANTIDAD_INSTRUMENTOS_GESTION    INT           NULL,
    TIENE_DATO_PREDIAL               BIT           NOT NULL,
    CLASIFICACION                    VARCHAR(1)    NULL,
    CUMPLIMIENTO_META_PREDIAL        FLOAT         NULL,
    FLAG_CUMPLIMIENTO_ATIPICO        BIT           NOT NULL,
    CONSTRAINT PK_estructura_municipal PRIMARY KEY (UBIGEO, ANO)
);

CREATE OR ALTER PROCEDURE gold.sp_cargar_estructura_municipal
AS
BEGIN
    SET NOCOUNT ON;

    TRUNCATE TABLE gold.ESTRUCTURA_MUNICIPAL;

    INSERT INTO gold.ESTRUCTURA_MUNICIPAL (
        UBIGEO, ANO, PREFIJO_UBIGEO, TIPOMUNI,
        TIENE_AREA_TRIBUTARIA, PERSONAL_AREA_TRIBUTARIA, PERSONAL_TOTAL,
        PCT_PERSONAL_TRIBUTARIO, PCT_PERSONAL_NOMBRADO,
        TIENE_CATASTRO_DIGITAL, CANTIDAD_INSTRUMENTOS_GESTION,
        TIENE_DATO_PREDIAL, CLASIFICACION, CUMPLIMIENTO_META_PREDIAL, FLAG_CUMPLIMIENTO_ATIPICO
    )
    SELECT
        r.UBIGEO,
        r.ANO,
        LEFT(r.UBIGEO, 4) AS PREFIJO_UBIGEO,
        r.TIPOMUNI,
        r.P32 AS TIENE_AREA_TRIBUTARIA,
        r.P32_1_T AS PERSONAL_AREA_TRIBUTARIA,
        r.P19D_T AS PERSONAL_TOTAL,
        CAST(r.P32_1_T AS FLOAT) / NULLIF(r.P19D_T, 0) AS PCT_PERSONAL_TRIBUTARIO,
        r.PCT_PERSONAL_NOMBRADO,
        r.P17_8 AS TIENE_CATASTRO_DIGITAL,
        -- Conteo de 15 instrumentos (no 16): P23_4 se excluye porque solo
        -- aplica a municipalidades provinciales (verificado contra el
        -- diccionario oficial y contra los datos: Tipomuni=2 siempre lo
        -- deja en blanco, no es "No", es "no aplica").
        (CASE WHEN r.P23_1 = '1' THEN 1 ELSE 0 END) +
        (CASE WHEN r.P23_2 = '1' THEN 1 ELSE 0 END) +
        (CASE WHEN r.P23_3 = '1' THEN 1 ELSE 0 END) +
        (CASE WHEN r.P23_5 = '1' THEN 1 ELSE 0 END) +
        (CASE WHEN r.P23_6 = '1' THEN 1 ELSE 0 END) +
        (CASE WHEN r.P23_7 = '1' THEN 1 ELSE 0 END) +
        (CASE WHEN r.P23_8 = '1' THEN 1 ELSE 0 END) +
        (CASE WHEN r.P23_9 = '1' THEN 1 ELSE 0 END) +
        (CASE WHEN r.P23_10 = '1' THEN 1 ELSE 0 END) +
        (CASE WHEN r.P23_11 = '1' THEN 1 ELSE 0 END) +
        (CASE WHEN r.P23_12 = '1' THEN 1 ELSE 0 END) +
        (CASE WHEN r.P23_13 = '1' THEN 1 ELSE 0 END) +
        (CASE WHEN LTRIM(RTRIM(r.P23_14)) = '1' THEN 1 ELSE 0 END) +
        (CASE WHEN r.P23_15 = '1' THEN 1 ELSE 0 END) +
        (CASE WHEN r.P23_16 = '1' THEN 1 ELSE 0 END) AS CANTIDAD_INSTRUMENTOS_GESTION,
        CASE WHEN m.UBIGEO IS NOT NULL THEN 1 ELSE 0 END AS TIENE_DATO_PREDIAL,
        m.CLASIFICACION,
        m.CUMPLIMIENTO_META_PREDIAL,
        ISNULL(m.FLAG_CUMPLIMIENTO_ATIPICO, 0) AS FLAG_CUMPLIMIENTO_ATIPICO
    FROM silver.renamu r
    LEFT JOIN silver.meta_predial m
        ON m.UBIGEO = r.UBIGEO AND m.ANO_ESTADISTICA = r.ANO;

    PRINT 'Filas insertadas: ' + CAST(@@ROWCOUNT AS VARCHAR);
END;

EXEC gold.sp_cargar_estructura_municipal;
