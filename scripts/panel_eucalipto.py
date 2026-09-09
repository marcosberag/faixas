"""Panel de evidencia de un rodal de eucalipto en faixa, con las tres miradas.

Para un punto senalado por el CHM como eucaliptal casi seguro (>35 m):

  1. la ortofoto del PNOA (sept 2023) — lo que ve un fotointerprete,
  2. el CHM del LiDAR (jun-jul 2024) — la altura que lo delata,
  3. Sentinel-2 DE AHORA — ¿sigue ahi o ya se ha cortado?

La tercera es la interesante: el LiDAR es una foto fija de 2024 y una corta
posterior invalidaria la prioridad. Sentinel-2 pasa cada pocos dias, asi que la
comprobacion de vigencia es gratis. Un eucaliptal en pie da NDVI alto y estable;
una corta reciente, suelo desnudo y una caida grande.

Mismas trampas de siempre con los COG de AWS: NO aplicar el offset que declara
el STAC (vienen armonizados) y guardia de rango en el NDVI.

Uso:
    python scripts/panel_eucalipto.py                      # el rodal de Mourentan
    python scripts/panel_eucalipto.py --x 558253 --y 4665280 --bloque PNOA-2024-GAL-558-4666-H29-NPC01
"""
import argparse
import pathlib
import sys

import geopandas as gpd
import numpy as np
import rasterio
import requests
from pyproj import Transformer
from rasterio.enums import Resampling
from rasterio.transform import from_origin
from rasterio.vrt import WarpedVRT
from shapely.geometry import box

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from chips_validacion import tesela  # ortofoto del WMS del IGN

RAIZ = pathlib.Path(__file__).resolve().parent.parent
PROC = RAIZ / "datos" / "procesado"
SALIDAS = RAIZ / "salidas"
STAC = "https://earth-search.aws.element84.com/v1/search"
LADO = 240          # m de encuadre
RES_ORTO = 0.25     # m/px de la ortofoto (960 px de panel)


def escena_reciente(bbox4326, dias="2026-07-01T00:00:00Z/2026-08-19T23:59:59Z"):
    r = requests.post(STAC, json={
        "collections": ["sentinel-2-l2a"], "bbox": list(bbox4326),
        "datetime": dias, "query": {"eo:cloud_cover": {"lt": 30}},
        "limit": 50}, timeout=90)
    r.raise_for_status()
    fs = sorted(r.json()["features"], key=lambda f: f["properties"]["eo:cloud_cover"])
    if not fs:
        raise SystemExit("sin escenas S2 recientes sin nubes: amplia la ventana")
    # la mas reciente entre las 5 menos nubladas: queremos vigencia, no belleza
    return max(fs[:5], key=lambda f: f["properties"]["datetime"])


def lee_cog(href, tr, w, h, remuestreo=Resampling.nearest):
    with rasterio.open(f"/vsicurl/{href}") as src:
        with WarpedVRT(src, crs="EPSG:25829", transform=tr, width=w, height=h,
                       resampling=remuestreo) as vrt:
            return vrt.read()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--x", type=float, default=558253)
    ap.add_argument("--y", type=float, default=4665280)
    ap.add_argument("--bloque", default="PNOA-2024-GAL-558-4666-H29-NPC01")
    ap.add_argument("--capa", default="nucleos")
    ap.add_argument("--titulo", default="Eucaliptal en franja de proteccion — Mourentan (Arbo)")
    ap.add_argument("--salida", default="eucalipto_mourentan.png")
    args = ap.parse_args()
    x, y, L = args.x, args.y, LADO

    # --- CHM y mascara de >35 m en el encuadre -----------------------------
    with rasterio.open(PROC / "lidar" / f"{args.bloque}_chm.tif") as s:
        ven = rasterio.windows.from_bounds(x - L/2, y - L/2, x + L/2, y + L/2,
                                           transform=s.transform)
        chm = s.read(1, window=ven, boundless=True, fill_value=0)
    chm[chm < -1000] = 0
    m35 = chm > 35

    fx = gpd.read_file(PROC / f"faixas_{args.capa}_paradanta_ok.gpkg")
    ext = (x - L/2, x + L/2, y - L/2, y + L/2)
    marco = box(ext[0], ext[2], ext[1], ext[3])

    # --- ortofoto ----------------------------------------------------------
    orto = tesela(x - L/2, y - L/2, L, int(L / RES_ORTO))

    # --- Sentinel-2 de ahora -----------------------------------------------
    a4326 = Transformer.from_crs(25829, 4326, always_xy=True)
    lon0, lat0 = a4326.transform(x - L/2, y - L/2)
    lon1, lat1 = a4326.transform(x + L/2, y + L/2)
    esc = escena_reciente((lon0, lat0, lon1, lat1))
    p = esc["properties"]
    fecha, nube = p["datetime"][:10], p["eo:cloud_cover"]
    print(f"escena S2: {esc['id']}  {fecha}  nube {nube:.0f} %", flush=True)

    tr10 = from_origin(x - L/2, y + L/2, 10, 10)
    n10 = int(L / 10)
    gdal_env = {"GDAL_DISABLE_READDIR_ON_OPEN": "EMPTY_DIR",
                "CPL_VSIL_CURL_ALLOWED_EXTENSIONS": ".tif"}
    with rasterio.Env(**gdal_env):
        vis = lee_cog(esc["assets"]["visual"]["href"], tr10, n10, n10)
        rojo = lee_cog(esc["assets"]["red"]["href"], tr10, n10, n10)[0].astype("float32")
        nir = lee_cog(esc["assets"]["nir"]["href"], tr10, n10, n10)[0].astype("float32")
        scl = lee_cog(esc["assets"]["scl"]["href"], tr10, n10, n10)[0]
    # sin offset a proposito (COG armonizados); guardia de rango como siempre
    r_, n_ = rojo * 1e-4, nir * 1e-4
    with np.errstate(invalid="ignore", divide="ignore"):
        ndvi_hoy = (n_ - r_) / (n_ + r_)
    ndvi_hoy[np.isin(scl, (0, 1, 3, 8, 9, 10, 11))] = np.nan
    fuera = np.nanmean(np.abs(ndvi_hoy) > 1)
    if np.isfinite(fuera) and fuera > 0.01:
        raise SystemExit("NDVI fuera de [-1,1]: revisa el escalado")

    # mascara del rodal a 10 m para promediar: los >35 m si los hay (el caso
    # eucalipto), y si no, el arbolado sobre el umbral calibrado
    base = m35 if m35.any() else (chm > 5.5)
    k = 10
    m10 = base[:n10*k, :n10*k].reshape(n10, k, n10, k).mean(axis=(1, 3)) > 0.5
    ndvi_rodal_hoy = float(np.nanmean(ndvi_hoy[m10]))

    with rasterio.open(PROC / "s2" / "ndvi_verano.tif") as s:
        v24 = s.read(1, window=rasterio.windows.from_bounds(
            x - L/2, y - L/2, x + L/2, y + L/2, transform=s.transform),
            boundless=True, out_shape=(n10, n10))
    ndvi_rodal_24 = float(np.nanmean(v24[m10]))
    print(f"NDVI del rodal: verano 2024 {ndvi_rodal_24:.3f}  ->  {fecha} {ndvi_rodal_hoy:.3f}")

    # --- panel ---------------------------------------------------------------
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    def franja(ax):
        for g in fx.geometry:
            if not g.intersects(marco):
                continue
            for poly in getattr(g, "geoms", [g]):
                xs, ys = poly.exterior.xy
                ax.plot(xs, ys, color="#FFE14D", lw=1.6, alpha=.95)
        ax.contour(m35[::-1], levels=[.5], extent=ext, colors="#FF5533",
                   linewidths=1.6, origin="lower")
        ax.set(xlim=ext[:2], ylim=ext[2:], xticks=[], yticks=[])

    fig, axs = plt.subplots(1, 3, figsize=(16.5, 6.1))
    axs[0].imshow(orto, extent=ext)
    franja(axs[0])
    axs[0].set_title("Ortofoto PNOA · septiembre 2023", fontsize=12)

    im = axs[1].imshow(np.where(chm > 0.5, chm, np.nan), extent=ext,
                       cmap="viridis", vmin=0, vmax=45)
    axs[1].set_facecolor("#111")
    franja(axs[1])
    axs[1].set_title("Altura LiDAR (CHM) · junio-julio 2024", fontsize=12)
    plt.colorbar(im, ax=axs[1], fraction=.046, label="m sobre el suelo")

    axs[2].imshow(np.moveaxis(vis, 0, -1), extent=ext, interpolation="nearest")
    franja(axs[2])
    axs[2].set_title(f"Sentinel-2 · {fecha} (10 m/px)", fontsize=12)
    axs[2].text(.02, .02,
                f"NDVI del rodal\nverano 2024: {ndvi_rodal_24:.2f}\n{fecha}: {ndvi_rodal_hoy:.2f}",
                transform=axs[2].transAxes, fontsize=11, color="w", va="bottom",
                bbox=dict(facecolor="black", alpha=.65, pad=6))

    fig.suptitle(f"{args.titulo}   |   "
                 "amarillo: limite de franja   ·   rojo: arbolado > 35 m",
                 fontsize=13, y=.98)
    fig.text(.5, .01, "PNOA (IGN, CC-BY 4.0) · Copernicus Sentinel-2 · elaboracion propia",
             ha="center", fontsize=9, color="#666")
    fig.tight_layout(rect=[0, .03, 1, .95])
    SALIDAS.mkdir(exist_ok=True)
    ruta = SALIDAS / args.salida
    fig.savefig(ruta, dpi=150)
    print(f"-> {ruta.relative_to(RAIZ)}")
