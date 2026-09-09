"""Calibra el umbral de altura contra la muestra anotada y da la tasa de FP.

Criterio de salida de la fase 2. Entra `anotacion.csv` (lo exporta el anotador) y
salen tres cosas: el umbral elegido, la tasa de falsos positivos con intervalo de
confianza, y una primera cota del sesgo de especie.

LAS DOS TASAS DE FALSOS POSITIVOS, QUE NO SON LA MISMA
-------------------------------------------------------
Se confunden constantemente y aqui importa cual se publica.

  FPR = FP / (FP + VN)      de todo lo que NO es arbol, que fraccion marcamos.
                            Es la del eje X de la curva ROC. Sirve para comparar
                            umbrales entre si.

  1 - precision = FP / (FP + VP)    de la superficie que declaramos arbolada,
                            que fraccion no lo es. Es la que le importa a quien
                            reciba el ranking, porque es la probabilidad de que
                            una inspeccion salga en balde.

La segunda es la que se publica, y se dice cual es. La primera va en el informe
tecnico. Publicar solo la primera, que casi siempre es mas bonita, seria
enganoso.

POR QUE TODO VA PONDERADO
--------------------------
La muestra es estratificada por altura y las cuotas no son proporcionales al
area (ver `muestra_validacion.py`). Contar puntos daria tasas del muestreo, no
del terreno. Todo se calcula sumando `peso_m2`, que convierte cada punto en los
metros cuadrados de faixa que representa. Asi las cifras son de superficie, que
ademas es la unidad del entregable.

INTERVALOS POR BOOTSTRAP ESTRATIFICADO
---------------------------------------
Con pesos desiguales el intervalo binomial de toda la vida no vale. Se remuestrea
con reemplazo dentro de cada estrato, respetando su tamano, y se recalcula todo
2000 veces. El percentil 2,5 y el 97,5 son el intervalo.

LO QUE ESTE SCRIPT NO PUEDE DECIR
----------------------------------
Si la faixa cumple la ley. Mide si hay arbol, no si ese arbol esta prohibido: la
disposicion adicional tercera solo lista 7 especies y exime a las frondosas no
listadas. La pregunta de tipo de copa del anotador da una primera cota de ese
sesgo, pero es fotointerpretacion a ojo, no clasificacion de especie. Ver
docs/03-marco-legal.md y la fase 3.

Uso:
    python scripts/calibra_umbral.py
    python scripts/calibra_umbral.py --anotacion otra.csv --replicas 5000
"""
import argparse
import pathlib

import matplotlib
import numpy as np
import pandas as pd

matplotlib.use("Agg")
from matplotlib import pyplot as plt

RAIZ = pathlib.Path(__file__).resolve().parent.parent
VAL = RAIZ / "datos" / "procesado" / "validacion"
SALIDAS = RAIZ / "salidas"

UMBRALES = np.round(np.arange(0.25, 20.01, 0.25), 2)
REPLICAS = 2000
SEMILLA = 20260817


def auc_roc(fpr, recall):
    """Area bajo la ROC, con la curva anclada en las dos esquinas.

    El barrido de umbrales no llega ni a marcarlo todo ni a no marcar nada, asi
    que la curva empieza y acaba a media altura. Integrarla tal cual da un numero
    sin sentido (la primera version daba 0,40 para una curva casi perfecta). Un
    umbral infinito no marca nada -> (0,0), y uno de -infinito lo marca todo ->
    (1,1); son puntos de la ROC igual que los demas y hay que incluirlos.
    """
    x = np.concatenate([[0.0], np.asarray(fpr, float), [1.0]])
    y = np.concatenate([[0.0], np.asarray(recall, float), [1.0]])
    o = np.argsort(x, kind="stable")
    return float(np.trapezoid(y[o], x[o]))


def confusion(chm, verdad, peso, u):
    """Matriz de confusion ponderada en m2 para un umbral."""
    pred = chm > u
    return (peso[pred & verdad].sum(), peso[pred & ~verdad].sum(),
            peso[~pred & ~verdad].sum(), peso[~pred & verdad].sum())  # VP FP VN FN


def metricas(vp, fp, vn, fn):
    seg = lambda a, b: a / b if b > 0 else np.nan
    prec = seg(vp, vp + fp)
    rec = seg(vp, vp + fn)          # sensibilidad
    esp = seg(vn, vn + fp)
    return {
        "precision": prec,
        "recall": rec,
        "especificidad": esp,
        "fpr": seg(fp, fp + vn),
        "tasa_fp_producto": np.nan if np.isnan(prec) else 1 - prec,
        "f1": seg(2 * prec * rec, prec + rec) if not (np.isnan(prec) or np.isnan(rec)) else np.nan,
        "youden": rec + esp - 1,
        "exactitud": seg(vp + vn, vp + fp + vn + fn),
    }


def barrido(chm, verdad, peso, umbrales=UMBRALES):
    filas = []
    for u in umbrales:
        vp, fp, vn, fn = confusion(chm, verdad, peso, u)
        filas.append({"umbral_m": u, "vp_ha": vp / 1e4, "fp_ha": fp / 1e4,
                      "vn_ha": vn / 1e4, "fn_ha": fn / 1e4,
                      **metricas(vp, fp, vn, fn)})
    return pd.DataFrame(filas)


def bootstrap(d, umbrales, n=REPLICAS, semilla=SEMILLA):
    """Remuestreo con reemplazo DENTRO de cada estrato. Devuelve (replicas, umbrales)
    para precision, recall y youden."""
    rng = np.random.default_rng(semilla)
    grupos = [g.index.to_numpy() for _, g in d.groupby("estrato", sort=True)]
    chm, verdad, peso = d.chm_m.to_numpy(), d.es_arbol.to_numpy(), d.peso_m2.to_numpy()
    pos = {ix: k for k, ix in enumerate(d.index)}
    grupos = [np.array([pos[i] for i in g]) for g in grupos]

    salida = {k: np.empty((n, len(umbrales))) for k in ("precision", "recall", "youden")}
    for r in range(n):
        sel = np.concatenate([rng.choice(g, size=len(g), replace=True) for g in grupos])
        c, v, p = chm[sel], verdad[sel], peso[sel]
        for j, u in enumerate(umbrales):
            m = metricas(*confusion(c, v, p, u))
            for k in salida:
                salida[k][r, j] = m[k]
    return salida


def ic(muestras, q=(2.5, 97.5)):
    with np.errstate(invalid="ignore"):
        return np.nanpercentile(muestras, q, axis=0)


def pinta(b, u_j, u_f, ic_prec, ic_rec, ruta):
    fig, ax = plt.subplots(1, 2, figsize=(13.5, 5.4))

    # se dibuja con las esquinas puestas, que es la curva de verdad: los tramos
    # punteados son la extrapolacion a umbral infinito y a umbral cero
    ax[0].plot([0, b.fpr.iloc[-1]], [0, b.recall.iloc[-1]], ":", color="#2b6cb0", lw=1.2)
    ax[0].plot([b.fpr.iloc[0], 1], [b.recall.iloc[0], 1], ":", color="#2b6cb0", lw=1.2)
    ax[0].plot(b.fpr, b.recall, "-", color="#2b6cb0", lw=1.8)
    ax[0].plot([0, 1], [0, 1], ":", color="#bbb", lw=1)
    marcas = [(u_j, "#c53030", (9, -14))] + ([] if u_f == u_j else [(u_f, "#2f855a", (9, 6))])
    for u, col, desp in marcas:
        f = b[b.umbral_m == u].iloc[0]
        ax[0].plot(f.fpr, f.recall, "o", color=col, ms=8)
        ax[0].annotate(f"{u:g} m", (f.fpr, f.recall), xytext=desp,
                       textcoords="offset points", color=col, fontsize=10)
    auc = auc_roc(b.fpr, b.recall)
    ax[0].set(xlabel="FPR — de lo que no es arbol, que marcamos",
              ylabel="sensibilidad — del arbolado real, que pillamos",
              title=f"ROC del CHM como detector de arbolado (AUC {auc:.3f})",
              xlim=(0, 1), ylim=(0, 1.02))
    ax[0].grid(alpha=.25)

    ax[1].fill_between(b.umbral_m, ic_prec[0], ic_prec[1], color="#2f855a", alpha=.18)
    ax[1].fill_between(b.umbral_m, ic_rec[0], ic_rec[1], color="#2b6cb0", alpha=.18)
    ax[1].plot(b.umbral_m, b.precision, color="#2f855a", lw=1.8, label="precisión")
    ax[1].plot(b.umbral_m, b.recall, color="#2b6cb0", lw=1.8, label="sensibilidad")
    ax[1].plot(b.umbral_m, b.f1, color="#805ad5", lw=1.4, ls="--", label="F1")
    ax[1].axvline(u_j, color="#c53030", lw=1.2)
    ax[1].annotate(f"Youden {u_j:g} m", (u_j, .04), color="#c53030", fontsize=10,
                   rotation=90, va="bottom", xytext=(4, 0), textcoords="offset points")
    ax[1].set(xlabel="umbral de altura (m)", ylabel="", ylim=(0, 1.02),
              xlim=(UMBRALES[0], min(20, UMBRALES[-1])),
              title="Precisión y sensibilidad según el umbral\n(banda: IC 95 % bootstrap)")
    ax[1].legend(loc="lower center", ncol=3, frameon=False)
    ax[1].grid(alpha=.25)

    fig.text(.5, .012, "Verdad de referencia: fotointerpretación sobre ortofoto PNOA "
             "(IGN, vuelo sept. 2023) — LiDAR PNOA 2024. CHM a 1 m de píxel.",
             ha="center", fontsize=8, color="#666")
    fig.tight_layout(rect=[0, .035, 1, 1])
    SALIDAS.mkdir(exist_ok=True)
    fig.savefig(ruta, dpi=125)
    plt.close(fig)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--anotacion", default=str(VAL / "anotacion.csv"))
    ap.add_argument("--replicas", type=int, default=REPLICAS)
    ap.add_argument("--etiqueta", default="", help="sufijo para los ficheros de salida")
    args = ap.parse_args()

    ruta_a = pathlib.Path(args.anotacion)
    if not ruta_a.exists():
        raise SystemExit(
            f"no encuentro {ruta_a}\n"
            "Anota la muestra con datos/procesado/validacion/anotador.html y "
            "guarda ahi el CSV que descarga.")

    m = pd.read_csv(VAL / "muestra.csv", encoding="utf-8-sig")
    a = pd.read_csv(ruta_a)
    d = m.merge(a, on="id", how="inner", validate="one_to_one")
    print(f"muestra {len(m)} puntos · anotados {len(a)} · cruzados {len(d)}")
    if len(d) < len(a):
        print(f"  aviso: {len(a)-len(d)} anotaciones sin punto en la muestra")

    # --- dudosos: se declaran y se excluyen -------------------------------
    dud = d[d.clase == "dudoso"]
    pct_dud = 100 * dud.peso_m2.sum() / d.peso_m2.sum() if len(d) else 0
    d = d[d.clase != "dudoso"].reset_index(drop=True)
    print(f"dudosos excluidos: {len(dud)} puntos, {pct_dud:.1f} % de la superficie\n")
    if len(d) < 30:
        raise SystemExit("quedan menos de 30 puntos utiles: no da para calibrar")

    # edificacion cuenta como negativo: el CHM ve el tejado y acierta la altura,
    # pero no es arbolado y el entregable habla de arbolado
    d["es_arbol"] = d.clase.values == "arbol"

    # --- composicion real de la faixa, que no depende del CHM -------------
    # con muestreo estratificado ponderado esto es un estimador insesgado de la
    # superficie de cada clase. Es una medicion independiente, util por si sola
    print("composicion de la faixa segun la fotointerpretacion (ha, ponderado):")
    comp = (d.groupby("clase").peso_m2.sum() / 1e4).sort_values(ascending=False)
    for k, v in comp.items():
        print(f"  {k:<14} {v:>7.1f} ha  ({100*v/comp.sum():>5.1f} %)")

    # --- barrido de umbrales ----------------------------------------------
    chm, verdad, peso = d.chm_m.to_numpy(), d.es_arbol.to_numpy(), d.peso_m2.to_numpy()
    b = barrido(chm, verdad, peso)

    u_j = float(b.loc[b.youden.idxmax(), "umbral_m"])
    u_f = float(b.loc[b.f1.idxmax(), "umbral_m"])

    print(f"\nbootstrap estratificado, {args.replicas} replicas", flush=True)
    boot = bootstrap(d, UMBRALES, n=args.replicas)
    ic_prec, ic_rec = ic(boot["precision"]), ic(boot["recall"])
    j = int(np.where(UMBRALES == u_j)[0][0])

    f = b.iloc[j]
    print(f"\n=== UMBRAL CALIBRADO: {u_j:g} m  (maximo indice de Youden)")
    print(f"    F1 maximo en {u_f:g} m — si difieren, el criterio manda y se explica")
    print(f"    sensibilidad   {f.recall:5.1%}  IC95 [{ic_rec[0][j]:.1%}, {ic_rec[1][j]:.1%}]")
    print(f"    precision      {f.precision:5.1%}  IC95 [{ic_prec[0][j]:.1%}, {ic_prec[1][j]:.1%}]")
    print(f"    TASA DE FALSOS POSITIVOS (del producto, 1-precision):")
    print(f"                   {1-f.precision:5.1%}  IC95 "
          f"[{1-ic_prec[1][j]:.1%}, {1-ic_prec[0][j]:.1%}]")
    print(f"    FPR (de la ROC){f.fpr:5.1%}      exactitud {f.exactitud:.1%}")
    print(f"    superficie: VP {f.vp_ha:.1f} ha · FP {f.fp_ha:.1f} ha · "
          f"FN {f.fn_ha:.1f} ha · VN {f.vn_ha:.1f} ha")

    # --- de que estan hechos los falsos positivos --------------------------
    fp = d[(d.chm_m > u_j) & ~d.es_arbol]
    if len(fp):
        print(f"\nfalsos positivos a {u_j:g} m, por lo que hay de verdad:")
        for k, v in (fp.groupby("clase").peso_m2.sum() / 1e4).sort_values(
                ascending=False).items():
            print(f"  {k:<14} {v:>6.1f} ha  ({100*v/(fp.peso_m2.sum()/1e4):>5.1f} % de los FP)")

    # --- puntos de operacion ------------------------------------------------
    print("\npuntos de operacion (para decidir con criterio, no solo por Youden):")
    print(f"  {'umbral':>7} {'sensib.':>9} {'precis.':>9} {'tasa FP':>9} {'ha marcadas':>12}")
    for u in (1.0, 1.5, 2.0, 3.0, 4.0, 5.0, 7.0, 10.0):
        if u not in set(b.umbral_m):
            continue
        r = b[b.umbral_m == u].iloc[0]
        print(f"  {u:>5g} m {r.recall:>8.1%} {r.precision:>9.1%} "
              f"{1-r.precision:>8.1%} {r.vp_ha+r.fp_ha:>10.1f} ha")

    # --- sesgo de especie ---------------------------------------------------
    # el agrupamiento es por ESTATUS LEGAL, no por botanica: la acacia es una
    # frondosa y esta en la lista prohibida (disp. ad. 3a.1), mientras que las
    # frondosas NO listadas estan exentas por el punto 3 del mismo articulo
    DE_LA_LISTA = ("pino", "eucalipto", "acacia")
    EXENTAS = ("frondosa",)

    n_arb = int(d.es_arbol.sum())
    arb = d[d.es_arbol & d.tipo.notna() & (d.tipo != "")]
    sin = n_arb - len(arb)
    if sin:
        print(f"\naviso: {sin} de {n_arb} arboles se quedaron SIN tipo de copa "
              f"({100*sin/max(n_arb,1):.0f} %).")
        print("  Cuidado con leer los porcentajes de abajo como si describieran el")
        print("  arbolado: describen solo el trozo que se pudo contestar.")
    if len(arb):
        print("\ntipo de copa sobre el arbolado real (ponderado). PRIMERA COTA DEL")
        print("SESGO DE ESPECIE: las frondosas no listadas estan EXENTAS por la")
        print("disp. ad. 3a.3, asi que no deberian contar como incumplimiento.")
        tot = arb.peso_m2.sum()
        for k, v in (arb.groupby("tipo").peso_m2.sum() / 1e4).sort_values(
                ascending=False).items():
            marca = ("prohibida" if k in DE_LA_LISTA else
                     "EXENTA" if k in EXENTAS else "")
            print(f"  {k:<12} {v:>6.1f} ha  ({100*v*1e4/tot:>5.1f} %)  {marca}")

        ex = arb[arb.tipo.isin(EXENTAS)].peso_m2.sum() / tot
        nd = arb[~arb.tipo.isin(DE_LA_LISTA + EXENTAS)].peso_m2.sum() / tot
        print(f"\n  -> un {100*ex:.0f} % del arbolado detectado esta EXENTO, y otro "
              f"{100*nd:.0f} % no se pudo tipificar.")
        print(f"     Sin la fase 3, el indicador sobrestima el incumplimiento entre "
              f"un {100*ex:.0f} % y un {100*(ex+nd):.0f} %.")

        # tres formas de que esta cota no valga nada, y las tres han pasado ya
        n_lista = int(arb.tipo.isin(DE_LA_LISTA).sum())
        if len(arb) < 40:
            print(f"\n     NO PUBLICABLE: la cota sale de {len(arb)} puntos. Con esa n")
            print("     no es una medicion, es una anecdota. Darla como pendiente.")
        if n_lista == 0:
            print("\n     NO PUBLICABLE: ni un solo punto marcado como especie de la")
            print("     lista. En Galicia eso no describe el monte, describe que la")
            print("     pregunta no se pudo contestar. Hace falta otra fuente.")
        elif nd > 0.25:
            print("     Aviso: mas de un cuarto sin tipificar. La cota es floja y hay")
            print("     que darla como rango, no como cifra.")

    # --- control de fatiga ---------------------------------------------------
    if "ms" in d and d.ms.notna().any():
        seg = d.ms.dropna() / 1000
        rapidas = 100 * (seg < 1).mean()
        print(f"\nritmo: mediana {seg.median():.1f} s/chip · "
              f"{rapidas:.0f} % por debajo de 1 s")
        if rapidas > 20:
            print("  aviso: muchas respuestas de menos de un segundo. Revisa si hubo prisa.")

    # --- salidas -------------------------------------------------------------
    suf = f"_{args.etiqueta}" if args.etiqueta else ""
    b["ic_precision_lo"], b["ic_precision_hi"] = ic_prec
    b["ic_recall_lo"], b["ic_recall_hi"] = ic_rec
    csv = VAL / f"calibracion{suf}.csv"
    b.round(5).to_csv(csv, index=False, encoding="utf-8-sig")

    png = SALIDAS / f"calibracion_umbral{suf}.png"
    pinta(b, u_j, u_f, ic_prec, ic_rec, png)

    resumen = {
        "umbral_youden_m": u_j, "umbral_f1_m": u_f,
        "resolucion_px_m": 1.0,          # el umbral NO es transferible a otra
        "n_anotados": int(len(a)), "n_utiles": int(len(d)),
        "pct_dudosos_superficie": round(pct_dud, 2),
        "sensibilidad": round(float(f.recall), 4),
        "precision": round(float(f.precision), 4),
        "tasa_fp_producto": round(float(1 - f.precision), 4),
        "tasa_fp_ic95_lo": round(float(1 - ic_prec[1][j]), 4),
        "tasa_fp_ic95_hi": round(float(1 - ic_prec[0][j]), 4),
        "fpr": round(float(f.fpr), 4), "auc": round(auc_roc(b.fpr, b.recall), 4),
        "ortofoto": "PNOA sept-2023", "lidar": "PNOA 2024",
    }
    pd.DataFrame([resumen]).to_csv(VAL / f"calibracion_resumen{suf}.csv",
                                   index=False, encoding="utf-8-sig")

    print(f"\n-> {csv.relative_to(RAIZ)}")
    print(f"-> {(VAL / f'calibracion_resumen{suf}.csv').relative_to(RAIZ)}")
    print(f"-> {png.relative_to(RAIZ)}")
