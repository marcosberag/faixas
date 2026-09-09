"""Recorta el CHM por los poligonos de faixa y mide superficie sobre umbral.

Criterio de salida de la fase 1. Produce dos CSV:

  metricas_faixa_bloque.csv   una fila por (faixa, bloque, umbral)
  metricas_parroquia.csv      agregado por parroquia, una fila por umbral

EL UMBRAL SE CALCULA A VARIAS ALTURAS (2, 3, 5, 8, 10 m) a proposito, para no
comprometerse con ninguna. Si ya existe `validacion/calibracion_resumen.csv`, se
anade ademas el umbral calibrado en la fase 2 y pasa a ser el de referencia para
ordenar y para lo que se imprime.

EL UMBRAL CALIBRADO SOLO VALE A 1 m DE PIXEL. A 0,5 m la misma faixa da un 17 %
menos de superficie sobre umbral, porque el MDS toma el maximo de la celda. Si
alguna vez se cambia RES en pipeline_chm.py, la calibracion hay que rehacerla.

Y NO ES UN INDICADOR DE INCUMPLIMIENTO. La Ley 3/2007 solo prohibe 7 especies
arboreas y su disposicion adicional tercera, punto 3, exime a las frondosas no
listadas: un castanhar dentro de la faixa es legal y da la misma senhal en el CHM
que un pinar. Ver docs/03-marco-legal.md. Esto es superficie arbolada, sin mas.

Como se recorta, que tiene su miga:
  - `rasterize` con `all_touched=False` marca el pixel si su CENTRO cae dentro del
    poligono. Es lo que hay que usar para medir superficie: con all_touched=True
    se cuentan los pixeles que el poligono roza, y la faixa saldria inflada en
    todo su perimetro, que es larguisimo (son bandas de 50 m).
  - El area de cada pixel es exactamente res*res porque estamos en EPSG:25829, que
    es metrico. Nada de reproyecciones ni de correcciones por latitud.
  - Una faixa cae en varios bloques y un bloque toca varias faixas. Se mide por
    pareja (faixa, bloque) y se suma despues, que ademas permite comprobar que la
    suma de trozos cuadra con el area del poligono completo.

Uso:
    python scripts/metricas_faixas.py
"""
import pathlib

import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio
from rasterio.errors import WindowError
from rasterio.features import rasterize
from rasterio.windows import Window, from_bounds
from shapely.geometry import box

RAIZ = pathlib.Path(__file__).resolve().parent.parent
PROC = RAIZ / "datos" / "procesado"
LIDAR = PROC / "lidar"
SALIDA = PROC / "metricas"

# El 35 no es un umbral de arbolado: en Galicia solo el eucalipto pasa de 35 m,
# asi que `ha_sobre_35m` es un suelo minimo de especie prohibida que sale del
# propio CHM, sin satelite. Precision altisima, recall bajo (solo eucaliptal
# maduro): se lee como cota inferior, nunca como estimacion.
UMBRALES = (2.0, 3.0, 5.0, 8.0, 10.0, 35.0)  # m. Ver docstring.


def calibracion():
    """El umbral de la fase 2, si ya se ha calibrado. Si no, None."""
    r = PROC / "validacion" / "calibracion_resumen.csv"
    if not r.exists():
        return None
    c = pd.read_csv(r, encoding="utf-8-sig").iloc[0]
    if float(c.resolucion_px_m) != 1.0:
        raise SystemExit(f"la calibracion es a {c.resolucion_px_m} m de pixel y el "
                         "CHM esta a 1 m: no es transferible, hay que recalibrar")
    return c


def sufijo(zona):
    """Sufijo de fichero de salida. Vacio para la zona piloto: asi los CSV que
    ya consumen ranking_final.py, el visor y los dossiers no cambian de nombre.
    """
    return "" if zona == "paradanta" else f"_{zona}"


def carga_faixas(zona="paradanta"):
    capas = []
    for nombre in ("nucleos", "illadas"):
        gdf = gpd.read_file(PROC / f"faixas_{nombre}_{zona}_ok.gpkg")
        gdf = gdf.assign(capa=nombre)
        gdf["faixa_id"] = [f"{nombre[:3]}-{i}" for i in gdf.index]
        capas.append(gdf)
    return gpd.GeoDataFrame(pd.concat(capas, ignore_index=True), crs=capas[0].crs)


def mide(chm_path, faixas):
    """Metricas de todas las faixas que solapan un CHM. Una fila por faixa."""
    filas = []
    with rasterio.open(chm_path) as src:
        recuadro = box(*src.bounds)
        area_px = src.res[0] * src.res[1]
        candidatas = faixas[faixas.intersects(recuadro)]
        for _, f in candidatas.iterrows():
            trozo = f.geometry.intersection(recuadro)
            if trozo.is_empty or trozo.area < area_px:
                continue
            # ventana ajustada al trozo: no hace falta leer el bloque entero
            ven = from_bounds(*trozo.bounds, transform=src.transform)
            ven = ven.round_offsets().round_lengths()
            try:
                ven = ven.intersection(Window(0, 0, src.width, src.height))
            except WindowError:
                # trozo que roza el borde del bloque: al redondear, la ventana
                # queda con 0 filas o columnas y la interseccion es vacia. Son
                # <1 pixel de faixa; el trozo entero lo mide el bloque vecino
                continue
            if ven.width < 1 or ven.height < 1:
                continue
            datos = src.read(1, window=ven, masked=True)
            tr = src.window_transform(ven)
            # all_touched=False: el pixel cuenta si su CENTRO cae dentro
            mascara = rasterize([(trozo, 1)], out_shape=datos.shape, transform=tr,
                                fill=0, all_touched=False, dtype="uint8").astype(bool)
            dentro = mascara & ~np.ma.getmaskarray(datos)
            n = int(dentro.sum())
            if n == 0:
                continue
            h = np.asarray(datos)[dentro]
            base = {
                "faixa_id": f.faixa_id, "capa": f.capa,
                "concello": f.NOMECONCEL, "parroquia": f.PARROQUIA,
                "codparro": f.CODPARRO, "bloque": chm_path.name,
                "px_medidos": n,
                "ha_medida": round(n * area_px / 1e4, 4),
                "ha_poligono_en_bloque": round(trozo.area / 1e4, 4),
                "h_mediana": round(float(np.median(h)), 2),
                "h_p90": round(float(np.percentile(h, 90)), 2),
                "h_max": round(float(h.max()), 2),
            }
            for u in UMBRALES:
                sobre = int((h > u).sum())
                base[f"ha_sobre_{u:g}m"] = round(sobre * area_px / 1e4, 4)
                base[f"pct_sobre_{u:g}m"] = round(100 * sobre / n, 2)
            filas.append(base)
    return filas


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--zona", default="paradanta",
                    help="sufijo de faixas_{capa}_{zona}_ok.gpkg")
    args = ap.parse_args()
    suf = sufijo(args.zona)
    SALIDA.mkdir(parents=True, exist_ok=True)

    cal = calibracion()
    if cal is not None:
        u_cal = float(cal.umbral_youden_m)
        if u_cal not in UMBRALES:
            UMBRALES = tuple(sorted(UMBRALES + (u_cal,)))
        print(f"umbral calibrado en la fase 2: {u_cal:g} m  "
              f"(tasa de falsos positivos {100*float(cal.tasa_fp_producto):.1f} %, "
              f"IC95 {100*float(cal.tasa_fp_ic95_lo):.1f}-"
              f"{100*float(cal.tasa_fp_ic95_hi):.1f} %)\n")
    else:
        u_cal = None
        print("sin calibrar todavia: corre calibra_umbral.py cuando tengas la "
              "muestra anotada. Los umbrales de aqui son provisionales.\n")

    faixas = carga_faixas(args.zona)
    chms = sorted(LIDAR.glob("*_chm.tif"))
    # los CHM de todas las zonas comparten carpeta (A Paradanta esta DENTRO de
    # Pontevedra), asi que se filtra por la malla de la zona: medir un bloque
    # que no toca su faixa no da error, solo tarda.
    malla = PROC / f"malla_lidar_{args.zona}.csv"
    if malla.exists():
        quiero = {b.replace(".LAZ", "_chm.tif")
                  for b in pd.read_csv(malla).bloque}
        chms = [c for c in chms if c.name in quiero]
    if not chms:
        raise SystemExit("no hay CHM en datos/procesado/lidar: corre pipeline_chm.py")
    print(f"{len(chms)} bloques con CHM, {len(faixas)} faixas en {args.zona}")

    filas = []
    for c in chms:
        f = mide(c, faixas)
        ha = sum(x["ha_medida"] for x in f)
        print(f"  {c.name:<46} {len(f):>3} faixas  {ha:>6.1f} ha de faixa")
        filas += f

    det = pd.DataFrame(filas)
    # utf-8-sig y no utf-8: los nombres de parroquia llevan enhes y acentos, y sin BOM
    # el Excel en castellano los destroza al abrir el CSV
    det.to_csv(SALIDA / f"metricas_faixa_bloque{suf}.csv", index=False, encoding="utf-8-sig")

    # control: lo medido en raster tiene que parecerse al area del poligono
    dif = 100 * (det.ha_medida.sum() - det.ha_poligono_en_bloque.sum()) / det.ha_poligono_en_bloque.sum()
    print(f"\ncontrol de rasterizacion: {det.ha_medida.sum():.1f} ha medidas vs "
          f"{det.ha_poligono_en_bloque.sum():.1f} ha de poligono ({dif:+.2f} %)")

    cols_ha = [f"ha_sobre_{u:g}m" for u in UMBRALES]
    # el calibrado si lo hay; si no, el de en medio, que al menos no es un numero
    # elegido a mano para que salga bonito
    u_ref = u_cal if u_cal is not None else UMBRALES[len(UMBRALES) // 2]
    col_ref = f"ha_sobre_{u_ref:g}m"
    agg = (det.groupby(["concello", "parroquia", "codparro"], as_index=False)
           .agg({"ha_medida": "sum", **{c: "sum" for c in cols_ha}}))
    for c in cols_ha:
        agg[c.replace("ha_sobre", "pct_sobre")] = (100 * agg[c] / agg.ha_medida).round(2)
    agg = agg.sort_values(col_ref, ascending=False)
    agg.round(3).to_csv(SALIDA / f"metricas_parroquia{suf}.csv", index=False, encoding="utf-8-sig")

    print(f"\nsuperficie de faixa cubierta por los {len(chms)} bloques: "
          f"{det.ha_medida.sum():.1f} ha "
          f"({100*det.ha_medida.sum()/(faixas.geometry.area.sum()/1e4):.1f} % de la comarca)")

    print("\narbolado sobre umbral, en el conjunto de lo medido:")
    for u in UMBRALES:
        ha = det[f"ha_sobre_{u:g}m"].sum()
        print(f"  > {u:>4g} m: {ha:>7.1f} ha  ({100*ha/det.ha_medida.sum():>5.1f} %)")

    etiqueta = (f"CALIBRADO en fase 2, a 1 m de pixel" if u_cal is not None
                else "PROVISIONAL, sin calibrar")
    print(f"\npor parroquia (umbral {u_ref:g} m, {etiqueta}):")
    print(f"  {'parroquia':<40} {'faixa':>8} {'>'+format(u_ref,'g')+'m':>8} {'%':>6}")
    for _, r in agg.head(12).iterrows():
        print(f"  {r.parroquia[:38]:<40} {r.ha_medida:>7.1f}h {r[col_ref]:>7.1f}h "
              f"{100*r[col_ref]/r.ha_medida:>5.1f}%")

    print(f"\n-> {(SALIDA / f'metricas_faixa_bloque{suf}.csv').relative_to(RAIZ)}")
    print(f"-> {(SALIDA / f'metricas_parroquia{suf}.csv').relative_to(RAIZ)}")
