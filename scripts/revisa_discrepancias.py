"""Hojas de contacto con los puntos donde el CHM y la fotointerpretacion no coinciden.

Se corre DESPUES de anotar y calibrar, nunca antes. Aqui es donde se mira el CHM
al lado de la ortofoto — durante la anotacion no se enseña, para no contaminar el
criterio (ver `anotador.py`).

Para que sirve, en orden de importancia:

1. SEPARAR ERROR DE DESFASE. El LiDAR es de 2024 y la ortofoto de septiembre de
   2023. Una corta hecha en medio aparece como falso negativo (en la foto hay
   arboles, en el CHM ya no) y una plantacion o un crecimiento fuerte, como falso
   positivo. No son errores del pipeline y contarlos como tales infla la tasa que
   vamos a publicar. Tampoco se pueden descontar a ojo sin declararlo: lo honesto
   es publicar la tasa entera y dar aparte cuantos casos parecen desfase.

2. ENCONTRAR FALLOS SISTEMATICOS. Si los falsos positivos se agrupan en taludes,
   en bordes de nucleo o en un bloque concreto, no es ruido: es el MDT hundiendose
   donde no debe, y se arregla en el pipeline.

3. CONTROLAR LA PROPIA ANOTACION. Algunas discrepancias son error de quien anota,
   y verlas juntas es la unica forma de darse cuenta.

Uso:
    python scripts/revisa_discrepancias.py                # usa el umbral calibrado
    python scripts/revisa_discrepancias.py --umbral 2.5
"""
import argparse
import pathlib

import matplotlib
import pandas as pd
from PIL import Image

matplotlib.use("Agg")
from matplotlib import pyplot as plt

RAIZ = pathlib.Path(__file__).resolve().parent.parent
VAL = RAIZ / "datos" / "procesado" / "validacion"
SALIDAS = RAIZ / "salidas"

POR_HOJA = 12   # pares orto/CHM por PNG


def umbral_calibrado():
    r = VAL / "calibracion_resumen.csv"
    if not r.exists():
        raise SystemExit("no hay calibracion_resumen.csv: corre antes "
                         "calibra_umbral.py, o pasa --umbral")
    return float(pd.read_csv(r, encoding="utf-8-sig").umbral_youden_m.iloc[0])


def hoja(sub, titulo, ruta):
    n = len(sub)
    cols = 4
    filas = -(-n // cols)
    # 3,35 de alto por fila y no 2,85: con menos, el titulo de cada fila se monta
    # sobre las imagenes de la de arriba
    fig, ax = plt.subplots(filas, cols * 2, figsize=(cols * 5.2, filas * 3.35),
                           squeeze=False)
    for k, (_, f) in enumerate(sub.iterrows()):
        fi, co = divmod(k, cols)
        a, b = ax[fi, co * 2], ax[fi, co * 2 + 1]
        a.imshow(Image.open(VAL / "chips" / f"{f.id}.jpg"))
        a.set_title(f"{f.id} · anotado: {f.clase}", fontsize=9)
        b.imshow(Image.open(VAL / "chips_chm" / f"{f.id}.png"))
        b.set_title(f"CHM {f.chm_m:.1f} m", fontsize=9)
    for a in ax.ravel():
        a.set_xticks([]); a.set_yticks([])
    for k in range(n, filas * cols):        # celdas sobrantes de la ultima fila
        fi, co = divmod(k, cols)
        ax[fi, co * 2].axis("off"); ax[fi, co * 2 + 1].axis("off")
    fig.suptitle(titulo, fontsize=12)
    fig.text(.5, .004, "Ortofoto PNOA sept-2023 · LiDAR PNOA 2024 · IGN/CNIG (CC-BY 4.0)."
             "  Escala del CHM: violeta 0 m → amarillo 30 m. Chips de 40 × 40 m.",
             ha="center", fontsize=8, color="#666")
    fig.tight_layout(rect=[0, .02, 1, .96])
    fig.savefig(ruta, dpi=95)
    plt.close(fig)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--anotacion", default=str(VAL / "anotacion.csv"))
    ap.add_argument("--umbral", type=float, default=None)
    args = ap.parse_args()

    u = args.umbral if args.umbral is not None else umbral_calibrado()
    m = pd.read_csv(VAL / "muestra.csv", encoding="utf-8-sig")
    a = pd.read_csv(args.anotacion)
    d = m.merge(a, on="id").query("clase != 'dudoso'").copy()
    d["es_arbol"] = d.clase == "arbol"
    d["predicho"] = d.chm_m > u

    fp = d[d.predicho & ~d.es_arbol].sort_values("chm_m", ascending=False)
    fn = d[~d.predicho & d.es_arbol].sort_values("chm_m")
    print(f"umbral {u:g} m — {len(fp)} falsos positivos, {len(fn)} falsos negativos "
          f"de {len(d)} puntos utiles")

    SALIDAS.mkdir(exist_ok=True)
    hechos = []
    for nombre, sub, expl in (
        ("fp", fp, "FALSOS POSITIVOS — el CHM dice arbol y la ortofoto no.\n"
                   "Candidatos: edificacion, matorral alto, talud con el MDT hundido, "
                   "o plantacion posterior a sept-2023"),
        ("fn", fn, "FALSOS NEGATIVOS — hay arbol en la ortofoto y el CHM no lo ve.\n"
                   "Candidatos: arbol joven o bajo, copa rala, "
                   "o CORTA entre sept-2023 y el vuelo de 2024"),
    ):
        for k in range(0, len(sub), POR_HOJA):
            trozo = sub.iloc[k:k + POR_HOJA]
            p = SALIDAS / f"discrepancias_{nombre}_{k//POR_HOJA + 1}.png"
            hoja(trozo, f"{expl}\numbral {u:g} m — hoja {k//POR_HOJA + 1}", p)
            hechos.append(p)
            print(f"  -> {p.relative_to(RAIZ)}  ({len(trozo)} casos)")

    if not hechos:
        print("  no hay discrepancias que revisar")

    cols = ["id", "clase", "tipo", "chm_m", "estrato", "peso_m2", "bloque", "x", "y"]
    rev = pd.concat([fp.assign(discrepancia="falso_positivo"),
                     fn.assign(discrepancia="falso_negativo")])[["discrepancia"] + cols]
    # columna vacia para anotar a mano al revisar las hojas
    rev["juicio"] = ""
    ruta = VAL / "discrepancias.csv"
    rev.to_csv(ruta, index=False, encoding="utf-8-sig")
    print(f"\n-> {ruta.relative_to(RAIZ)}")
    print("   rellena la columna `juicio` mirando las hojas: "
          "desfase | error_chm | error_anotacion | correcto")
