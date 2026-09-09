"""Aplica al ranking los reemplazos de dosel CONFIRMADOS por la anotacion.

El detector de eventos no supero la validacion (39 % de precision) y no entra
en el ranking. Pero la anotacion contra ortofoto historica dejo 22 rodales con
reemplazo CONFIRMADO por el ojo — eso es verdad validada rodal a rodal, y esos
si pueden corregir la etiqueta del IFN 2010:

  - etiqueta Eucalyptus + reemplazo -> sigue prohibida (rebrota de cepa): la
    fraccion del rodal no cambia y no hay ajuste.
  - otra etiqueta + reemplazo -> DESCONOCIDA desde el evento. En la maquinaria
    de cotas: su arbolado detectado sale de la cota inferior (ya no se puede
    afirmar que sea prohibido) y sube la superior a 1 (la replantacion gallega
    tiende a eucalipto). Es la misma asimetria declarada en detecta_eventos.py.
    (La acacia tambien rebrota, pero se sigue la regla declarada — solo
    eucalipto — y el error va en la direccion segura: baja la cota inferior.)

El ajuste se calcula con el CHM real: hectareas sobre el umbral calibrado
dentro de (rodal con reemplazo confirmado) x (faixa), por parroquia. Escribe
metricas_parroquia_especie_verdades.csv, que ranking_final.py prefiere si
existe (mismo patron que resumen_producto.csv).

Uso:
    python scripts/verdades_en_ranking.py   (y despues ranking_final.py)
"""
import pathlib
import sys

import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio
from rasterio.features import rasterize
from rasterio.windows import Window, from_bounds
from shapely.geometry import box

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from especie_faixas import frac_prohibida  # noqa: E402

RAIZ = pathlib.Path(__file__).resolve().parent.parent
PROC = RAIZ / "datos" / "procesado"
LIDAR = PROC / "lidar"
MET = PROC / "metricas"
VALP = PROC / "validacion_persistencia"


def ha_alto_en(geo, umbral):
    """Hectareas de CHM sobre el umbral dentro de una geometria."""
    total = 0.0
    for chm_path in sorted(LIDAR.glob("*_chm.tif")):
        with rasterio.open(chm_path) as src:
            rec = box(*src.bounds)
            if not geo.intersects(rec):
                continue
            trozo = geo.intersection(rec)
            area_px = src.res[0] * src.res[1]
            if trozo.is_empty or trozo.area < area_px:
                continue
            ven = from_bounds(*trozo.bounds, transform=src.transform)
            ven = ven.round_offsets().round_lengths()
            ven = ven.intersection(Window(0, 0, src.width, src.height))
            if ven.width < 1 or ven.height < 1:
                continue
            dat = src.read(1, window=ven, masked=True)
            tr = src.window_transform(ven)
            msk = rasterize([(trozo, 1)], out_shape=dat.shape, transform=tr,
                            fill=0, all_touched=False, dtype="uint8").astype(bool)
            alto = msk & ~np.ma.getmaskarray(dat) & (np.asarray(dat) > umbral)
            total += alto.sum() * area_px / 1e4
    return total


if __name__ == "__main__":
    m = pd.read_csv(VALP / "muestra.csv", encoding="utf-8-sig")
    a = pd.read_csv(VALP / "anotacion.csv")
    d = m.merge(a, on="id", validate="one_to_one")
    si = d[d.respuesta == "si"]
    print(f"reemplazos confirmados por el ojo: {len(si)} de {len(d)} rodales")

    ifn = gpd.read_file(PROC / "ifn_especies_paradanta.gpkg")
    ifn["f_mal"] = frac_prohibida(ifn)
    ifn = ifn.set_index("OBJECTID_12")

    euca = si[si.sp.str.startswith("Eucalyptus")]
    corr = si[~si.sp.str.startswith("Eucalyptus")].copy()
    print(f"  eucalipto (rebrote, sigue prohibida, sin ajuste): {len(euca)}")
    print(f"  otra especie -> DESCONOCIDA: {len(corr)}"
          f" (en faixa: {int((corr.ha_faixa > 0.01).sum())})")
    corr = corr[corr.ha_faixa > 0.01]

    cal = pd.read_csv(PROC / "validacion" / "calibracion_resumen.csv",
                      encoding="utf-8-sig").iloc[0]
    u = float(cal.umbral_youden_m)

    faixas = gpd.GeoDataFrame(pd.concat(
        [gpd.read_file(PROC / f"faixas_{n}_paradanta_ok.gpkg")
         for n in ("nucleos", "illadas")], ignore_index=True), crs=ifn.crs)

    # ajuste por (concello, parroquia): el arbolado del rodal desconocido sale
    # de la cota inferior (delta_lo) y sube a 1 en la superior (delta_hi)
    ajustes = {}
    print(f"\narbolado (CHM > {u:g} m) dentro de rodal-desconocido x faixa:")
    for f in corr.itertuples():
        geo = ifn.geometry.loc[f.OBJECTID_12]
        fmal = float(ifn.f_mal.loc[f.OBJECTID_12])
        for _, fx in faixas[faixas.intersects(geo)].iterrows():
            inter = geo.intersection(fx.geometry)
            if inter.is_empty:
                continue
            ha = ha_alto_en(inter, u)
            if ha <= 0:
                continue
            k = (fx.NOMECONCEL, fx.PARROQUIA)
            dl, dh = ajustes.get(k, (0.0, 0.0))
            ajustes[k] = (dl + fmal * ha, dh + (1 - fmal) * ha)
            print(f"  {f.id}  rodal {f.OBJECTID_12}  {f.sp:<16} f_mal {fmal:.2f}"
                  f"  {ha:5.2f} ha  -> {fx.PARROQUIA[:34]}")

    e = pd.read_csv(MET / "metricas_parroquia_especie.csv", encoding="utf-8-sig")
    e = e.set_index(["concello", "parroquia"])
    print("\najuste por parroquia (ha que salen de la cota inferior / suben en la superior):")
    for (con, par), (dl, dh) in sorted(ajustes.items()):
        e.loc[(con, par), "ha_prohibida"] = max(
            0.0, e.loc[(con, par), "ha_prohibida"] - dl)
        e.loc[(con, par), "ha_prohibida_hi"] = (
            e.loc[(con, par), "ha_prohibida_hi"] + dh)
        print(f"  {par[:40]:<42} -{dl:5.2f} ha / +{dh:5.2f} ha")

    e = e.reset_index()
    for c, n in (("ha_prohibida", "pct_prohibida_lo"),
                 ("ha_prohibida_hi", "pct_prohibida_hi")):
        e[n] = (100 * e[c] / e.ha_faixa).round(2)
    ruta = MET / "metricas_parroquia_especie_verdades.csv"
    e.round(3).to_csv(ruta, index=False, encoding="utf-8-sig")

    post_lidar = si[(si.estado == "evento") & (si.anho_evento > 2024)]
    if len(post_lidar):
        pl = post_lidar[post_lidar.ha_faixa > 0.01]
        print(f"\nvigencia confirmada (evento posterior al vuelo LiDAR): "
              f"{len(post_lidar)} rodal(es), de ellos {len(pl)} en faixa"
              + ("" if len(pl) else " — sin efecto en el ranking"))

    print(f"\n-> {ruta.relative_to(RAIZ)}  (ranking_final.py lo usa si existe)")
