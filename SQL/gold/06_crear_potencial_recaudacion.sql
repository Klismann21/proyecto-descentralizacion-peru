IF OBJECT_ID('gold.POTENCIAL_RECAUDACION', 'U') IS NOT NULL DROP TABLE gold.POTENCIAL_RECAUDACION;
CREATE TABLE gold.POTENCIAL_RECAUDACION (
    UBIGEO                      VARCHAR(6)    NOT NULL,
    ANO                          SMALLINT      NOT NULL,
    PREFIJO_UBIGEO               VARCHAR(4)    NOT NULL,
    MUNICIPALIDAD_NOMBRE         VARCHAR(120)  NULL,
    MUNICIPIO_ETIQUETA           VARCHAR(180)  NULL,
    CLASIFICACION                VARCHAR(1)    NULL,
    CUMPLIMIENTO_META_PREDIAL    FLOAT         NULL,
    P75_CUMPLIMIENTO_GRUPO       FLOAT         NULL,
    POTENCIAL_NO_APROVECHADO     DECIMAL(18,2) NULL,
    FLAG_CUMPLIMIENTO_ATIPICO    BIT           NOT NULL,
    FLAG_GRUPO_SIN_REFERENCIA    BIT           NOT NULL,
    FLAG_EMISION_ATIPICA_ALTA    BIT           NOT NULL,
    CONSTRAINT PK_potencial_recaudacion PRIMARY KEY (UBIGEO, ANO)
);

CREATE OR ALTER PROCEDURE gold.sp_cargar_potencial_recaudacion
AS
BEGIN
    SET NOCOUNT ON;

    TRUNCATE TABLE gold.POTENCIAL_RECAUDACION;

    WITH BASE AS (
        SELECT
            c.UBIGEO,
            c.ANO,
            c.PREFIJO_UBIGEO,
            -- MUNICIPALIDAD_NOMBRE no vive en gold.CUMPLIMIENTO_PREDIAL,
            -- asi que se trae con un JOIN aparte a silver.meta_predial por
            -- (UBIGEO, ANO_ESTADISTICA) -- misma combinacion que ya usa
            -- gold.CUMPLIMIENTO_PREDIAL como llave, verificada unica.
            m.MUNICIPALIDAD_NOMBRE,
            -- Mismo criterio que gold.CUMPLIMIENTO_PREDIAL: desambigua
            -- homonimos (30 nombres repetidos en el pais) con la
            -- provincia entre parentesis.
            CASE WHEN m.PROVINCIA_NOMBRE IS NOT NULL
                 THEN m.MUNICIPALIDAD_NOMBRE + ' (' + m.PROVINCIA_NOMBRE + ')'
                 ELSE m.MUNICIPALIDAD_NOMBRE END AS MUNICIPIO_ETIQUETA,
            c.CLASIFICACION,
            c.CUMPLIMIENTO_META_PREDIAL,
            c.MON_EMISIONPREDIAL_AFECTO,
            c.MON_RECAUDACTUAL_TOTAL,
            c.FLAG_CUMPLIMIENTO_ATIPICO,
            c.FLAG_EMISION_ATIPICA_ALTA,
            -- Solo los casos "limpios" (no atipicos) definen el desempeño
            -- de referencia del grupo; un caso corrupto tipo Sapallanga no
            -- deberia mover el percentil de nadie.
            CASE WHEN c.FLAG_CUMPLIMIENTO_ATIPICO = 0 THEN c.CUMPLIMIENTO_META_PREDIAL END AS CUMPLIMIENTO_PARA_REFERENCIA
        FROM gold.CUMPLIMIENTO_PREDIAL c
        LEFT JOIN silver.meta_predial m
            ON m.UBIGEO = c.UBIGEO AND m.ANO_ESTADISTICA = c.ANO
    ),
    CON_REFERENCIA AS (
        SELECT
            *,
            -- Percentil 75 por (CLASIFICACION, ANO): "si esta muni alcanzara
            -- la eficiencia del mejor 25% de sus pares del MISMO año" -- no
            -- se mezclan años entre si, y PERCENTILE_CONT ignora los NULL
            -- del grupo solo (atipicos y denominador-cero) sin que haga
            -- falta filtrarlos aparte.
            CASE WHEN CLASIFICACION IS NULL THEN NULL ELSE
                PERCENTILE_CONT(0.75) WITHIN GROUP (ORDER BY CUMPLIMIENTO_PARA_REFERENCIA)
                    OVER (PARTITION BY CLASIFICACION, ANO)
            END AS P75_CUMPLIMIENTO_GRUPO
        FROM BASE
    )
    INSERT INTO gold.POTENCIAL_RECAUDACION (
        UBIGEO, ANO, PREFIJO_UBIGEO, MUNICIPALIDAD_NOMBRE, MUNICIPIO_ETIQUETA, CLASIFICACION,
        CUMPLIMIENTO_META_PREDIAL, P75_CUMPLIMIENTO_GRUPO,
        POTENCIAL_NO_APROVECHADO, FLAG_CUMPLIMIENTO_ATIPICO, FLAG_GRUPO_SIN_REFERENCIA,
        FLAG_EMISION_ATIPICA_ALTA
    )
    SELECT
        UBIGEO, ANO, PREFIJO_UBIGEO, MUNICIPALIDAD_NOMBRE, MUNICIPIO_ETIQUETA, CLASIFICACION,
        CUMPLIMIENTO_META_PREDIAL, P75_CUMPLIMIENTO_GRUPO,
        CASE
            WHEN MON_EMISIONPREDIAL_AFECTO = 0 THEN NULL
            WHEN P75_CUMPLIMIENTO_GRUPO IS NULL THEN NULL
            ELSE (P75_CUMPLIMIENTO_GRUPO * MON_EMISIONPREDIAL_AFECTO) - MON_RECAUDACTUAL_TOTAL
        END AS POTENCIAL_NO_APROVECHADO,
        FLAG_CUMPLIMIENTO_ATIPICO,
        -- El "mejor 25% de tus pares" no es una referencia util si ese
        -- percentil tambien es 0 (o no existe ningun dato limpio del
        -- grupo/año para calcularlo) -- ahi comparar contra pares no
        -- tiene sentido interpretativo, aunque el numero este bien
        -- calculado.
        CASE WHEN P75_CUMPLIMIENTO_GRUPO IS NULL OR P75_CUMPLIMIENTO_GRUPO = 0 THEN 1 ELSE 0 END AS FLAG_GRUPO_SIN_REFERENCIA,
        FLAG_EMISION_ATIPICA_ALTA
    FROM CON_REFERENCIA;

    PRINT 'Filas insertadas: ' + CAST(@@ROWCOUNT AS VARCHAR);
END;

EXEC gold.sp_cargar_potencial_recaudacion;
