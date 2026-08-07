import sys
import pandas as pd
from pathlib import Path
from sqlalchemy import text
from conexion import obtener_motor
import numpy as np
def truncar_tablas():
    motor=obtener_motor("GoldFiscal")
    tablas = ["silver.ingreso", "silver.meta_predial", "silver.renamu"]
    with motor.begin() as con:
        for tabla in tablas:
            con.execute(text(f"TRUNCATE TABLE {tabla}"))
            print(f"{tabla} vaciada")
def crear_database():
    motor_master=obtener_motor("master")
    motor_master= motor_master.execution_options(isolation_level="AUTOCOMMIT")

    ruta_sql=Path("SQL/ddl/01_crear_database.sql")
    sql=ruta_sql.read_text(encoding="utf-8")
    with motor_master.connect() as con:
        con.execute(text(sql))
    print("Base de Datos Creada")
def rellenar_query():
    motor=obtener_motor("GoldFiscal")
    df=pd.read_parquet("Data/silver/renamu/renamu.parquet")
    columnas_p23 = sorted(c for c in df.columns if c.startswith("P23"))
    bloque_columnas = ",\n    ".join(f"{c} VARCHAR(100) NULL" for c in columnas_p23) + ","
    sql = Path("SQL/ddl/02_crear_esquema_y_tablas.sql").read_text(encoding="utf-8")
    sql = sql.replace("{{COLUMNAS_P23}}", bloque_columnas)
    with motor.begin() as con:
        con.execute(text(sql))
def cargar_meta_predial():
    motor=obtener_motor("GoldFiscal")
    df=pd.read_parquet("Data/silver/meta_predial/meta_predial.parquet")
    df = df.replace([np.inf, -np.inf], np.nan)
    df = df.astype(object).where(pd.notna(df), None)
    registros=list(df.itertuples(index=False, name=None))
    columnas = list(df.columns)
    marcadores = ", ".join("?" for _ in columnas)
    insert_sql = f"INSERT INTO silver.meta_predial ({', '.join(columnas)}) VALUES ({marcadores})"
    conn = motor.raw_connection()      
    cursor = conn.cursor()
    cursor.fast_executemany = True     
    cursor.executemany(insert_sql, registros)
    conn.commit()                      
    conn.close()
def cargar_renamu():
    motor=obtener_motor("GoldFiscal")
    df=pd.read_parquet("Data/silver/renamu/renamu.parquet")
    df = df.replace([np.inf, -np.inf], np.nan)
    df = df.astype(object).where(pd.notna(df), None)
    registros=list(df.itertuples(index=False, name=None))
    columnas = list(df.columns)
    marcadores = ", ".join("?" for _ in columnas)
    insert_sql = f"INSERT INTO silver.renamu ({', '.join(columnas)}) VALUES ({marcadores})"
    conn = motor.raw_connection()      
    cursor = conn.cursor()
    cursor.fast_executemany = True     
    cursor.executemany(insert_sql, registros)
    conn.commit()                      
    conn.close()
def cargar_ingreso():
    motor=obtener_motor("GoldFiscal")
    df=pd.read_parquet("Data/silver/ingreso/ingreso.parquet")
    df = df.replace([np.inf, -np.inf], np.nan)
    df = df.astype(object).where(pd.notna(df), None)
    registros=list(df.itertuples(index=False, name=None))
    tamano_lote=50000
    total=len(registros)
    columnas = list(df.columns)
    marcadores = ", ".join("?" for _ in columnas)
    insert_sql = f"INSERT INTO silver.ingreso ({', '.join(columnas)}) VALUES ({marcadores})"
    conn = motor.raw_connection()
    cursor = conn.cursor()
    cursor.fast_executemany = True 
    for inicio in range(0, total, tamano_lote):
        lote = registros[inicio:inicio + tamano_lote]   
        cursor.executemany(insert_sql, lote)
        conn.commit()                                     
        print(f"Insertadas {min(inicio + tamano_lote, total)} / {total} filas")
    conn.close()
def main():
    truncar_tablas()
    cargar_meta_predial()
    cargar_renamu()
    cargar_ingreso()
if __name__ == "__main__":
    if "--setup" in sys.argv:
        crear_database()
        rellenar_query()
    else:
        main()
