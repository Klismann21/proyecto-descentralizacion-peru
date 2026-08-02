import re
from pathlib import Path

import pandas as pd

BRONZE = Path("Data/bronze/renamu")
SILVER = Path("Data/silver/renamu")

ARCHIVOS = {
    "2022": BRONZE / "2022" / "783-Modulo1726" / "Base_RENAMU_2022_f.csv",
    "2023": BRONZE / "2023" / "CSV" / "Base-Datos_2023_f.csv",
    "2024": BRONZE / "2024" / "928-Modulo1814" / "Base-Datos_2024_f.csv",
    "2025": BRONZE / "2025" / "984-Modulo1963" / "Base-Datos_2025_f_.csv",
}

COLUMNAS_IDENTIDAD = ["Año", "Ubigeo", "Departamento", "Provincia", "Distrito", "Tipomuni"]

COLUMNAS_PERSONAL = [
    "P19D_T", "P19D_NM", "P19D_NH", "P19D_CM", "P19D_CH",
    "P19D_LM", "P19D_LH", "P19D_VM", "P19D_VH",
]

COLUMNAS_PERSONAL_CATEGORIA = [
    "P19_1_T", "P19_2_T", "P19_3_T", "P19_4_T", "P19_5_T", "P19_6_T",
]

COLUMNAS_TRIBUTARIA = ["P32", "P32_1_T", "P32_1_M", "P32_1_H"]

COLUMNA_CATASTRO = ["P17_8"]

# Las 90 columnas P23_* (instrumentos de gestion) se seleccionan por
# prefijo en tiempo de ejecucion -- no se listan a mano aca.

COLUMNAS_NUMERICAS = COLUMNAS_PERSONAL + COLUMNAS_PERSONAL_CATEGORIA + ["P32_1_T", "P32_1_M", "P32_1_H"]

UBIGEO_VALIDO = re.compile(r"^\d{6}$")


def leer_renamu():
    partes = []
    for anio, ruta in ARCHIVOS.items():
        df = pd.read_csv(ruta, encoding="utf-8-sig", sep=";", dtype={"Ubigeo": str}, low_memory=False)
        print(f"{ruta.name} ({anio}): {len(df)} filas, {len(df.columns)} columnas leidas")
        partes.append(df)
    return pd.concat(partes, ignore_index=True)


def recortar_columnas(df):
    columnas_p23 = sorted(c for c in df.columns if c.startswith("P23"))
    print(f"Columnas P23_* encontradas (instrumentos de gestion): {len(columnas_p23)}")

    columnas_finales = (
        COLUMNAS_IDENTIDAD + COLUMNAS_PERSONAL + COLUMNAS_PERSONAL_CATEGORIA
        + columnas_p23 + COLUMNAS_TRIBUTARIA + COLUMNA_CATASTRO
    )
    df = df[columnas_finales].copy()
    df = df.rename(columns={"Año": "ANO"})
    print(f"Recorte de columnas: {len(columnas_finales)} columnas conservadas de las originales")

    # P23_*, P32 y P17_8 mezclan flags (1/2), texto libre y numeros de
    # resolucion -- no se tipan como numero (ver CLAUDE.md). Al concatenar
    # los 4 anios, algunas quedan con una mezcla de int/str en la misma
    # columna (pandas las infiere distinto segun el archivo), lo que rompe
    # el guardado a Parquet. Se castean a texto explicito (dtype "string",
    # no simple str, para no convertir los NaN reales en el string "nan").
    columnas_texto = columnas_p23 + ["P32", "P17_8", "Tipomuni"]
    df[columnas_texto] = df[columnas_texto].astype("string")
    return df


def tipar_numericas(df):
    for col in COLUMNAS_NUMERICAS:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df["ANO"] = df["ANO"].astype(int)
    return df


def calcular_pct_personal_nombrado(df):
    df["PCT_PERSONAL_NOMBRADO"] = (df["P19D_NM"] + df["P19D_NH"]) / df["P19D_T"]
    return df


def validar(df):
    print("\n--- VALIDACIONES (solo reporte, no corrigen ni filtran nada) ---")

    # 1. Longitud y formato de UBIGEO
    largo_malo = df[df["Ubigeo"].str.len() != 6]
    print(f"\n1. UBIGEO con longitud distinta de 6: {len(largo_malo)} filas")
    formato_malo = df[~df["Ubigeo"].str.match(UBIGEO_VALIDO)]
    print(f"   UBIGEO con caracteres que no son digitos: {len(formato_malo)} filas")

    # 2. Filas por ANO
    print("\n2. Filas por ANO:")
    print(df["ANO"].value_counts().sort_index())

    # 3. Denominador cero / porcentaje fuera de rango
    total = len(df)
    denom_cero = (df["P19D_T"] == 0).sum()
    print(f"\n3. P19D_T == 0 (denominador cero, PCT_PERSONAL_NOMBRADO queda inf/nan): {denom_cero} / {total} ({denom_cero/total:.1%})")
    fuera_rango = (df["PCT_PERSONAL_NOMBRADO"] > 1.0).sum()
    print(f"   PCT_PERSONAL_NOMBRADO > 1.0 (NM+NH mayor al total, inconsistencia de la fuente): {fuera_rango}")

    # 4. Nulos en columnas numericas de personal
    print("\n4. Nulos por columna numerica:")
    for col in COLUMNAS_NUMERICAS:
        nulos = df[col].isna().sum()
        if nulos:
            print(f"   {col}: {nulos}")
    if not any(df[col].isna().sum() for col in COLUMNAS_NUMERICAS):
        print("   (ninguna)")

    # 5. Duplicados exactos
    duplicados = df[df.duplicated(keep=False)]
    print(f"\n5. Filas exactamente duplicadas: {len(duplicados)}")

    print("\n--- FIN VALIDACIONES ---\n")


def guardar(df):
    SILVER.mkdir(parents=True, exist_ok=True)
    destino = SILVER / "renamu.parquet"
    df.to_parquet(destino, index=False)
    print(f"Guardado: {destino} ({len(df)} filas, {len(df.columns)} columnas)")


def main():
    df = leer_renamu()
    df = recortar_columnas(df)
    df = tipar_numericas(df)
    df = calcular_pct_personal_nombrado(df)
    validar(df)
    guardar(df)


if __name__ == "__main__":
    main()
