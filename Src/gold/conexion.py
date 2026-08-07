import os
from urllib.parse import quote_plus
from dotenv import load_dotenv
from sqlalchemy import create_engine

load_dotenv()

def armar_cadena_odbc(base_datos):
    return(
        f"DRIVER={{{os.environ['SQL_DRIVER']}}};"
        f"SERVER={os.environ['SQL_SERVER']};"
        f"DATABASE={base_datos};"
        f"Trusted_Connection={os.environ['SQL_TRUSTED_CONNECTION']};"
        "TrustServerCertificate=yes;"
    )
def obtener_motor(base_datos=None):
    base_datos=base_datos or os.environ["SQL_DATABASE"]
    cadena = armar_cadena_odbc(base_datos)
    url=f"mssql+pyodbc:///?odbc_connect={quote_plus(cadena)}"
    return create_engine(url, fast_executemany=True)


