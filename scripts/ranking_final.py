"""El entregable: ranking de parroquias y concellos por franja con arbolado prohibido.

Ensambla las piezas VALIDADAS del proyecto y solo esas:

  - CHM a 1 m sobre los 263 bloques (fase 4), umbral de arbolado calibrado en
    5,5 m con tasa de falsos positivos medida (fase 2).
  - Especie del IFN4 aplicada como fraccion continua por rodal (fase 3), con el
    arbolado disperso — que el IFN no cartografia — llevado a las cotas, no a
    una etiqueta inventada.
  - Regla estructural de los 35 m: en Galicia solo el eucalipto los pasa, asi
    que `ha_sobre_35m` es un suelo de especie prohibida que no depende de nada.

El clasificador Sentinel-2 NO entra: la validacion cruzada por zonas dio AUC
0,746 con precision del 45,8 % al eximir, y varianza espacial 0,30-0,93. Esta
publicado como resultado negativo en docs/02-walkthrough.md, seccion 13.

COMO SE COMPONEN LAS COTAS
---------------------------
Sea A el arbolado detectado (ha sobre 5,5 m), FP la tasa de falsos positivos del
producto (0,242, IC95 [0,170-0,312], y es un TECHO: el ruido del anotador solo
puede inflarla), y [p_lo, p_hi] la fraccion prohibida segun el IFN — p_lo cuenta
como prohibido solo lo medido en rodal, p_hi anhade el disperso entero.

  ha_prohibida_min = max( A x (1 - FP_hi) x p_lo , ha_sobre_35m )
  ha_prohibida_max =      A x (1 - FP_lo) x p_hi

El producto de terminos supone independencia entre el error del CHM y la especie
(un falso positivo no es mas ni menos probable bajo pinar que bajo robledal);
es la hipotesis mas debil disponible y queda declarada. Se ORDENA por el punto
medio de las cotas y se publican siempre las dos: el orden es para priorizar
inspeccion, los numeros no son superficie de infraccion.

Uso:
    python scripts/ranking_final.py
"""
import pathlib

import numpy as np
import pandas as pd

RAIZ = pathlib.Path(__file__).resolve().parent.parent
MET = RAIZ / "datos" / "procesado" / "metricas"
VAL = RAIZ / "datos" / "procesado" / "validacion"

if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--zona", default="paradanta",
                    help="sufijo de las metricas de la zona")
    args = ap.parse_args()
    # vacio para la zona piloto: no cambia el nombre de nada ya existente
    suf = "" if args.zona == "paradanta" else f"_{args.zona}"
    m = pd.read_csv(MET / f"metricas_parroquia{suf}.csv", encoding="utf-8-sig")
    # si verdades_en_ranking.py ya paso los reemplazos de dosel CONFIRMADOS
    # contra ortofoto a la fraccion de especie, esa version manda (el rodal
    # reemplazado no-eucalipto pasa a desconocida: baja la cota inferior)
    copas = MET / f"metricas_parroquia_especie_copas{suf}.csv"
    verdades = MET / f"metricas_parroquia_especie_verdades{suf}.csv"
    if copas.exists():
        origen_esp = ("verdades + clasificador de copas en zonas validadas "
                      "(aplica_copas)")
        e = pd.read_csv(copas, encoding="utf-8-sig")
    elif verdades.exists():
        origen_esp = "con reemplazos confirmados (verdades_en_ranking)"
        e = pd.read_csv(verdades, encoding="utf-8-sig")
    else:
        origen_esp = "IFN 2010 sin correccion de eventos"
        e = pd.read_csv(MET / f"metricas_parroquia_especie{suf}.csv",
                        encoding="utf-8-sig")
    # la tasa de FP fuera de muestra manda sobre la de calibracion si existe:
    # esta medida en el dominio donde el producto se aplica, y salio mas alta
    # (33,5 % vs 24,2 % en el piloto). Pecar de pesimista es el criterio del
    # proyecto. Cada zona valida en SU carpeta (la del piloto conserva el
    # nombre historico validacion_producto): sin esto, Pontevedra heredaria
    # la tasa del interior de A Paradanta en silencio
    carpeta_fuera = ("validacion_producto" if args.zona == "paradanta"
                     else f"validacion_{args.zona}")
    fuera = VAL.parent / carpeta_fuera / "resumen_producto.csv"
    if fuera.exists():
        cal = pd.read_csv(fuera, encoding="utf-8-sig").iloc[0]
        fp, fp_lo, fp_hi = (float(cal.tasa_fp), float(cal.tasa_fp_lo),
                            float(cal.tasa_fp_hi))
        origen_fp = f"fuera de muestra ({carpeta_fuera})"
    else:
        cal = pd.read_csv(VAL / "calibracion_resumen.csv",
                          encoding="utf-8-sig").iloc[0]
        fp, fp_lo, fp_hi = (float(cal.tasa_fp_producto),
                            float(cal.tasa_fp_ic95_lo), float(cal.tasa_fp_ic95_hi))
        origen_fp = "calibracion fase 2 (sin contraste fuera de muestra)"

    t = m.merge(e, on=["concello", "parroquia"], how="inner",
                validate="one_to_one")
    assert len(t) == len(m) == len(e), "los CSV no casan parroquia a parroquia"
    # misma magnitud medida por dos caminos: si divergen, algo esta desalineado
    d = (t["ha_sobre_5.5m"] - t.ha_arbolado).abs().max()
    assert d < 0.5, f"ha_arbolado difiere {d:.2f} ha entre metricas y especie"

    A = t.ha_arbolado
    p_lo = np.where(A > 0, t.ha_prohibida / A, 0.0)
    p_hi = np.where(A > 0, t.ha_prohibida_hi / A, 0.0)
    t["ha_prohibida_min"] = np.maximum(A * (1 - fp_hi) * p_lo,
                                       t.ha_sobre_35m).round(1)
    t["ha_prohibida_max"] = (A * (1 - fp_lo) * p_hi).round(1)
    t["ha_prohibida_punto_medio"] = ((t.ha_prohibida_min
                                      + t.ha_prohibida_max) / 2).round(1)

    cols = ["concello", "parroquia", "ha_medida", "ha_arbolado",
            "ha_sobre_35m", "ha_prohibida_min", "ha_prohibida_max",
            "ha_prohibida_punto_medio"]
    par = (t[cols].sort_values("ha_prohibida_punto_medio", ascending=False)
           .reset_index(drop=True))
    par.insert(0, "puesto", par.index + 1)
    par.to_csv(MET / f"ranking_final{suf}.csv", index=False, encoding="utf-8-sig")

    con = (par.groupby("concello", as_index=False)
           .sum(numeric_only=True).drop(columns="puesto")
           .sort_values("ha_prohibida_punto_medio", ascending=False)
           .reset_index(drop=True))
    con.insert(0, "puesto", con.index + 1)
    con.to_csv(MET / f"ranking_final_concello{suf}.csv", index=False,
               encoding="utf-8-sig")

    print(f"tasa de FP aplicada: {fp:.1%} (IC95 [{fp_lo:.1%}-{fp_hi:.1%}], techo)")
    print(f"  origen: {origen_fp}")
    print(f"fraccion de especie: {origen_esp}")
    print(f"franja medida: {t.ha_medida.sum():,.0f} ha - "
          f"arbolado {A.sum():,.0f} ha - prohibido "
          f"[{t.ha_prohibida_min.sum():,.0f} - {t.ha_prohibida_max.sum():,.0f}] ha\n")

    print("POR CONCELLO")
    print(f"  {'concello':<12}{'faixa ha':>10}{'arbolado':>10}{'prohibido (cotas)':>22}")
    for _, r in con.iterrows():
        print(f"  {r.concello:<12}{r.ha_medida:>10,.0f}{r.ha_arbolado:>10,.0f}"
              f"{r.ha_prohibida_min:>11,.0f} -{r.ha_prohibida_max:>7,.0f}")

    print("\nTOP 12 PARROQUIAS (orden = punto medio de las cotas)")
    print(f"  {'parroquia':<34}{'faixa':>8}{'arbol.':>8}{'prohibido':>14}{'>35m':>7}")
    for _, r in par.head(12).iterrows():
        print(f"  {r.parroquia[:32]:<34}{r.ha_medida:>8,.0f}{r.ha_arbolado:>8,.0f}"
              f"{r.ha_prohibida_min:>6,.0f} -{r.ha_prohibida_max:>5,.0f}"
              f"{r.ha_sobre_35m:>7.1f}")

    print(f"\n-> {(MET / f'ranking_final{suf}.csv').relative_to(RAIZ)}")
    print(f"-> {(MET / f'ranking_final_concello{suf}.csv').relative_to(RAIZ)}")
