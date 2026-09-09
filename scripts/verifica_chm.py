"""Comprueba que el CHM no esta roto, antes de creerse ninguna metrica.

Dos controles independientes:

1. NUMERICO. Contrasta la clasificacion de suelo que hace SMRF contra la que trae
   el fichero (NPC01). No es una verdad de referencia — NPC01 es clasificacion
   automatica provisional y por eso la rehacemos — pero son dos algoritmos
   distintos sobre la misma nube: si coincidieran poco, uno de los dos esta mal y
   habria que mirarlo. Se espera coincidencia alta con discrepancia en los bordes.

2. VISUAL. Un PNG por bloque con cuatro paneles: ortofoto PNOA, sombreado del MDT,
   CHM y CHM recortado a las faixas. El sombreado es el que delata un MDT malo:
   si SMRF ha dejado arboles dentro del terreno, salen bultos y crateres que no
   corresponden a nada del relieve.

Uso:
    python scripts/verifica_chm.py                 # todos los bloques
    python scripts/verifica_chm.py 559 4674        # uno
"""
import io
import pathlib
import sys

import geopandas as gpd
import matplotlib
import numpy as np
import pandas as pd
import rasterio
import requests
from matplotlib import pyplot as plt
from matplotlib.colors import LightSource
from rasterio.features import rasterize
from shapely.geometry import box

matplotlib.use("Agg")

RAIZ = pathlib.Path(__file__).resolve().parent.parent
PROC = RAIZ / "datos" / "procesado"
LIDAR = PROC / "lidar"
SALIDAS = RAIZ / "salidas"

WMS_PNOA = "https://www.ign.es/wms-inspire/pnoa-ma"


def ortofoto(bounds, px=1000):
    """Ortofoto PNOA del mismo recuadro, en EPSG:25829. Solo para comparar."""
    r = requests.get(WMS_PNOA, timeout=120, params={
        "SERVICE": "WMS", "VERSION": "1.3.0", "REQUEST": "GetMap",
        "LAYERS": "OI.OrthoimageCoverage", "STYLES": "", "CRS": "EPSG:25829",
        # en WMS 1.3.0 con CRS proyectado el orden del BBOX es minx,miny,maxx,maxy
        "BBOX": ",".join(str(v) for v in bounds),
        "WIDTH": px, "HEIGHT": px, "FORMAT": "image/jpeg",
    })
    r.raise_for_status()
    from PIL import Image
    return np.asarray(Image.open(io.BytesIO(r.content)))


def compara_con_npc01(laz, bloque):
    """Contrasta nuestro MDT contra uno hecho con la clase suelo del NPC01.

    No es una verdad de referencia: NPC01 es clasificacion automatica sin revisar,
    y rehacerla es justo el motivo de meter SMRF. Pero son dos algoritmos
    independientes sobre la misma nube, asi que una discrepancia grande es senhal
    de que algo va mal en uno de los dos.

    El MDT de referencia se hace con el MINIMO de Z de los puntos clase 2 por
    celda, sin interpolar. Solo se comparan las celdas donde NPC01 tiene puntos de
    suelo de verdad, sin rellenar huecos, para no comparar contra una invencion.
    """
    import laspy
    with rasterio.open(LIDAR / f"{bloque}_mdt.tif") as s:
        mio = s.read(1, masked=True)
        x0, y1 = s.bounds.left, s.bounds.top
        res = s.res[0]
        alto, ancho = s.shape

    las = laspy.read(laz)
    cls = np.asarray(las.classification)
    sel = cls == 2  # suelo segun NPC01, tal cual, con solape incluido
    x = np.asarray(las.x)[sel]
    y = np.asarray(las.y)[sel]
    z = np.asarray(las.z)[sel]
    col = np.clip(((x - x0) / res).astype(int), 0, ancho - 1)
    fil = np.clip(((y1 - y) / res).astype(int), 0, alto - 1)
    ref = np.full((alto, ancho), np.inf)
    np.minimum.at(ref, (fil, col), z)
    hay = np.isfinite(ref)

    d = (np.asarray(mio) - ref)[hay & ~np.ma.getmaskarray(mio)]
    print(f"  suelo NPC01: {sel.sum():,} pts en {hay.sum():,} celdas "
          f"({100*hay.mean():.1f} % del bloque)")
    print(f"  MDT nuestro - MDT NPC01:  mediana {np.median(d):+.3f} m   "
          f"media {d.mean():+.3f} m   sigma {d.std():.3f} m")
    print(f"    |dif| < 0,25 m: {100*(np.abs(d) < .25).mean():.1f} %   "
          f"< 0,50 m: {100*(np.abs(d) < .5).mean():.1f} %   "
          f"> 2 m: {100*(np.abs(d) > 2).mean():.2f} %")
    return float(np.median(d)), float(d.std())


def panel(bloque, faixas):
    mdt = LIDAR / f"{bloque}_mdt.tif"
    chm = LIDAR / f"{bloque}_chm.tif"
    with rasterio.open(mdt) as s:
        t = s.read(1, masked=True)
        limite = s.bounds
        tr = s.transform
        forma = s.shape
    with rasterio.open(chm) as s:
        h = s.read(1, masked=True)

    recuadro = box(*limite)
    trozos = [(g.intersection(recuadro), 1) for g in faixas.geometry
              if g.intersects(recuadro)]
    mascara = (rasterize(trozos, out_shape=forma, transform=tr, fill=0,
                         all_touched=False, dtype="uint8").astype(bool)
               if trozos else np.zeros(forma, bool))

    ext = [limite.left, limite.right, limite.bottom, limite.top]
    fig, ax = plt.subplots(2, 2, figsize=(15, 15.6))
    fig.suptitle(f"{bloque}   —   comprobacion del CHM", fontsize=13)

    try:
        ax[0, 0].imshow(ortofoto(limite), extent=ext)
        ax[0, 0].set_title("ortofoto PNOA (IGN)")
    except Exception as e:
        ax[0, 0].text(.5, .5, f"sin ortofoto:\n{e}", ha="center", transform=ax[0, 0].transAxes)

    ls = LightSource(azdeg=315, altdeg=45)
    ax[0, 1].imshow(ls.hillshade(np.asarray(t), vert_exag=2, dx=1, dy=1),
                    cmap="gray", extent=ext)
    ax[0, 1].set_title(f"sombreado del MDT  ({t.min():.0f}–{t.max():.0f} m)")

    im = ax[1, 0].imshow(h, cmap="viridis", vmin=0, vmax=30, extent=ext)
    ax[1, 0].set_title("CHM: altura sobre el terreno")
    fig.colorbar(im, ax=ax[1, 0], shrink=.7, label="m")

    solo_faixa = np.ma.masked_where(~mascara, h)
    ax[1, 1].imshow(ls.hillshade(np.asarray(t), vert_exag=2, dx=1, dy=1),
                    cmap="gray", extent=ext, alpha=.5)
    ax[1, 1].imshow(solo_faixa, cmap="viridis", vmin=0, vmax=30, extent=ext)
    ha = mascara.sum() / 1e4
    ax[1, 1].set_title(f"CHM dentro de faixa  ({ha:.1f} ha)")

    for a in ax.ravel():
        a.set_xticks([])
        a.set_yticks([])
        for g, _ in trozos:
            for p in (g.geoms if g.geom_type == "MultiPolygon" else [g]):
                x, y = p.exterior.xy
                a.plot(x, y, color="red", lw=.7)
    fig.text(.5, .012, "LiDAR y ortofoto: PNOA, IGN/CNIG (CC-BY 4.0). "
             "Faixas: Xunta de Galicia.", ha="center", fontsize=8, color="#555")
    fig.tight_layout(rect=[0, .02, 1, .98])
    SALIDAS.mkdir(exist_ok=True)
    out = SALIDAS / f"verifica_{bloque}.png"
    fig.savefig(out, dpi=110)
    plt.close(fig)
    return out, ha


if __name__ == "__main__":
    faixas = gpd.GeoDataFrame(
        pd.concat([gpd.read_file(PROC / f"faixas_{n}_paradanta_ok.gpkg")
                   for n in ("nucleos", "illadas")], ignore_index=True),
        crs="EPSG:25829")

    if len(sys.argv) == 3:
        pats = [f"PNOA-2024-GAL-{sys.argv[1]}-{sys.argv[2]}-H29-NPC01"]
    else:
        pats = [p.name[:-8] for p in sorted(LIDAR.glob("*_chm.tif"))]

    for b in pats:
        print(f"\n=== {b}")
        laz = RAIZ / "datos" / "crudo" / "lidar" / f"{b}.LAZ"
        if laz.exists():
            compara_con_npc01(laz, b)
        out, ha = panel(b, faixas)
        print(f"  -> {out.relative_to(RAIZ)}   ({ha:.1f} ha de faixa en el bloque)")
