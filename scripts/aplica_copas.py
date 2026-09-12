"""Aplica el clasificador de copas al arbolado DISPERSO en faixa, por zonas.

Solo donde esta validado: zonas de 5x5 km con AUC OOS >= 0.80 en
entrena_copas.py --cnn. En esas zonas el disperso deja de ser cota [0,1] y
pasa a fraccion medida con el error OOS propagado; en las zonas malas o sin
rodal puro (sin validacion posible) la cota ancha se queda como estaba.

La correccion de mala clasificacion es la estandar: si o es la fraccion
OBSERVADA de area clasificada prohibida, fpr = P(pred prohibida | exenta) y
fnr = P(pred exenta | prohibida) medidas FUERA DE ZONA en las zonas validadas,
la fraccion real es r = (o - fpr) / (1 - fpr - fnr). Los limites del IC de
fpr/fnr (Jeffreys) se propagan evaluando r en las cuatro esquinas y tomando
min/max. El ruido de etiqueta del IFN infla fpr/fnr -> ensancha el intervalo:
pesimista, el lado correcto.

Encadena sobre metricas_parroquia_especie_verdades.csv (o la base) y escribe
metricas_parroquia_especie_copas.csv, que ranking_final.py preferira.

Uso:
    python scripts/aplica_copas.py
"""
import argparse
import pathlib
import subprocess
import sys

import geopandas as gpd
import joblib
import numpy as np
import pandas as pd
from scipy import stats

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from entrena_copas import rasgos  # noqa: E402
from parches_copas import parches_de_bloque  # noqa: E402

RAIZ = pathlib.Path(__file__).resolve().parent.parent
PROC = RAIZ / "datos" / "procesado"
COPAS = PROC / "copas"
ORTO25 = PROC / "orto25"
MET = PROC / "metricas"

AUC_MIN = 0.80
ZONA_M = 5000


def jeffreys(k, n):
    return (stats.beta.ppf(0.025, k + 0.5, n - k + 0.5),
            stats.beta.ppf(0.975, k + 0.5, n - k + 0.5))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--zona", default="paradanta")
    args = ap.parse_args()
    suf = "" if args.zona == "paradanta" else "_" + args.zona

    # ---- zonas validadas: AUC binario OOS por zona, del propio OOS ----------
    oos = pd.read_csv(COPAS / f"oos_predicciones{suf}.csv", encoding="utf-8-sig")
    oos["y_pro"] = oos.grupo.isin(("eucalipto", "pino")).astype(int)
    oos["p_pro"] = oos.p_eucalipto + oos.p_pino
    from sklearn.metrics import roc_auc_score
    validadas = set()
    for z, g in oos.groupby("zona"):
        if g.y_pro.nunique() == 2 and len(g) >= 50:
            if roc_auc_score(g.y_pro, g.p_pro) >= AUC_MIN:
                validadas.add(z)
    print(f"zonas validadas (AUC OOS >= {AUC_MIN}): {sorted(validadas)}")

    # tasas de error OOS binarias en las zonas validadas (a argmax binario)
    ov = oos[oos.zona.isin(validadas)]
    pred_pro = (ov.p_pro > 0.5).astype(int)
    ex = ov[ov.y_pro == 0]
    pro = ov[ov.y_pro == 1]
    k_fp, n_fp = int((pred_pro[ex.index] == 1).sum()), len(ex)
    k_fn, n_fn = int((pred_pro[pro.index] == 0).sum()), len(pro)
    fpr, fnr = k_fp / n_fp, k_fn / n_fn
    fpr_lo, fpr_hi = jeffreys(k_fp, n_fp)
    fnr_lo, fnr_hi = jeffreys(k_fn, n_fn)
    print(f"error OOS en zonas validadas: fpr {fpr:.3f} [{fpr_lo:.3f}-{fpr_hi:.3f}]"
          f"  fnr {fnr:.3f} [{fnr_lo:.3f}-{fnr_hi:.3f}]")

    # ---- el disperso en faixa ----------------------------------------------
    fx = gpd.GeoDataFrame(pd.concat(
        [gpd.read_file(PROC / f"faixas_{n}_{args.zona}_ok.gpkg")
         for n in ("nucleos", "illadas")], ignore_index=True), crs="EPSG:25829")
    fx_cols = fx[["NOMECONCEL", "PARROQUIA", "geometry"]]

    # Las copas de todas las zonas comparten carpeta (A Paradanta esta DENTRO de
    # Pontevedra): se filtran por la malla de la zona, igual que los CHM. Y el
    # cruce va bloque a bloque en vez de concatenar los 12,9 M de copas de la
    # provincia para quedarse con el ~9 % que cae en faixa. sjoin conserva el
    # orden del lado izquierdo, asi que concatenar despues da el mismo resultado.
    malla = pd.read_csv(PROC / f"malla_lidar_{args.zona}.csv",
                        encoding="utf-8-sig")
    nombres = sorted({pathlib.Path(b).stem for b in malla.bloque})
    trozos, leidas = [], 0
    for nom in nombres:
        ruta = COPAS / f"{nom}.csv"
        if not ruta.exists():
            continue
        try:
            c = pd.read_csv(ruta)
        except pd.errors.EmptyDataError:
            continue
        if not len(c):
            continue
        leidas += len(c)
        gb = gpd.GeoDataFrame(c.assign(bloque=nom),
                              geometry=gpd.points_from_xy(c.x, c.y),
                              crs="EPSG:25829")
        d = gpd.sjoin(gb, fx_cols, how="inner", predicate="within")
        if len(d):
            trozos.append(d[~d.index.duplicated(keep="first")].drop(
                columns="index_right"))
    en_fx = gpd.GeoDataFrame(pd.concat(trozos, ignore_index=True),
                             crs="EPSG:25829")
    print(f"{leidas:,} copas leidas, {len(en_fx):,} dentro de faixa", flush=True)
    ifn = gpd.read_file(PROC / f"ifn_especies_{args.zona}.gpkg")
    con_rodal = gpd.sjoin(en_fx, ifn[["geometry"]], how="left",
                          predicate="within")
    con_rodal = con_rodal[~con_rodal.index.duplicated(keep="first")]
    disp = con_rodal[con_rodal.index_right.isna()].drop(
        columns=["index_right", "geometry"]).reset_index(drop=True)
    disp["zona"] = (disp.x // ZONA_M).astype(int).astype(str) + "_" + \
                   (disp.y // ZONA_M).astype(int).astype(str)
    disp["validada"] = disp.zona.isin(validadas)

    # filtro de edificios del Catastro: un tejado a dos aguas pasa el umbral
    # de 5,5 m del CHM y el watershed lo delinea como "copa". En agregado ya
    # lo paga la tasa de FP; aqui se quita del mapa y de la fraccion del
    # disperso, que es donde ensucia.
    # Puede no estar: el WFS del Catastro limita por IP y una provincia son 3.197
    # celdas. Se declara y se sigue, porque el efecto esta medido en el piloto y
    # es pequeno: 589 copas de 32.035 (1,8 %), la fraccion observada baja de 60,2
    # a 59,9 % y la cota inferior del titular 1 ha de 353. La razon de fondo es
    # que EN AGREGADO los tejados ya los paga la tasa de FP — el anotador ciego
    # tiene categoria «edificacion» y esos puntos cuentan como fallo del CHM.
    # Este filtro limpia el MAPA y la fraccion del disperso, no el agregado.
    #
    # Lo que NO se hace es filtrar con un catastro PARCIAL: cubrir un tercio de
    # la provincia introduciria un sesgo espacial heterogeneo, imposible de
    # declarar con una cifra, y eso es peor que no filtrar. Por eso
    # descarga_catastro.py solo escribe el agregado cuando esta completo.
    ruta_edif = PROC / f"edificios_catastro{suf}.gpkg"
    con_filtro = ruta_edif.exists()
    if con_filtro:
        edif = gpd.read_file(ruta_edif)
        edif = gpd.GeoDataFrame(geometry=edif.buffer(1.0), crs=edif.crs)
        print(f"filtro de edificios: {len(edif):,} huellas del Catastro")
    else:
        print()
        print(f"AVISO: no existe {ruta_edif.name}. Se corre SIN filtro de "
              "edificios del Catastro.")
        print("  Consecuencia declarada: algun tejado a dos aguas pasa el umbral "
              "de 5,5 m y")
        print("  el watershed lo delinea como copa, asi que la fraccion del "
              "disperso sale")
        print("  ligeramente ALTA (en el piloto, +0,3 puntos). Direccion "
              "conocida, y en")
        print("  agregado ya lo descuenta la tasa de FP. Relanzar cuando el "
              "catastro este.")
        print()

    def sin_edificios(df):
        if not con_filtro:
            return np.ones(len(df), dtype=bool)
        g2 = gpd.GeoDataFrame(df.copy(), geometry=gpd.points_from_xy(df.x, df.y),
                              crs="EPSG:25829")
        j = gpd.sjoin(g2, edif, predicate="within", how="left")
        j = j[~j.index.duplicated(keep="first")]
        fuera = j.index_right.isna().to_numpy()
        return fuera

    fuera = sin_edificios(disp)
    print(f"copas del disperso sobre edificio del Catastro, excluidas: "
          f"{int((~fuera).sum()):,}")
    disp = disp[fuera].reset_index(drop=True)
    print(f"disperso en faixa: {len(disp):,} copas; en zona validada: "
          f"{int(disp.validada.sum()):,} ({disp.validada.mean():.0%})")

    # ---- parches + embeddings + prediccion (solo zona validada) -------------
    dv = disp[disp.validada].reset_index(drop=True)
    ruta_p = COPAS / f"parches_disperso{suf}.npy"
    ruta_i = COPAS / f"indice_disperso{suf}.csv"
    ruta_e = COPAS / f"embeddings_disperso{suf}.npy"
    if not ruta_p.exists():
        trozos, indices = [], []
        for b, sub in dv.groupby("bloque"):
            if not (ORTO25 / f"{b}.tif").exists():
                continue
            trozos.append(parches_de_bloque(ORTO25 / f"{b}.tif", sub))
            indices.append(sub)
        parches = np.concatenate(trozos)
        indice = pd.concat(indices, ignore_index=True)
        negros = (parches == 0).all(axis=3).mean(axis=(1, 2))
        vale = negros <= 0.2
        parches, indice = parches[vale], indice[vale].reset_index(drop=True)
        np.save(ruta_p, parches)
        indice.to_csv(ruta_i, index=False, encoding="utf-8-sig")
        print(f"{len(indice):,} parches extraidos")
    if not ruta_e.exists():
        subprocess.run([sys.executable, str(RAIZ / "scripts" / "embeddings_copas.py"),
                        "--parches", str(ruta_p), "--salida", str(ruta_e)],
                       check=True)

    parches = np.load(ruta_p)
    indice = pd.read_csv(ruta_i, encoding="utf-8-sig")
    emb = np.load(ruta_e)
    # la cache de parches puede ser anterior al filtro de edificios
    fuera_i = sin_edificios(indice)
    if (~fuera_i).any():
        print(f"cache: {int((~fuera_i).sum())} parches sobre edificio, excluidos")
        parches, emb = parches[fuera_i], emb[fuera_i]
        indice = indice[fuera_i].reset_index(drop=True)
    X = rasgos(parches, indice)
    X = pd.concat([X, pd.DataFrame(emb, columns=[f"e{i}" for i in range(emb.shape[1])])],
                  axis=1)
    guardado = joblib.load(COPAS / f"modelo_especie_copas{suf}.joblib")
    mod, clases = guardado["modelo"], guardado["clases"]
    assert list(X.columns) == guardado["rasgos"], "rasgos desalineados con el modelo"
    prob = mod.predict_proba(X)
    p_pro = prob[:, clases.index("eucalipto")] + prob[:, clases.index("pino")]
    indice["pred_prohibida"] = (p_pro > 0.5).astype(int)
    for c in clases:
        indice[f"p_{c}"] = np.round(prob[:, clases.index(c)], 4)
    indice.to_csv(COPAS / f"disperso_clasificado{suf}.csv", index=False,
                  encoding="utf-8-sig")

    w = indice.area_m2.to_numpy(float)
    o_global = float(np.average(indice.pred_prohibida, weights=w))
    print(f"fraccion observada prohibida del disperso validado "
          f"(ponderada por area): {o_global:.1%}")

    # ---- correccion y cotas por parroquia -----------------------------------
    def corrige(o):
        esquinas = [(o - a) / (1 - a - b)
                    for a in (fpr_lo, fpr_hi) for b in (fnr_lo, fnr_hi)]
        return (float(np.clip(min(esquinas), 0, 1)),
                float(np.clip(max(esquinas), 0, 1)))

    base = pd.read_csv(MET / f"metricas_parroquia_especie{suf}.csv",
                       encoding="utf-8-sig")
    con_dispersa = base[base.ha_dispersa > 0]
    p_mal_d = float(((con_dispersa.ha_prohibida_hi - con_dispersa.ha_prohibida)
                     / con_dispersa.ha_dispersa).median())
    print(f"p_mal_d recuperado de la base: {p_mal_d:.3f}")

    verdades = MET / f"metricas_parroquia_especie_verdades{suf}.csv"
    e = pd.read_csv(verdades if verdades.exists()
                    else MET / f"metricas_parroquia_especie{suf}.csv",
                    encoding="utf-8-sig")

    # por parroquia: fraccion del area dispersa que esta en zona validada, y
    # su fraccion observada prohibida
    area_total = disp.groupby(["NOMECONCEL", "PARROQUIA"]).area_m2.sum()
    gval = indice.groupby(["NOMECONCEL", "PARROQUIA"])
    area_val = gval.area_m2.sum()
    o_par = gval.apply(lambda s: np.average(s.pred_prohibida, weights=s.area_m2),
                       include_groups=False)

    e = e.set_index(["concello", "parroquia"])
    ajustadas = 0
    for (con, par) in e.index:
        k = (con, par)
        if k not in area_val.index or k not in area_total.index:
            continue
        v_frac = float(area_val[k] / area_total[k])
        d_val = e.loc[k, "ha_dispersa"] * v_frac
        if d_val <= 0:
            continue
        r_lo, r_hi = corrige(float(o_par[k]))
        e.loc[k, "ha_prohibida"] = e.loc[k, "ha_prohibida"] + d_val * r_lo
        e.loc[k, "ha_prohibida_hi"] = (e.loc[k, "ha_prohibida_hi"]
                                       - d_val * p_mal_d + d_val * r_hi)
        ajustadas += 1
    e = e.reset_index()
    for c, n in (("ha_prohibida", "pct_prohibida_lo"),
                 ("ha_prohibida_hi", "pct_prohibida_hi")):
        e[n] = (100 * e[c] / e.ha_faixa).round(2)
    ruta = MET / f"metricas_parroquia_especie_copas{suf}.csv"
    e.round(3).to_csv(ruta, index=False, encoding="utf-8-sig")
    print(f"{ajustadas} parroquias ajustadas")
    print(f"-> {ruta.relative_to(RAIZ)}  (ranking_final.py lo prefiere)")
