"""¿Es eucalipto todo lo que pasa de 35 m en faixa? Contraste fenologico.

La regla estructural (`ha_sobre_35m` = eucaliptal seguro) se apoya en que en
Galicia solo el eucalipto pasa de 35 m. Casi: el abeto Douglas tambien puede,
pero esta en la lista de prohibidas igual, asi que no rompe el producto. El
riesgo real es el CHOPO de ribera (35-40 m y EXENTO por ser frondosa no listada).

Distincion barata: el chopo es caducifolio y el eucalipto perennifolio. El mapa
de caida estacional de NDVI (verano - invierno) ya existe. Si un pixel de >35 m
pierde el verdor en invierno, no es eucalipto y hay que restarlo del suelo.

OJO: esto NO resucita el clasificador de especie que se rechazo. Aquella tarea
era clasificar arbolado desconocido con precision por pixel; esta es comprobar
una masa concreta contra la senal mas fuerte que existe (caida 0,26 en caducifolia
contra ~0,00 en eucalipto/pino, medida aqui). Cribar no es clasificar.

Uso:
    python scripts/verifica_35m_fenologia.py
"""
import pathlib

import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio
from rasterio.enums import Resampling
from rasterio.features import rasterize
from rasterio.vrt import WarpedVRT
from shapely.geometry import box

RAIZ = pathlib.Path(__file__).resolve().parent.parent
PROC = RAIZ / "datos" / "procesado"
LIDAR = PROC / "lidar"

UMBRAL_CADUCA = 0.175   # el corte calibrado en fenologia_especie.py

if __name__ == "__main__":
    faixas = gpd.GeoDataFrame(pd.concat(
        [gpd.read_file(PROC / f"faixas_{n}_paradanta_ok.gpkg").assign(capa=n)
         for n in ("nucleos", "illadas")], ignore_index=True), crs="EPSG:25829")

    caidas, veranos, sitios = [], [], []
    with rasterio.open(PROC / "s2" / "ndvi_caida.tif") as s_c, \
         rasterio.open(PROC / "s2" / "ndvi_verano.tif") as s_v:
        for chm_path in sorted(LIDAR.glob("*_chm.tif")):
            with rasterio.open(chm_path) as s:
                h = s.read(1, masked=True)
                m35 = ~np.ma.getmaskarray(h) & (np.asarray(h) > 35)
                if not m35.any():
                    continue
                rec = box(*s.bounds)
                geos = [(g.intersection(rec), 1) for g in faixas.geometry
                        if g.intersects(rec)]
                if not geos:
                    continue
                dentro = rasterize(geos, out_shape=s.shape, transform=s.transform,
                                   fill=0, all_touched=False, dtype="uint8").astype(bool)
                m = m35 & dentro
                if not m.any():
                    continue
                with WarpedVRT(s_c, crs=s.crs, transform=s.transform, width=s.width,
                               height=s.height, resampling=Resampling.nearest) as v:
                    ca = v.read(1)
                with WarpedVRT(s_v, crs=s.crs, transform=s.transform, width=s.width,
                               height=s.height, resampling=Resampling.nearest) as v:
                    ve = v.read(1)
                fil, col = np.nonzero(m)
                caidas.append(ca[fil, col])
                veranos.append(ve[fil, col])
                x, y = rasterio.transform.xy(s.transform, fil, col)
                sitios.append(pd.DataFrame({
                    "x": x, "y": y, "caida": ca[fil, col], "bloque": chm_path.name[:-8]}))

    d = pd.concat(sitios, ignore_index=True)
    ok = np.isfinite(d.caida)
    print(f"{len(d):,} px de >35 m en faixa ({len(d)/1e4:.1f} ha), "
          f"{100*ok.mean():.1f} % con dato de NDVI\n")

    c = d.caida[ok]
    print("caida estacional de NDVI (verano - invierno) en esos pixeles:")
    print(f"  mediana {c.median():+.3f}   p10 {c.quantile(.1):+.3f}   "
          f"p90 {c.quantile(.9):+.3f}")
    print(f"  referencia medida en la comarca: eucalipto -0,03 · pino +0,01 · "
          f"roble +0,26\n")

    sospe = d[ok & (d.caida > UMBRAL_CADUCA)]
    print(f"pixeles con perfil CADUCIFOLIO (caida > {UMBRAL_CADUCA:g}): "
          f"{len(sospe):,} de {ok.sum():,} ({100*len(sospe)/ok.sum():.1f} %)")
    if len(sospe):
        print("  posibles chopos u otra frondosa alta: restar del suelo y mirar a ojo.")
        agr = (sospe.groupby("bloque").agg(n=("caida", "size"),
                                           x=("x", "mean"), y=("y", "mean"))
               .sort_values("n", ascending=False))
        for b, f in agr.head(6).iterrows():
            print(f"    {b}  {f.n:>4.0f} px  hacia ({f.x:.0f}, {f.y:.0f})")
    else:
        print("  ninguno: el suelo estructural es perennifolio al completo.")
