"""Uno-off: completa celdas rebeldes de Catastro bajandolas por cuadrantes de 500 m.

El WFS rechaza bbox grandes ("Area of extension out of limits"), asi que las
celdas que fallaron de una pieza se piden troceadas en 4 cuadrantes de 500x500 m
y se concatenan. Mismo formato de guardado que scripts/descarga_catastro.py:
GPKG con [gml_id, geometry] en EPSG:25829.

Uso:
    python scripts/aux_descarga_cuadrantes.py <x0_y0> [<x0_y0> ...]
"""
import io
import sys
import time
import pathlib

import geopandas as gpd
import pandas as pd
import requests

RAIZ = pathlib.Path(__file__).resolve().parent.parent
CELDAS = RAIZ / "datos" / "procesado" / "catastro_celdas"

URL = "http://ovc.catastro.meh.es/INSPIRE/wfsBU.aspx"
LADO = 500                      # cuadrante
PAUSA = 12                      # s entre requests (rate-limit de Catastro)
VACIA = gpd.GeoDataFrame(geometry=[], crs="EPSG:25829")


def baja(x0, y0, intentos=4):
    """Un cuadrante de 500 m, o None si el servicio no responde."""
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
                print(f"    ({type(e).__name__}) cuadrante {x0}_{y0} FALLA "
                      f"tras {intentos} intentos", flush=True)
                return None
            print(f"    ({type(e).__name__}, reintento {t})", flush=True)
            time.sleep(20 * t)
            continue
        if b"ExceptionReport" in r.content[:500]:
            return VACIA.copy()
        try:
            return gpd.read_file(io.BytesIO(r.content))
        except IndexError:
            return VACIA.copy()


def una_celda(x0, y0):
    cuadrantes = [(x0, y0), (x0 + 500, y0), (x0, y0 + 500), (x0 + 500, y0 + 500)]
    partes = []
    for i, (cx, cy) in enumerate(cuadrantes):
        if i:
            time.sleep(PAUSA)
        g = baja(cx, cy)
        if g is None:
            return None
        partes.append(g)
        print(f"    cuadrante {cx}_{cy}: {len(g)} features", flush=True)
    return gpd.GeoDataFrame(pd.concat(partes, ignore_index=True),
                            crs="EPSG:25829")


if __name__ == "__main__":
    t0 = time.perf_counter()
    fallos = []
    for arg in sys.argv[1:]:
        x, y = (int(v) for v in arg.split("_"))
        ruta = CELDAS / f"{x}_{y}.gpkg"
        print(f"celda {x}_{y}", flush=True)
        g = una_celda(x, y)
        if g is None:
            fallos.append(arg)
            continue
        cols = [c for c in ("gml_id",) if c in g.columns]
        g[cols + ["geometry"]].to_file(ruta, driver="GPKG")
        print(f"  -> {ruta.name}: {len(g)} features", flush=True)
    print(f"\n{len(sys.argv)-1-len(fallos)}/{len(sys.argv)-1} celdas "
          f"en {(time.perf_counter()-t0)/60:.1f} min", flush=True)
    if fallos:
        print("FALLOS:", " ".join(fallos), flush=True)
