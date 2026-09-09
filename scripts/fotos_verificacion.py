"""Dos figuras de verificacion tras el filtro de edificios del Catastro.

  salidas/hilo/14_sat_lidar_clasificacion.png
      la misma escena en 2x2: ortofoto y CHM, solos y con la clasificacion
  salidas/diag_casa_usuario_filtrada.png
      la casa que salia delineada como "copa" de 10 m: huella del Catastro,
      copas descartadas por el filtro (x) y las que quedan (circulos)

Uso:
    python scripts/fotos_verificacion.py
"""
import pathlib

import geopandas as gpd
import matplotlib
import numpy as np
import pandas as pd
import rasterio
from rasterio.windows import from_bounds

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

RAIZ = pathlib.Path(__file__).resolve().parent.parent
PROC = RAIZ / "datos" / "procesado"
COPAS = PROC / "copas"
HILO = RAIZ / "salidas" / "hilo"

BLOQUE = "PNOA-2024-GAL-557-4670-H29-NPC01"
COLORES = {"eucalipto": "#E4002B", "pino": "#FF8A00", "frondosa": "#19C24A"}
ATTR = "ortofoto PNOA (c) IGN - LiDAR PNOA 2024 (IGN) - edificios: Catastro"


def crop_orto(x, y, L):
    with rasterio.open(PROC / "orto25" / f"{BLOQUE}.tif") as s:
        v = from_bounds(x - L/2, y - L/2, x + L/2, y + L/2, transform=s.transform)
        a = s.read(window=v.round_offsets().round_lengths(), boundless=True,
                   fill_value=0)
    return np.moveaxis(a, 0, 2)


def crop_chm(x, y, L):
    with rasterio.open(PROC / "lidar" / f"{BLOQUE}_chm.tif") as s:
        v = from_bounds(x - L/2, y - L/2, x + L/2, y + L/2, transform=s.transform)
        a = s.read(1, window=v.round_offsets().round_lengths(), boundless=True,
                   fill_value=0)
    a = np.where(np.isfinite(a) & (a > -1000), a, 0)
    a[a < 0] = 0
    return a


def pinta_faixa(ax, fx):
    for g in fx.geometry:
        bnd = g.boundary
        for linea in getattr(bnd, "geoms", [bnd]):
            xs, ys = linea.xy
            ax.plot(xs, ys, color="#FFE14D", lw=1.6)


def pinta_clases(ax, sub, s=40, lw=1.7, etiqueta=True):
    for cl, c in COLORES.items():
        p = sub[sub.clase == cl]
        ax.scatter(p.x, p.y, s=s, facecolors="none", edgecolors=c,
                   linewidths=lw, label=f"{cl} ({len(p)})" if etiqueta else None)


if __name__ == "__main__":
    d = pd.read_csv(COPAS / "disperso_clasificado.csv", encoding="utf-8-sig")
    d["clase"] = d[["p_eucalipto", "p_frondosa", "p_pino"]].idxmax(axis=1).str[2:]
    fx = gpd.GeoDataFrame(pd.concat(
        [gpd.read_file(PROC / f"faixas_{n}_paradanta_ok.gpkg")
         for n in ("nucleos", "illadas")], ignore_index=True), crs="EPSG:25829")
    edif = gpd.read_file(PROC / "edificios_catastro.gpkg")

    # ---- 14: la misma escena en 2x2 ----------------------------------------
    sub = d[d.bloque == BLOQUE]
    cx, cy, L = sub.x.median(), sub.y.median(), 400
    sub = sub[(sub.x > cx - L/2) & (sub.x < cx + L/2)
              & (sub.y > cy - L/2) & (sub.y < cy + L/2)]
    ext = (cx - L/2, cx + L/2, cy - L/2, cy + L/2)
    orto = crop_orto(cx, cy, L)
    chm = crop_chm(cx, cy, L)

    fig, axs = plt.subplots(2, 2, figsize=(13.6, 14.2))
    axs[0, 0].imshow(orto, extent=ext)
    axs[0, 0].set_title("1 - ortofoto (lo que ve el ojo)", fontsize=12)
    im = axs[0, 1].imshow(chm, extent=ext, cmap="viridis", vmin=0, vmax=30)
    axs[0, 1].set_title("2 - CHM LiDAR: altura de la vegetacion (m)", fontsize=12)
    fig.colorbar(im, ax=axs[0, 1], fraction=0.045, pad=0.02)
    axs[1, 0].imshow(orto, extent=ext)
    pinta_clases(axs[1, 0], sub)
    axs[1, 0].set_title("3 - ortofoto + clasificacion del disperso", fontsize=12)
    axs[1, 0].legend(loc="lower right", fontsize=9, framealpha=0.9)
    axs[1, 1].imshow(chm, extent=ext, cmap="viridis", vmin=0, vmax=30)
    pinta_clases(axs[1, 1], sub, etiqueta=False)
    axs[1, 1].set_title("4 - CHM + clasificacion (cada circulo, una copa >5,5 m)",
                        fontsize=12)
    for ax in axs.flat:
        pinta_faixa(ax, fx)
        ax.set(xlim=ext[:2], ylim=ext[2:], xticks=[], yticks=[])
    fig.suptitle("La misma escena, tres miradas: satelite, LiDAR y clasificacion\n"
                 f"(encuadre de {L} m, zona validada; amarillo = limite de faixa; "
                 "copas sobre edificio del Catastro ya excluidas)", fontsize=13)
    fig.text(0.01, 0.006, ATTR, fontsize=9, color="#666")
    fig.savefig(HILO / "14_sat_lidar_clasificacion.png", dpi=140,
                facecolor="white", bbox_inches="tight", pad_inches=0.15)
    plt.close(fig)
    print("  14_sat_lidar_clasificacion.png")

    # ---- la casa del usuario: el tejado ya no es un arbol -------------------
    x0, y0, L2 = 557570, 4669170, 140
    ext2 = (x0 - L2/2, x0 + L2/2, y0 - L2/2, y0 + L2/2)
    orto2 = crop_orto(x0, y0, L2)

    # copas del bloque descartadas por caer sobre edificio (recalculadas aqui)
    todas = pd.read_csv(COPAS / f"{BLOQUE}.csv")
    todas = todas[(todas.x > ext2[0]) & (todas.x < ext2[1])
                  & (todas.y > ext2[2]) & (todas.y < ext2[3])]
    g2 = gpd.GeoDataFrame(todas, geometry=gpd.points_from_xy(todas.x, todas.y),
                          crs="EPSG:25829")
    buf = gpd.GeoDataFrame(geometry=edif.buffer(1.0), crs=edif.crs)
    j = gpd.sjoin(g2, buf, predicate="within", how="left")
    j = j[~j.index.duplicated(keep="first")]
    fuera = j.index_right.isna()
    descartadas = todas[~fuera.to_numpy()]

    queda = d[(d.x > ext2[0]) & (d.x < ext2[1])
              & (d.y > ext2[2]) & (d.y < ext2[3])]

    fig, ax = plt.subplots(figsize=(10.2, 10.8))
    ax.imshow(orto2, extent=ext2)
    pinta_faixa(ax, fx)
    rec = edif.cx[ext2[0]:ext2[1], ext2[2]:ext2[3]]
    for g in rec.geometry:
        for poli in getattr(g, "geoms", [g]):
            xs, ys = poli.exterior.xy
            ax.plot(xs, ys, color="#00E5FF", lw=1.6)
    ax.scatter(descartadas.x, descartadas.y, s=140, marker="x", color="white",
               linewidths=2.6, zorder=4,
               label=f"descartada: edificio Catastro ({len(descartadas)})")
    pinta_clases(ax, queda, s=60, lw=2.0)
    for _, r in queda.iterrows():
        ax.annotate(f"{r.h_max:.0f} m", (r.x, r.y), textcoords="offset points",
                    xytext=(7, 7), fontsize=9, color="white",
                    path_effects=None, weight="bold")
    ax.legend(loc="lower right", fontsize=10, framealpha=0.9)
    ax.set(xlim=ext2[:2], ylim=ext2[2:], xticks=[], yticks=[])
    ax.set_title("El tejado ya no es un arbol: copas sobre huella del Catastro "
                 "(cian)\nse descartan (x); los arboles conservan su circulo",
                 fontsize=12.5)
    fig.text(0.01, 0.006, ATTR, fontsize=9, color="#666")
    fig.savefig(RAIZ / "salidas" / "diag_casa_usuario_filtrada.png", dpi=140,
                facecolor="white", bbox_inches="tight", pad_inches=0.15)
    plt.close(fig)
    print("  diag_casa_usuario_filtrada.png")
    print(f"  descartadas en el encuadre de la casa: {len(descartadas)}")
