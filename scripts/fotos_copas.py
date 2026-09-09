"""Tres fotos que ensenhan la fase 6: segmentacion, parches y resultado.

  11_copas_segmentadas.png   ortofoto + limites de copa del watershed (proceso)
  12_parches_ejemplo.png     lo que ve el modelo: parches por clase (proceso)
  13_disperso_clasificado.png copas dispersas en faixa coloreadas por la
                              prediccion del modelo (resultado)

Van a salidas/hilo/ con la atribucion horneada, como el resto del material.

Uso:
    python scripts/fotos_copas.py
"""
import pathlib

import geopandas as gpd
import matplotlib
import numpy as np
import pandas as pd
import rasterio
from rasterio.windows import from_bounds
from scipy import ndimage as ndi
from skimage.feature import peak_local_max
from skimage.segmentation import find_boundaries, watershed

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402

RAIZ = pathlib.Path(__file__).resolve().parent.parent
PROC = RAIZ / "datos" / "procesado"
COPAS = PROC / "copas"
ORTO25 = PROC / "orto25"
HILO = RAIZ / "salidas" / "hilo"

ATTR = "ortofoto PNOA © IGN · LiDAR PNOA 2024 (IGN)"


def guarda(fig, nombre):
    fig.savefig(HILO / nombre, dpi=140, facecolor="white",
                bbox_inches="tight", pad_inches=0.15)
    plt.close(fig)
    print(f"  {nombre}")


def orto_crop(bloque, x, y, L):
    with rasterio.open(ORTO25 / f"{bloque}.tif") as s:
        v = from_bounds(x - L/2, y - L/2, x + L/2, y + L/2, transform=s.transform)
        a = s.read(window=v.round_offsets().round_lengths(), boundless=True,
                   fill_value=0)
    return np.moveaxis(a, 0, 2)


if __name__ == "__main__":
    # ---- 11. segmentacion de copas sobre el eucaliptal de Mourentan ---------
    bloque = "PNOA-2024-GAL-558-4666-H29-NPC01"
    x, y, L = 558253, 4665280, 160
    with rasterio.open(PROC / "lidar" / f"{bloque}_chm.tif") as s:
        v = from_bounds(x - L/2, y - L/2, x + L/2, y + L/2, transform=s.transform)
        chm = s.read(1, window=v.round_offsets().round_lengths(),
                     boundless=True, fill_value=0)
    chm = np.where(np.isfinite(chm) & (chm > -1000), chm, 0)
    chm[chm < 0] = 0
    suave = ndi.gaussian_filter(chm.astype("float32"), 1.0)
    masa = suave > 5.5
    picos = peak_local_max(suave, min_distance=2, labels=masa,
                           exclude_border=False)
    sem = np.zeros(chm.shape, "int32")
    sem[tuple(picos.T)] = np.arange(1, len(picos) + 1)
    et = watershed(-suave, sem, mask=masa)
    borde = find_boundaries(et, mode="outer") & masa

    orto = orto_crop(bloque, x, y, L)
    k = orto.shape[0] // borde.shape[0]
    borde4 = np.kron(borde, np.ones((k, k), bool))[:orto.shape[0], :orto.shape[1]]
    ext = (x - L/2, x + L/2, y - L/2, y + L/2)

    fig, axs = plt.subplots(1, 2, figsize=(12.8, 6.8))
    axs[0].imshow(orto, extent=ext)
    axs[0].set_title("la ortofoto, tal cual", fontsize=12)
    con = orto.copy()
    con[borde4] = (255, 225, 77)
    axs[1].imshow(con, extent=ext)
    ys, xs_ = picos[:, 0], picos[:, 1]
    with rasterio.open(PROC / "lidar" / f"{bloque}_chm.tif") as s:
        pass
    axs[1].scatter(x - L/2 + (xs_ + .5), y + L/2 - (ys + .5), s=4,
                   color="red", zorder=3)
    axs[1].set_title(f"las {int(et.max())} copas que separa el watershed "
                     "(punto rojo: ápice)", fontsize=12)
    for ax in axs:
        ax.set(xticks=[], yticks=[])
    fig.suptitle("Del CHM a árboles individuales — eucaliptal de Mourentán, "
                 f"encuadre de {L} m", fontsize=13)
    fig.text(0.01, 0.008, ATTR, fontsize=9, color="#666")
    guarda(fig, "11_copas_segmentadas.png")

    # ---- 12. parches de entrenamiento por clase (zonas buenas) --------------
    parches = np.load(COPAS / "parches_entrenamiento.npy")
    ind = pd.read_csv(COPAS / "indice_entrenamiento.csv", encoding="utf-8-sig")
    buenas = {"110_935", "111_933", "109_934", "110_936"}
    rng = np.random.default_rng(20260820)
    fig, axs = plt.subplots(3, 8, figsize=(13.6, 5.6))
    etiquetas = {"eucalipto": "eucalipto (PROHIBIDA)",
                 "pino": "pino (PROHIBIDA)",
                 "frondosa": "frondosa (exenta)"}
    for fila, grupo in enumerate(("eucalipto", "pino", "frondosa")):
        idx = ind[(ind.grupo == grupo) & ind.zona.isin(buenas)].index.to_numpy()
        for c, i in enumerate(rng.choice(idx, 8, replace=False)):
            axs[fila, c].imshow(parches[i])
            axs[fila, c].set(xticks=[], yticks=[])
            if c == 0:
                axs[fila, c].set_ylabel(etiquetas[grupo], fontsize=10)
    fig.suptitle("Lo que ve el modelo: parches de 16×16 m centrados en la copa, "
                 "etiquetados por el rodal del IFN", fontsize=12.5)
    fig.text(0.01, 0.008, "ortofoto PNOA © IGN · etiquetas: IFN4 2010 "
             "(rodales puros persistentes)", fontsize=9, color="#666")
    guarda(fig, "12_parches_ejemplo.png")

    # ---- 13. resultado: el disperso clasificado en una faixa real -----------
    d = pd.read_csv(COPAS / "disperso_clasificado.csv", encoding="utf-8-sig")
    d["clase"] = d[["p_eucalipto", "p_frondosa", "p_pino"]].idxmax(axis=1).str[2:]
    # el mejor escaparate: bloque con muchas copas y mezcla real de clases
    cand = (d.groupby("bloque").agg(n=("x", "size"),
                                    mezcla=("clase", lambda s: s.value_counts(normalize=True).min()))
            .query("n >= 60 and mezcla >= 0.15").sort_values("n", ascending=False))
    b = cand.index[0]
    sub = d[d.bloque == b]
    cx, cy, L2 = sub.x.median(), sub.y.median(), 400
    sub = sub[(sub.x > cx - L2/2) & (sub.x < cx + L2/2)
              & (sub.y > cy - L2/2) & (sub.y < cy + L2/2)]
    orto = orto_crop(b, cx, cy, L2)
    ext = (cx - L2/2, cx + L2/2, cy - L2/2, cy + L2/2)
    fx = gpd.GeoDataFrame(pd.concat(
        [gpd.read_file(PROC / f"faixas_{n}_paradanta_ok.gpkg")
         for n in ("nucleos", "illadas")], ignore_index=True), crs="EPSG:25829")

    fig, ax = plt.subplots(figsize=(9.6, 9.9))
    ax.imshow(orto, extent=ext)
    for g in fx.geometry:
        bnd = g.boundary
        for linea in getattr(bnd, "geoms", [bnd]):
            xs, ys2 = linea.xy
            ax.plot(xs, ys2, color="#FFE14D", lw=1.8)
    colores = {"eucalipto": "#E4002B", "pino": "#FF8A00", "frondosa": "#19C24A"}
    for cl, c in colores.items():
        s = sub[sub.clase == cl]
        ax.scatter(s.x, s.y, s=42, facecolors="none", edgecolors=c,
                   linewidths=1.8, label=f"{cl} ({len(s)})")
    ax.set(xlim=ext[:2], ylim=ext[2:], xticks=[], yticks=[])
    ax.legend(loc="lower right", fontsize=10, framealpha=0.9)
    ax.set_title("El resultado: arbolado disperso en franja, clasificado copa a copa\n"
                 f"(zona validada, encuadre de {L2} m; rojo/naranja = especie "
                 "prohibida, verde = exenta)", fontsize=12)
    fig.text(0.01, 0.008, "ortofoto PNOA © IGN · predicción del clasificador "
             "de la fase 6 (AUC 0,86 fuera de zona)", fontsize=9, color="#666")
    guarda(fig, "13_disperso_clasificado.png")
    print(f"bloque del escaparate: {b}")
