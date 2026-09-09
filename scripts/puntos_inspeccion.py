"""Puntos concretos de inspeccion: del ranking por parroquia al sitio al que ir.

El ranking dice QUE parroquia mirar; esto dice DONDE aparcar. Tres fuentes,
por certeza descendente, cada una con su respaldo declarado:

  35m       calvas contiguas de CHM > 35 m dentro de faixa. En Galicia solo el
            eucalipto pasa de 35 m; regla comprobada a ojo (14/15).
  rodal     rodal del IFN con fraccion prohibida >= 0.5, PERSISTENTE segun la
            fase 5, y con arbolado real (CHM > 5.5 m) dentro de faixa.
  disperso  cluster de copas sueltas clasificadas prohibidas por la fase 6,
            solo en zonas validadas (AUC >= 0.80).

Salida: metricas/puntos_inspeccion.csv + .gpkg, rankeados por hectareas
estimadas dentro de cada concello. Consumidos por el visor y los dossiers.

Uso:
    python scripts/puntos_inspeccion.py
"""
import pathlib
import sys
import warnings

import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio
from rasterio import features
from rasterio.windows import from_bounds
from scipy import ndimage as ndi
from shapely.geometry import MultiPolygon, Point, shape
from shapely.ops import unary_union

warnings.filterwarnings("ignore")
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from especie_faixas import frac_prohibida  # noqa: E402

RAIZ = pathlib.Path(__file__).resolve().parent.parent
PROC = RAIZ / "datos" / "procesado"
LIDAR = PROC / "lidar"
MET = PROC / "metricas"

UMBRAL = 5.5
MIN_M2_35 = 400       # calva de >35 m minima para listarla
MIN_HA_RODAL = 0.5    # arbolado prohibido minimo del rodal
MIN_COPAS = 8         # copas prohibidas minimas de un cluster disperso
RADIO_CLUSTER = 35.0  # m entre copas del mismo cluster


def ancla(xs, ys):
    """Punto REAL mas cercano al centro de masa de un conjunto de puntos.

    El centroide a secas puede caer en un hueco: sobre una casa, un camino o
    el claro de en medio del rodal. Un punto de inspeccion que senhala un
    tejado destruye la confianza en el producto entero (paso, y con razon).
    Se devuelve siempre una posicion donde hay arbolado medido.
    """
    cx, cy = float(np.mean(xs)), float(np.mean(ys))
    i = int(np.argmin((xs - cx) ** 2 + (ys - cy) ** 2))
    return float(xs[i]), float(ys[i])


def carga_faixas():
    fx = gpd.GeoDataFrame(pd.concat(
        [gpd.read_file(PROC / f"faixas_{n}_paradanta_ok.gpkg")
         for n in ("nucleos", "illadas")], ignore_index=True), crs="EPSG:25829")
    return fx, fx.union_all()


def puntos_35m(fx_union):
    filas = []
    for chm_p in sorted(LIDAR.glob("*_chm.tif")):
        with rasterio.open(chm_p) as s:
            chm = s.read(1)
            tr = s.transform
        chm = np.where(np.isfinite(chm) & (chm > -1000), chm, 0)
        alto = chm > 35
        if not alto.any():
            continue
        mask_fx = features.rasterize(
            [(fx_union, 1)], out_shape=chm.shape, transform=tr,
            all_touched=False, fill=0).astype(bool)
        alto &= mask_fx
        if not alto.any():
            continue
        et, n = ndi.label(alto, structure=np.ones((3, 3)))
        for i in range(1, n + 1):
            masa = et == i
            m2 = int(masa.sum())
            if m2 < MIN_M2_35:
                continue
            fy, fx_ = np.nonzero(masa)
            px, py = tr * (fx_ + 0.5, fy + 0.5)
            x, y = ancla(px, py)
            poli = unary_union([shape(g) for g, v in
                                features.shapes(masa.astype("uint8"),
                                                mask=masa, transform=tr)
                                if v == 1])
            filas.append({"tipo": "eucaliptal_35m", "x": x, "y": y,
                          "ha": m2 / 1e4, "certeza": "alta",
                          "nota": f"dosel >35 m ({m2} m2); solo eucalipto llega",
                          "area": poli})
    return filas


def puntos_rodal(fx_union):
    ifn = gpd.read_file(PROC / "ifn_especies_paradanta.gpkg")
    ifn["f_mal"] = frac_prohibida(ifn)
    pers = pd.read_csv(MET / "persistencia_ifn.csv", encoding="utf-8-sig")
    ifn = ifn.merge(pers[["OBJECTID_12", "estado"]], on="OBJECTID_12", how="left")
    sel = ifn[(ifn.f_mal >= 0.5) & (ifn.estado.fillna("persistente") == "persistente")]
    filas = []
    for r in sel.itertuples():
        inter = r.geometry.intersection(fx_union)
        if inter.is_empty or inter.area < 1000:
            continue
        # arbolado real dentro: CHM > umbral en los bloques que toca
        x0, y0, x1, y1 = inter.bounds
        m2_arbol = 0
        cx_a, cy_a = [], []
        trozos = []
        for bx in range(int(x0 // 1000), int(x1 // 1000) + 1):
            for by in range(int(y0 // 1000), int(y1 // 1000) + 1):
                p = LIDAR / f"PNOA-2024-GAL-{bx}-{by+1}-H29-NPC01_chm.tif"
                if not p.exists():
                    continue
                with rasterio.open(p) as s:
                    v = from_bounds(max(x0, bx*1000), max(y0, by*1000),
                                    min(x1, bx*1000+1000), min(y1, by*1000+1000),
                                    transform=s.transform)
                    v = v.round_offsets().round_lengths()
                    if v.width <= 0 or v.height <= 0:
                        continue
                    chm = s.read(1, window=v)
                    tr = s.window_transform(v)
                chm = np.where(np.isfinite(chm) & (chm > -1000), chm, 0)
                m = features.rasterize([(inter, 1)], out_shape=chm.shape,
                                       transform=tr, all_touched=False, fill=0)
                arbol = (chm > UMBRAL) & m.astype(bool)
                m2_arbol += int(arbol.sum())
                if arbol.any():
                    fy, fx_ = np.nonzero(arbol)
                    ax_, ay_ = tr * (fx_ + 0.5, fy + 0.5)
                    cx_a.append(ax_)
                    cy_a.append(ay_)
                    # la mancha que se dibuja es SOLO el arbolado. Pintar el
                    # rodal entero mete naves, pistas y prados dentro de una
                    # figura que dice "38 ha de pinar": el inspector lo ve y
                    # deja de creerse el mapa, con razon.
                    trozos += [shape(gj) for gj, v in features.shapes(
                        arbol.astype("uint8"), mask=arbol, transform=tr)
                        if v == 1]
        ha_est = m2_arbol / 1e4 * r.f_mal
        if ha_est < MIN_HA_RODAL or not cx_a:
            continue
        # el punto va al centro de la MASA ARBOLADA, no al centro geometrico
        # del rodal: ese cae en cualquier claro, camino o tejado de dentro
        x, y = ancla(np.concatenate(cx_a), np.concatenate(cy_a))
        mancha = unary_union([t for t in trozos if t.area >= 100]).simplify(1)
        filas.append({"tipo": "rodal_ifn", "x": x, "y": y,
                      "ha": round(ha_est, 2), "certeza": "media-alta",
                      "nota": f"{r.NOMBRE_SP1} (IFN 2010, persistente), "
                              f"f_prohibida {r.f_mal:.0%}",
                      "area": mancha if not mancha.is_empty else inter.simplify(2)})
    return filas


def puntos_disperso():
    d = pd.read_csv(PROC / "copas" / "disperso_clasificado.csv",
                    encoding="utf-8-sig")
    d = d[d.pred_prohibida == 1].reset_index(drop=True)
    from scipy.spatial import cKDTree
    xy = d[["x", "y"]].to_numpy()
    arbol = cKDTree(xy)
    pares = arbol.query_pairs(RADIO_CLUSTER)
    padre = np.arange(len(d))

    def raiz(i):
        while padre[i] != i:
            padre[i] = padre[padre[i]]
            i = padre[i]
        return i

    for a, b in pares:
        padre[raiz(a)] = raiz(b)
    d["cl"] = [raiz(i) for i in range(len(d))]
    filas = []
    for _, g in d.groupby("cl"):
        if len(g) < MIN_COPAS:
            continue
        # el punto cae en una copa REAL del grupo, no en la media (que puede
        # quedar en el hueco de en medio)
        x, y = ancla(g.x.to_numpy(), g.y.to_numpy())
        copas = [Point(a, b).buffer(np.sqrt(m / np.pi))
                 for a, b, m in zip(g.x, g.y, g.area_m2)]
        filas.append({"tipo": "disperso_copas", "x": x, "y": y,
                      "ha": round(g.area_m2.sum() / 1e4, 2), "certeza": "media",
                      "nota": f"{len(g)} copas prohibidas (clasificador fase 6, "
                              "zona validada)",
                      "area": MultiPolygon(unary_union(copas).geoms)
                              if unary_union(copas).geom_type == "MultiPolygon"
                              else unary_union(copas)})
    return filas


if __name__ == "__main__":
    fx, fx_union = carga_faixas()
    filas = []
    for fn in (lambda: puntos_35m(fx_union), lambda: puntos_rodal(fx_union),
               puntos_disperso):
        f = fn()
        filas += f
        if f:
            print(f"  {f[0]['tipo']}: {len(f)} puntos")
    areas = [f.pop("area") for f in filas]
    g = gpd.GeoDataFrame(pd.DataFrame(filas),
                         geometry=[Point(f["x"], f["y"]) for f in filas],
                         crs="EPSG:25829")
    g["id_punto"] = np.arange(len(g))
    # ATRIBUCION POR SUPERFICIE, no por donde caiga el ancla. Una mancha a
    # caballo de dos concellos cambiaria de municipio segun en que parte de si
    # misma cae el punto (paso con un rodal de 6,9 ha que salto de Arbo a
    # A Canhiza al mover el ancla 640 m). El dossier es POR CONCELLO: una
    # atribucion inestable manda al inspector a la oficina equivocada.
    fxp = fx[["NOMECONCEL", "PARROQUIA", "geometry"]]
    j = g.copy()
    j["NOMECONCEL"], j["PARROQUIA"] = None, None
    for i, a in enumerate(areas):
        cand = fxp.iloc[list(fxp.sindex.query(a, predicate="intersects"))]
        if len(cand):
            sup = cand.geometry.intersection(a).area
            sup = sup.groupby([cand.NOMECONCEL, cand.PARROQUIA]).sum()
            con, par = sup.idxmax()
        else:  # mancha fuera de faixa (no deberia): la faixa mas cercana
            k = int(fxp.sindex.nearest(g.geometry.iloc[i])[1][0])
            con, par = fxp.NOMECONCEL.iloc[k], fxp.PARROQUIA.iloc[k]
        j.iat[i, j.columns.get_loc("NOMECONCEL")] = con
        j.iat[i, j.columns.get_loc("PARROQUIA")] = par
    j = j.sort_values(["NOMECONCEL", "ha"], ascending=[True, False])
    j["puesto_concello"] = j.groupby("NOMECONCEL").cumcount() + 1

    j.drop(columns="geometry").round(2).to_csv(MET / "puntos_inspeccion.csv",
                                               index=False, encoding="utf-8-sig")
    j.to_file(MET / "puntos_inspeccion.gpkg", driver="GPKG")

    # la MANCHA de cada punto: para que la ficha ensenhe la extension, no solo
    # una chincheta. Se guarda aparte (un GPKG, una geometria por capa).
    ga = gpd.GeoDataFrame(
        j.drop(columns="geometry").reset_index(drop=True),
        geometry=[areas[i] for i in j.id_punto], crs="EPSG:25829")
    ga.to_file(MET / "areas_inspeccion.gpkg", driver="GPKG")
    print(f"\n{len(j)} puntos -> metricas/puntos_inspeccion.csv (+ .gpkg, "
          "+ areas_inspeccion.gpkg)")
    print("\ntop 5 por concello:")
    for c, gc in j.groupby("NOMECONCEL"):
        print(f"\n  {c}")
        for r in gc.head(5).itertuples():
            print(f"    {r.tipo:<15} {r.ha:>6.2f} ha  ({r.x:.0f},{r.y:.0f})  "
                  f"{r.PARROQUIA} - {r.nota}")
