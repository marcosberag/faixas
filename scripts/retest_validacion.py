"""Segunda pasada ciega sobre una submuestra, para medir la fiabilidad del anotador.

POR QUE HACE FALTA
------------------
En la primera pasada, la clase "no arbol" se respondio con mediana de 1,3 s y un
33 % por debajo del segundo, mientras que "dudoso" llevo 3,4 s y ningun caso bajo
el segundo. Ese patron — una respuesta mucho mas rapida que las demas — es el de
una tecla por defecto, no el de una decision.

Y deja huella en el resultado: la precision del CHM se estanca en 0,92 aunque se
suba el umbral a 20 m. Deberia tender a 1, porque a 20 m sobre el terreno no
puede no haber arbol. Ese techo es ruido de la verdad de referencia.

COMO SE ARREGLA, Y COMO NO
---------------------------
NO se arregla mirando el CHM y corrigiendo lo que discrepa. Eso fuerza el acuerdo
y la tasa de falsos positivos saldria buenisima y falsa: estarias midiendo tu
obediencia al CHM, no su acierto.

Se arregla volviendo a anotar A CIEGAS, sin ver ni el CHM ni tu respuesta
anterior, y comparando las dos pasadas. La discordancia entre ellas ES un dato:
es la fiabilidad intra-anotador, y se publica junto a la tasa de falsos
positivos. Un producto validado por una persona sin medir su consistencia esta
a medio validar.

EL GRUPO DE CONTROL
--------------------
La submuestra no son solo los puntos rapidos. Lleva ademas una muestra aleatoria
de los que se respondieron con calma. Sin ese control no se puede separar "fallo
por prisa" de "fallo porque el chip era dificil": si solo se reanotan los
rapidos y discrepan mucho, no se sabe si es la prisa o es que los casos rapidos
eran justo los faciles o los dificiles. Con control, la diferencia entre los dos
grupos responde la pregunta.

Van barajados y mezclados: durante la segunda pasada no se puede saber si un
chip viene del grupo rapido o del de control.

Uso:
    python scripts/retest_validacion.py              # genera el HTML
    python scripts/retest_validacion.py --compara    # compara las dos pasadas
"""
import argparse
import json
import pathlib
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from anotador import PAGINA  # noqa: E402

RAIZ = pathlib.Path(__file__).resolve().parent.parent
VAL = RAIZ / "datos" / "procesado" / "validacion"
SEMILLA = 20260818


def carga():
    m = pd.read_csv(VAL / "muestra.csv", encoding="utf-8-sig")
    a = pd.read_csv(VAL / "anotacion.csv")
    return m.merge(a, on="id", validate="one_to_one")


def genera(d, rapido_s, n_control, sin_tipo):
    rng = np.random.default_rng(SEMILLA)
    rapidos = d[d.ms < rapido_s * 1000]
    lentos = d[d.ms >= rapido_s * 1000]
    control = lentos.sample(min(n_control, len(lentos)), random_state=SEMILLA)

    sub = pd.concat([rapidos.assign(grupo="rapido"),
                     control.assign(grupo="control")])
    sub = sub.iloc[rng.permutation(len(sub))].reset_index(drop=True)

    # el CSV de referencia guarda a que grupo pertenece cada punto; el HTML no lo
    # sabe, para que la segunda pasada no pueda condicionarse por el grupo
    sub[["id", "grupo", "clase", "tipo", "ms", "chm_m", "estrato", "peso_m2"]] \
        .to_csv(VAL / "retest_referencia.csv", index=False, encoding="utf-8-sig")

    html = (PAGINA
            .replace("__DATOS__", json.dumps([{"id": i} for i in sub.id],
                                             separators=(",", ":")))
            .replace("__FIRMA__", f"retest-{len(sub)}")
            .replace("__PIDE_TIPO__", "false" if sin_tipo else "true")
            .replace("anotacion.csv", "anotacion_retest.csv"))
    salida = VAL / "anotador_retest.html"
    salida.write_text(html, encoding="utf-8")

    print(f"{len(sub)} puntos para la segunda pasada:")
    print(f"  {len(rapidos):>4} respondidos en menos de {rapido_s:g} s")
    print(f"  {len(control):>4} de control, tomados al azar de los demas")
    print(f"\nVAN MEZCLADOS Y BARAJADOS. No mires tu respuesta anterior ni el CHM:")
    print(f"si intentas reproducir lo que pusiste, la comparacion no mide nada.")
    print(f"\n-> {salida.relative_to(RAIZ)}")
    print(f"\nabrelo, anota con calma, y guarda el CSV como "
          f"{(VAL / 'anotacion_retest.csv').relative_to(RAIZ)}")


def compara():
    ref = pd.read_csv(VAL / "retest_referencia.csv", encoding="utf-8-sig")
    ruta = VAL / "anotacion_retest.csv"
    if not ruta.exists():
        raise SystemExit(f"falta {ruta}: anota antes anotador_retest.html")
    b = pd.read_csv(ruta).rename(columns={"clase": "clase2", "tipo": "tipo2",
                                          "ms": "ms2"})
    d = ref.merge(b, on="id", validate="one_to_one")
    print(f"{len(d)} puntos anotados dos veces\n")

    d["igual"] = d.clase == d.clase2
    for g, sub in d.groupby("grupo"):
        # kappa de Cohen: el acuerdo por encima del que saldria por azar. Con
        # clases desbalanceadas el porcentaje bruto engana, porque acertar
        # siempre "no" ya da un 70 %
        po = sub.igual.mean()
        pe = sum((sub.clase == k).mean() * (sub.clase2 == k).mean()
                 for k in set(sub.clase) | set(sub.clase2))
        kappa = (po - pe) / (1 - pe) if pe < 1 else float("nan")
        print(f"grupo {g:<8} n={len(sub):<4} acuerdo {100*po:>5.1f} %   "
              f"kappa {kappa:>5.2f}")

    print("\nque cambio, de la primera pasada a la segunda:")
    cam = d[~d.igual]
    if len(cam):
        for (c1, c2), n in cam.groupby(["clase", "clase2"]).size() \
                              .sort_values(ascending=False).items():
            print(f"  {c1:<12} -> {c2:<12} {n:>3}   "
                  f"(CHM mediano {cam[(cam.clase==c1)&(cam.clase2==c2)].chm_m.median():.1f} m)")
    else:
        print("  nada")

    alto = d[d.chm_m > 15]
    if len(alto):
        print(f"\ncontrol de coherencia — puntos con CHM > 15 m (n={len(alto)}):")
        for col, et in (("clase", "1a pasada"), ("clase2", "2a pasada")):
            v = alto[col].value_counts()
            print(f"  {et}: " + " · ".join(f"{k} {n}" for k, n in v.items()))
        print("  a 15 m sobre el terreno tiene que haber algo: cuantos menos"
              " 'no' aqui, mas fiable la pasada")

    print(f"\n-> pega {ruta.name} sobre anotacion.csv para los puntos revisados,")
    print("   o quedate con la primera y publica la concordancia como limitacion")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--compara", action="store_true")
    ap.add_argument("--rapido", type=float, default=1.0,
                    help="segundos por debajo de los cuales se considera prisa")
    ap.add_argument("--control", type=int, default=40)
    ap.add_argument("--sin-tipo", action="store_true", default=True)
    args = ap.parse_args()

    if args.compara:
        compara()
    else:
        genera(carga(), args.rapido, args.control, args.sin_tipo)
