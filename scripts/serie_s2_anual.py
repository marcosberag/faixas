"""Serie anual de NDVI de verano (2017-2026) sobre la zona piloto, por rodal.

Primera pieza del detector de eventos de dosel. La idea que la sostiene: los
arboles no cambian de especie, asi que si un rodal del IFN 2010 no ha sufrido
un evento de reemplazo (corta, incendio, plantacion), su etiqueta de especie
sigue valiendo hoy. Detectar EVENTOS es lo tratable con Sentinel-2; clasificar
especie por pixel no lo era, y esta medido en el walkthrough (seccion 13).

Que hace:
  1. Para cada verano de 2017 a 2026, compone la mediana de NDVI de las 3
     escenas menos nubladas (15-jun a 31-ago, la misma ventana que el vuelo
     LiDAR). Reusa las funciones de descarga_s2.py, con sus dos guardias:
     el offset del STAC NO se aplica (COG armonizados) y se aborta si el NDVI
     sale de [-1, 1].
  2. Rasteriza los 658 rodales del IFN a la rejilla de 10 m y saca la media
     de NDVI de cada rodal en cada anho.

Por que 2017 y no 2010: la cobertura L2A fiable de Sentinel-2 en AWS empieza
en 2017. El hueco 2010-2017 queda declarado; taparlo es trabajo para las
ortofotos historicas del PNOA (2011, 2014, 2017) o Landsat, no para esto.

DIAGNOSTICO DE DERIVA incluido: se imprime la mediana de NDVI de toda la zona
por anho. Un escalon brusco en 2022 delataria que la armonizacion de los COG
no es homogenea en todo el archivo (el cambio de baseline de Copernicus fue
entonces). Si aparece, parar y revisar antes de creerse ningun evento.

Reanudable: los compuestos ya en disco no se rehacen.

Uso:
    python scripts/serie_s2_anual.py
"""
import pathlib
import sys

import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio
from rasterio.features import rasterize

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from descarga_s2 import GDAL, busca, ndvi_escena, rejilla

RAIZ = pathlib.Path(__file__).resolve().parent.parent
PROC = RAIZ / "datos" / "procesado"
S2 = PROC / "s2"

ANHOS = range(2017, 2027)
ESCENAS_POR_ANHO = 3


def compuesta_verano(anho, tr, w, h):
    rango = f"{anho}-06-15T00:00:00Z/{anho}-08-31T23:59:59Z"
    items = busca(rango, ESCENAS_POR_ANHO, nube_max=15)
    if len(items) < 2:
        # verano nublado o archivo corto: se relaja el filtro antes de rendirse
        items = busca(rango, ESCENAS_POR_ANHO, nube_max=50)
    if not items:
        return None, 0
    capas = [ndvi_escena(it, tr, w, h) for it in items]
    return np.nanmedian(np.stack(capas), axis=0), len(items)


if __name__ == "__main__":
    tr, w, h = rejilla()
    perfil = dict(driver="GTiff", dtype="float32", count=1, width=w, height=h,
                  crs="EPSG:25829", transform=tr, nodata=np.nan,
                  compress="deflate", tiled=True, blockxsize=512, blockysize=512)

    print("compuestas anuales de verano (mediana de las escenas menos nubladas)")
    with rasterio.Env(**GDAL):
        for a in ANHOS:
            ruta = S2 / f"ndvi_verano_{a}.tif"
            if ruta.exists():
                print(f"  {a}: ya en disco", flush=True)
                continue
            nd, n = compuesta_verano(a, tr, w, h)
            if nd is None:
                print(f"  {a}: SIN ESCENAS utilizables", flush=True)
                continue
            with rasterio.open(ruta, "w", **perfil) as dst:
                dst.write(nd.astype("float32"), 1)
            print(f"  {a}: {n} escenas, mediana de zona {np.nanmedian(nd):.3f}, "
                  f"{100*np.isfinite(nd).mean():.0f} % con dato", flush=True)

    # --- media por rodal y anho ---------------------------------------------
    ifn = gpd.read_file(PROC / "ifn_especies_paradanta.gpkg")
    ids = rasterize(
        [(g, i + 1) for i, g in enumerate(ifn.geometry)],
        out_shape=(h, w), transform=tr, fill=0, all_touched=False, dtype="int32")
    print(f"\n{len(ifn)} rodales rasterizados a 10 m "
          f"({(ids > 0).sum():,} celdas)")

    filas = {"OBJECTID_12": ifn.OBJECTID_12, "sp": ifn.NOMBRE_SP1.str.strip(),
             "n_px": np.bincount(ids.ravel(), minlength=len(ifn) + 1)[1:]}
    print(f"\n{'anho':>6} {'mediana zona':>13}   (diagnostico de deriva: sin escalones)")
    for a in ANHOS:
        ruta = S2 / f"ndvi_verano_{a}.tif"
        if not ruta.exists():
            continue
        with rasterio.open(ruta) as s:
            nd = s.read(1)
        val = np.isfinite(nd)
        suma = np.bincount(ids[val].ravel(), weights=nd[val].ravel(),
                           minlength=len(ifn) + 1)[1:]
        cuenta = np.bincount(ids[val].ravel(), minlength=len(ifn) + 1)[1:]
        with np.errstate(invalid="ignore"):
            filas[f"ndvi_{a}"] = np.round(suma / cuenta, 4)
        print(f"  {a:>4} {np.nanmedian(nd):>13.3f}")

    out = pd.DataFrame(filas)
    out.to_csv(S2 / "serie_ndvi_rodal.csv", index=False, encoding="utf-8-sig")
    print(f"\n-> {(S2 / 'serie_ndvi_rodal.csv').relative_to(RAIZ)}")
