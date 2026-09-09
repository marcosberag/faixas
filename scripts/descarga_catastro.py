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
import argparse
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
    ap = argparse.ArgumentParser()
    ap.add_argument("--zona", default="paradanta")
    args = ap.parse_args()
    suf = "" if args.zona == "paradanta" else "_" + args.zona
    CELDAS.mkdir(parents=True, exist_ok=True)

    faixas = gpd.GeoDataFrame(pd.concat(
        [gpd.read_file(PROC / f"faixas_{n}_{args.zona}_ok.gpkg")
         for n in ("nucleos", "illadas")], ignore_index=True),
        crs="EPSG:25829")
    x0, y0, x1, y1 = (int(v // LADO * LADO) for v in faixas.total_bounds)

    # Que celdas tocan faixa. NO disolver: con la provincia, un union_all() da un
    # multipoligono de medio millon de vertices y este bucle lo evalua celda a
    # celda (aqui serian ~8.600). Se pregunta al indice espacial, que ademas
    # descarta por bbox antes de tocar geometria.
    rejilla = [(x, y) for x in range(x0, x1 + LADO, LADO)
               for y in range(y0, y1 + LADO, LADO)]
    marcos = gpd.GeoDataFrame(
        # OJO con los nombres: `cx` es el indexador de coordenadas de GeoPandas
        # y una columna asi llamada no se puede leer como atributo.
        {"celda_x": [c[0] for c in rejilla], "celda_y": [c[1] for c in rejilla]},
        geometry=[box(x, y, x + LADO, y + LADO) for x, y in rejilla],
        crs="EPSG:25829")
    piezas = faixas.explode(index_parts=False).reset_index(drop=True)
    piezas = piezas[piezas.geometry.notna() & ~piezas.geometry.is_empty]
    tocan = gpd.sjoin(marcos, gpd.GeoDataFrame(geometry=piezas.geometry,
                                               crs=marcos.crs),
                      predicate="intersects", how="inner")
    celdas = sorted(set(zip(tocan.celda_x, tocan.celda_y)))
    print(f"{len(celdas)} celdas de {LADO} m tocan faixa en {args.zona} "
          f"(de {len(rejilla)} de la rejilla)", flush=True)

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

    # OJO: la carpeta de celdas es COMPARTIDA entre zonas (A Paradanta esta
    # DENTRO de Pontevedra), igual que la de los CHM. Un glob("*.gpkg") mezclaria
    # las celdas de todas las zonas descargadas hasta ahora y cambiaria en
    # silencio el resultado del piloto. Se agregan solo las celdas de esta zona.
    rutas = [CELDAS / f"{x}_{y}.gpkg" for x, y in celdas]
    partes = [gpd.read_file(r) for r in rutas if r.exists()]
    todo = gpd.GeoDataFrame(pd.concat(partes, ignore_index=True),
                            crs="EPSG:25829")
    if "gml_id" in todo.columns:
        todo = todo.drop_duplicates("gml_id")
    todo.to_file(PROC / f"edificios_catastro{suf}.gpkg", driver="GPKG")
    print(f"{len(todo):,} edificios -> "
          f"{(PROC / ('edificios_catastro' + suf + '.gpkg')).relative_to(RAIZ)}")
