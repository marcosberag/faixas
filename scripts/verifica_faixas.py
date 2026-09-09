"""Verifica que el shapefile descargado coincide con lo que pinta el servicio oficial,
y caracteriza la geometria real de la faixa."""
import io
import json
import pathlib

import geopandas as gpd
import numpy as np
import requests
from PIL import Image
from shapely.geometry import box

RAIZ = pathlib.Path(__file__).resolve().parent.parent
PROC = RAIZ / "datos" / "procesado"
BASE = ("https://ideg.xunta.gal/servizos/rest/services/PBA/"
        "Afeccions_Agropecuaria_Faixas/MapServer")
WHERE = "CONCELLO IN ('Arbo', 'Cañiza, A', 'Covelo', 'Crecente')"

nuc = gpd.read_file(PROC / "faixas_nucleos_paradanta_ok.gpkg")
ill = gpd.read_file(PROC / "faixas_illadas_paradanta_ok.gpkg")

# --- 1. caracterizacion: que es el poligono? --------------------------------
print("=== geometria real de la faixa")
for nombre, gdf in (("nucleos", nuc), ("illadas", ill)):
    partes = gdf.explode(index_parts=False).reset_index(drop=True)
    partes = partes[partes.geometry.area > 500]
    a = partes.geometry.area.values
    p = partes.geometry.length.values
    ancho = 2 * a / p          # ancho medio de una banda: 2*area/perimetro
    print(f"\n  {nombre}: {len(gdf)} registros -> {len(partes)} poligonos sueltos")
    print(f"    area por parte: mediana {np.median(a):,.0f} m2, "
          f"p90 {np.percentile(a,90):,.0f}, max {a.max():,.0f}")
    print(f"    ancho medio (2A/P): mediana {np.median(ancho):.1f} m, "
          f"p25 {np.percentile(ancho,25):.1f}, p75 {np.percentile(ancho,75):.1f}")
    # radio inscrito de las partes grandes
    grandes = partes.nlargest(15, partes.geometry.area.name if False else None,
                              keep="all") if False else partes.iloc[
        np.argsort(-a)[:15]]
    radios = []
    for g in grandes.geometry:
        lo, hi = 0.0, 500.0
        for _ in range(22):
            mid = (lo + hi) / 2
            if g.buffer(-mid).is_empty: hi = mid
            else: lo = mid
        radios.append(lo)
    print(f"    radio inscrito de las 15 partes mayores: mediana "
          f"{np.median(radios):.0f} m, max {max(radios):.0f} m")

# --- 2. el shapefile coincide con lo que pinta el servicio? ------------------
print("\n=== contraste contra el /export del servicio oficial")
ZC = (559731.0, 4666398.0)
LADO, PX = 1400.0, 1000
CAJA = (ZC[0] - LADO/2, ZC[1] - LADO/2, ZC[0] + LADO/2, ZC[1] + LADO/2)

r = requests.get(f"{BASE}/export", params={
    "bbox": "{},{},{},{}".format(*CAJA), "bboxSR": 25829, "imageSR": 25829,
    "size": f"{PX},{PX}", "layers": "show:0,1",
    "layerDefs": json.dumps({"0": WHERE, "1": WHERE}),
    "transparent": "true", "format": "png32", "f": "image"}, timeout=180)
alfa = np.array(Image.open(io.BytesIO(r.content)).convert("RGBA"))[:, :, 3] > 40
print(f"  servicio: {alfa.sum():,} px de faixa ({alfa.mean():.2%} del encuadre)")

# rasterizar el shapefile en la misma rejilla
from rasterio.features import rasterize
from rasterio.transform import from_bounds

recorte = gpd.GeoDataFrame(
    geometry=list(nuc.geometry) + list(ill.geometry), crs=nuc.crs)
recorte = recorte[recorte.intersects(box(*CAJA))]
tr = from_bounds(*CAJA, PX, PX)
shp = rasterize([(g, 1) for g in recorte.geometry], out_shape=(PX, PX),
                transform=tr, fill=0, all_touched=False).astype(bool)
print(f"  shapefile: {shp.sum():,} px de faixa ({shp.mean():.2%} del encuadre)")

inter = (alfa & shp).sum()
union = (alfa | shp).sum()
print(f"  IoU (Jaccard): {inter/union:.4f}")
print(f"  solo en servicio: {(alfa & ~shp).sum():,} px")
print(f"  solo en shapefile: {(shp & ~alfa).sum():,} px")
print(f"  -> {'COINCIDEN' if inter/union > 0.95 else 'DIFIEREN, revisar'}")
