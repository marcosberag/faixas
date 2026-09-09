"""Repara las geometrias invalidas del shapefile oficial y verifica la banda de 50 m.

El shapefile de la Xunta trae poligonos con auto-interseccion (anillos que se tocan).
Sin reparar, cualquier recorte del CHM contra ellos da resultados silenciosamente malos.
"""
import pathlib

import geopandas as gpd
from shapely import make_valid

RAIZ = pathlib.Path(__file__).resolve().parent.parent
PROC = RAIZ / "datos" / "procesado"

for nombre in ("nucleos", "illadas"):
    ruta = PROC / f"faixas_{nombre}_paradanta.gpkg"
    gdf = gpd.read_file(ruta)
    print(f"\n=== {nombre}: {len(gdf)} registros")

    malas = ~gdf.geometry.is_valid
    print(f"  invalidas antes: {malas.sum()}")
    if malas.any():
        from shapely.validation import explain_validity
        for i in gdf[malas].index[:3]:
            print(f"    fid {i}: {explain_validity(gdf.geometry[i])[:90]}")

    area_antes = gdf.geometry.area.sum()
    gdf["geometry"] = gdf.geometry.apply(make_valid)
    # make_valid puede devolver colecciones: quedarse solo con la parte poligonal
    gdf["geometry"] = gdf.geometry.buffer(0)
    area_despues = gdf.geometry.area.sum()

    print(f"  invalidas despues: {(~gdf.geometry.is_valid).sum()}")
    print(f"  superficie {area_antes/1e4:,.1f} ha -> {area_despues/1e4:,.1f} ha "
          f"(cambio {100*(area_despues-area_antes)/area_antes:+.3f} %)")
    print(f"  vacias: {gdf.geometry.is_empty.sum()}  area cero: {(gdf.geometry.area == 0).sum()}")

    salida = PROC / f"faixas_{nombre}_paradanta_ok.gpkg"
    gdf.to_file(salida, driver="GPKG")
    print(f"  -> {salida.name}")

# --- la banda mide 50 m? -----------------------------------------------------
# Cada poligono de illadas envuelve una edificacion aislada. Al erosionarlo 50 m
# deberia quedar solo la huella del edificio; a algo mas de 50 m, nada.
print("\n=== verificacion del ancho: erosion progresiva de las illadas")
ill = gpd.read_file(PROC / "faixas_illadas_paradanta_ok.gpkg")
partes = ill.explode(index_parts=False).reset_index(drop=True)
partes = partes[partes.geometry.area > 1000].copy()
partes["a"] = partes.geometry.area
print(f"  {len(partes)} poligonos con area > 1000 m2")

for _, f in partes.nsmallest(6, "a").iterrows():
    g = f.geometry
    fila = [f"  {g.area:>9,.0f} m2 |"]
    for d in (40, 49, 50, 51, 55):
        r = g.buffer(-d)
        fila.append(f" -{d}m:{'vacio' if r.is_empty else format(r.area, '>7,.0f')}")
    print("".join(fila))

# el radio maximo inscrito de los poligonos mas pequenos deberia rondar los 50 m
import numpy as np
radios = []
for g in partes.nsmallest(40, "a").geometry:
    lo, hi = 0.0, 200.0
    for _ in range(24):
        mid = (lo + hi) / 2
        if g.buffer(-mid).is_empty:
            hi = mid
        else:
            lo = mid
    radios.append(lo)
radios = np.array(radios)
print(f"\n  radio inscrito de las 40 illadas mas pequenas:")
print(f"    mediana {np.median(radios):.1f} m | min {radios.min():.1f} | "
      f"max {radios.max():.1f} | p25 {np.percentile(radios,25):.1f} "
      f"| p75 {np.percentile(radios,75):.1f}")
