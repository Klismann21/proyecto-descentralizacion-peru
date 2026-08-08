from pathlib import Path

import pandas as pd
from sqlalchemy import text

from conexion import obtener_motor

BRONZE = Path("Data/bronze/ingreso")

ARCHIVOS = [
    "2022-Ingreso.csv",
    "2023-Ingreso.csv",
    "2024-Ingreso.csv",
    "2025-Ingreso-Mensual.csv",
]

COLUMNAS = ["NIVEL_GOBIERNO_NOMBRE", "ANO_DOC", "MONTO_PIM", "MONTO_RECAUDADO"]


def leer_bronze_sin_filtrar():
    # Lee los CSV crudos de Bronze, NO los de Silver -- Silver excluye
    # GOBIERNO NACIONAL a proposito (regla congelada), y acá se necesita
    # justo ese nivel para el contexto. No se filtra ningun nivel.
    partes = []
    for nombre in ARCHIVOS:
        df = pd.read_csv(BRONZE / nombre, encoding="utf-8", sep=",", usecols=COLUMNAS)
        partes.append(df)
    df = pd.concat(partes, ignore_index=True)
    print(f"Filas leidas de Bronze (3 niveles, sin filtrar): {len(df):,}")
    print(f"Niveles de gobierno encontrados: {sorted(df['NIVEL_GOBIERNO_NOMBRE'].unique())}")
    return df


def agregar_por_nivel_y_anio(df):
    agregado = (
        df.groupby(["NIVEL_GOBIERNO_NOMBRE", "ANO_DOC"], as_index=False)[["MONTO_PIM", "MONTO_RECAUDADO"]]
        .sum()
        .rename(columns={"ANO_DOC": "ANO"})
    )
    print(f"Filas agregadas (nivel x año): {len(agregado)}")
    return agregado


def cargar(agregado):
    motor = obtener_motor()
    with motor.begin() as con:
        con.execute(text("TRUNCATE TABLE gold.REPARTO_NIVEL_GOBIERNO"))

    registros = list(agregado.itertuples(index=False, name=None))
    insert_sql = (
        "INSERT INTO gold.REPARTO_NIVEL_GOBIERNO "
        "(NIVEL_GOBIERNO_NOMBRE, ANO, MONTO_PIM, MONTO_RECAUDADO) VALUES (?, ?, ?, ?)"
    )
    conn = motor.raw_connection()
    cursor = conn.cursor()
    cursor.fast_executemany = True
    cursor.executemany(insert_sql, registros)
    conn.commit()
    conn.close()
    print(f"Filas cargadas en gold.REPARTO_NIVEL_GOBIERNO: {len(registros)}")


def reportar_porcentajes(agregado):
    print("\n--- % de MONTO_PIM por nivel de gobierno, por año ---")
    pim = agregado.pivot(index="ANO", columns="NIVEL_GOBIERNO_NOMBRE", values="MONTO_PIM")
    pim_pct = pim.div(pim.sum(axis=1), axis=0) * 100
    print(pim_pct.round(2))

    print("\n--- % de MONTO_RECAUDADO por nivel de gobierno, por año ---")
    rec = agregado.pivot(index="ANO", columns="NIVEL_GOBIERNO_NOMBRE", values="MONTO_RECAUDADO")
    rec_pct = rec.div(rec.sum(axis=1), axis=0) * 100
    print(rec_pct.round(2))


def main():
    df = leer_bronze_sin_filtrar()
    agregado = agregar_por_nivel_y_anio(df)
    cargar(agregado)
    reportar_porcentajes(agregado)


if __name__ == "__main__":
    main()
