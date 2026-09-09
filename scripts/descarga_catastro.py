"""Huellas de edificio del Catastro (INSPIRE WFS) para la zona de faixas.

Para filtrar los falsos positivos de edificacion en las copas: un tejado a dos
aguas pasa el umbral de 5,5 m del CHM y el watershed lo delinea como "copa"
(se cazo uno de 229 m2 sobre una casa de 238 m2 de huella). La tasa de FP ya
los descuenta en agregado; esto los quita del mapa y de la fraccion de especie
del disperso, que es donde ensucian.

WFS INSPIRE de Catastro (BU:Building), por celdas de 2x2 km que tocan faixa,
en EPSG:25829 directo. Reanudable por celda. Salida unica deduplicada:
datos/procesado/edificios_catastro.gpkg

Uso:
    python scripts/descarga_catastro.py
"""
import io
import pathlib
import time

import geopandas as gpd
import pandas as pd
import requests
from shapely.geometry import box

RAIZ = pathlib.Path(__file__).resolve().parent.parent
PROC = RAIZ / "datos" / "procesado"
CELDAS = PROC / "catastro_celdas"

URL = "http://ovc.catastro.meh.es/INSPIRE/wfsBU.aspx"
LADO = 1000        # el WFS rechaza bbox de 2x2 km: "Area of extension out of limits"


VACIA = gpd.GeoDataFrame(geometry=[], crs="EPSG:25829")


def baja_celda(x0, y0, intentos=4):
    for t in range(1, intentos + 1):
        try:
            r = requests.get(URL, timeout=120, params={
                "service": "WFS", "version": "2.0.0", "request": "GetFeature",
                "typeNames": "BU:Building", "srsName": "EPSG::25829",
                "bbox": f"{x0},{y0},{x0+LADO},{y0+LADO},"
                        "urn:ogc:def:crs:EPSG::25829"})
            r.raise_for_status()
        except Exception as e:
            if t == intentos:
                raise
            print(f"    ({type(e).__name__}, reintento {t})", flush=True)
            time.sleep(10 * t)
            continue
        if b"ExceptionReport" in r.content[:500]:
            # celda sin edificios: el servicio devuelve excepcion vacia
            return VACIA.copy()
        try:
            return gpd.read_file(io.BytesIO(r.content))
        except IndexError:
            # otra variante de celda vacia: GML bien formado pero sin capa
            return VACIA.copy()


if __name__ == "__main__":
    CELDAS.mkdir(parents=True, exist_ok=True)
    faixas = gpd.GeoDataFrame(pd.concat(
        [gpd.read_file(PROC / f"faixas_{n}_paradanta_ok.gpkg")
         for n in ("nucleos", "illadas")], ignore_index=True),
        crs="EPSG:25829").union_all()
    x0, y0, x1, y1 = (int(v // LADO * LADO) for v in faixas.bounds)
    celdas = [(x, y) for x in range(x0, x1 + LADO, LADO)
              for y in range(y0, y1 + LADO, LADO)
              if faixas.intersects(box(x, y, x + LADO, y + LADO))]
    print(f"{len(celdas)} celdas de {LADO} m tocan faixa")

    t0 = time.perf_counter()
    for k, (x, y) in enumerate(celdas, 1):
        ruta = CELDAS / f"{x}_{y}.gpkg"
        if ruta.exists():
            continue
        g = baja_celda(x, y)
        cols = [c for c in ("gml_id",) if c in g.columns]
        g[cols + ["geometry"]].to_file(ruta, driver="GPKG")
        if k % 15 == 0 or k == len(celdas):
            print(f"  {k}/{len(celdas)}  "
                  f"{(time.perf_counter()-t0)/k:.1f} s/celda", flush=True)

    partes = [gpd.read_file(p) for p in sorted(CELDAS.glob("*.gpkg"))]
    todo = gpd.GeoDataFrame(pd.concat(partes, ignore_index=True),
                            crs="EPSG:25829")
    if "gml_id" in todo.columns:
        todo = todo.drop_duplicates("gml_id")
    todo.to_file(PROC / "edificios_catastro.gpkg", driver="GPKG")
    print(f"{len(todo):,} edificios -> "
          f"{(PROC / 'edificios_catastro.gpkg').relative_to(RAIZ)}")
