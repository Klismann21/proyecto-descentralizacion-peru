import re
from pathlib import Path

import pandas as pd

BRONZE = Path("Data/bronze/ingreso")
SILVER = Path("Data/silver/ingreso")

ARCHIVOS = [
    "2022-Ingreso.csv",
    "2023-Ingreso.csv",
    "2024-Ingreso.csv",
    "2025-Ingreso-Mensual.csv",
]

COLUMNAS_TEXTO_UBIGEO = ["DEPARTAMENTO_EJECUTORA", "PROVINCIA_EJECUTORA", "DISTRITO_EJECUTORA"]

COLUMNAS_FINALES = [
    "ANO_DOC",
    "MES_DOC",
    "UBIGEO",
    "DEPARTAMENTO_EJECUTORA_NOMBRE",
    "PROVINCIA_EJECUTORA_NOMBRE",
    "DISTRITO_EJECUTORA_NOMBRE",
    "NIVEL_GOBIERNO_NOMBRE",
    "RUBRO_NOMBRE",
    "MONTO_PIA",
    "MONTO_PIM",
    "MONTO_RECAUDADO",
]

UBIGEO_VALIDO = re.compile(r"^\d{6}$")


def leer_ingreso():
    dtype = {col: str for col in COLUMNAS_TEXTO_UBIGEO}
    partes = []
    for nombre in ARCHIVOS:
        ruta = BRONZE / nombre
        df = pd.read_csv(ruta, encoding="utf-8", sep=",", dtype=dtype)
        print(f"{nombre}: {len(df)} filas leidas")
        partes.append(df)
    return pd.concat(partes, ignore_index=True)


def construir_ubigeo(df):
    df["UBIGEO"] = (
        df["DEPARTAMENTO_EJECUTORA"] + df["PROVINCIA_EJECUTORA"] + df["DISTRITO_EJECUTORA"]
    )
    return df


def filtrar_nivel_gobierno(df):
    antes = len(df)
    df = df[df["NIVEL_GOBIERNO_NOMBRE"] != "GOBIERNO NACIONAL"].copy()
    print(f"Filtro NIVEL_GOBIERNO_NOMBRE: {antes} -> {len(df)} filas (se excluyo GOBIERNO NACIONAL)")
    return df


def tipar_columnas(df):
    df["ANO_DOC"] = df["ANO_DOC"].astype(int)
    df["MES_DOC"] = df["MES_DOC"].astype(int)
    df["MONTO_PIA"] = df["MONTO_PIA"].astype(float)
    df["MONTO_PIM"] = df["MONTO_PIM"].astype(float)
    df["MONTO_RECAUDADO"] = df["MONTO_RECAUDADO"].astype(float)
    return df


def recortar_columnas(df):
    return df[COLUMNAS_FINALES].copy()


def validar(df):
    print("\n--- VALIDACIONES (solo reporte, no corrigen ni filtran nada) ---")

    # 1. Longitud de UBIGEO
    largo_malo = df[df["UBIGEO"].str.len() != 6]
    print(f"\n1. UBIGEO con longitud distinta de 6: {len(largo_malo)} filas")
    if len(largo_malo):
        print(
            largo_malo[
                ["ANO_DOC", "UBIGEO", "DEPARTAMENTO_EJECUTORA_NOMBRE", "DISTRITO_EJECUTORA_NOMBRE"]
            ].head(10)
        )

    # 2. Formato de UBIGEO (solo digitos) + valores distintos
    n_distintos = df["UBIGEO"].nunique()
    formato_malo = df[~df["UBIGEO"].str.match(UBIGEO_VALIDO)]
    print(f"\n2. UBIGEO valores distintos: {n_distintos}")
    print(f"   UBIGEO con caracteres que no son digitos: {len(formato_malo)} filas")
    if len(formato_malo):
        print(formato_malo[["ANO_DOC", "UBIGEO"]].head(10))

    # 3. Duplicados exactos (fila completa repetida en las columnas finales)
    duplicados = df[df.duplicated(keep=False)]
    print(f"\n3. Filas exactamente duplicadas (las {len(COLUMNAS_FINALES)} columnas finales iguales): {len(duplicados)}")
    print(
        "   Nota: NO es error que existan varias filas con el mismo (ANO_DOC, UBIGEO, RUBRO_NOMBRE) -- "
        "eso es normal porque se descartaron GENERICA/SUBGENERICA/ESPECIFICA, y la formula de autonomia "
        "necesita sumarlas. Este chequeo busca fila COMPLETA repetida, no esa repeticion esperada."
    )
    if len(duplicados):
        print(duplicados.head(10))

    # 4. Cobertura por año
    print("\n4. Filas por ANO_DOC (post-filtro de nivel de gobierno):")
    print(df["ANO_DOC"].value_counts().sort_index())

    # 5. Rubros presentes
    rubros = sorted(df["RUBRO_NOMBRE"].unique())
    print(f"\n5. RUBRO_NOMBRE distintos ({len(rubros)}):")
    for r in rubros:
        print(f"   - {r}")
    for clave in ["RECURSOS DIRECTAMENTE RECAUDADOS", "IMPUESTOS MUNICIPALES"]:
        print(f"   presente '{clave}': {clave in rubros}")

    # Montos nulos
    print("\n6. Nulos por columna de monto:")
    for col in ["MONTO_PIA", "MONTO_PIM", "MONTO_RECAUDADO"]:
        print(f"   {col}: {df[col].isna().sum()}")

    # Montos negativos
    negativos = (df["MONTO_RECAUDADO"] < 0).sum()
    print(f"\n7. MONTO_RECAUDADO negativo: {negativos} filas ({negativos / len(df):.2%})")

    print("\n--- FIN VALIDACIONES ---\n")


def guardar(df):
    SILVER.mkdir(parents=True, exist_ok=True)
    destino = SILVER / "ingreso.parquet"
    df.to_parquet(destino, index=False)
    print(f"Guardado: {destino} ({len(df)} filas)")


def main():
    df = leer_ingreso()
    df = construir_ubigeo(df)
    df = filtrar_nivel_gobierno(df)
    df = tipar_columnas(df)
    df = recortar_columnas(df)
    validar(df)
    guardar(df)


if __name__ == "__main__":
    main()
