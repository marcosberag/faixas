"""Conjunto de entrenamiento: copas con etiqueta de especie del IFN.

Las etiquetas salen GRATIS de los rodales puros del IFN4 (O1 >= 80 % de la
ocupacion), filtrados por la fase de persistencia: solo rodales SIN evento
2017-2026 (la etiqueta de 2010 sigue describiendo lo que hay) y erosionados
10 m hacia dentro (el borde del rodal es mezcla y desregistro seguro).

Clases: eucalipto / pino / frondosa. La acacia se queda fuera (1 solo rodal
puro en la comarca) y queda declarada como limite: una copa de acacia se
clasificara como lo que mas se le parezca.

Cada copa lleva su zona de validacion espacial (rejilla de 5x5 km): la
leccion de la fase Sentinel-2 es que validar sin dejar ZONAS enteras fuera
infla el resultado por autocorrelacion espacial.

Salida: datos/procesado/copas/entrenamiento.csv con x, y, h_max, area_m2,
bloque, grupo, OBJECTID_12, zona. Balanceo: se limita cada clase a CAP copas
por sorteo (semilla fija) ANTES de extraer parches.

Uso:
    python scripts/muestra_copas.py
"""
import argparse
import pathlib

import geopandas as gpd
import numpy as np
import pandas as pd

RAIZ = pathlib.Path(__file__).resolve().parent.parent
PROC = RAIZ / "datos" / "procesado"
COPAS = PROC / "copas"

PUREZA_MIN = 0.8
EROSION_M = 10
CAP = 8000            # copas por clase, como mucho
SEMILLA = 20260820
ZONA_M = 5000


def grupo_de(sp):
    if sp.startswith("Eucalyptus"):
        return "eucalipto"
    if sp.startswith("Pinus"):
        return "pino"
    if sp.startswith("Acacia"):
        return None            # fuera: sin masa critica para entrenar
    return "frondosa"


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--zona", default="paradanta")
    args = ap.parse_args()
    suf = "" if args.zona == "paradanta" else "_" + args.zona

    ifn = gpd.read_file(PROC / f"ifn_especies_{args.zona}.gpkg")
    per = pd.read_csv(PROC / "metricas" / f"persistencia_ifn{suf}.csv",
                      encoding="utf-8-sig")
    d = ifn.merge(per[["OBJECTID_12", "estado"]], on="OBJECTID_12")
    oc = d[["O1", "O2", "O3"]].fillna(0)
    d["pureza"] = oc.O1 / oc.sum(axis=1)
    d["grupo"] = d.NOMBRE_SP1.map(grupo_de)
    puros = d[(d.pureza >= PUREZA_MIN) & (d.estado == "persistente")
              & d.grupo.notna()].copy()
    puros["geometry"] = puros.geometry.buffer(-EROSION_M)
    puros = puros[~puros.geometry.is_empty]
    print(f"{len(puros)} rodales puros persistentes tras erosionar {EROSION_M} m")

    # Las copas de todas las zonas comparten carpeta (A Paradanta esta DENTRO de
    # Pontevedra), asi que se filtran por la malla de la zona, igual que los CHM.
    malla = pd.read_csv(PROC / f"malla_lidar_{args.zona}.csv",
                        encoding="utf-8-sig")
    # OJO: la columna `bloque` de la malla trae el nombre con extension .LAZ
    nombres = sorted({pathlib.Path(b).stem for b in malla.bloque})
    rutas = [COPAS / f"{b}.csv" for b in nombres]
    rutas = [r for r in rutas if r.exists()]

    # Y el cruce va bloque a bloque, no sobre la tabla entera: la provincia son
    # 12,9 M de copas y concatenarlas antes de filtrar se come varios GB para
    # tirar el 99 %. Cruzar por bloque y concatenar lo que queda da exactamente
    # el mismo orden de filas, porque sjoin conserva el del lado izquierdo.
    puros_g = puros[["OBJECTID_12", "grupo", "geometry"]]
    trozos, total = [], 0
    for ruta in rutas:
        try:
            c = pd.read_csv(ruta)
        except pd.errors.EmptyDataError:
            continue
        if not len(c):
            continue
        total += len(c)
        g = gpd.GeoDataFrame(c.assign(bloque=ruta.stem),
                             geometry=gpd.points_from_xy(c.x, c.y),
                             crs="EPSG:25829")
        d = gpd.sjoin(g, puros_g, how="inner", predicate="within")
        if len(d):
            trozos.append(d[~d.index.duplicated(keep="first")].drop(
                columns=["index_right", "geometry"]))
    print(f"{total:,} copas en {len(rutas):,} bloques de {args.zona}")
    dentro = pd.concat(trozos, ignore_index=True)
    print("\ncopas dentro de rodal puro, por clase:")
    print(dentro.grupo.value_counts().to_string())

    rng = np.random.default_rng(SEMILLA)
    partes = []
    for gr, sub in dentro.groupby("grupo"):
        if len(sub) > CAP:
            sub = sub.sample(CAP, random_state=SEMILLA)
        partes.append(sub)
    m = pd.concat(partes, ignore_index=True)
    m["zona"] = (m.x // ZONA_M).astype(int).astype(str) + "_" + \
                (m.y // ZONA_M).astype(int).astype(str)

    print(f"\nmuestra final: {len(m):,} copas")
    print(m.groupby("grupo").agg(copas=("x", "size"),
                                 zonas=("zona", "nunique"),
                                 rodales=("OBJECTID_12", "nunique")).to_string())
    m.to_csv(COPAS / f"entrenamiento{suf}.csv", index=False, encoding="utf-8-sig")
    print(f"-> {(COPAS / ('entrenamiento' + suf + '.csv')).relative_to(RAIZ)}")
