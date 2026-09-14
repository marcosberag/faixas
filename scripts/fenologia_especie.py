"""Calibra la caida estacional de NDVI como separador perennifolia / caducifolia.

Cierre de la fase 3. El IFN da la especie pero es de 2010 y solo cartografia monte;
esto mide lo que habia en 2024 y llega tambien al arbolado disperso, que es el
38,7 % del que hay en faixa.

EL ENCADENADO, Y DONDE SE PIERDE PRECISION EN CADA PASO
--------------------------------------------------------
    caida de NDVI  ->  perennifolia / caducifolia  ->  prohibida / exenta

El segundo paso ya esta medido contra el IFN y cuesta un 0,6 % (`Quercus suber`,
`Arbutus unedo` y `Laurus nobilis` son perennifolias exentas; no hay ninguna
caducifolia prohibida). El primero es lo que calibra este script.

SE CALIBRA DENTRO DE LA FAIXA, QUE ES DONDE SE APLICA
-------------------------------------------------------
La primera version calibro sobre rodales de monte puros y densos y saco AUC 0,868,
sensibilidad 85 %. Parecia bien. Al contrastarlo contra el IFN **dentro de la
faixa**, que es donde de verdad se usa, el acuerdo se desplomo al 63,9 %: de lo
que el IFN da por perennifolia, el clasificador acertaba el **48,7 %**, peor que
una moneda. Un clasificador calibrado en un dominio y aplicado en otro.

La causa esta medida: es la **mezcla dentro del pixel de 10 m**. Exigiendo que los
100 m2 del pixel sean todo arbolado (segun el CHM, que va a 1 m) la separacion se
recupera entera:

| pureza minima del pixel | n px | AUC |
|---|---|---|
| sin filtro | 29.125 | 0,793 |
| 80 % | 22.660 | 0,853 |
| 100 % | 14.695 | **0,901** |

Tiene sentido fisico: en la faixa un pixel de 10 m rara vez es copa llena — mezcla
arbolado con prado, huerta, camino o tejado, y el prado gallego si verdea en
primavera, asi que la mezcla empuja la caida de NDVI hacia el lado «caducifolia».

De ahi el diseno actual:

  - la muestra de calibracion son pixeles **dentro de la faixa**, arbolados
    (CHM > umbral), en rodal **puro** del IFN (`O1 >= 8`) y con **pureza >= 0,8**;
  - lo que no llega a esa pureza se declara **no clasificable** y se deja al IFN,
    en vez de inventarle una etiqueta;
  - y el umbral se valida **dejando fuera una zona de 5x5 km** cada vez. Con la
    comarca entera no vale dejar fuera bloques de 1 km: un rodal del IFN cruza
    bloques vecinos, y el mismo rodal en entrenamiento y prueba es una fuga que
    infla el resultado. Calibrar y validar contra el mismo IFN en los mismos
    pixeles seria circular.

La referencia sigue siendo de 2010: un rodal cortado y replantado en 2015 entra
etiquetado como lo que era. Ese ruido baja el rendimiento aparente, no lo sube, o
sea que lo que se mide es una **cota inferior**.

Uso:
    python scripts/fenologia_especie.py
"""
import pathlib
import sys

import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio
from rasterio.enums import Resampling
from rasterio.features import rasterize
from rasterio.vrt import WarpedVRT
from shapely.geometry import box

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from especie_faixas import frac_prohibida  # noqa: E402

RAIZ = pathlib.Path(__file__).resolve().parent.parent
PROC = RAIZ / "datos" / "procesado"
LIDAR = PROC / "lidar"
S2 = PROC / "s2"
SALIDA = PROC / "metricas"

# perennifolia = conserva hoja en invierno, que es lo que el indice mide.
# NO es lo mismo que «prohibida»: ver el 0,6 % del docstring
PERENNE = {
    "Pinus_pinaster": 1, "Pinus_sylvestris": 1, "Pinus_radiata": 1,
    "Pseudotsuga_menziesii": 1, "Acacia_dealbata": 1, "Acacia_melanoxylon": 1,
    "Acacia_spp": 1, "Eucalyptus_globulus": 1, "Eucalyptus_nitens": 1,
    "Eucalyptus_camaldulensis": 1, "Quercus_suber": 1, "Arbutus_unedo_": 1,
    "Laurus_nobilis": 1,
    "Quercus_robur": 0, "Quercus_pyrenaica": 0, "Quercus_rubra": 0,
    "Castanea_sativa": 0, "Betula_alba": 0, "Betula_spp": 0,
    "Alnus_glutinosa": 0, "Salix_spp": 0, "Salix_atrocinerea": 0,
    "Fraxinus_angustifolia": 0, "Corylus_avellana": 0, "Acer_pseudoplatanus": 0,
    "Acer_negundo": 0, "Platanus_hispanica": 0, "Sambucus_nigra": 0,
    "Robinia_pseudoacacia": 0,
}
PURO_O1 = 8          # decimas de ocupacion de la especie principal en el rodal
PUREZA = 0.8         # fraccion del pixel de 10 m que ha de ser arbolado
LADO_S2 = 10         # m del pixel de Sentinel-2
UMBRALES = np.round(np.arange(-0.10, 0.51, 0.005), 3)


def auc(y_caduci, score):
    """AUC por el estadistico de Mann-Whitney. y=1 es caducifolia."""
    o = np.argsort(np.asarray(score), kind="stable")
    y = np.asarray(y_caduci)[o].astype(int)
    n1, n0 = int(y.sum()), int(len(y) - y.sum())
    if not n1 or not n0:
        return np.nan
    r = np.arange(1, len(y) + 1)
    return float((r[y == 1].sum() - n1 * (n1 + 1) / 2) / (n1 * n0))


def pureza_arbolado(arb):
    """Fraccion arbolada de cada celda de 10 m, devuelta a la rejilla de 1 m."""
    k = LADO_S2
    h, w = arb.shape[0] // k * k, arb.shape[1] // k * k
    blo = arb[:h, :w].reshape(h // k, k, w // k, k).mean(axis=(1, 3))
    out = np.kron(blo, np.ones((k, k), "float32"))
    return np.pad(out, ((0, arb.shape[0] - h), (0, arb.shape[1] - w)))


def zona_de(nombre):
    """Celda de 5x5 km del bloque. Es la unidad de la validacion cruzada: mas
    grande que cualquier rodal, para que un rodal partido entre bloques vecinos
    no caiga a la vez en entrenamiento y prueba."""
    partes = nombre.split("-")
    return f"{int(partes[3]) // 5 * 5}-{int(partes[4]) // 5 * 5}"


def barrido(caida, es_caduci):
    filas = []
    for u in UMBRALES:
        p = caida > u
        vp, fp = int((p & es_caduci).sum()), int((p & ~es_caduci).sum())
        vn, fn = int((~p & ~es_caduci).sum()), int((~p & es_caduci).sum())
        rec = vp / (vp + fn) if vp + fn else np.nan
        esp = vn / (vn + fp) if vn + fp else np.nan
        filas.append({"umbral": u, "recall": rec, "especificidad": esp,
                      "precision": vp / (vp + fp) if vp + fp else np.nan,
                      "fpr": 1 - esp, "youden": rec + esp - 1})
    return pd.DataFrame(filas)


def por_bloque(chm_path, faixas, u_chm):
    """Todo lo que hace falta de un bloque, ya en la rejilla de 1 m del CHM."""
    with rasterio.open(chm_path) as src:
        sh, tr, rec = (src.height, src.width), src.transform, box(*src.bounds)
        with rasterio.open(S2 / "ndvi_caida.tif") as s2:
            with WarpedVRT(s2, crs=src.crs, transform=tr, width=src.width,
                           height=src.height, resampling=Resampling.nearest) as vrt:
                caida = vrt.read(1)
        chm = src.read(1, masked=True)
        area_px = src.res[0] * src.res[1]

    def pinta(geoms, valores=None):
        g = list(geoms)
        if not g:
            return np.zeros(sh, "float32")
        vals = list(valores) if valores is not None else [1.0] * len(g)
        return rasterize(list(zip(g, vals)), out_shape=sh, transform=tr, fill=0,
                         all_touched=False, dtype="float32")

    fx = faixas[faixas.intersects(rec)]
    arbolado = (~np.ma.getmaskarray(chm)) & (np.asarray(chm) > u_chm)
    return dict(caida=caida, arbolado=arbolado, pureza=pureza_arbolado(arbolado),
                en_faixa=pinta(fx.geometry).astype(bool), area_px=area_px,
                pinta=pinta, rec=rec, fx=fx)


if __name__ == "__main__":
    if not (S2 / "ndvi_caida.tif").exists():
        raise SystemExit("falta datos/procesado/s2/ndvi_caida.tif: corre descarga_s2.py")

    ifn = gpd.read_file(PROC / "ifn_especies_paradanta.gpkg")
    ifn["sp"] = ifn.NOMBRE_SP1.str.strip()
    ifn["f_mal"] = frac_prohibida(ifn)
    faixas = gpd.GeoDataFrame(pd.concat(
        [gpd.read_file(PROC / f"faixas_{n}_paradanta_ok.gpkg").assign(capa=n)
         for n in ("nucleos", "illadas")], ignore_index=True), crs=ifn.crs)
    u_chm = float(pd.read_csv(PROC / "validacion" / "calibracion_resumen.csv",
                              encoding="utf-8-sig").iloc[0].umbral_youden_m)
    bloques = sorted(LIDAR.glob("*_chm.tif"))
    print(f"{len(bloques)} bloques - umbral de arbolado {u_chm:g} m - "
          f"pureza minima del pixel {PUREZA:.0%}\n")

    # ---- muestra de calibracion, DENTRO de la faixa ------------------------
    # sin cache a proposito: con 263 bloques serian varios GB de RAM. La segunda
    # pasada vuelve a leer cada CHM, que son ~2 s por bloque y memoria plana
    muestras = []
    for b in bloques:
        d = por_bloque(b, faixas, u_chm)
        base = d["en_faixa"] & d["arbolado"] & np.isfinite(d["caida"])
        cerca = ifn[ifn.intersects(d["rec"])]
        puro = cerca[(cerca.O1 >= PURO_O1) & cerca.sp.isin(PERENNE)]
        for etiq in (0, 1):
            g = puro[puro.sp.map(PERENNE) == etiq]
            m = base & d["pinta"](g.geometry).astype(bool)
            if m.any():
                muestras.append(pd.DataFrame({
                    "bloque": b.name, "zona": zona_de(b.name), "peren": etiq,
                    "caida": d["caida"][m], "pureza": d["pureza"][m]}))
    ref = pd.concat(muestras, ignore_index=True)
    ref["caduci"] = ref.peren == 0

    print("SEPARACION SEGUN LA PUREZA DEL PIXEL (en faixa, verdad = IFN puro)")
    print(f"  {'pureza min':>11}{'n px':>10}{'ha':>7}{'% caduci':>10}{'AUC':>8}")
    for p in (0.0, 0.5, 0.7, 0.8, 0.9, 1.0):
        g = ref[ref.pureza >= p]
        if len(g) < 500:
            print(f"  {p:>10.0%}{len(g):>10,}   (pocos)")
            continue
        print(f"  {p:>10.0%}{len(g):>10,}{len(g)/1e4:>7.1f}"
              f"{100*g.caduci.mean():>9.1f}%{auc(g.caduci, g.caida):>8.3f}")

    cal = ref[ref.pureza >= PUREZA].reset_index(drop=True)
    if len(cal) < 1000:
        raise SystemExit("muy pocos pixeles puros para calibrar: baja PUREZA")

    # ---- validacion dejando una zona de 5x5 km fuera --------------------------------
    print("\nreparto de la muestra pura por zona de 5x5 km:")
    rep = cal.groupby("zona").caduci.agg(["size", "sum"])
    for b, r in rep.iterrows():
        print(f"  {b:<12}{r['size']:>9,} px  caduci {r['sum']:>7,} "
              f"({100*r['sum']/r['size']:>4.0f} %)")

    print("\nVALIDACION CRUZADA (se calibra sin la zona y se prueba en ella)")
    print(f"  {'zona':<12}{'umbral':>8}{'acierto':>9}{'AUC':>8}{'n px':>10}")
    filas = []
    for b in sorted(cal.zona.unique()):
        tr_, te = cal[cal.zona != b], cal[cal.zona == b]
        # hacen falta las dos clases a ambos lados: sin negativos no hay umbral
        # que calibrar, y sin positivos no hay nada que medir. Hay que decirlo
        # en vez de dejar que idxmax devuelva NaN
        if (len(tr_) < 500 or len(te) < 500
                or tr_.caduci.nunique() < 2 or te.caduci.nunique() < 2):
            falta = "entrenamiento" if tr_.caduci.nunique() < 2 else "prueba"
            print(f"  {b:<12}   (sin evaluar: una sola clase en {falta})")
            continue
        bar = barrido(tr_.caida.to_numpy(), tr_.caduci.to_numpy())
        u = float(bar.loc[bar.youden.idxmax(), "umbral"])
        ac = float(((te.caida > u) == te.caduci).mean())
        filas.append({"zona": b, "umbral": u, "acierto": ac,
                      "auc": auc(te.caduci, te.caida), "n": len(te)})
        print(f"  {b:<12}{u:>8.3f}{ac:>8.1%}{filas[-1]['auc']:>8.3f}{len(te):>10,}")
    vc = pd.DataFrame(filas)
    if len(vc):
        print(f"  {'media ponderada':<12}{'':>8}"
              f"{np.average(vc.acierto, weights=vc.n):>8.1%}"
              f"{np.average(vc.auc.fillna(0.5), weights=vc.n):>8.3f}")

    bar = barrido(cal.caida.to_numpy(), cal.caduci.to_numpy())
    u_j = float(bar.loc[bar.youden.idxmax(), "umbral"])
    f = bar[bar.umbral == u_j].iloc[0]
    print(f"\n=== UMBRAL: caida de NDVI > {u_j:.3f} => CADUCIFOLIA (exenta)")
    print(f"    sobre {len(cal):,} px puros - AUC {auc(cal.caduci, cal.caida):.3f}")
    print(f"    sensibilidad {f.recall:.1%} - especificidad {f.especificidad:.1%} "
          f"- precision {f.precision:.1%}")

    # sin validacion cruzada el AUC es in-sample y no dice cuanto generaliza
    con_ambas = int((rep["sum"].between(1, rep["size"] - 1)).sum())
    if len(vc) == 0 or con_ambas < 2:
        print("\n    *** ESTE NUMERO NO ESTA VALIDADO ***")
        print(f"    Solo {con_ambas} zona(s) tienen las dos clases en faixa, asi que")
        print("    la validacion cruzada no se puede hacer: el AUC de arriba es")
        print("    in-sample y practicamente toda la senal de «caducifolia» sale de")
        print("    un unico sitio. Mide que la senal EXISTE, no cuanto generaliza.")
        print("    No usar el reparto de abajo como resultado. Se valida solo con")
        print("    mas bloques, o sea como subproducto de la fase 4.")
    bar.round(4).to_csv(SALIDA / "fenologia_calibracion.csv", index=False,
                        encoding="utf-8-sig")

    # ---- aplicacion: solo donde se puede -----------------------------------
    filas = []
    for b in bloques:
        d = por_bloque(b, faixas, u_chm)
        cerca = ifn[ifn.intersects(d["rec"])]
        f_mal = d["pinta"](cerca.geometry, cerca.f_mal)
        hay_ifn = d["pinta"](cerca.geometry).astype(bool)
        for _, fx in d["fx"].iterrows():
            trozo = fx.geometry.intersection(d["rec"])
            if trozo.is_empty or trozo.area < d["area_px"]:
                continue
            m = d["pinta"]([trozo]).astype(bool)
            alto = m & d["arbolado"]
            if not alto.any():
                continue
            clasif = alto & (d["pureza"] >= PUREZA) & np.isfinite(d["caida"])
            per = clasif & (d["caida"] <= u_j)
            filas.append({
                "concello": fx.NOMECONCEL, "parroquia": fx.PARROQUIA,
                "ha_faixa": m.sum() * d["area_px"] / 1e4,
                "ha_arbolado": alto.sum() * d["area_px"] / 1e4,
                "ha_clasificable": clasif.sum() * d["area_px"] / 1e4,
                "ha_perenne": per.sum() * d["area_px"] / 1e4,
                "ha_ifn": (alto & hay_ifn).sum() * d["area_px"] / 1e4,
                "ha_ifn_prohibida": float(f_mal[alto].sum()) * d["area_px"] / 1e4,
            })

    det = pd.DataFrame(filas)
    agg = det.groupby(["concello", "parroquia"], as_index=False).sum(numeric_only=True)
    agg["pct_clasificable"] = (100 * agg.ha_clasificable / agg.ha_arbolado).round(1)
    agg["pct_perenne"] = (100 * agg.ha_perenne / agg.ha_clasificable).round(1)
    agg = agg.sort_values("ha_perenne", ascending=False)
    agg.round(3).to_csv(SALIDA / "metricas_parroquia_fenologia.csv", index=False,
                        encoding="utf-8-sig")

    T = det.sum(numeric_only=True)
    print("\nAPLICADO A LA FAIXA")
    print(f"  arbolado > {u_chm:g} m       {T.ha_arbolado:>6.1f} ha")
    print(f"  de eso, clasificable   {T.ha_clasificable:>6.1f} ha "
          f"({100*T.ha_clasificable/T.ha_arbolado:.1f} %) - el resto es pixel mixto")
    print(f"    perennifolia         {T.ha_perenne:>6.1f} ha "
          f"({100*T.ha_perenne/T.ha_clasificable:.1f} % de lo clasificable)")

    if T.ha_ifn > 0:
        a, b_ = (100 * T.ha_ifn_prohibida / T.ha_ifn,
                 100 * T.ha_perenne / T.ha_clasificable)
        print("\n  contraste donde ambas fuentes opinan (deberian parecerse):")
        print(f"    IFN 2010 dice prohibida    {a:>5.1f} %")
        print(f"    S2 2024 dice perennifolia  {b_:>5.1f} %")
        print(f"    diferencia                 {a-b_:>+5.1f} pp")
        print("    Parte puede ser real —corta de eucalipto entre 2010 y 2024— y")
        print("    parte error del clasificador. Con estos bloques NO se pueden")
        print("    separar las dos causas, asi que la diferencia no se interpreta.")

    print(f"\n-> {(SALIDA / 'fenologia_calibracion.csv').relative_to(RAIZ)}")
    print(f"-> {(SALIDA / 'metricas_parroquia_fenologia.csv').relative_to(RAIZ)}")
