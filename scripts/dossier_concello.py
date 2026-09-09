"""Dossier de inspeccion en PDF, uno por concello.

Convierte el ranking y puntos_inspeccion.csv en el documento que un servicio
de inspeccion puede imprimir y llevar en el coche: portada con el resumen y
las parroquias ordenadas, y despues una ficha por punto con su recorte de
ortofoto, la escala metrica, y las coordenadas en UTM y en lat/lon para el GPS.

El recorte se MOSAICA desde los bloques vecinos: la cache de ortofoto es de
1x1 km exacto y un punto cerca del borde saldria con medio encuadre en negro
(la misma trampa que en los chips de la fase 2, alli resuelta con margen).

Uso:
    python scripts/dossier_concello.py                 # todos los concellos
    python scripts/dossier_concello.py --concello Arbo --puntos 12
"""
import argparse
import pathlib
import warnings

import geopandas as gpd
import matplotlib
import numpy as np
import pandas as pd
import rasterio
from rasterio.windows import from_bounds

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.backends.backend_pdf import PdfPages  # noqa: E402
from matplotlib.patches import Circle, Rectangle  # noqa: E402

warnings.filterwarnings("ignore")

RAIZ = pathlib.Path(__file__).resolve().parent.parent
PROC = RAIZ / "datos" / "procesado"
ORTO25 = PROC / "orto25"
MET = PROC / "metricas"
SALIDA = RAIZ / "salidas" / "dossiers"

LADO_CHIP = 200          # m de lado del recorte de cada ficha
POR_PAGINA = 4
COLOR = {"eucaliptal_35m": "#E4002B", "rodal_ifn": "#FF8A00",
         "disperso_copas": "#8B5CF6"}
ETIQUETA = {"eucaliptal_35m": "Eucaliptal seguro (dosel >35 m)",
            "rodal_ifn": "Rodal IFN de especie prohibida",
            "disperso_copas": "Arbolado disperso clasificado"}


def crop_mosaico(x, y, L):
    """Recorte de ortofoto de LxL m centrado en (x,y), cosido entre bloques."""
    px = int(L / 0.25)
    lienzo = np.zeros((px, px, 3), "uint8")
    x0, y0 = x - L / 2, y - L / 2
    for bx in range(int(x0 // 1000), int((x0 + L) // 1000) + 1):
        for by in range(int(y0 // 1000), int((y0 + L) // 1000) + 1):
            p = ORTO25 / f"PNOA-2024-GAL-{bx}-{by+1}-H29-NPC01.tif"
            if not p.exists():
                continue
            with rasterio.open(p) as s:
                v = from_bounds(x0, y0, x0 + L, y0 + L, transform=s.transform)
                v = v.round_offsets().round_lengths()
                a = s.read(window=v, boundless=True, fill_value=0)
            a = np.moveaxis(a, 0, 2)
            if a.shape[:2] != (px, px):
                a = a[:px, :px]
            m = a.any(axis=2)
            lienzo[:a.shape[0], :a.shape[1]][m] = a[m]
    return lienzo


def ficha(ax, r, fx, area=None):
    # el encuadre se ajusta a la mancha: una chincheta fija de 200 m deja un
    # rodal de 17 ha medio fuera y no dice nada de su extension
    L = LADO_CHIP
    if area is not None and not area.is_empty:
        ax0, ay0, ax1, ay1 = area.bounds
        L = float(np.clip(max(ax1 - ax0, ay1 - ay0) * 1.35, LADO_CHIP, 700))
    L = round(L / 4) * 4
    orto = crop_mosaico(r.x, r.y, L)
    ext = (r.x - L/2, r.x + L/2, r.y - L/2, r.y + L/2)
    ax.imshow(orto, extent=ext)
    for g in fx.geometry:
        b = g.boundary
        for linea in getattr(b, "geoms", [b]):
            xs, ys = linea.xy
            ax.plot(xs, ys, color="#FFE14D", lw=1.4)
    c = COLOR.get(r.tipo, "#fff")
    if area is not None and not area.is_empty:
        for poli in getattr(area, "geoms", [area]):
            xs, ys = poli.exterior.xy
            ax.plot(xs, ys, color=c, lw=1.8, alpha=0.95)
            ax.fill(xs, ys, color=c, alpha=0.16)
    # doble trazo: un circulo blanco solo desaparece sobre prado o pista
    rad = max(7, L / 34)
    ax.add_patch(Circle((r.x, r.y), rad, fill=False, ec="#101010", lw=4.0))
    ax.add_patch(Circle((r.x, r.y), rad, fill=False, ec="white", lw=2.0))
    ax.plot([r.x], [r.y], marker="+", ms=9, mew=2.2, color="white")
    # barra de escala proporcional al encuadre
    paso = 50 if L <= 300 else 100
    ax.add_patch(Rectangle((ext[0] + L*0.06, ext[2] + L*0.06), paso, L*0.02,
                           fc="white", ec="black", lw=0.6))
    ax.text(ext[0] + L*0.06 + paso/2, ext[2] + L*0.105, f"{paso} m",
            ha="center", fontsize=7.5, color="white", weight="bold")
    ax.set(xlim=ext[:2], ylim=ext[2:], xticks=[], yticks=[])
    ax.set_title(f"{r.puesto_concello}. {ETIQUETA.get(r.tipo, r.tipo)} — "
                 f"{r.ha:.2f} ha", fontsize=9.5, color=c, weight="bold",
                 loc="left", pad=4)
    ax.set_xlabel(f"{r.PARROQUIA}\nUTM29 {r.x:.0f}, {r.y:.0f}  ·  "
                  f"GPS {r.lat:.5f}, {r.lon:.5f}\n{r.nota}",
                  fontsize=7.4, loc="left", labelpad=4)


def portada(pdf, concello, rank, pts, tot):
    fig = plt.figure(figsize=(8.27, 11.69))
    fig.text(0.08, 0.94, "Dossier de inspección de franjas", fontsize=12,
             color="#666")
    fig.text(0.08, 0.90, concello, fontsize=26, weight="bold")
    fig.text(0.08, 0.865, "Ley 3/2007 · franja de 50 m · arbolado de especie "
             "prohibida (disp. ad. 3ª)", fontsize=9.5, color="#444")

    y = 0.80
    filas = [("Franja medida", f"{tot.ha_medida:,.0f} ha"),
             ("Con arbolado (CHM > 5,5 m)", f"{tot.ha_arbolado:,.0f} ha"),
             ("Estimación de especie prohibida",
              f"{tot.ha_prohibida_min:,.0f} – {tot.ha_prohibida_max:,.0f} ha"),
             ("Eucaliptal seguro (dosel > 35 m)", f"{tot.ha_sobre_35m:,.1f} ha"),
             ("Puntos de inspección en este dossier", f"{len(pts)}")]
    for k, v in filas:
        fig.text(0.08, y, k, fontsize=10.5, color="#333")
        fig.text(0.62, y, v, fontsize=11.5, weight="bold", family="monospace")
        y -= 0.032

    fig.text(0.08, y - 0.02, "Parroquias del concello, por estimación de "
             "superficie prohibida", fontsize=10.5, weight="bold")
    y -= 0.055
    fig.text(0.08, y, "PARROQUIA", fontsize=8, color="#777")
    fig.text(0.55, y, "FRANJA", fontsize=8, color="#777")
    fig.text(0.67, y, "ARBOLADO", fontsize=8, color="#777")
    fig.text(0.82, y, "PROHIBIDO", fontsize=8, color="#777")
    y -= 0.008
    fig.add_artist(plt.Line2D([0.08, 0.92], [y, y], color="#333", lw=0.8))
    y -= 0.022
    for r in rank.itertuples():
        fig.text(0.08, y, r.parroquia[:38], fontsize=9)
        fig.text(0.55, y, f"{r.ha_medida:,.0f} ha", fontsize=9, family="monospace")
        fig.text(0.67, y, f"{r.ha_arbolado:,.0f} ha", fontsize=9, family="monospace")
        fig.text(0.82, y, f"{r.ha_prohibida_min:.0f}–{r.ha_prohibida_max:.0f} ha",
                 fontsize=9, family="monospace", weight="bold")
        y -= 0.021
        if y < 0.16:
            break

    fig.text(0.08, 0.125,
             "Cómo leer este documento", fontsize=10, weight="bold")
    fig.text(0.08, 0.108, va="top", s=
             "Es un INDICADOR DE RIESGO para priorizar visitas, no una acreditación de infracción.\n"
             "La propia ley admite excepciones que ningún sensor puede evaluar (árbol singular u\n"
             "ornamental, zona recreativa con discontinuidad de combustible, ejemplar aislado sin\n"
             "riesgo de propagación), y las especies no listadas —castaño, roble, frutales— son legales.\n"
             "Tasa de falsos positivos del detector de arbolado medida fuera de muestra: 33,5 % [25–42].\n"
             "LiDAR PNOA 2024 y ortofoto PNOA 2023 (IGN, CC-BY 4.0) · franjas: Xunta de Galicia · IFN4 2010.",
             fontsize=7.6, color="#333", linespacing=1.6)
    pdf.savefig(fig)
    plt.close(fig)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--concello", default=None)
    ap.add_argument("--puntos", type=int, default=20,
                    help="fichas por dossier (las de mayor superficie)")
    args = ap.parse_args()

    SALIDA.mkdir(parents=True, exist_ok=True)
    pts = gpd.read_file(MET / "puntos_inspeccion.gpkg")
    ll = pts.to_crs("EPSG:4326")
    pts["lon"], pts["lat"] = ll.geometry.x, ll.geometry.y
    ruta_areas = MET / "areas_inspeccion.gpkg"
    areas = (gpd.read_file(ruta_areas).set_index("id_punto").geometry
             if ruta_areas.exists() else None)
    rank = pd.read_csv(MET / "ranking_final.csv", encoding="utf-8-sig")
    rank_c = pd.read_csv(MET / "ranking_final_concello.csv", encoding="utf-8-sig")
    fx = gpd.GeoDataFrame(pd.concat(
        [gpd.read_file(PROC / f"faixas_{n}_paradanta_ok.gpkg")
         for n in ("nucleos", "illadas")], ignore_index=True), crs="EPSG:25829")

    concellos = [args.concello] if args.concello else sorted(pts.NOMECONCEL.unique())
    for con in concellos:
        p = pts[pts.NOMECONCEL == con].nlargest(args.puntos, "ha")
        r = rank[rank.concello == con].sort_values("ha_prohibida_punto_medio",
                                                   ascending=False)
        tot = rank_c[rank_c.concello == con].iloc[0]
        nombre = con.replace(",", "").replace(" ", "_")
        ruta = SALIDA / f"dossier_{nombre}.pdf"
        with PdfPages(ruta) as pdf:
            portada(pdf, con, r, p, tot)
            fx_c = fx[fx.NOMECONCEL == con]
            for i in range(0, len(p), POR_PAGINA):
                lote = p.iloc[i:i + POR_PAGINA]
                fig, axs = plt.subplots(2, 2, figsize=(8.27, 11.69))
                for ax in axs.flat:
                    ax.axis("off")
                for ax, (_, r_) in zip(axs.flat, lote.iterrows()):
                    ax.axis("on")
                    a = (areas.get(r_.id_punto) if areas is not None
                         and "id_punto" in lote.columns else None)
                    ficha(ax, r_, fx_c, a)
                fig.suptitle(f"{con} — puntos de inspección "
                             f"{i+1}–{min(i+POR_PAGINA, len(p))} de {len(p)}",
                             fontsize=11)
                fig.tight_layout(rect=(0, 0.01, 1, 0.97))
                pdf.savefig(fig)
                plt.close(fig)
        print(f"  {ruta.relative_to(RAIZ)}  ({len(p)} fichas, "
              f"{ruta.stat().st_size/1e6:.1f} MB)")
