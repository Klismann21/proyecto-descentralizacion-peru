from pathlib import Path
import requests
import zipfile

BRONZE=Path("Data/bronze")

FUENTES = {
    "ingreso": [
        ("2022-Ingreso.csv", "https://fs.datosabiertos.mef.gob.pe/datastorefiles/2022-Ingreso.csv"),
        ("2023-Ingreso.csv", "https://fs.datosabiertos.mef.gob.pe/datastorefiles/2023-Ingreso.csv"),
        ("2024-Ingreso.csv", "https://fs.datosabiertos.mef.gob.pe/datastorefiles/2024-Ingreso.csv"),
        ("2025-Ingreso-Mensual.csv", "https://fs.datosabiertos.mef.gob.pe/datastorefiles/2025-Ingreso-Mensual.csv"),
    ],
    "meta_predial": [
        ("rentas_preguntas.csv", "https://fs.datosabiertos.mef.gob.pe/datastorefiles/rentas_preguntas.csv"),
        ("rentas_estadistica.csv", "https://fs.datosabiertos.mef.gob.pe/datastorefiles/rentas_estadistica.csv"),
        ("rentas_formulario.csv", "https://fs.datosabiertos.mef.gob.pe/datastorefiles/rentas_formulario.csv"),
        ("rentas_esat_estadistica_atm.csv", "https://fs.datosabiertos.mef.gob.pe/datastorefiles/rentas_esat_estadistica_atm.csv"),
        ("rentas_respuestas.csv", "https://fs.datosabiertos.mef.gob.pe/datastorefiles/rentas_respuestas.csv"),
        ("rentas_ano_aplicacion.csv", "https://fs.datosabiertos.mef.gob.pe/datastorefiles/rentas_ano_aplicacion.csv"),
        ("rentas_entidad_estado.csv", "https://fs.datosabiertos.mef.gob.pe/datastorefiles/rentas_entidad_estado.csv"),    
            ]
}
def descargar(url,destino):
    respuesta=requests.get(url,stream=True)
    respuesta.raise_for_status()

    with open(destino,"wb") as f:
        for pedazo in respuesta.iter_content(chunk_size=8192):
            f.write(pedazo)
    peso_en_kb=destino.stat().st_size // 1024
    print(f"{destino.name}({peso_en_kb}KB)")

RENAMU = {
    "2022": "https://www.inei.gob.pe/media/DATOS_ABIERTOS/RENAMU/DATA/2022.zip",
    "2023": "https://www.inei.gob.pe/media/DATOS_ABIERTOS/RENAMU/DATA/2023.zip",
    "2024": "https://www.inei.gob.pe/media/DATOS_ABIERTOS/RENAMU/DATA/2024.zip",
    "2025": "https://proyectos.inei.gob.pe/iinei/srienaho/descarga/CSV/984-Modulo1963.zip",
}

def descargar_renamu(anio, url):
    carpeta = BRONZE / "renamu" / anio          
    carpeta.mkdir(parents=True, exist_ok=True)
    zip_temporal = carpeta / f"renamu_{anio}.zip"
    descargar(url, zip_temporal)
    with zipfile.ZipFile(zip_temporal, "r") as z:
        z.extractall(carpeta)
    zip_temporal.unlink()
    print(f" RENAMU {anio} descomprimido")
   
def main():
    for fuente, archivos in FUENTES.items():
        carpeta = BRONZE / fuente
        carpeta.mkdir(parents=True, exist_ok=True)
        for nombre, url in archivos:
            destino = carpeta / nombre
            try:
                descargar(url, destino)
            except Exception as error:
                print(f"✗ Falló {nombre}: {error}")
    for anio, url in RENAMU.items():
        descargar_renamu(anio, url)

if __name__ == "__main__":
    main()

