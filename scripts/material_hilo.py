"""Genera el material grafico del hilo de difusion en salidas/hilo/.

Reune lo que ya existia (mapa de comarca, zoom de franja, hoja de contacto de
una cicatriz de incendio, chip de anotacion) y genera lo que faltaba:

  03  ortofoto vs CHM del mismo encuadre (el eucaliptal >35 m de Mourentan)
  04  bosque prohibido vs bosque exento, misma senal desde el aire
  05  serie NDVI 2017-2026: incendios de 2017 y sequia de 2026
  06  mapa de eventos regenerado con el pie ACTUALIZADO (ya esta validado)
  08  ranking de parroquias con cotas
  09  caida estacional de NDVI por especie (por que el satelite prometia)

Toda imagen con ortofoto o satelite lleva la atribucion PNOA (c) IGN /
Copernicus horneada: la licencia CC-BY la exige en cualquier pieza publicada.

Uso:
    python scripts/material_hilo.py
"""
import pathlib
import shutil
import sys

import geopandas as gpd
import matplotlib
import numpy as np
import pandas as pd
import rasterio
from rasterio.windows import from_bounds

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402
from matplotlib.patches import Patch  # noqa: E402

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from chips_validacion import tesela  # noqa: E402  ortofoto del WMS del IGN

RAIZ = pathlib.Path(__file__).resolve().parent.parent
PROC = RAIZ / "datos" / "procesado"
SAL = RAIZ / "salidas"
HILO = SAL / "hilo"

ATTR_ORTO = "ortofoto PNOA © IGN"
ATTR_S2 = "Sentinel-2 © Copernicus"


def pie(fig, texto):
    fig.text(0.01, 0.008, texto, fontsize=9, color="#666", ha="left")


def guarda(fig, nombre):
    fig.savefig(HILO / nombre, dpi=140, facecolor="white",
                bbox_inches="tight", pad_inches=0.15)
    plt.close(fig)
    print(f"  {nombre}")


if __name__ == "__main__":
    HILO.mkdir(parents=True, exist_ok=True)

    # ---- 0. reutilizar lo que ya existe ------------------------------------
    print("copias de material existente:")
    copias = [
        (SAL / "post_1_comarca.jpg", "01_comarca_franjas.jpg"),
        (SAL / "post_zoom_atribucion.jpg", "02_zoom_franja.jpg"),
        (PROC / "validacion_persistencia" / "hojas" / "v017.png",
         "07_serie_historica_incendio.png"),
        (PROC / "validacion" / "chips" / "v0000.jpg", "10_chip_anotacion.jpg"),
    ]
    for origen, destino in copias:
        shutil.copyfile(origen, HILO / destino)
        print(f"  {destino}  (de {origen.name})")

    print("generadas:")
    fx = gpd.read_file(PROC / "faixas_nucleos_paradanta_ok.gpkg")

    # ---- 03. ortofoto vs CHM (Mourentan, el eucaliptal >35 m) --------------
    x, y, L = 558253, 4665280, 240
    orto = tesela(x - L/2, y - L/2, L, 960)
    with rasterio.open(PROC / "lidar" / "PNOA-2024-GAL-558-4666-H29-NPC01_chm.tif") as s:
        ven = from_bounds(x - L/2, y - L/2, x + L/2, y + L/2, transform=s.transform)
        chm = s.read(1, window=ven, boundless=True, fill_value=0)
    chm[chm < -1000] = 0
    ext = (x - L/2, x + L/2, y - L/2, y + L/2)

    fig, axs = plt.subplots(1, 2, figsize=(12.6, 6.6))
    axs[0].imshow(orto, extent=ext)
    axs[0].set_title("lo que ve una ortofoto", fontsize=12)
    im = axs[1].imshow(chm, extent=ext, cmap="viridis", vmin=0, vmax=40)
    axs[1].contour(np.flipud(chm), levels=[35], extent=ext,
                   colors="red", linewidths=1.2)
    axs[1].set_title("lo que mide el LiDAR: altura del dosel (CHM)", fontsize=12)
    for ax in axs:
        for g in fx.geometry:
            try:
                b = g.boundary
                for linea in getattr(b, "geoms", [b]):
                    xs, ys = linea.xy
                    ax.plot(xs, ys, color="#FFE14D", lw=1.6)
            except Exception:
                pass
        ax.set(xlim=ext[:2], ylim=ext[2:], xticks=[], yticks=[])
    cb = fig.colorbar(im, ax=axs[1], fraction=0.046, pad=0.02)
    cb.set_label("altura sobre el suelo (m)")
    fig.suptitle("Mourentán (Arbo): eucaliptal dentro de franja de protección · "
                 "en rojo, copas de más de 35 m", fontsize=13)
    pie(fig, f"{ATTR_ORTO} (sept 2023) · LiDAR PNOA 2024 (IGN) · "
             "amarillo: límite de franja")
    guarda(fig, "03_ortofoto_vs_chm.png")

    # ---- 04. prohibido vs exento, misma senal desde el aire ----------------
    infx = gpd.read_file(PROC / "ifn_en_faixa_paradanta.gpkg")
    infx["ha"] = infx.geometry.area / 1e4
    euca = infx[(infx.f_mal > 0.9) &
                infx.NOMBRE_SP1.str.startswith("Eucalyptus")].nlargest(1, "ha").iloc[0]
    fron = infx[(infx.f_mal < 0.1) &
                infx.NOMBRE_SP1.isin(("Quercus_robur", "Castanea_sativa"))
                ].nlargest(1, "ha").iloc[0]
    fig, axs = plt.subplots(1, 2, figsize=(12.6, 6.9))
    for ax, r, titulo, color in (
            (axs[0], euca,
             "PROHIBIDA · " + euca.NOMBRE_SP1.replace("_", " "), "#B3261E"),
            (axs[1], fron,
             "EXENTA · " + fron.NOMBRE_SP1.replace("_", " ")
             + " (frondosa autóctona)", "#177A4C")):
        p = r.geometry.representative_point()
        e = (p.x - L/2, p.x + L/2, p.y - L/2, p.y + L/2)
        ax.imshow(tesela(e[0], e[2], L, 960), extent=e)
        geo = r.geometry
        for poly in getattr(geo, "geoms", [geo]):
            xs, ys = poly.exterior.xy
            ax.plot(xs, ys, color=color, lw=2.2)
        ax.set(xlim=e[:2], ylim=e[2:], xticks=[], yticks=[])
        ax.set_title(titulo, fontsize=13, color=color)
    fig.suptitle("Dos bosques dentro de franja: desde el aire dan la misma señal · "
                 "la ley solo prohíbe uno", fontsize=13.5)
    pie(fig, f"{ATTR_ORTO} · especie: IFN4 2010 (rodales en franja) · "
             "encuadres de 240 m")
    guarda(fig, "04_prohibido_vs_exento.png")

    # ---- 05. serie NDVI: los incendios de 2017 y la sequia de 2026 ---------
    serie = pd.read_csv(PROC / "s2" / "serie_ndvi_rodal.csv", encoding="utf-8-sig")
    p = pd.read_csv(PROC / "metricas" / "persistencia_ifn.csv", encoding="utf-8-sig")
    d = serie.merge(p[["OBJECTID_12", "estado", "anho_evento"]], on="OBJECTID_12")
    anhos = list(range(2017, 2027))
    cols = [f"ndvi_{a}" for a in anhos]
    fuego = d[(d.estado == "evento") & (d.anho_evento == 2018)]
    pers = d[d.estado == "persistente"]

    fig, ax = plt.subplots(figsize=(11.4, 6.2))
    for _, f in fuego.iterrows():
        ax.plot(anhos, f[cols].astype(float), color="#B3261E", alpha=0.16, lw=1)
    ax.plot(anhos, pers[cols].median().astype(float), color="#177A4C", lw=3,
            label=f"mediana de los {len(pers)} rodales persistentes")
    ax.plot(anhos, fuego[cols].median().astype(float), color="#B3261E", lw=3,
            label=f"mediana de los {len(fuego)} rodales quemados en oct-2017")
    ax.annotate("incendios de octubre de 2017\n(el detector los encontró a ciegas)",
                xy=(2018, float(fuego[cols].median().iloc[1])), xytext=(2019.2, 0.42),
                arrowprops=dict(arrowstyle="->", color="#B3261E"), color="#B3261E",
                fontsize=11)
    ax.annotate("sequía de agosto de 2026:\nbaja TODO — el espejismo\nque engaña al detector",
                xy=(2026, float(pers[cols].median().iloc[-1])), xytext=(2022.6, 0.55),
                arrowprops=dict(arrowstyle="->", color="#666"), color="#555",
                fontsize=11)
    ax.set_xticks(anhos)
    ax.set_ylabel("NDVI mediano de verano (verdor)")
    ax.set_ylim(0.2, 0.9)
    ax.grid(axis="y", color="#e5e5e5")
    ax.legend(loc="lower right", frameon=False)
    ax.set_title("Diez veranos de satélite sobre cada rodal del inventario",
                 fontsize=13.5)
    pie(fig, f"{ATTR_S2} · mediana de NDVI de verano por rodal del IFN4")
    guarda(fig, "05_serie_ndvi.png")

    # ---- 06. mapa de eventos con el pie actualizado -------------------------
    ifn = gpd.read_file(PROC / "ifn_especies_paradanta.gpkg")
    g = ifn.merge(p, on="OBJECTID_12")
    fig, ax = plt.subplots(figsize=(10.5, 12))
    g[g.estado == "persistente"].plot(ax=ax, color="#E4EAE4", edgecolor="none")
    fx.plot(ax=ax, facecolor="#FFF7DC", edgecolor="#E8D9A0", lw=0.3, alpha=0.9)
    # paleta sin rojos: el rojo queda reservado para las cicatrices de 2018
    paleta = ["#E58606", "#5D69B1", "#52BCA3", "#99C945", "#CC61B0",
              "#24796C", "#DAA51B", "#2F8AC4"]
    ev = g[g.estado == "evento"]
    leyenda = []
    for i, a in enumerate(sorted(ev.anho_evento.dropna().unique())):
        sel = ev[ev.anho_evento == a]
        c = "#B3261E" if a == 2018 else paleta[i % len(paleta)]
        sel.plot(ax=ax, color=c, edgecolor="black", lw=0.3)
        leyenda.append(Patch(facecolor=c, label=f"{int(a)}  ({len(sel)} rodales)"))
    ax.legend(handles=leyenda, title="evento de dosel detectado", loc="upper right",
              fontsize=10)
    ax.annotate("cicatrices de los incendios\nde octubre de 2017\n(confirmadas contra ortofoto)",
                xy=(551500, 4664500), xytext=(549000, 4671500), fontsize=11,
                color="#B3261E", style="italic",
                arrowprops=dict(arrowstyle="->", color="#B3261E"))
    ax.set(xticks=[], yticks=[])
    ax.set_title("Eventos de dosel 2018-2026 por rodal del IFN — A Paradanta\n"
                 "gris: persistentes · amarillo: franjas de protección",
                 fontsize=13)
    pie(fig, f"{ATTR_S2} sobre rodales IFN4 · validado contra ortofoto: 2019-2023 "
             "confirmado el 69 %; 2024-2026 domina el espejismo de sequía (0/8 en 2026)")
    guarda(fig, "06_mapa_eventos.png")

    # ---- 08. ranking de parroquias con cotas --------------------------------
    r = pd.read_csv(PROC / "metricas" / "ranking_final.csv",
                    encoding="utf-8-sig").head(10).iloc[::-1]
    fig, ax = plt.subplots(figsize=(10.8, 6.4))
    ypos = np.arange(len(r))
    ax.barh(ypos, r.ha_prohibida_max - r.ha_prohibida_min, left=r.ha_prohibida_min,
            height=0.5, color="#C8DFD1", edgecolor="none")
    ax.scatter(r.ha_prohibida_punto_medio, ypos, color="#177A4C", zorder=3, s=48)
    ax.set_yticks(ypos, [f"{p}" for p in r.parroquia])
    ax.set_xlabel("hectáreas de franja con arbolado prohibido (cotas y punto medio)")
    ax.grid(axis="x", color="#e5e5e5")
    ax.set_title("Las diez parroquias donde mirar primero", fontsize=13.5)
    ax.legend(handles=[Patch(facecolor="#C8DFD1", label="intervalo entre cotas"),
                       Line2D([], [], marker="o", ls="", color="#177A4C",
                              label="punto medio")],
              loc="lower right", frameon=False)
    pie(fig, "cotas: tasa de FP del CHM (IC95) × fracción prohibida del IFN · "
             "el orden prioriza inspección, no acredita infracción")
    guarda(fig, "08_ranking_parroquias.png")

    # ---- 09. la caida estacional que prometia (y no llego a producto) -------
    # valores medidos en rodales puros de la comarca (fase Sentinel-2, CLAUDE.md)
    datos = [("Quercus robur\n(roble, exenta)", 0.257, "#177A4C"),
             ("Pinus pinaster\n(prohibida)", 0.009, "#B3261E"),
             ("Eucalyptus globulus\n(prohibida)", -0.033, "#B3261E")]
    fig, ax = plt.subplots(figsize=(9.6, 5.8))
    xs = np.arange(3)
    ax.bar(xs, [d[1] for d in datos], color=[d[2] for d in datos], width=0.55)
    ax.set_xticks(xs, [d[0] for d in datos])
    ax.axhline(0, color="#999", lw=1)
    ax.set_ylabel("caída de NDVI verano → invierno")
    for i, (_, v, _c) in enumerate(datos):
        ax.text(i, v + (0.008 if v >= 0 else -0.02), f"{v:+.3f}",
                ha="center", fontsize=12)
    ax.set_title("El roble pierde la hoja en invierno; el pino y el eucalipto no.\n"
                 "La señal existe — pero en píxeles mezclados de 10 m "
                 "no superó la validación", fontsize=12.5)
    pie(fig, f"{ATTR_S2} · medianas estacionales sobre rodales puros del IFN · "
             "resultado negativo publicado: AUC 0,746 fuera de muestra")
    guarda(fig, "09_caida_estacional.png")

    print(f"\n-> {HILO.relative_to(RAIZ)}")
