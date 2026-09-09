"""Serie anual de NDVI de verano (2017-2026) por rodal del IFN, TILE A TILE.

Primera pieza del detector de eventos de dosel. La idea que la sostiene: los
arboles no cambian de especie, asi que si un rodal del IFN 2010 no ha sufrido
un evento de reemplazo (corta, incendio, plantacion), su etiqueta de especie
sigue valiendo hoy. Detectar EVENTOS es lo tratable con Sentinel-2; clasificar
especie por pixel no lo era, y esta medido en el walkthrough (seccion 13).

POR QUE TILE A TILE (el cambio al salir de la comarca, 09-09-2026)
------------------------------------------------------------------
La version del piloto componia la mediana de las 3 escenas menos nubladas de
TODO el bbox. Se lo podia permitir porque A Paradanta cabe entera en un unico
tile MGRS (29TNG) y toda escena cubria toda la zona.

Pontevedra son 8.500 km2 contra 500, y caen en CUATRO tiles: 29TNG, 29TMG,
29TNH y 29TMH. Con el metodo viejo las 3 escenas menos nubladas de un verano
pueden salir todas del mismo tile, y entonces el compuesto tiene dato en un
cuarto de la provincia y NaN en el resto. Sin avisar, porque un NaN no es un
error: se propaga a la media del rodal y de ahi al detector de eventos.

Asi que se compone por tile, sobre la interseccion de ese tile con la zona, y
las medias por rodal se acumulan (suma y cuenta de pixeles validos) a lo largo
de los tiles. Un rodal en el solape de dos tiles recibe la media ponderada por
pixeles validos de cada uno, que es lo que se quiere.

Que hace:
  1. Descubre los tiles MGRS que cubren la zona, preguntando al catalogo.
  2. Para cada tile y cada verano de 2017 a 2026, compone la mediana de NDVI de
     las 3 escenas menos nubladas DE ESE TILE (15-jun a 31-ago, la misma ventana
     que el vuelo LiDAR). Reusa las funciones de descarga_s2.py con sus dos
     guardias: el offset del STAC NO se aplica (COG armonizados) y se aborta si
     el NDVI sale de [-1, 1].
  3. Rasteriza los rodales del IFN a la rejilla de 10 m de cada tile y acumula
     suma y cuenta de NDVI por rodal y anho.

Por que 2017 y no 2010: la cobertura L2A fiable de Sentinel-2 en AWS empieza
en 2017. El hueco 2010-2017 queda declarado; taparlo es trabajo para las
ortofotos historicas del PNOA (2011, 2014, 2017) o Landsat, no para esto.

DIAGNOSTICO DE DERIVA incluido: se imprime la mediana de NDVI de cada tile por
anho. Un escalon brusco en 2022 delataria que la armonizacion de los COG no es
homogenea en todo el archivo (el cambio de baseline de Copernicus fue entonces).
Si aparece, parar y revisar antes de creerse ningun evento.

Reanudable: los compuestos ya en disco no se rehacen. Con --zona paradanta
reutiliza los `ndvi_verano_{anho}.tif` del piloto, que no llevaban tile en el
nombre, para no rehacer trabajo ni romper la no-regresion.

Uso:
    python scripts/serie_s2_anual.py --zona pontevedra
"""
import argparse
import pathlib
import sys

import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio
import requests
from rasterio.features import rasterize
from rasterio.transform import from_origin

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from descarga_s2 import (BBOX_4326, BBOX_25829, CRS, GDAL, RES, STAC,  # noqa: E402
                         ndvi_escena)

RAIZ = pathlib.Path(__file__).resolve().parent.parent
PROC = RAIZ / "datos" / "procesado"
S2 = PROC / "s2"

ANHOS = range(2017, 2027)
ESCENAS_POR_ANHO = 3
MARGEN = 500.0          # m de holgura alrededor de la zona


def sufijo(zona):
    return "" if zona == "paradanta" else f"_{zona}"


def caja_zona(zona):
    """Bbox de la zona en EPSG:25829 y en EPSG:4326, con margen.

    La zona piloto conserva la caja historica que declara descarga_s2.py: los
    compuestos de 2017-2026 ya en disco se cortaron con ella, y recalcularla
    desde las faixas daria una rejilla de otro tamano que no encajaria con
    ellos. No-regresion antes que elegancia.
    """
    if zona == "paradanta":
        return BBOX_25829, BBOX_4326
    fx = gpd.GeoDataFrame(pd.concat(
        [gpd.read_file(PROC / f"faixas_{n}_{zona}_ok.gpkg")
         for n in ("nucleos", "illadas")], ignore_index=True), crs=CRS)
    x0, y0, x1, y1 = fx.total_bounds
    caja = (x0 - MARGEN, y0 - MARGEN, x1 + MARGEN, y1 + MARGEN)
    g4 = gpd.GeoSeries.from_wkt(
        [f"POINT ({caja[0]} {caja[1]})", f"POINT ({caja[2]} {caja[3]})"],
        crs=CRS).to_crs(4326)
    return caja, (g4.x.min(), g4.y.min(), g4.x.max(), g4.y.max())


def consulta(rango, caja4326, nube_max, limite=500):
    r = requests.post(STAC, json={
        "collections": ["sentinel-2-l2a"], "bbox": list(caja4326),
        "datetime": rango, "query": {"eo:cloud_cover": {"lt": nube_max}},
        "limit": limite}, timeout=120)
    r.raise_for_status()
    return r.json().get("features", [])


def tile_de(item):
    p = item["properties"]
    for k in ("grid:code", "s2:mgrs_tile"):
        if k in p:
            return str(p[k]).replace("MGRS-", "")
    return item["id"].split("_")[1]


def escenas_del_anho(anho, tile, caja4326):
    """Las ESCENAS_POR_ANHO menos nubladas de ese tile en ese verano."""
    rango = f"{anho}-06-15T00:00:00Z/{anho}-08-31T23:59:59Z"
    for nube in (15, 50):
        fs = [f for f in consulta(rango, caja4326, nube) if tile_de(f) == tile]
        if len(fs) >= 2:
            break
    fs.sort(key=lambda x: x["properties"]["eo:cloud_cover"])
    return fs[:ESCENAS_POR_ANHO]


def rejilla_de(caja):
    """Grid a 10 m alineado a multiplos de 10 en EPSG:25829."""
    x0 = np.floor(caja[0] / RES) * RES
    y1 = np.ceil(caja[3] / RES) * RES
    w = int(np.ceil((caja[2] - x0) / RES))
    h = int(np.ceil((y1 - caja[1]) / RES))
    return from_origin(x0, y1, RES, RES), w, h


def caja_del_tile(items, caja):
    """Interseccion del tile (bbox de sus escenas) con la caja de la zona."""
    bs = np.array([f["bbox"] for f in items])
    g = gpd.GeoSeries.from_wkt(
        [f"POINT ({bs[:, 0].min()} {bs[:, 1].min()})",
         f"POINT ({bs[:, 2].max()} {bs[:, 3].max()})"], crs=4326).to_crs(CRS)
    t = (g.x.min(), g.y.min(), g.x.max(), g.y.max())
    inter = (max(t[0], caja[0]), max(t[1], caja[1]),
             min(t[2], caja[2]), min(t[3], caja[3]))
    return inter if inter[2] > inter[0] and inter[3] > inter[1] else None


def ruta_compuesta(anho, tile, suf):
    nueva = S2 / f"ndvi_verano_{anho}{suf}_{tile}.tif"
    if nueva.exists():
        return nueva
    legada = S2 / f"ndvi_verano_{anho}.tif"      # el piloto, sin tile en el nombre
    if suf == "" and legada.exists():
        return legada
    return nueva


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--zona", default="paradanta")
    args = ap.parse_args()
    suf = sufijo(args.zona)
    S2.mkdir(parents=True, exist_ok=True)

    caja, caja4326 = caja_zona(args.zona)
    print(f"zona {args.zona}: {(caja[2]-caja[0])/1000:.0f} x "
          f"{(caja[3]-caja[1])/1000:.0f} km", flush=True)

    ifn = gpd.read_file(PROC / f"ifn_especies_{args.zona}.gpkg")
    n_rod = len(ifn)
    print(f"{n_rod:,} rodales del IFN", flush=True)

    # --- que tiles cubren la zona -------------------------------------------
    sonda = consulta("2024-06-15T00:00:00Z/2024-08-31T23:59:59Z", caja4326, 15)
    por_tile = {}
    for f in sonda:
        por_tile.setdefault(tile_de(f), []).append(f)
    tiles = sorted(por_tile)
    print(f"tiles MGRS que cubren la zona: {', '.join(tiles)}", flush=True)

    suma = {a: np.zeros(n_rod) for a in ANHOS}
    cuenta = {a: np.zeros(n_rod, dtype="int64") for a in ANHOS}
    medianas = {}
    px_rodal = np.zeros(n_rod, dtype="int64")

    with rasterio.Env(**GDAL):
        for tile in tiles:
            recorte = caja_del_tile(por_tile[tile], caja)
            if recorte is None:
                print(f"\n{tile}: no solapa la zona, se salta", flush=True)
                continue
            tr, w, h = rejilla_de(recorte)
            print(f"\n=== {tile}: {w} x {h} px "
                  f"({w*h/1e6:.0f} M) ===", flush=True)

            ids = rasterize(
                [(g, i + 1) for i, g in enumerate(ifn.geometry)],
                out_shape=(h, w), transform=tr, fill=0,
                all_touched=False, dtype="int32")
            if not (ids > 0).any():
                print("  ningun rodal cae aqui, se salta", flush=True)
                continue
            print(f"  {(ids > 0).sum():,} celdas de rodal", flush=True)
            px_rodal += np.bincount(ids.ravel(), minlength=n_rod + 1)[1:]

            for a in ANHOS:
                ruta = ruta_compuesta(a, tile, suf)
                if not ruta.exists():
                    items = escenas_del_anho(a, tile, caja4326)
                    if not items:
                        print(f"  {a}: SIN ESCENAS utilizables", flush=True)
                        continue
                    capas = np.stack([ndvi_escena(it, tr, w, h) for it in items])
                    nd = np.nanmedian(capas, axis=0, overwrite_input=True)
                    del capas
                    perfil = dict(driver="GTiff", dtype="float32", count=1,
                                  width=w, height=h, crs=CRS, transform=tr,
                                  nodata=np.nan, compress="deflate", tiled=True,
                                  blockxsize=512, blockysize=512)
                    tmp = ruta.with_suffix(".tmp.tif")
                    with rasterio.open(tmp, "w", **perfil) as dst:
                        dst.write(nd.astype("float32"), 1)
                    tmp.replace(ruta)
                    print(f"  {a}: {len(items)} escenas, mediana "
                          f"{np.nanmedian(nd):.3f}, "
                          f"{100*np.isfinite(nd).mean():.0f} % con dato",
                          flush=True)
                else:
                    with rasterio.open(ruta) as s:
                        nd = s.read(1)
                    if nd.shape != (h, w):
                        print(f"  {a}: compuesto en disco con otra rejilla "
                              f"{nd.shape} != {(h, w)}, se salta", flush=True)
                        continue
                    print(f"  {a}: ya en disco", flush=True)

                medianas[(tile, a)] = float(np.nanmedian(nd))
                val = np.isfinite(nd)
                idv = ids[val].ravel()
                suma[a] += np.bincount(idv, weights=nd[val].ravel(),
                                       minlength=n_rod + 1)[1:]
                cuenta[a] += np.bincount(idv, minlength=n_rod + 1)[1:]
                del nd, val, idv

    # --- diagnostico de deriva ----------------------------------------------
    print("\ndiagnostico de deriva (mediana de NDVI por tile y anho; "
          "sin escalones)")
    print("  anho  " + "  ".join(f"{t:>8}" for t in tiles))
    for a in ANHOS:
        fila = "  ".join(
            f"{medianas.get((t, a), float('nan')):>8.3f}" for t in tiles)
        print(f"  {a}  {fila}")

    # --- salida --------------------------------------------------------------
    filas = {"OBJECTID_12": ifn.OBJECTID_12, "sp": ifn.NOMBRE_SP1.str.strip(),
             "n_px": px_rodal}
    for a in ANHOS:
        with np.errstate(invalid="ignore", divide="ignore"):
            filas[f"ndvi_{a}"] = np.round(
                np.where(cuenta[a] > 0, suma[a] / np.maximum(cuenta[a], 1),
                         np.nan), 4)
    out = pd.DataFrame(filas)
    ruta = S2 / f"serie_ndvi_rodal{suf}.csv"
    out.to_csv(ruta, index=False, encoding="utf-8-sig")
    con_dato = int((out[[f"ndvi_{a}" for a in ANHOS]].notna().sum(axis=1) > 0).sum())
    print(f"\n{con_dato:,} de {n_rod:,} rodales con serie -> "
          f"{ruta.relative_to(RAIZ)}")
