"""Valida el producto final fuera de muestra: ¿aguanta la tasa de FP del 24,2 %?

La fase 2 calibro umbral y tasa de falsos positivos sobre 3 bloques. El producto
los aplica a 263. Este script cierra el circulo con la anotacion ciega de la
muestra del producto (250 puntos de los 260 bloques NO usados en fase 2):

  - tasa de FP del producto fuera de muestra, con IC bootstrap estratificado,
    puesta al lado de la publicada (24,2 %, IC95 [17,0-31,2]);
  - sensibilidad fuera de muestra;
  - el estrato >= 35 m aparte: alli la pregunta era si el suelo estructural del
    eucalipto son arboles de verdad o artefactos del CHM;
  - y la composicion de la faixa por fotointerpretacion, que es una medicion
    independiente del CHM (en fase 2 dio 27,7 % de arbolado).

El umbral NO se recalibra aqui: esta fijado. Solo se comprueba.

Uso:
    python scripts/valida_producto.py
"""
import pathlib
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from calibra_umbral import confusion, metricas  # noqa: E402

RAIZ = pathlib.Path(__file__).resolve().parent.parent
PROC = RAIZ / "datos" / "procesado"
VAL = PROC / "validacion_producto"
REPLICAS = 4000
SEMILLA = 20260819

if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", default="validacion_producto",
                    help="subcarpeta de datos/procesado con muestra.csv y anotacion.csv")
    VAL = PROC / ap.parse_args().dir

    ruta_a = VAL / "anotacion.csv"
    if not ruta_a.exists():
        raise SystemExit(
            f"no encuentro {ruta_a}\n"
            "Anota con datos/procesado/validacion_producto/anotador.html y "
            "guarda ahi el CSV que descarga, como anotacion.csv")

    cal = pd.read_csv(PROC / "validacion" / "calibracion_resumen.csv",
                      encoding="utf-8-sig").iloc[0]
    u = float(cal.umbral_youden_m)

    m = pd.read_csv(VAL / "muestra.csv", encoding="utf-8-sig")
    a = pd.read_csv(ruta_a)
    d = m.merge(a, on="id", how="inner", validate="one_to_one")
    print(f"muestra {len(m)} · anotados {len(a)} · cruzados {len(d)} · umbral {u:g} m\n")

    # el estrato del eucalipto se informa aparte y ENTERO, dudosos incluidos:
    # alli el dudoso tambien es noticia
    alto = d[d.chm_m >= 35]
    if len(alto):
        print(f"estrato >= 35 m ({len(alto)} puntos - el suelo del eucalipto):")
        for k, v in alto.clase.value_counts().items():
            print(f"  {k:<14}{v:>3}")
        print()

    dud = d[d.clase == "dudoso"]
    pct_dud = 100 * dud.peso_m2.sum() / d.peso_m2.sum()
    d = d[d.clase != "dudoso"].reset_index(drop=True)
    print(f"dudosos excluidos: {len(dud)} puntos ({pct_dud:.1f} % de la superficie)")

    d["es_arbol"] = d.clase.values == "arbol"
    print("\ncomposicion por fotointerpretacion (ponderada; fase 2 dio 27,7 % arbol):")
    comp = (d.groupby("clase").peso_m2.sum() / 1e4).sort_values(ascending=False)
    for k, v in comp.items():
        print(f"  {k:<14}{v:>8.1f} ha  ({100*v/comp.sum():>5.1f} %)")

    chm, verdad, peso = d.chm_m.to_numpy(), d.es_arbol.to_numpy(), d.peso_m2.to_numpy()
    obs = metricas(*confusion(chm, verdad, peso, u))

    rng = np.random.default_rng(SEMILLA)
    grupos = [g.index.to_numpy() for _, g in d.groupby("estrato", sort=True)]
    boot = {"tasa_fp_producto": [], "recall": []}
    for _ in range(REPLICAS):
        sel = np.concatenate([rng.choice(g, len(g), replace=True) for g in grupos])
        mm = metricas(*confusion(chm[sel], verdad[sel], peso[sel], u))
        for k in boot:
            boot[k].append(mm[k])
    ic = {k: np.nanpercentile(v, [2.5, 97.5]) for k, v in boot.items()}

    print(f"\n=== PRODUCTO FUERA DE MUESTRA (umbral {u:g} m, {REPLICAS} replicas)")
    print(f"                        fase 2 (3 bloques)     ahora (260 bloques)")
    print(f"  tasa de FP            24.2 % [17.0-31.2]     "
          f"{100*obs['tasa_fp_producto']:.1f} % [{100*ic['tasa_fp_producto'][0]:.1f}-"
          f"{100*ic['tasa_fp_producto'][1]:.1f}]")
    print(f"  sensibilidad          89.4 % [81.4-96.6]     "
          f"{100*obs['recall']:.1f} % [{100*ic['recall'][0]:.1f}-"
          f"{100*ic['recall'][1]:.1f}]")

    lo, hi = 100 * ic["tasa_fp_producto"][0], 100 * ic["tasa_fp_producto"][1]
    pt = 100 * obs["tasa_fp_producto"]
    if hi < 17.0 or lo > 31.2:
        print("\n  los IC NO se solapan: la tasa publicada no describe la comarca.")
        print("  ranking_final.py usara la tasa nueva; hay que contarlo en portada.")
    elif pt < 17.0 or pt > 31.2:
        print("\n  compatible pero DESPLAZADA: los IC se solapan, pero el punto nuevo")
        print("  cae fuera del IC de la fase 2. Pecar de pesimista es el criterio")
        print("  del proyecto: las cotas del ranking usan esta tasa, que ademas")
        print("  esta medida en el dominio donde el producto se aplica.")
    else:
        print("\n  los IC se solapan y el punto cae dentro: la tasa de la fase 2")
        print("  describe tambien la comarca entera. Validado fuera de muestra.")

    pd.DataFrame([{
        "umbral_m": u, "n_anotados": len(d) + len(dud), "n_dudosos": len(dud),
        "tasa_fp": round(obs["tasa_fp_producto"], 4),
        "tasa_fp_lo": round(ic["tasa_fp_producto"][0], 4),
        "tasa_fp_hi": round(ic["tasa_fp_producto"][1], 4),
        "sensibilidad": round(obs["recall"], 4),
        "sens_lo": round(ic["recall"][0], 4), "sens_hi": round(ic["recall"][1], 4),
    }]).to_csv(VAL / "resumen_producto.csv", index=False, encoding="utf-8-sig")
    print(f"\n-> {(VAL / 'resumen_producto.csv').relative_to(RAIZ)}")
