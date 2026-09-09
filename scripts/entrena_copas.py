"""Clasificador de especie por copa (eucalipto / pino / frondosa) y su validacion.

Rasgos por parche de 64x64 px a 0,25 m: color (RGB y HSV, momentos y
percentiles), textura (gradiente, laplaciano, contraste local a dos escalas)
y estructura de la copa segun el LiDAR (h_max, h_media, area). Modelo:
HistGradientBoosting. Es la linea base deliberadamente simple; si no llega al
liston, el siguiente paso declarado es un embedding CNN preentrenado.

VALIDACION, la leccion de la fase Sentinel-2: GroupKFold dejando fuera ZONAS
enteras de 5x5 km, nunca copas sueltas (autocorrelacion espacial). Se publica
ademas el AUC por zona (estabilidad): un promedio bonito con zonas en 0,30
no vale nada.

Liston prefijado (antes de mirar resultados): AUC eucalipto-contra-resto
>= 0,85 fuera de zona. Si no llega, resultado negativo y se publica.

Salidas: oos_predicciones.csv (probabilidades fuera de zona por copa),
modelo_especie_copas.joblib (ajustado con todo, para aplicar despues).

Uso:
    python scripts/entrena_copas.py          # rasgos clasicos (plan A)
    python scripts/entrena_copas.py --cnn    # + embedding MobileNet (plan B)
"""
import argparse
import pathlib

import joblib
import numpy as np
import pandas as pd
from matplotlib.colors import rgb_to_hsv
from scipy import ndimage as ndi
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import confusion_matrix, roc_auc_score
from sklearn.model_selection import GroupKFold

RAIZ = pathlib.Path(__file__).resolve().parent.parent
COPAS = RAIZ / "datos" / "procesado" / "copas"

CLASES = ("eucalipto", "frondosa", "pino")
LISTON_AUC_EUCA = 0.85


def rasgos(parches, indice):
    """Matriz de rasgos por parche. Vectorizado salvo el laplaciano."""
    x = parches.astype("float32") / 255.0
    hsv = rgb_to_hsv(x)
    val = hsv[..., 2]

    cols = {}
    for i, c in enumerate("rgb"):
        cols[f"{c}_media"] = x[..., i].mean(axis=(1, 2))
        cols[f"{c}_std"] = x[..., i].std(axis=(1, 2))
    for i, c in enumerate(("tono", "sat", "valor")):
        cols[f"{c}_media"] = hsv[..., i].mean(axis=(1, 2))
        cols[f"{c}_std"] = hsv[..., i].std(axis=(1, 2))
    for p in (5, 50, 95):
        cols[f"valor_p{p}"] = np.percentile(val, p, axis=(1, 2))

    gy, gx = np.gradient(val, axis=(1, 2))
    grad = np.hypot(gx, gy)
    cols["grad_media"] = grad.mean(axis=(1, 2))
    cols["grad_std"] = grad.std(axis=(1, 2))
    cols["grad_p95"] = np.percentile(grad, 95, axis=(1, 2))

    lap = np.empty(len(x), "float32")
    for k in range(len(x)):
        lap[k] = ndi.laplace(val[k]).var()
    cols["lap_var"] = lap

    # contraste a dos escalas: fino (pixel) y de estructura (bloques de 8 px,
    # ~2 m: el tamanho al que las copas individuales moteian la textura)
    b = val.reshape(len(x), 8, 8, 8, 8).mean(axis=(2, 4))
    cols["contraste_2m"] = b.std(axis=(1, 2))
    cols["verdor"] = (x[..., 1] - 0.5 * x[..., 0] - 0.5 * x[..., 2]).mean(axis=(1, 2))

    f = pd.DataFrame(cols)
    for c in ("h_max", "h_media", "area_m2"):
        f[c] = indice[c].to_numpy()
    return f


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--cnn", action="store_true",
                    help="anhade el embedding de embeddings_copas.py")
    ap.add_argument("--gw", action="store_true",
                    help="correccion gray-world por parche (deriva de "
                         "iluminacion entre pasadas del mosaico PNOA)")
    args = ap.parse_args()

    parches = np.load(COPAS / "parches_entrenamiento.npy")
    if args.gw:
        x = parches.astype("float32")
        medias = x.mean(axis=(1, 2), keepdims=True)
        parches = np.clip(x * (110.0 / np.maximum(medias, 1.0)),
                          0, 255).astype("uint8")
        print("gray-world aplicado por parche")
    indice = pd.read_csv(COPAS / "indice_entrenamiento.csv", encoding="utf-8-sig")
    print(f"{len(indice):,} parches; clases:")
    print(indice.grupo.value_counts().to_string(), "\n")

    X = rasgos(parches, indice)
    if args.cnn:
        emb = np.load(COPAS / "embeddings_entrenamiento.npy")
        assert len(emb) == len(indice), "embeddings desalineados: regenerar"
        X = pd.concat([X, pd.DataFrame(
            emb, columns=[f"e{i}" for i in range(emb.shape[1])])], axis=1)
        print(f"con embedding CNN: {X.shape[1]} rasgos")
    y = indice.grupo.to_numpy()
    zonas = indice.zona.to_numpy()

    def modelo_nuevo():
        return HistGradientBoostingClassifier(
            max_iter=400, learning_rate=0.08, max_leaf_nodes=31,
            l2_regularization=1.0, random_state=20260820)

    # ---- validacion fuera de zona ------------------------------------------
    gkf = GroupKFold(n_splits=5)
    prob_oos = np.zeros((len(y), len(CLASES)))
    for tr, te in gkf.split(X, y, groups=zonas):
        mod = modelo_nuevo().fit(X.iloc[tr], y[tr])
        prob_oos[te] = mod.predict_proba(X.iloc[te])[:, [list(mod.classes_).index(c) for c in CLASES]]
    pred = np.array(CLASES)[prob_oos.argmax(axis=1)]

    print("FUERA DE ZONA (GroupKFold 5 por celdas de 5x5 km)")
    print(f"  acierto global: {(pred == y).mean():.1%}\n")
    cm = confusion_matrix(y, pred, labels=list(CLASES))
    print(pd.DataFrame(cm, index=[f"real {c}" for c in CLASES],
                       columns=[f"-> {c}" for c in CLASES]).to_string(), "\n")
    for i, c in enumerate(CLASES):
        auc = roc_auc_score((y == c).astype(int), prob_oos[:, i])
        print(f"  AUC {c}-contra-resto: {auc:.3f}")
    y_pro = np.isin(y, ("eucalipto", "pino")).astype(int)
    p_pro = prob_oos[:, CLASES.index("eucalipto")] + prob_oos[:, CLASES.index("pino")]
    auc_pro = roc_auc_score(y_pro, p_pro)
    print(f"  AUC prohibida-contra-frondosa (la del producto): {auc_pro:.3f}\n")

    # ---- estabilidad por zona (la leccion del S2) --------------------------
    d = indice.assign(p_pro=p_pro, y_pro=y_pro)
    aucs_z = []
    for z, g in d.groupby("zona"):
        if g.y_pro.nunique() == 2 and len(g) >= 50:
            aucs_z.append((z, len(g), roc_auc_score(g.y_pro, g.p_pro)))
    if aucs_z:
        vals = sorted(a for _, _, a in aucs_z)
        print(f"AUC prohibida/frondosa POR ZONA ({len(aucs_z)} zonas con ambas "
              f"clases y n>=50):")
        print(f"  min {vals[0]:.2f} · mediana {vals[len(vals)//2]:.2f} · "
              f"max {vals[-1]:.2f}")
        for z, n, a in sorted(aucs_z, key=lambda t: t[2]):
            print(f"    zona {z:<10} n={n:<6} AUC {a:.2f}")

    auc_euca = roc_auc_score((y == "eucalipto").astype(int),
                             prob_oos[:, CLASES.index("eucalipto")])
    veredicto = "SUPERA" if auc_euca >= LISTON_AUC_EUCA else "NO llega a"
    print(f"\nLISTON prefijado: AUC eucalipto >= {LISTON_AUC_EUCA} -> "
          f"{auc_euca:.3f}, {veredicto} el liston")

    # ---- persistir ----------------------------------------------------------
    oos = indice[["x", "y", "bloque", "grupo", "zona", "OBJECTID_12"]].copy()
    for i, c in enumerate(CLASES):
        oos[f"p_{c}"] = np.round(prob_oos[:, i], 4)
    oos.to_csv(COPAS / "oos_predicciones.csv", index=False, encoding="utf-8-sig")

    final = modelo_nuevo().fit(X, y)
    joblib.dump({"modelo": final, "clases": list(final.classes_),
                 "rasgos": list(X.columns)},
                COPAS / "modelo_especie_copas.joblib")
    print(f"\n-> {(COPAS / 'oos_predicciones.csv').relative_to(RAIZ)}")
    print(f"-> {(COPAS / 'modelo_especie_copas.joblib').relative_to(RAIZ)}")
