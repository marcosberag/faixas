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
    ifn = gpd.read_file(PROC / "ifn_especies_paradanta.gpkg")
    per = pd.read_csv(PROC / "metricas" / "persistencia_ifn.csv",
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

    trozos = []
    for ruta in sorted(COPAS.glob("PNOA-*.csv")):
        c = pd.read_csv(ruta)
        if len(c):
            trozos.append(c.assign(bloque=ruta.stem))
    copas = pd.concat(trozos, ignore_index=True)
    print(f"{len(copas):,} copas en la comarca")

    g = gpd.GeoDataFrame(copas, geometry=gpd.points_from_xy(copas.x, copas.y),
                         crs="EPSG:25829")
    dentro = gpd.sjoin(g, puros[["OBJECTID_12", "grupo", "geometry"]],
                       how="inner", predicate="within")
    dentro = dentro[~dentro.index.duplicated(keep="first")].drop(
        columns=["index_right", "geometry"])
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
    m.to_csv(COPAS / "entrenamiento.csv", index=False, encoding="utf-8-sig")
    print(f"-> {(COPAS / 'entrenamiento.csv').relative_to(RAIZ)}")
