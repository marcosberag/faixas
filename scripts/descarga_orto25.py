"""Cache de ortofoto PNOA a 0,25 m/px por bloque LiDAR, para los parches de copa.

A 0,25 m un parche de 16x16 m son 64x64 px: suficiente textura de copa para
clasificar y 16 veces menos disco que la cache de 0,125 m de la fase 2
(aqui hacen falta cientos de bloques, no tres). GeoTIFF con JPEG dentro,
~4-8 MB por km2.

Que bloques: los que tocan rodal puro persistente del IFN (entrenamiento) y
los que tienen faixa con arbolado (aplicacion) — se pasan por argumento o se
calculan aqui. Reanudable.

Uso:
    python scripts/descarga_orto25.py               # entrenamiento + faixa
    python scripts/descarga_orto25.py --solo-puros  # solo entrenamiento
    python scripts/descarga_orto25.py --trozo 0/3   # particion para paralelizar
"""
import argparse
import os
import pathlib
import sys
import time

import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio
from shapely.geometry import box

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from chips_validacion import tesela  # noqa: E402

RAIZ = pathlib.Path(__file__).resolve().parent.parent
PROC = RAIZ / "datos" / "procesado"
LIDAR = PROC / "lidar"
ORTO25 = PROC / "orto25"

RES = 0.25
PX_TESELA = 2000          # 500 m por tesela; 2x2 teselas por bloque
N = 2


def bounds_bloque(nombre):
    p = nombre.split("-")
    x0, y1 = int(p[3]) * 1000, int(p[4]) * 1000   # esquina NOROESTE
    return x0, y1 - 1000, x0 + 1000, y1


def baja_bloque(nombre, intentos=6):
    ruta = ORTO25 / f"{nombre}.tif"
    if ruta.exists():
        return False
    x0, y0, x1, y1 = bounds_bloque(nombre)
    lado = PX_TESELA * RES
    lienzo = np.zeros((N * PX_TESELA, N * PX_TESELA, 3), "uint8")
    for i in range(N):
        for j in range(N):
            for t in range(1, intentos + 1):
                try:
                    a = tesela(x0 + i * lado, y0 + j * lado, lado, PX_TESELA)
                    break
                except Exception as e:
                    if t == intentos:
                        raise
                    print(f"    ({type(e).__name__}, reintento {t})", flush=True)
                    time.sleep(15 * t)
            fila = (N - 1 - j) * PX_TESELA
            lienzo[fila:fila + PX_TESELA, i * PX_TESELA:(i + 1) * PX_TESELA] = a
    perfil = {"driver": "GTiff", "height": N * PX_TESELA, "width": N * PX_TESELA,
              "count": 3, "dtype": "uint8", "crs": "EPSG:25829",
              "transform": rasterio.transform.from_origin(x0, y1, RES, RES),
              "compress": "JPEG", "jpeg_quality": 90, "photometric": "YCBCR",
              "tiled": True, "blockxsize": 512, "blockysize": 512}
    # escritura atomica: varias instancias en paralelo no deben pisarse. Si
    # otra instancia ha creado el destino mientras tanto (la particion se
    # recalcula al relanzar), su trabajo vale igual: se tira el tmp propio.
    tmp = ruta.with_suffix(f".tmp{os.getpid()}.tif")
    with rasterio.open(tmp, "w", **perfil) as dst:
        dst.write(np.moveaxis(lienzo, 2, 0))
    for _ in range(5):
        if ruta.exists():
            tmp.unlink(missing_ok=True)
            return False
        try:
            os.replace(tmp, ruta)
            return True
        except PermissionError:
            time.sleep(2)
    tmp.unlink(missing_ok=True)
    return False


def bloques_que_tocan(marcos, geoms):
    """Bloques que intersecan alguna de `geoms`, sin disolverlas.

    OJO, trampa medida y repetida tres veces en este proyecto: NO hacer
    union_all() antes. Un multipoligono provincial de medio millon de vertices
    deja el indice espacial inutil y cada bloque paga la geometria entera
    (2 h de CPU sin terminar, frente a minutos troceando). sjoin trabaja pieza
    a pieza y usa los indices de los dos lados.
    """
    piezas = gpd.GeoDataFrame(geometry=geoms, crs=marcos.crs)
    piezas = piezas.explode(index_parts=False).reset_index(drop=True)
    piezas = piezas[piezas.geometry.notna() & ~piezas.geometry.is_empty]
    j = gpd.sjoin(marcos, piezas, predicate="intersects", how="inner")
    return set(j.bloque)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--zona", default="paradanta",
                    help="sufijo de faixas_{capa}_{zona}_ok.gpkg e ifn_especies_{zona}.gpkg")
    ap.add_argument("--solo-puros", action="store_true")
    ap.add_argument("--trozo", default="0/1",
                    help="i/n: procesa los pendientes con indice %% n == i")
    args = ap.parse_args()
    trozo_i, trozo_n = (int(v) for v in args.trozo.split("/"))
    suf = "" if args.zona == "paradanta" else "_" + args.zona
    ORTO25.mkdir(parents=True, exist_ok=True)

    bloques = sorted(p.stem.replace("_chm", "") for p in LIDAR.glob("*_chm.tif"))
    marcos = gpd.GeoDataFrame(
        {"bloque": bloques},
        geometry=[box(*bounds_bloque(b)) for b in bloques], crs="EPSG:25829")

    ifn = gpd.read_file(PROC / f"ifn_especies_{args.zona}.gpkg")
    quiere = set()

    # rodales puros persistentes (los del entrenamiento), erosionados 10 m.
    # La persistencia es la fase 5 y puede no estar hecha todavia en una zona
    # nueva: entonces se avisa y se baja solo lo de faixa, que no depende de
    # ella. Al relanzar despues, la cache es reanudable y completa los puros.
    ruta_per = PROC / "metricas" / f"persistencia_ifn{suf}.csv"
    if ruta_per.exists():
        per = pd.read_csv(ruta_per, encoding="utf-8-sig")
        d = ifn.merge(per[["OBJECTID_12", "estado"]], on="OBJECTID_12")
        oc = d[["O1", "O2", "O3"]].fillna(0)
        d["pureza"] = oc.O1 / oc.sum(axis=1)
        puros = d[(d.pureza >= 0.8) & (d.estado == "persistente")
                  & ~d.NOMBRE_SP1.str.startswith("Acacia")]
        erosion = puros.geometry.buffer(-10)
        quiere |= bloques_que_tocan(marcos, erosion)
        print(f"{len(puros)} rodales puros persistentes -> {len(quiere)} bloques",
              flush=True)
    elif args.solo_puros:
        raise SystemExit(
            f"no existe {ruta_per.name}: los puros del entrenamiento salen de la "
            f"fase 5 (persistencia), que en la zona {args.zona} no esta hecha")
    else:
        print(f"AVISO: sin {ruta_per.name} (fase 5 pendiente en {args.zona}): "
              "se baja solo lo de faixa. Relanzar cuando exista para completar "
              "los bloques de entrenamiento.", flush=True)

    if not args.solo_puros:
        faixas = gpd.GeoDataFrame(pd.concat(
            [gpd.read_file(PROC / f"faixas_{n}_{args.zona}_ok.gpkg")
             for n in ("nucleos", "illadas")], ignore_index=True), crs=ifn.crs)
        quiere |= bloques_que_tocan(marcos, faixas.geometry)

    hechos = {p.stem for p in ORTO25.glob("*.tif")}
    pendientes = [b for k, b in enumerate(sorted(quiere - hechos))
                  if k % trozo_n == trozo_i]
    print(f"{len(quiere)} bloques necesarios, {len(pendientes)} en este trozo "
          f"({args.trozo})", flush=True)

    t0 = time.perf_counter()
    for k, b in enumerate(pendientes, 1):
        baja_bloque(b)
        media = (time.perf_counter() - t0) / k
        if k % 10 == 0 or k == len(pendientes):
            mb = sum(p.stat().st_size for p in ORTO25.glob("*.tif")) / 1e6
            print(f"  {k}/{len(pendientes)}  {media:.0f} s/bloque  {mb:.0f} MB",
                  flush=True)
    print(f"-> {ORTO25.relative_to(RAIZ)}")
