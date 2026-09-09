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
    # ---- zonas validadas: AUC binario OOS por zona, del propio OOS ----------
    oos = pd.read_csv(COPAS / "oos_predicciones.csv", encoding="utf-8-sig")
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
    todos = pd.concat([pd.read_csv(p).assign(bloque=p.stem)
                       for p in sorted(COPAS.glob("PNOA-*.csv"))],
                      ignore_index=True)
    g = gpd.GeoDataFrame(todos, geometry=gpd.points_from_xy(todos.x, todos.y),
                         crs="EPSG:25829")
    fx = gpd.GeoDataFrame(pd.concat(
        [gpd.read_file(PROC / f"faixas_{n}_paradanta_ok.gpkg")
         for n in ("nucleos", "illadas")], ignore_index=True), crs="EPSG:25829")
    en_fx = gpd.sjoin(g, fx[["NOMECONCEL", "PARROQUIA", "geometry"]],
                      how="inner", predicate="within")
    en_fx = en_fx[~en_fx.index.duplicated(keep="first")].drop(columns="index_right")
    ifn = gpd.read_file(PROC / "ifn_especies_paradanta.gpkg")
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
    edif = gpd.read_file(PROC / "edificios_catastro.gpkg")
    edif = gpd.GeoDataFrame(geometry=edif.buffer(1.0), crs=edif.crs)

    def sin_edificios(df):
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
    ruta_p = COPAS / "parches_disperso.npy"
    ruta_i = COPAS / "indice_disperso.csv"
    ruta_e = COPAS / "embeddings_disperso.npy"
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
    guardado = joblib.load(COPAS / "modelo_especie_copas.joblib")
    mod, clases = guardado["modelo"], guardado["clases"]
    assert list(X.columns) == guardado["rasgos"], "rasgos desalineados con el modelo"
    prob = mod.predict_proba(X)
    p_pro = prob[:, clases.index("eucalipto")] + prob[:, clases.index("pino")]
    indice["pred_prohibida"] = (p_pro > 0.5).astype(int)
    for c in clases:
        indice[f"p_{c}"] = np.round(prob[:, clases.index(c)], 4)
    indice.to_csv(COPAS / "disperso_clasificado.csv", index=False,
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

    base = pd.read_csv(MET / "metricas_parroquia_especie.csv", encoding="utf-8-sig")
    con_dispersa = base[base.ha_dispersa > 0]
    p_mal_d = float(((con_dispersa.ha_prohibida_hi - con_dispersa.ha_prohibida)
                     / con_dispersa.ha_dispersa).median())
    print(f"p_mal_d recuperado de la base: {p_mal_d:.3f}")

    verdades = MET / "metricas_parroquia_especie_verdades.csv"
    e = pd.read_csv(verdades if verdades.exists()
                    else MET / "metricas_parroquia_especie.csv",
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
    ruta = MET / "metricas_parroquia_especie_copas.csv"
    e.round(3).to_csv(ruta, index=False, encoding="utf-8-sig")
    print(f"{ajustadas} parroquias ajustadas")
    print(f"-> {ruta.relative_to(RAIZ)}  (ranking_final.py lo prefiere)")
