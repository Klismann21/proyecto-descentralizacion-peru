import re
from pathlib import Path

import numpy as np
import pandas as pd

BRONZE = Path("Data/bronze/meta_predial")
SILVER = Path("Data/silver/meta_predial")

ANOS_ESTADISTICA = ["2022", "2023", "2024", "2025"]

COLUMNAS_TEXTO = ["SEC_EJEC", "UBIGEO", "DEPARTAMENTO", "PROVINCIA", "DISTRITO"]

# NUM_CONTRIPREDIO y NUM_PREDIOTOTAL NO estan aca: el MEF dejo de
# reportarlas despues de ANO_ESTADISTICA=2019, quedan en 0 para todo
# nuestro alcance (2022-2025). Ver CLAUDE.md.
COLUMNAS_MONTO = [
    "MON_EMISIONPREDIAL_AFECTO",
    "MON_EMISIONPREDIAL_EXON",
    "MON_BASEIMPONIBLE_AFECTO",
    "MON_RECAUDACTUAL_ORDIN",
    "MON_RECAUDACTUAL_COAC",
    "MON_RECAUDANTER_ORDI",
    "MON_RECAUDANTER_COAC",
    "MON_SALDOPREDIAL_ORD",
    "MON_SALDOPREDIAL_COAC",
]

COLUMNAS_IDENTIDAD = [
    "SEC_EJEC",
    "UBIGEO",
    "DEPARTAMENTO_NOMBRE",
    "PROVINCIA_NOMBRE",
    "DISTRITO_NOMBRE",
    "MUNICIPALIDAD_NOMBRE",
]

UBIGEO_VALIDO = re.compile(r"^\d{6}$")


def leer_esat_estadistica_atm():
    dtype = {col: str for col in COLUMNAS_TEXTO}
    ruta = BRONZE / "rentas_esat_estadistica_atm.csv"
    df = pd.read_csv(ruta, encoding="utf-8", sep=",", dtype=dtype, low_memory=False)
    print(f"rentas_esat_estadistica_atm.csv: {len(df)} filas leidas")
    return df


def filtrar_anual_y_alcance(df):
    antes = len(df)
    df = df[df["MES_ESTADISTICA"] == 13].copy()
    print(f"Filtro MES_ESTADISTICA=13 (total anual, evita doble conteo con meses 1-12): {antes} -> {len(df)} filas")

    antes = len(df)
    df = df[df["ANO_ESTADISTICA"].isin([int(a) for a in ANOS_ESTADISTICA])].copy()
    print(f"Filtro ANO_ESTADISTICA en {ANOS_ESTADISTICA}: {antes} -> {len(df)} filas")
    return df


def tipar_montos(df):
    for col in COLUMNAS_MONTO:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    return df


def leer_titulo_formulario():
    ruta = BRONZE / "rentas_formulario.csv"
    df = pd.read_csv(ruta, encoding="utf-8", sep=",", low_memory=False)
    df = df.drop_duplicates(subset=["ANO_APLICACION", "PERIODO", "FORMULARIO_ID"])
    print(f"rentas_formulario.csv: {len(df)} filas (catalogo de titulos por ronda+periodo+formulario)")
    return df[["ANO_APLICACION", "PERIODO", "FORMULARIO_ID", "TITULO"]]


def marcar_arbitrios(df, titulos):
    df = df.merge(titulos, on=["ANO_APLICACION", "PERIODO", "FORMULARIO_ID"], how="left")
    df["ES_ARBITRIOS"] = df["TITULO"].str.contains("ARBITRIO", case=False, na=False)
    print(f"Filas marcadas como formulario de Arbitrios (otra tasa, no predial): {df['ES_ARBITRIOS'].sum()}")
    return df


def agregar_por_municipalidad_anio(df):
    # El numero de FORMULARIO_ID que representa cada concepto (emision,
    # recaudacion, saldos) cambia de ronda en ronda -- verificado en el
    # crudo (ej. recaudacion ordinaria fue FORMULARIO_ID=7 en 2021-2023,
    # =11 en 2024, =12 en 2025). Por eso NO se puede fijar "columna X
    # viene de FORMULARIO_ID Y", ni sumar entre formularios (eso duplica
    # la misma cifra reportada en dos rondas distintas).
    #
    # Regla: por cada (SEC_EJEC, ANO_ESTADISTICA) y cada columna de monto
    # por separado, se toma el valor de la fila con (ANO_APLICACION,
    # PERIODO) mas reciente entre las que tengan esa columna != 0, sin
    # importar el FORMULARIO_ID.
    #
    # Desempate: en 3 columnas (RECAUDACTUAL_ORDIN/COAC, RECAUDANTER_ORDI)
    # hay casos donde dos filas empatan en la ronda mas reciente con
    # valores distintos. Verificado: SIEMPRE es 1 fila titulada
    # "ARBITRIOS" (otra tasa) + 1 fila de predial real -- se descarta la
    # de Arbitrios SOLO para desempatar. No se filtra "Arbitrios" de
    # entrada: la recaudacion real 2024/2025 de San Isidro (UBIGEO
    # 150131) esta mal catalogada como "ARBITRIOS" en rentas_formulario.csv
    # (error de catalogacion del MEF) y no tiene ningun otro registro
    # predial-titulado con valor -- filtrar Arbitrios a priori la habria
    # borrado por completo. Ver CLAUDE.md.
    df = df.sort_values(["ANO_APLICACION", "PERIODO"])
    df["_prioridad_no_arbitrios"] = (~df["ES_ARBITRIOS"]).astype(int)

    identidad = df.groupby(["SEC_EJEC", "ANO_ESTADISTICA"], as_index=False)[COLUMNAS_IDENTIDAD].last()

    piezas = []
    for col in COLUMNAS_MONTO:
        con_valor = df[df[col] != 0].copy()
        con_valor["_clave_ronda"] = list(zip(con_valor["ANO_APLICACION"], con_valor["PERIODO"]))
        maximo_por_grupo = con_valor.groupby(["SEC_EJEC", "ANO_ESTADISTICA"])["_clave_ronda"].transform("max")
        n_grupos_empatados = (
            con_valor[con_valor["_clave_ronda"] == maximo_por_grupo]
            .groupby(["SEC_EJEC", "ANO_ESTADISTICA"])
            .filter(lambda g: len(g) > 1)
            .groupby(["SEC_EJEC", "ANO_ESTADISTICA"])
            .ngroups
        )
        if n_grupos_empatados:
            print(f"   {col}: {n_grupos_empatados} empates desempatados por titulo (se prefirio la fila no-Arbitrios)")

        con_valor = con_valor.sort_values(["ANO_APLICACION", "PERIODO", "_prioridad_no_arbitrios"])
        piezas.append(con_valor.groupby(["SEC_EJEC", "ANO_ESTADISTICA"])[col].last())

    montos = pd.concat(piezas, axis=1).reset_index()
    agg = identidad.merge(montos, on=["SEC_EJEC", "ANO_ESTADISTICA"], how="left")
    agg[COLUMNAS_MONTO] = agg[COLUMNAS_MONTO].fillna(0.0)
    print(f"Agregacion por (SEC_EJEC, ANO_ESTADISTICA): {len(agg)} filas (regla: ultima ronda no-cero por columna, sin sumar entre formularios)")
    return agg


def calcular_cumplimiento(df):
    df["CUMPLIMIENTO_META_PREDIAL"] = (
        df["MON_RECAUDACTUAL_ORDIN"] + df["MON_RECAUDACTUAL_COAC"]
    ) / df["MON_EMISIONPREDIAL_AFECTO"]
    return df


def marcar_outliers(df):
    # No se borra ni corrige nada -- solo se marca para que quede visible
    # en Gold. FLAG_CUMPLIMIENTO_ATIPICO es False en inf/NaN a proposito:
    # esos casos ya se identifican por MON_EMISIONPREDIAL_AFECTO==0 (ver
    # validacion 4), no son "un cumplimiento alto", son "sin dato".
    df["FLAG_CUMPLIMIENTO_ATIPICO"] = np.isfinite(df["CUMPLIMIENTO_META_PREDIAL"]) & (
        df["CUMPLIMIENTO_META_PREDIAL"] > 2.0
    )
    df["FLAG_EMISION_SOSPECHOSA"] = (df["MON_EMISIONPREDIAL_AFECTO"] > 0) & (df["MON_EMISIONPREDIAL_AFECTO"] < 10000)
    print(
        f"FLAG_CUMPLIMIENTO_ATIPICO=True: {df['FLAG_CUMPLIMIENTO_ATIPICO'].sum()} filas | "
        f"FLAG_EMISION_SOSPECHOSA=True: {df['FLAG_EMISION_SOSPECHOSA'].sum()} filas"
    )
    return df


def leer_clasificacion():
    ruta = BRONZE / "rentas_entidad_estado.csv"
    df = pd.read_csv(ruta, encoding="utf-8", sep=",", dtype={"SEC_EJEC": str}, low_memory=False)
    df = df.drop_duplicates(subset=["SEC_EJEC", "ANO_APLICACION"])
    df = df[["SEC_EJEC", "ANO_APLICACION", "CLASIFICACION", "TIPO_META"]]
    print(f"rentas_entidad_estado.csv: {len(df)} filas tras deduplicar por (SEC_EJEC, ANO_APLICACION)")
    return df


def unir_clasificacion(df, clasificacion):
    df = df.copy()
    df["CLASIFICACION"] = pd.NA
    df["TIPO_META"] = pd.NA
    df["ANO_CLASIFICACION"] = pd.NA

    for offset in (0, 1, 2):
        pendiente = df["CLASIFICACION"].isna()
        candidatos = df.loc[pendiente, ["SEC_EJEC", "ANO_ESTADISTICA"]].copy()
        candidatos["ANO_APLICACION"] = candidatos["ANO_ESTADISTICA"] + offset
        match = candidatos.merge(clasificacion, on=["SEC_EJEC", "ANO_APLICACION"], how="left")
        encontrados = match["CLASIFICACION"].notna().values

        idx = candidatos.index[encontrados]
        df.loc[idx, "CLASIFICACION"] = match.loc[encontrados, "CLASIFICACION"].values
        df.loc[idx, "TIPO_META"] = match.loc[encontrados, "TIPO_META"].values
        df.loc[idx, "ANO_CLASIFICACION"] = match.loc[encontrados, "ANO_APLICACION"].values

        etiqueta = "exacto (ANO_APLICACION=ANO_ESTADISTICA)" if offset == 0 else f"fallback +{offset}"
        print(f"Union con CLASIFICACION, intento {etiqueta}: {encontrados.sum()} filas encontradas ({pendiente.sum()} pendientes antes de este intento)")

    df["ANO_CLASIFICACION"] = df["ANO_CLASIFICACION"].astype("Int64")
    return df


def validar(df):
    print("\n--- VALIDACIONES (solo reporte, no corrigen ni filtran nada) ---")

    # 1. Longitud y formato de UBIGEO
    largo_malo = df[df["UBIGEO"].str.len() != 6]
    print(f"\n1. UBIGEO con longitud distinta de 6: {len(largo_malo)} filas")
    formato_malo = df[~df["UBIGEO"].str.match(UBIGEO_VALIDO)]
    print(f"   UBIGEO con caracteres que no son digitos: {len(formato_malo)} filas")

    # 2. Cobertura por ANO_ESTADISTICA
    print("\n2. Filas por ANO_ESTADISTICA:")
    print(df["ANO_ESTADISTICA"].value_counts().sort_index())

    # 3. Desglose del join con CLASIFICACION: exacto / +1 / +2 / sin match
    offset_usado = df["ANO_CLASIFICACION"] - df["ANO_ESTADISTICA"]
    total = len(df)
    exacto = (offset_usado == 0).sum()
    mas_1 = (offset_usado == 1).sum()
    mas_2 = (offset_usado == 2).sum()
    sin_match = df["ANO_CLASIFICACION"].isna().sum()
    print("\n3. Desglose del cruce con CLASIFICACION:")
    print(f"   match exacto (ANO_APLICACION=ANO_ESTADISTICA): {exacto} ({exacto / total:.1%})")
    print(f"   match fallback +1: {mas_1} ({mas_1 / total:.1%})")
    print(f"   match fallback +2: {mas_2} ({mas_2 / total:.1%})")
    print(f"   sin match (ninguno de los 3 intentos): {sin_match} ({sin_match / total:.1%})")

    # 4. Denominador cero en la formula de cumplimiento
    denom_cero = (df["MON_EMISIONPREDIAL_AFECTO"] == 0).sum()
    print(f"\n4. MON_EMISIONPREDIAL_AFECTO == 0 (denominador cero, CUMPLIMIENTO_META_PREDIAL queda inf/nan): {denom_cero} / {len(df)} ({denom_cero / len(df):.1%})")

    # 5. Nulos en columnas de monto
    print("\n5. Nulos por columna de monto:")
    for col in COLUMNAS_MONTO:
        print(f"   {col}: {df[col].isna().sum()}")

    # 6. Duplicados exactos
    columnas_comparables = [c for c in df.columns]
    duplicados = df[df.duplicated(subset=columnas_comparables, keep=False)]
    print(f"\n6. Filas exactamente duplicadas: {len(duplicados)}")
    print(
        "   Nota: al igual que en Ingreso, esto es diagnostico, no indica error -- "
        "no afecta la formula de cumplimiento porque cada fila ya es unica por (SEC_EJEC, ANO_ESTADISTICA)."
    )

    # 7. Flags de outliers (solo marcan, no corrigen ni filtran)
    atipico = df["FLAG_CUMPLIMIENTO_ATIPICO"].sum()
    sospechosa = df["FLAG_EMISION_SOSPECHOSA"].sum()
    print(f"\n7. FLAG_CUMPLIMIENTO_ATIPICO (cumplimiento > 2.0, finito): {atipico} ({atipico / total:.1%})")
    print(f"   FLAG_EMISION_SOSPECHOSA (0 < emision < 10,000): {sospechosa} ({sospechosa / total:.1%})")

    print("\n--- FIN VALIDACIONES ---\n")


def guardar(df):
    SILVER.mkdir(parents=True, exist_ok=True)
    destino = SILVER / "meta_predial.parquet"
    df.to_parquet(destino, index=False)
    print(f"Guardado: {destino} ({len(df)} filas)")


def main():
    df = leer_esat_estadistica_atm()
    df = filtrar_anual_y_alcance(df)
    df = tipar_montos(df)

    titulos = leer_titulo_formulario()
    df = marcar_arbitrios(df, titulos)
    df = agregar_por_municipalidad_anio(df)
    df = calcular_cumplimiento(df)
    df = marcar_outliers(df)

    clasificacion = leer_clasificacion()
    df = unir_clasificacion(df, clasificacion)

    validar(df)
    guardar(df)


if __name__ == "__main__":
    main()
