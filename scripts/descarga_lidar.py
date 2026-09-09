"""Descarga bloques LiDAR de la 3a cobertura del PNOA desde el Centro de Descargas.

El CNIG no publica URLs directas a los LAZ: hay que pasar por el buscador. La
secuencia, deducida del javascript de la pagina (js/funciones.js y el inline de
`lidar-tercera-cobertura`), es esta:

  1. GET  /CentroDescargas/lidar-tercera-cobertura     -> abre sesion (JSESSIONID)
  2. POST /CentroDescargas/archivosSerie               -> lista de hojas
       codAgr=MOMDT, codSerie=LIDA3 identifican la serie LiDAR 3a cobertura.
       `coordenadas` es un GeoJSON FeatureCollection con un punto en WGS84;
       devuelve HTML con la hoja que contiene ese punto y su `sec`.
  3. POST /CentroDescargas/initDescargaDir             -> {"muestraLic": ...}
       Para esta serie devuelve muestraLic=NO: no hay licencia que aceptar.
  4. POST /CentroDescargas/descargaDir  secDescDirLA=<sec>  -> el LAZ

Mide y guarda tiempos y tamanos en datos/crudo/lidar/descargas.csv, que es medio
criterio de salida de la fase 1: de ahi sale si la comarca entera es viable.

Uso:
    python scripts/descarga_lidar.py                 # los bloques de BLOQUES
    python scripts/descarga_lidar.py 559 4674        # un bloque concreto
"""
import csv
import json
import pathlib
import re
import sys
import time

import requests
from pyproj import Transformer

RAIZ = pathlib.Path(__file__).resolve().parent.parent
DESTINO = RAIZ / "datos" / "crudo" / "lidar"

BASE = "https://centrodedescargas.cnig.es/CentroDescargas"
COD_AGR = "MOMDT"       # agrupacion "Modelos digitales del terreno"
COD_SERIE = "LIDA3"     # serie "LiDAR 3a cobertura"

# Bloques del prototipo, elegidos con scripts/malla_lidar.py.
# Tres concellos distintos, y reparto distinto entre nucleos e illadas.
BLOQUES = [
    (559, 4674),   # A Canhiza / As Achas   38,0 ha de faixa (26,2 nucleo + 11,8 illada)
    (562, 4668),   # Crecente / Vilar       36,0 ha (23,0 + 13,0)
    (549, 4679),   # Covelo / Barcia        30,3 ha (16,7 + 13,6), zona de mas relieve
]

A_WGS84 = Transformer.from_crs(25829, 4326, always_xy=True)


def sesion():
    s = requests.Session()
    s.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
        "X-Requested-With": "XMLHttpRequest",
    })
    s.get(f"{BASE}/lidar-tercera-cobertura", timeout=60)
    return s


def busca_hoja(s, nw_x, nw_y):
    """Devuelve (nombre, secuencial, mb) de la hoja cuyo centro cae en el bloque.

    El nombre del LAZ codifica la esquina NW, asi que el centro del bloque
    (nw_x, nw_y) esta en X+500, Y-500.
    """
    x, y = nw_x * 1000 + 500, nw_y * 1000 - 500
    lon, lat = A_WGS84.transform(x, y)
    coords = json.dumps({"type": "FeatureCollection", "features": [
        {"type": "Feature", "geometry": {"type": "Point", "coordinates": [lon, lat]}}]})
    r = s.post(f"{BASE}/archivosSerie", timeout=120, data={
        "numPagina": "1", "codAgr": COD_AGR, "codSerie": COD_SERIE,
        "coordenadas": coords,
    })
    r.raise_for_status()
    nombres = re.findall(r"([A-Za-z0-9\-]+\.LAZ)", r.text)
    secs = re.findall(r"linkDescDir_(\d+)", r.text)
    megas = re.findall(r"displayInlineBlock\">([\d.]+)\s*</div>", r.text)
    if not nombres or not secs:
        raise RuntimeError(f"el CNIG no devuelve hoja para {nw_x}-{nw_y} ({x},{y})")
    nombre, sec = nombres[0], secs[0]
    # el nombre tiene que corresponder al bloque pedido, o hemos entendido mal la malla
    if f"-{nw_x}-{nw_y}-" not in nombre:
        raise RuntimeError(f"pedido {nw_x}-{nw_y} pero el CNIG devuelve {nombre}")
    mb = float(megas[-1]) if megas else None
    return nombre, sec, mb


def descarga(s, sec, ruta):
    """Descarga el LAZ a `ruta`. Devuelve (segundos, bytes)."""
    init = s.post(f"{BASE}/initDescargaDir", data={"secuencial": sec}, timeout=60).json()
    if init.get("muestraLic") == "SI":
        # No ha pasado con esta serie. Si pasa, hay que aceptar la licencia a mano.
        raise RuntimeError(f"el CNIG pide aceptar licencia para {sec}: hazlo en el navegador")
    sec_dir = init["secuencialDescDir"]

    t0 = time.perf_counter()
    total = 0
    parcial = ruta.with_suffix(ruta.suffix + ".parcial")
    with s.post(f"{BASE}/descargaDir", data={"secDescDirLA": sec_dir},
                stream=True, timeout=(60, 600)) as r:
        r.raise_for_status()
        with open(parcial, "wb") as f:
            for trozo in r.iter_content(chunk_size=1 << 20):
                f.write(trozo)
                total += len(trozo)
    parcial.replace(ruta)
    return time.perf_counter() - t0, total


def es_laz(ruta):
    """El CNIG puede devolver una pagina de error con codigo 200."""
    with open(ruta, "rb") as f:
        return f.read(4) == b"LASF"


if __name__ == "__main__":
    DESTINO.mkdir(parents=True, exist_ok=True)
    if len(sys.argv) == 3:
        objetivo = [(int(sys.argv[1]), int(sys.argv[2]))]
    else:
        objetivo = BLOQUES

    s = sesion()
    registro = []
    for nw_x, nw_y in objetivo:
        nombre, sec, mb = busca_hoja(s, nw_x, nw_y)
        ruta = DESTINO / nombre
        print(f"\n=== {nombre}  sec={sec}  {mb} MB segun el CNIG")
        if ruta.exists() and es_laz(ruta):
            print(f"  ya esta en disco ({ruta.stat().st_size/1e6:.1f} MB), no se repite")
            continue
        seg, bytes_ = descarga(s, sec, ruta)
        ok = es_laz(ruta)
        print(f"  {bytes_/1e6:>8.1f} MB en {seg:>6.1f} s  "
              f"({bytes_/1e6/seg:.1f} MB/s)  cabecera LASF: {'si' if ok else 'NO'}")
        if not ok:
            raise RuntimeError(f"{nombre} no es un LAZ: mira {ruta}")
        registro.append({"bloque": nombre, "sec": sec, "nw_x": nw_x, "nw_y": nw_y,
                         "bytes": bytes_, "mb": round(bytes_ / 1e6, 2),
                         "segundos": round(seg, 1),
                         "mb_por_s": round(bytes_ / 1e6 / seg, 2)})

    if registro:
        csv_path = DESTINO / "descargas.csv"
        nuevo = not csv_path.exists()
        with open(csv_path, "a", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(registro[0]))
            if nuevo:
                w.writeheader()
            w.writerows(registro)
        mb_tot = sum(r["mb"] for r in registro)
        s_tot = sum(r["segundos"] for r in registro)
        print(f"\n=== {len(registro)} bloques, {mb_tot:,.0f} MB en {s_tot:,.0f} s "
              f"({mb_tot/s_tot:.1f} MB/s de media)")
        print(f"    extrapolado a los 263 bloques de la comarca: "
              f"{263*mb_tot/len(registro)/1024:.1f} GB, "
              f"{263*s_tot/len(registro)/3600:.1f} h de descarga")
        print(f"-> {csv_path.relative_to(RAIZ)}")
