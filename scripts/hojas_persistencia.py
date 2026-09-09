"""Hojas de contacto para validar el detector de eventos: la serie por rodal.

Una imagen por rodal de la muestra, con 8 paneles:

    PNOA 2010   PNOA 2014   PNOA 2017   PNOA 2020
    PNOA 2023   S2 ver.2024 S2 reciente contexto (x2.5)

Los cinco primeros son los vuelos del PNOA historico que existen en la zona
(comprobado contra el WMS: 2004, 2008, 2010, 2014, 2017, 2020, 2023; se
empieza en 2010 porque es el anho de la etiqueta del IFN). Los dos de
Sentinel-2 cubren el tramo posterior al ultimo vuelo: el verano de 2024
(cuando volo el LiDAR) y la escena reciente. A 10 m/px son toscos, pero una
corta rasa de media hectarea se ve igual.

CIEGO: la hoja no lleva veredicto del detector, ni especie, ni NDVI. Solo el
contorno del rodal (sin el no se sabe que masa juzgar) y la escala. La
pregunta del anotador es en que INTERVALO se ve el reemplazo, si se ve; la
comparacion con el detector viene despues, en valida_persistencia.py.

Reanudable: las hojas ya en disco no se rehacen. Los visuales de zona de
Sentinel-2 se bajan una vez y se recortan en local.

Uso:
    python scripts/hojas_persistencia.py
"""
import io
import pathlib
import sys
import time

import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio
import requests
from PIL import Image
from rasterio.enums import Resampling
from rasterio.vrt import WarpedVRT
from rasterio.windows import from_bounds

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from descarga_s2 import GDAL, busca, rejilla

RAIZ = pathlib.Path(__file__).resolve().parent.parent
PROC = RAIZ / "datos" / "procesado"
VAL = PROC / "validacion_persistencia"
S2 = PROC / "s2"

WMS_HIST = "https://www.ign.es/wms/pnoa-historico"
ANHOS_PNOA = (2010, 2014, 2017, 2020, 2023)
PX = 640                 # lado en px de cada panel de ortofoto
FACTOR_CTX = 2.5         # el panel de contexto amplia el encuadre


def tesela_hist(capa, x0, y0, lado, px, intentos=4):
    """GetMap del PNOA historico con reintentos (el WMS suelta 502 a veces)."""
    for i in range(1, intentos + 1):
        try:
            r = requests.get(WMS_HIST, timeout=300, params={
                "SERVICE": "WMS", "VERSION": "1.3.0", "REQUEST": "GetMap",
                "LAYERS": capa, "STYLES": "", "CRS": "EPSG:25829",
                "BBOX": f"{x0},{y0},{x0+lado},{y0+lado}",
                "WIDTH": px, "HEIGHT": px, "FORMAT": "image/jpeg"})
            r.raise_for_status()
            if "image" not in r.headers.get("Content-Type", ""):
                raise RuntimeError(f"el WMS devolvio {r.text[:200]}")
            return np.asarray(Image.open(io.BytesIO(r.content)).convert("RGB"))
        except Exception as e:
            if i == intentos:
                raise
            print(f"    ({capa}: {type(e).__name__}, reintento {i})", flush=True)
            time.sleep(10 * i)


def visual_zona(anho, reciente=False):
    """Visual (TCI) de Sentinel-2 de toda la zona, cacheado en disco."""
    ruta = S2 / f"visual_{anho}.tif"
    if ruta.exists():
        with rasterio.open(ruta) as s:
            return ruta, s.tags().get("fecha", str(anho))
    fin = "2026-08-19" if anho == 2026 else f"{anho}-08-31"
    rango = f"{anho}-06-15T00:00:00Z/{fin}T23:59:59Z"
    items = busca(rango, 5, nube_max=30)
    if not items:
        raise SystemExit(f"sin escenas S2 de verano de {anho}")
    # para vigencia interesa la mas reciente entre las menos nubladas;
    # para 2024, simplemente la menos nublada del verano del vuelo
    esc = (max(items, key=lambda f: f["properties"]["datetime"])
           if reciente else items[0])
    fecha = esc["properties"]["datetime"][:10]
    print(f"  visual S2 {anho}: escena {fecha}, "
          f"nube {esc['properties']['eo:cloud_cover']:.0f} %", flush=True)

    tr, w, h = rejilla()
    with rasterio.Env(**GDAL):
        with rasterio.open(f"/vsicurl/{esc['assets']['visual']['href']}") as src:
            with WarpedVRT(src, crs="EPSG:25829", transform=tr, width=w,
                           height=h, resampling=Resampling.nearest) as vrt:
                a = vrt.read()
    perfil = dict(driver="GTiff", dtype="uint8", count=3, width=w, height=h,
                  crs="EPSG:25829", transform=tr, compress="deflate",
                  tiled=True, blockxsize=512, blockysize=512)
    with rasterio.open(ruta, "w", **perfil) as dst:
        dst.write(a.astype("uint8"))
        dst.update_tags(fecha=fecha, escena=esc["id"])
    return ruta, fecha


def recorte_s2(ruta, x, y, lado):
    with rasterio.open(ruta) as s:
        v = from_bounds(x - lado/2, y - lado/2, x + lado/2, y + lado/2,
                        transform=s.transform)
        a = s.read(window=v.round_offsets().round_lengths(),
                   boundless=True, fill_value=0)
    return np.moveaxis(a, 0, 2)


def contorno(ax, geo, ext, color="#FFE14D"):
    for poly in getattr(geo, "geoms", [geo]):
        xs, ys = poly.exterior.xy
        ax.plot(xs, ys, color="black", lw=3.2, alpha=.55)
        ax.plot(xs, ys, color=color, lw=1.6, alpha=.95)
    ax.set(xlim=ext[:2], ylim=ext[2:], xticks=[], yticks=[])


if __name__ == "__main__":
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    m = pd.read_csv(VAL / "muestra.csv", encoding="utf-8-sig")
    ifn = gpd.read_file(PROC / "ifn_especies_paradanta.gpkg").set_index("OBJECTID_12")
    HOJAS = VAL / "hojas"
    HOJAS.mkdir(parents=True, exist_ok=True)

    print("visuales de zona de Sentinel-2 (una vez, luego recorte local):")
    v24, fecha24 = visual_zona(2024)
    v26, fecha26 = visual_zona(2026, reciente=True)

    hechas = {p.stem for p in HOJAS.glob("v*.png")}
    pendientes = m[~m.id.isin(hechas)]
    print(f"\n{len(m)} hojas, {len(hechas)} ya en disco, {len(pendientes)} pendientes")

    t0 = time.perf_counter()
    for k, f in enumerate(pendientes.itertuples(), 1):
        x, y, L = f.x, f.y, f.lado
        ext = (x - L/2, x + L/2, y - L/2, y + L/2)
        geo = ifn.geometry.loc[f.OBJECTID_12]

        paneles = []
        for a in ANHOS_PNOA:
            im = tesela_hist(f"PNOA{a}", x - L/2, y - L/2, L, PX)
            sin = im.std() < 5          # blanco uniforme = sin vuelo ahi
            paneles.append((f"PNOA {a}", im, sin))
        paneles.append((f"Sentinel-2  {fecha24}", recorte_s2(v24, x, y, L), False))
        paneles.append((f"Sentinel-2  {fecha26}", recorte_s2(v26, x, y, L), False))

        LC = L * FACTOR_CTX
        ctx = tesela_hist("PNOA2023", x - LC/2, y - LC/2, LC, PX)
        extc = (x - LC/2, x + LC/2, y - LC/2, y + LC/2)

        # 2 filas de paneles CUADRADOS de ~4,2": si la figura se queda corta de
        # alto, los titulos de la fila de abajo pisan las imagenes de arriba
        fig, axs = plt.subplots(2, 4, figsize=(17.6, 9.6),
                                gridspec_kw=dict(hspace=0.08, wspace=0.04))
        for ax, (titulo, im, sin) in zip(axs.flat[:7], paneles):
            ax.imshow(im, extent=ext, interpolation="nearest")
            contorno(ax, geo, ext)
            ax.set_title(titulo, fontsize=11)
            if sin:
                ax.text(.5, .5, "sin vuelo", transform=ax.transAxes,
                        ha="center", fontsize=14, color="#888")
        axc = axs.flat[7]
        axc.imshow(ctx, extent=extc)
        contorno(axc, geo, extc)
        axc.plot([ext[0], ext[1], ext[1], ext[0], ext[0]],
                 [ext[2], ext[2], ext[3], ext[3], ext[2]],
                 color="white", lw=1.2, ls="--", alpha=.9)
        axc.set_title("contexto · PNOA 2023", fontsize=11)

        # barra de escala en el primer panel: 100 m reales
        ax0 = axs.flat[0]
        bx, by = ext[0] + L*.06, ext[2] + L*.06
        ax0.plot([bx, bx + 100], [by, by], color="black", lw=5)
        ax0.plot([bx, bx + 100], [by, by], color="white", lw=2.5)
        ax0.text(bx, by + L*.025, "100 m", color="white", fontsize=10,
                 path_effects=None, bbox=dict(facecolor="black", alpha=.5, pad=1))

        fig.suptitle(f"{f.id}   ·   encuadre {L} m   ·   "
                     "amarillo: limite del rodal", fontsize=13, y=.985)
        # a mano y no tight_layout: con aspect igual, tight_layout dejaba las
        # filas pegadas y los titulos de abajo caian sobre las imagenes de arriba
        fig.subplots_adjust(left=.01, right=.99, top=.915, bottom=.015,
                            hspace=.12, wspace=.04)
        fig.savefig(HOJAS / f"{f.id}.png", dpi=105)
        plt.close(fig)

        media = (time.perf_counter() - t0) / k
        print(f"  {f.id}  ({k}/{len(pendientes)}, {media:.0f} s/hoja)", flush=True)

    mb = sum(p.stat().st_size for p in HOJAS.glob("v*.png")) / 1e6
    print(f"\n{len(list(HOJAS.glob('v*.png')))} hojas, {mb:.0f} MB")
    print(f"-> {HOJAS.relative_to(RAIZ)}")
