"""Material grafico del hilo provincial (salidas/hilo/16-20).

Continua material_hilo.py (figuras 01-15, la comarca) con lo que el hilo de
Pontevedra necesita y no existia:

  16  mapa de la provincia: cada franja coloreada por el arbolado prohibido
      estimado de su parroquia (punto medio de las cotas), con A Paradanta
      recuadrada
  17  ranking de concellos con cotas; los cuatro de A Paradanta resaltados
      (A Canhiza era 1.a de 4 y queda 7.a de 54)
  18  curva de concentracion comarca vs provincia: la mitad del problema
      estimado cabe en el 22 % de las parroquias a las dos escalas
  19  las diez parroquias de la provincia donde mirar primero
  20  la tasa de falsos positivos, medida tres veces a ciegas, con su IC95

Todo sale de los CSV de datos/procesado/metricas/ y de los resumenes de
validacion; los numeros de la figura 20 son los publicados en el README.
Sin ortofoto ni satelite: solo la atribucion de las franjas (PBA, Xunta).

Uso:
    python scripts/material_hilo_pontevedra.py
"""
import pathlib
import sys

import geopandas as gpd
import matplotlib
import numpy as np
import pandas as pd

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.colors import LinearSegmentedColormap, Normalize  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402
from matplotlib.patches import Patch, Rectangle  # noqa: E402

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from material_hilo import guarda, pie  # noqa: E402

RAIZ = pathlib.Path(__file__).resolve().parent.parent
PROC = RAIZ / "datos" / "procesado"
MET = PROC / "metricas"

# paleta: un solo tono para magnitud (teja claro -> oscuro) y dos categorias
# fijas: A = la provincia / el resto (azul), B = A Paradanta (naranja). Par
# validado para daltonismo: dE 22 protan, contraste > 3:1 sobre blanco.
COLOR_A, BANDA_A = "#1F5FA8", "#CFDDF0"
COLOR_B, BANDA_B = "#C4540A", "#F6D5BF"
TINTA, MUTED, REJILLA = "#1F2823", "#5C6A61", "#E3E6E2"
FONDO_MAPA = "#F4F2EF"
RAMPA = LinearSegmentedColormap.from_list("prohibido", ["#F7DED3", "#B3261E", "#5E1208"])
PILOTO = ["A Cañiza", "Arbo", "Covelo", "Crecente"]


def concello_natural(s):
    """Devuelve el nombre con el articulo delante: el PBA lo lleva pospuesto."""
    if isinstance(s, str) and ", " in s:
        base, art = s.rsplit(", ", 1)
        return f"{art} {base}"
    return s


def estilo(ax):
    for lado in ("top", "right"):
        ax.spines[lado].set_visible(False)
    for lado in ("left", "bottom"):
        ax.spines[lado].set_color(REJILLA)
    ax.tick_params(colors=TINTA, labelsize=10.5)


if __name__ == "__main__":
    rp = pd.read_csv(MET / "ranking_final_pontevedra.csv", encoding="utf-8-sig")
    rc = pd.read_csv(MET / "ranking_final_concello_pontevedra.csv", encoding="utf-8-sig")
    ra = pd.read_csv(MET / "ranking_final.csv", encoding="utf-8-sig")
    rp = rp.sort_values("ha_prohibida_punto_medio", ascending=False).reset_index(drop=True)
    rc = rc.sort_values("ha_prohibida_punto_medio", ascending=False).reset_index(drop=True)
    ra = ra.sort_values("ha_prohibida_punto_medio", ascending=False).reset_index(drop=True)
    print("generadas:")

    # ---- 16. mapa: cada franja coloreada por su parroquia -------------------
    capas = []
    for f in ("faixas_nucleos_pontevedra_ok.gpkg", "faixas_illadas_pontevedra_ok.gpkg"):
        g = gpd.read_file(PROC / f)
        g["concello"] = g.NOMECONCEL.map(concello_natural)
        capas.append(g[["concello", "PARROQUIA", "geometry"]])
    fx = pd.concat(capas, ignore_index=True)
    fx = gpd.GeoDataFrame(fx, geometry="geometry", crs=capas[0].crs)
    clave = rp.set_index(["concello", "parroquia"]).ha_prohibida_punto_medio
    fx["valor"] = [clave.get((c, p), np.nan) for c, p in zip(fx.concello, fx.PARROQUIA)]
    sin = fx.valor.isna().mean()
    print(f"  franjas sin parroquia en el ranking: {sin:.1%}")
    assert sin < 0.02, "los nombres de parroquia no casan con el ranking"

    norma = Normalize(vmin=0, vmax=float(rp.ha_prohibida_punto_medio.quantile(0.98)))
    fig, ax = plt.subplots(figsize=(10.5, 13.6))
    fig.patch.set_facecolor("white")
    ax.set_facecolor(FONDO_MAPA)
    if fx.valor.isna().any():
        fx[fx.valor.isna()].plot(ax=ax, color="#D9D9D9", edgecolor="#D9D9D9", lw=0.35)
    fxv = fx[fx.valor.notna()].sort_values("valor")
    colores = RAMPA(norma(fxv.valor.to_numpy()))
    fxv.plot(ax=ax, color=colores, edgecolor=colores, lw=0.45)
    # recuadro de A Paradanta (extension de la zona piloto)
    px0, py0, px1, py1 = 548731, 4661398, 567278, 4685317
    ax.add_patch(Rectangle((px0, py0), px1 - px0, py1 - py0, fill=False,
                           edgecolor=TINTA, lw=2.2))
    ax.annotate("A Paradanta, el primer hilo:\nel 7 % de la franja y el 7 % del problema",
                xy=(px1, (py0 + py1) / 2), xytext=(px1 + 4000, py0 - 5000),
                fontsize=11, color=TINTA, ha="left",
                arrowprops=dict(arrowstyle="-", color=TINTA, lw=1.4))
    # los tres primeros concellos, rotulados sobre el centro de sus franjas
    for i, r in rc.head(3).iterrows():
        sel = fx[fx.concello == r.concello]
        c = sel.geometry.union_all().centroid
        ax.annotate(f"{i + 1}. {r.concello}\n{r.ha_prohibida_min:.0f}–{r.ha_prohibida_max:.0f} ha",
                    xy=(c.x, c.y), xytext=(c.x - 26000 if i != 1 else c.x + 14000,
                                            c.y + (9000 if i == 0 else 7000)),
                    fontsize=11, color=TINTA, weight="bold", ha="left",
                    bbox=dict(boxstyle="round,pad=0.3", fc="white", ec=REJILLA),
                    arrowprops=dict(arrowstyle="-", color=TINTA, lw=1.2))
    # barra de escala y leyenda de color
    x0, y0 = fx.total_bounds[2] - 24000, fx.total_bounds[1] + 3000
    ax.plot([x0, x0 + 20000], [y0, y0], color=TINTA, lw=4, solid_capstyle="butt")
    ax.text(x0 + 10000, y0 + 2200, "20 km", ha="center", va="bottom", fontsize=12,
            color=TINTA)
    sm = plt.cm.ScalarMappable(norm=norma, cmap=RAMPA)
    cb = fig.colorbar(sm, ax=ax, orientation="horizontal", fraction=0.035, pad=0.01,
                      shrink=0.55, anchor=(0.0, 0.0))
    cb.set_label("hectáreas de franja con arbolado prohibido, por parroquia "
                 "(punto medio de las cotas)", fontsize=10.5, color=TINTA)
    cb.outline.set_edgecolor(REJILLA)
    ax.set(xticks=[], yticks=[])
    for lado in ax.spines.values():
        lado.set_visible(False)
    ax.set_title("Pontevedra, parroquia a parroquia: 38.601 ha de franja de protección\n"
                 "y entre 4.770 y 8.141 ha con arbolado que la ley no permite",
                 fontsize=14, color=TINTA, loc="left")
    pie(fig, "franxas: Xunta de Galicia (PBA) · LiDAR PNOA 2024 (IGN) · IFN4 2010 · "
             "gris: parroquias sin métrica · elaboración propia")
    guarda(fig, "16_mapa_pontevedra_ranking.png")

    # ---- 17. ranking de concellos, con los cuatro del piloto ---------------
    rc["puesto"] = np.arange(1, len(rc) + 1)
    filas = pd.concat([rc.head(10), rc[rc.concello.isin(PILOTO) & (rc.puesto > 10)]])
    filas = filas.iloc[::-1].reset_index(drop=True)
    y = np.arange(len(filas), dtype=float)
    # un hueco visual entre el top 10 y los rezagados del piloto
    salto = int((filas.puesto > 10).sum())
    y[:salto] -= 0.9
    fig, ax = plt.subplots(figsize=(11.2, 7.6))
    for yi, (_, r) in zip(y, filas.iterrows()):
        es_piloto = r.concello in PILOTO
        ax.barh(yi, r.ha_prohibida_max - r.ha_prohibida_min, left=r.ha_prohibida_min,
                height=0.52, color=BANDA_B if es_piloto else BANDA_A)
        ax.scatter(r.ha_prohibida_punto_medio, yi, s=54, zorder=3,
                   color=COLOR_B if es_piloto else COLOR_A)
    ax.set_yticks(y, [f"{int(r.puesto)}.  {r.concello}" for _, r in filas.iterrows()])
    ax.set_xlabel("hectáreas de franja con arbolado prohibido (cotas y punto medio)",
                  color=TINTA)
    ax.grid(axis="x", color=REJILLA)
    ax.set_axisbelow(True)
    estilo(ax)
    fila_can = int(filas.index[filas.concello == "A Cañiza"][0])
    ax.annotate("1.ª de 4 en la comarca,\n7.ª de 54 en la provincia",
                xy=(filas.loc[fila_can, "ha_prohibida_max"] + 8, y[fila_can]),
                xytext=(400, y[fila_can] - 2.4), fontsize=11, color=COLOR_B,
                arrowprops=dict(arrowstyle="->", color=COLOR_B))
    ax.legend(handles=[Patch(facecolor=BANDA_A, label="intervalo entre cotas"),
                       Line2D([], [], marker="o", ls="", color=COLOR_A, label="punto medio"),
                       Line2D([], [], marker="o", ls="", color=COLOR_B,
                              label="concellos de A Paradanta (el piloto)")],
              loc="lower right", frameon=False)
    ax.set_title("Los diez concellos donde mirar primero, y dónde quedó el piloto",
                 fontsize=13.5, color=TINTA, loc="left")
    pie(fig, "cotas: tasa de FP medida en la provincia (IC95) × fracción prohibida "
             "del IFN + clasificador de copas donde valida · orden para priorizar "
             "inspección, no infracción acreditada")
    guarda(fig, "17_ranking_concellos.png")

    # ---- 18. curva de concentracion: comarca vs provincia ------------------
    fig, ax = plt.subplots(figsize=(9.8, 7.2))
    ax.plot([0, 100], [0, 100], ls=":", color=MUTED, lw=1.2)
    ax.text(62, 57, "si todas las parroquias\npesaran lo mismo", color=MUTED,
            fontsize=10, rotation=36, ha="center")
    for r, nombre, color, dy, va in ((ra, "A Paradanta · 40 parroquias", COLOR_B, 3, "bottom"),
                                     (rp, "Pontevedra · 563 parroquias", COLOR_A, -3, "top")):
        v = r.ha_prohibida_punto_medio.to_numpy()
        xs = np.concatenate([[0], 100 * np.arange(1, len(v) + 1) / len(v)])
        ys = np.concatenate([[0], 100 * np.cumsum(v) / v.sum()])
        ax.plot(xs, ys, color=color, lw=2.4)
        k = int(np.argmax(ys >= 50))
        ax.scatter([xs[k]], [50], color=color, s=64, zorder=4,
                   edgecolor="white", linewidth=1.5)
        j = int(np.argmax(xs >= 60))
        ax.text(60, ys[j] + dy, nombre, color=color, ha="center", va=va,
                fontsize=11.5, weight="bold")
        print(f"  {nombre}: 50 % del problema en el {xs[k]:.1f} % de las parroquias")
    ax.annotate("la mitad del problema estimado\ncabe en el 22 % de las parroquias,\n"
                "a las dos escalas", xy=(22.4, 50), xytext=(34, 30), fontsize=11.5,
                color=TINTA, arrowprops=dict(arrowstyle="->", color=TINTA))
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 100)
    ax.set_xlabel("% de parroquias, de más a menos arbolado prohibido", color=TINTA)
    ax.set_ylabel("% del arbolado prohibido estimado que acumulan", color=TINTA)
    ax.grid(color=REJILLA)
    ax.set_axisbelow(True)
    estilo(ax)
    ax.legend(handles=[Line2D([], [], color=COLOR_B, lw=2.4, label="A Paradanta · 40 parroquias"),
                       Line2D([], [], color=COLOR_A, lw=2.4, label="Pontevedra · 563 parroquias")],
              loc="upper left", frameon=False)
    ax.set_title("El argumento del triaje sobrevive a multiplicar por catorce",
                 fontsize=13.5, color=TINTA, loc="left")
    pie(fig, "punto medio de las cotas por parroquia · ranking_final.csv y "
             "ranking_final_pontevedra.csv · elaboración propia")
    guarda(fig, "18_curva_concentracion.png")

    # ---- 19. las diez parroquias de la provincia ---------------------------
    r = rp.head(10).iloc[::-1]
    fig, ax = plt.subplots(figsize=(11.2, 6.6))
    ypos = np.arange(len(r))
    ax.barh(ypos, r.ha_prohibida_max - r.ha_prohibida_min, left=r.ha_prohibida_min,
            height=0.52, color=BANDA_A)
    ax.scatter(r.ha_prohibida_punto_medio, ypos, color=COLOR_A, zorder=3, s=54)
    etiquetas = [f"{p.split(' (')[0]}  ·  {c}" for p, c in zip(r.parroquia, r.concello)]
    ax.set_yticks(ypos, etiquetas)
    ax.set_xlabel("hectáreas de franja con arbolado prohibido (cotas y punto medio)",
                  color=TINTA)
    ax.grid(axis="x", color=REJILLA)
    ax.set_axisbelow(True)
    estilo(ax)
    ax.legend(handles=[Patch(facecolor=BANDA_A, label="intervalo entre cotas"),
                       Line2D([], [], marker="o", ls="", color=COLOR_A, label="punto medio")],
              loc="lower right", frameon=False)
    ax.set_title("Las diez parroquias de Pontevedra donde mirar primero",
                 fontsize=13.5, color=TINTA, loc="left")
    pie(fig, "de 563 parroquias con franja medida · cotas: FP del CHM (IC95) × "
             "especie del IFN y del clasificador de copas · prioriza inspección, "
             "no acredita infracción")
    guarda(fig, "19_ranking_parroquias_pontevedra.png")

    # ---- 20. la tasa de FP, medida tres veces a ciegas ---------------------
    # cifras publicadas (README): calibracion_resumen.csv, resumen_producto.csv
    # del piloto y de validacion_pontevedra/
    medidas = [
        ("calibración · 400 puntos\n3 bloques de A Paradanta", 24.2, 17.0, 31.2, 89.4, 81.4, 96.6),
        ("producto · 250 puntos frescos\n260 bloques que la calibración no vio", 33.5, 25.2, 41.8, 89.8, None, None),
        ("provincia · 150 puntos frescos\nterritorio nuevo, costa incluida", 20.1, 12.8, 28.0, 90.1, 83.6, 96.5),
    ]
    fig, axs = plt.subplots(1, 2, figsize=(12.4, 5.4), gridspec_kw=dict(width_ratios=[1.35, 1]))
    ypos = np.arange(len(medidas))[::-1]
    for ax, (i0, i1, i2), titulo, xlim in (
            (axs[0], (1, 2, 3), "tasa de falsos positivos", (0, 50)),
            (axs[1], (4, 5, 6), "sensibilidad", (70, 100))):
        for yi, m in zip(ypos, medidas):
            v, lo, hi = m[i0], m[i1], m[i2]
            if lo is not None:
                ax.plot([lo, hi], [yi, yi], color=BANDA_A, lw=7, solid_capstyle="round")
            ax.scatter([v], [yi], color=COLOR_A, s=70, zorder=3, edgecolor="white", lw=1.2)
            ax.text(v, yi + 0.27, f"{v:.1f} %".replace(".", ","), ha="center",
                    fontsize=11, color=TINTA, weight="bold")
        ax.set_xlim(*xlim)
        ax.set_ylim(-0.6, len(medidas) - 0.3)
        ax.grid(axis="x", color=REJILLA)
        ax.set_axisbelow(True)
        ax.set_title(titulo, fontsize=12.5, color=TINTA, loc="left")
        estilo(ax)
    axs[0].set_yticks(ypos, [m[0] for m in medidas])
    axs[1].set_yticks(ypos, ["", "", ""])
    axs[0].set_xlabel("% de los avisos de árbol que no lo son (IC95)", color=TINTA)
    axs[1].set_xlabel("% de los árboles reales que el CHM detecta", color=TINTA)
    fig.suptitle("La tasa de error, medida tres veces a ciegas contra ortofoto",
                 fontsize=13.5, color=TINTA, x=0.01, ha="left")
    pie(fig, "anotación ciega: el anotador nunca ve la altura del CHM · IC por bootstrap "
             "estratificado · el producto usa la tasa del territorio donde se aplica")
    guarda(fig, "20_tasa_fp_tres_veces.png")

    print(f"\n-> {(RAIZ / 'salidas' / 'hilo').relative_to(RAIZ)}")
