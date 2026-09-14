"""Cuanto ruido mete el anotador en el resultado, medido y propagado.

La pregunta que responde: "yo dudo mucho, sobre todo entre arbusto y arbol
pequeno. Como de fiable es entonces el umbral calibrado?"

Se responde en tres pasos y ninguno es una opinion:

1. DONDE duda. El retest ciego (`retest_validacion.py --compara`) da el acuerdo
   consigo mismo punto a punto. Aqui se corta por altura del CHM para ver si la
   inseguridad esta repartida o concentrada.

2. CUANTO pesa esa zona en superficie, ponderando por `peso_m2`.

3. CUANTO MUEVE el resultado. Se remuestrea la anotacion entera metiendo el ruido
   MEDIDO en el paso 1: cada punto cambia de clase con la probabilidad observada
   para su clase y su banda de altura, y el destino se sortea de la matriz de
   transicion empirica del retest. Se recalibra en cada replica. La dispersion del
   umbral y de la tasa de FP que sale de ahi es, literalmente, el efecto de las
   dudas del anotador sobre el entregable.

   LA TASA DE VOLTEO HAY QUE CONDICIONARLA A LA CLASE, no solo a la banda. La
   primera version aplicaba la tasa de la banda por igual a todo lo que caia en
   ella y la tasa de FP saltaba de 24 % a 36 %: eso no era dispersion, era sesgo.
   'arbol' son 87 puntos de 400 y 'no' son 231, asi que forzar el mismo volteo a
   los dos destruye arboles mucho mas deprisa de lo que los crea, y cada arbol
   perdido por encima del umbral se convierte en un falso positivo de mentira. Se
   combinan ambos condicionantes de forma multiplicativa (estilo raking):
       p(cambio | clase, banda) = p(cambio | clase) * p(cambio | banda) / p(cambio)
   que respeta las dos marginales medidas en vez de imponer una y romper la otra.

POR QUE ESTO NO ES LO MISMO QUE EL BOOTSTRAP DE `calibra_umbral.py`
-------------------------------------------------------------------
Aquel remuestrea PUNTOS: mide cuanto dependeria el resultado de que hubieran
tocado otras 400 posiciones. Este remuestrea ETIQUETAS sobre los mismos puntos:
mide cuanto dependeria de que el anotador hubiera tenido otro dia. Son dos
fuentes de error distintas y la comparacion entre ambas es el resultado que
importa: dice cual de las dos limita, y por tanto donde tendria sentido invertir
esfuerzo si hubiera que mejorar.

EL RUIDO DEL ANOTADOR SOBRESTIMA LA TASA DE FP, NO LA ESCONDE
--------------------------------------------------------------
Al meter ruido en las etiquetas la tasa de FP siempre SUBE, y sube en las dos
direcciones del error: un arbol mal marcado como 'no' se convierte en falso
positivo aunque el CHM haya acertado. O sea, el desacuerdo entre CHM y anotador
se cobra como fallo del CHM aunque el fallo sea del anotador.

De ahi sale la lectura que importa: la anotacion real YA lleva una dosis de ese
ruido, luego el 24,2 % publicado es un TECHO de la tasa de FP verdadera, no una
cifra optimista. Si el anotador fuera infalible el numero seria menor. Se da una
extrapolacion indicativa de cuanto menor, suponiendo que el efecto es lineal en
la dosis de ruido, que es lo que se supone en la correccion por error de medida
de toda la vida. Es orientativa: lo que se publica sigue siendo el 24,2 %, porque
equivocarse del lado de declarar mas error que el que hay es el lado correcto.

LIMITACION DEL PROPIO METODO
-----------------------------
El retest son 126 puntos y su grupo de control se sorteo entre los que tardaron
mas de un segundo, o sea entre los dificiles. La tasa de desacuerdo que se mide
en la zona de decision es por tanto un TECHO, no la tasa media. Propagar un techo
da un intervalo conservador: si aun asi el resultado aguanta, aguanta.

Uso:
    python scripts/fiabilidad_anotador.py
    python scripts/fiabilidad_anotador.py --replicas 1000
"""
import argparse
import pathlib
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from calibra_umbral import barrido  # noqa: E402

RAIZ = pathlib.Path(__file__).resolve().parent.parent
VAL = RAIZ / "datos" / "procesado" / "validacion"

# la de en medio es la zona de decision: donde el CHM esta cerca del umbral y
# donde en la ortofoto un arbol joven y una mata de tojo se parecen
BANDAS = [(0.0, 2.0, "matorral / suelo"),
          (2.0, 8.0, "ZONA DE DECISION"),
          (8.0, np.inf, "arbolado alto")]
SEMILLA = 20260818


def banda(h):
    for i, (lo, hi, _) in enumerate(BANDAS):
        if lo <= h < hi:
            return i
    return len(BANDAS) - 1


def kappa(a, b):
    """Cohen sobre dos series de etiquetas alineadas. (kappa, acuerdo, esperado).

    OJO CON LEER EL KAPPA A SECAS: penaliza el acuerdo que se lograria por azar,
    y cuando una clase se come la muestra ese azar ya es altisimo. Un 94 % de
    acuerdo con un 94 % esperado da kappa 0 sin que el anotador haya hecho nada
    mal; es la paradoja de kappa, y por eso aqui se imprimen las tres cifras.
    """
    cl = sorted(set(a) | set(b))
    obs = float(np.mean([x == y for x, y in zip(a, b)]))
    esp = float(sum(np.mean([x == c for x in a]) * np.mean([y == c for y in b])
                    for c in cl))
    return ((obs - esp) / (1 - esp) if esp < 1 else np.nan), obs, esp


def etiqueta(lo, hi):
    return f"{lo:g}-{hi:g} m" if np.isfinite(hi) else f">{lo:g} m"


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--replicas", type=int, default=500)
    args = ap.parse_args()

    m = pd.read_csv(VAL / "muestra.csv", encoding="utf-8-sig")
    ref = pd.read_csv(VAL / "retest_referencia.csv", encoding="utf-8-sig")
    re2 = pd.read_csv(VAL / "anotacion_retest.csv")
    fin = pd.read_csv(VAL / "anotacion.csv")

    # ---- 1. donde duda ----------------------------------------------------
    r = ref.merge(re2, on="id", suffixes=("_1", "_2"))
    r["b"] = r.chm_m.map(banda)
    print(f"RETEST CIEGO: {len(r)} puntos anotados dos veces sin ver la primera "
          "respuesta\n")
    print(f"  {'banda de altura del CHM':<30} {'n':>4} {'acuerdo':>9} "
          f"{'p/azar':>8} {'kappa':>7}")
    tasa_b = {}
    for i, (lo, hi, nom) in enumerate(BANDAS):
        g = r[r.b == i]
        et = f"{etiqueta(lo, hi)}  {nom}"
        if len(g) < 5:
            print(f"  {et:<30} {len(g):>4} {'-':>9} {'-':>8} {'-':>7}  (pocos)")
            tasa_b[i] = np.nan
            continue
        k, obs, esp = kappa(g.clase_1.tolist(), g.clase_2.tolist())
        tasa_b[i] = 1 - obs
        print(f"  {et:<30} {len(g):>4} {obs:>8.1%} {esp:>7.1%} {k:>7.2f}")
    print("  (p/azar = acuerdo que saldria etiquetando al tuntun con esas mismas\n"
          "   frecuencias. Si el acuerdo real lo supera poco, el kappa se hunde\n"
          "   aunque el acuerdo sea altisimo: es la paradoja de kappa, no un fallo)")

    # las bandas sin datos suficientes heredan la tasa de la peor: nunca suponer
    # que una banda no medida se porta bien
    peor = float(np.nanmax(list(tasa_b.values())))
    tasa_b = {i: (peor if np.isnan(v) else v) for i, v in tasa_b.items()}

    # matriz de transicion empirica: dado que cambia, a que clase se va, y con
    # que frecuencia cambia cada clase (ver docstring: sin esto se sesga)
    cambios = r[r.clase_1 != r.clase_2]
    destinos = {c: g.clase_2.value_counts(normalize=True)
                for c, g in cambios.groupby("clase_1")}
    tasa_c = (r.assign(cambia=r.clase_1 != r.clase_2)
              .groupby("clase_1").cambia.mean().to_dict())
    p_global = float((r.clase_1 != r.clase_2).mean())

    print(f"\n  {len(cambios)} desacuerdos de {len(r)}. Por clase de partida:")
    for c in sorted(tasa_c):
        n = int((r.clase_1 == c).sum())
        g = cambios[cambios.clase_1 == c]
        destino = ", ".join(f"{k} x{v}" for k, v in g.clase_2.value_counts().items())
        print(f"    {c:<12} {tasa_c[c]:>5.0%} de {n:>3}  -> {destino or '(ninguno)'}")

    # ---- 2. cuanto pesa esa zona -----------------------------------------
    d = m.merge(fin, on="id", validate="one_to_one")
    d["b"] = d.chm_m.map(banda)
    tot = d.peso_m2.sum()
    print("\nREPARTO DE LA FAIXA por banda (ponderado por superficie):")
    print(f"  {'banda':<30} {'puntos':>7} {'ha':>8} {'% faixa':>9} {'% dudosos':>10}")
    for i, (lo, hi, nom) in enumerate(BANDAS):
        g = d[d.b == i]
        et = f"{etiqueta(lo, hi)}  {nom}"
        pdud = (100 * g[g.clase == "dudoso"].peso_m2.sum() / g.peso_m2.sum()
                if len(g) else 0)
        print(f"  {et:<30} {len(g):>7} {g.peso_m2.sum()/1e4:>7.1f} "
              f"{100*g.peso_m2.sum()/tot:>8.1f}% {pdud:>9.1f}%")

    # ---- 3. cuanto mueve el resultado ------------------------------------
    rng = np.random.default_rng(SEMILLA)
    clases = d.clase.to_numpy().astype(object)
    chm_todo = d.chm_m.to_numpy()
    peso_todo = d.peso_m2.to_numpy()

    # p(cambio | clase, banda), combinando las dos marginales medidas
    p_cambio = np.clip(
        np.array([tasa_c.get(c, p_global) for c in clases])
        * np.array([tasa_b[i] for i in d.b.to_numpy()]) / max(p_global, 1e-9),
        0.0, 1.0)
    print("\ntasa de volteo aplicada, p(cambio | clase, banda):")
    print(f"  {'clase':<14} " + " ".join(f"{etiqueta(*b[:2]):>10}" for b in BANDAS))
    for c in sorted(set(clases)):
        fila = [np.clip(tasa_c.get(c, p_global) * tasa_b[i] / max(p_global, 1e-9), 0, 1)
                for i in range(len(BANDAS))]
        print(f"  {c:<14} " + " ".join(f"{v:>9.1%}" for v in fila))

    def calibra(cl):
        """Umbral Youden y tasa de FP a partir de un vector de clases."""
        util = cl != "dudoso"
        if util.sum() < 30:
            return np.nan, np.nan, np.nan
        b = barrido(chm_todo[util], cl[util] == "arbol", peso_todo[util])
        i = b.youden.idxmax()
        fijo = b[b.umbral_m == 5.5].iloc[0]
        return (float(b.loc[i, "umbral_m"]), float(1 - b.loc[i, "precision"]),
                float(1 - fijo.precision))

    def simula(mover_dudosos):
        """Replicas del ruido. mover_dudosos=False respeta el protocolo real.

        Los 60 dudosos NO entran en la calibracion: se declaran y se excluyen.
        Dejarlos mutar a arbol/no los devuelve al calculo a cara o cruz, y como
        pesan mas en la parte alta del CHM eso no dispersa el resultado, lo
        desplaza. Es una pregunta legitima ("y si me hubiera obligado a decidir?")
        pero es OTRA, y ademas se apoya en 6 dudosos re-anotados, que no dan para
        estimar nada. Va como escenario aparte y etiquetado de pesimista.
        """
        us, fps, fps55 = [], [], []
        for _ in range(args.replicas):
            cl = clases.copy()
            candidatos = np.flatnonzero(rng.random(len(cl)) < p_cambio)
            for k in candidatos:
                if not mover_dudosos and cl[k] == "dudoso":
                    continue
                dist = destinos.get(cl[k])
                if dist is None or dist.empty:
                    continue
                nueva = rng.choice(dist.index.to_numpy(), p=dist.to_numpy())
                cl[k] = nueva
            u, fp, fp55 = calibra(cl)
            us.append(u)
            fps.append(fp)
            fps55.append(fp55)
        return np.array(us), np.array(fps), np.array(fps55)

    q = lambda v: np.nanpercentile(v, [2.5, 50, 97.5])  # noqa: E731
    u0, fp0, _ = calibra(clases)
    print(f"\nPROPAGACION DEL RUIDO DEL ANOTADOR ({args.replicas} replicas)")
    print(f"  punto de partida: umbral {u0:g} m, tasa de FP {fp0:.1%}", flush=True)

    us, fps, fps55 = simula(mover_dudosos=False)
    qu, qf, q5 = q(us), q(fps), q(fps55)
    print("\n  ESCENARIO REAL (los dudosos siguen fuera, como en el protocolo)")
    print(f"    umbral Youden                   {qu[1]:g} m   "
          f"IC95 [{qu[0]:g}, {qu[2]:g}]")
    print(f"    tasa de FP (a su propio umbral) {qf[1]:>5.1%}  "
          f"IC95 [{qf[0]:.1%}, {qf[2]:.1%}]")
    print(f"    tasa de FP (umbral fijo 5,5 m)  {q5[1]:>5.1%}  "
          f"IC95 [{q5[0]:.1%}, {q5[2]:.1%}]")
    print(f"    el umbral se queda a +-1 m del calibrado en el "
          f"{100*np.mean(np.abs(us - u0) <= 1.0):.0f} % de las replicas")

    up, fpp, fpp55 = simula(mover_dudosos=True)
    qup, qfp, q5p = q(up), q(fpp), q(fpp55)
    print("\n  ESCENARIO PESIMISTA (obligado a mojarse tambien en los dudosos)")
    print(f"    umbral Youden                   {qup[1]:g} m   "
          f"IC95 [{qup[0]:g}, {qup[2]:g}]")
    print(f"    tasa de FP (umbral fijo 5,5 m)  {q5p[1]:>5.1%}  "
          f"IC95 [{q5p[0]:.1%}, {q5p[2]:.1%}]")
    print(f"    -> declarar las dudas en vez de adivinar ahorra "
          f"{100*(q5p[1]-q5[1]):.0f} puntos de tasa de FP.")
    print("       La tecla 'dudoso' no es tibieza: es lo que impide que el ruido")
    print("       entre en el numero que se publica.")

    # ---- en que direccion empuja el ruido --------------------------------
    # una dosis mas de ruido sube la tasa de FP en `delta`. La anotacion real ya
    # lleva una dosis, asi que extrapolando hacia ruido cero la tasa de FP baja
    # otro tanto. Lineal y por tanto cruda: es una orientacion, no el resultado
    delta = q5[1] - fp0
    print("\nEN QUE DIRECCION EMPUJA TU INSEGURIDAD")
    print(f"  una dosis mas de ruido sube la tasa de FP {100*delta:+.1f} pp "
          f"({fp0:.1%} -> {q5[1]:.1%})")
    print(f"  el desacuerdo CHM/anotador se apunta como fallo del CHM aunque sea")
    print(f"  del anotador, asi que el 24,2 % que se publica es un TECHO.")
    print(f"  extrapolando a un anotador infalible: ~{max(fp0-delta, 0):.0%} "
          "(indicativo, supone linealidad)")
    print("  -> dudar no inventa aciertos, se los come. El numero publicado peca")
    print("     de pesimista, que es el lado por el que hay que pecar.")

    # ---- comparacion de las dos fuentes de error -------------------------
    res = VAL / "calibracion_resumen.csv"
    if res.exists():
        c = pd.read_csv(res, encoding="utf-8-sig").iloc[0]
        anc_mu = 100 * (float(c.tasa_fp_ic95_hi) - float(c.tasa_fp_ic95_lo))
        anc_an = 100 * (q5[2] - q5[0])
        print("\nQUE LIMITA, EL MUESTREO O EL ANOTADOR")
        print("(anchura del IC95 de la tasa de FP, en puntos porcentuales):")
        print(f"  por tener solo {len(d)} puntos          {anc_mu:>5.1f} pp")
        print(f"  por la variabilidad del criterio  {anc_an:>5.1f} pp")
        print("  -> manda " + ("el tamano de la muestra" if anc_mu > anc_an
                               else "el criterio del anotador"))

    sal = pd.DataFrame({"replica": np.arange(len(us)), "umbral_m": us,
                        "tasa_fp": fps, "tasa_fp_u55": fps55,
                        "umbral_m_pesim": up, "tasa_fp_u55_pesim": fpp55})
    sal.round(5).to_csv(VAL / "fiabilidad_anotador.csv", index=False,
                        encoding="utf-8-sig")
    print(f"\n-> {(VAL / 'fiabilidad_anotador.csv').relative_to(RAIZ)}")
