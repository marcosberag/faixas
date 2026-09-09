"""Regla de los dos veranos, contrastada RETROACTIVAMENTE con la anotacion.

La validacion contra ortofoto (valida_persistencia.py) dejo el detector de
eventos en 39,4 % de precision, con el danho concentrado en 2024-2026: la
sequia de agosto de 2026 hunde el NDVI de rodales enteros sin que haya corta.
Ni FCCARB ni la magnitud de la caida separan el espejismo de la corta real.

Lo que si deberia separarlos es el TIEMPO: una corta deja el NDVI hundido
tambien al verano siguiente (suelo desnudo, rebrote de 1-2 anhos); una sequia
rebota al anho siguiente. La regla: el evento en t se da por SOSTENIDO si en
t+1, respecto al MISMO techo pre-evento (max de los 2 anhos previos a t, con
el efecto-anho descontado igual que en detecta_eventos.py), sigue habiendo
caida >= 0.18 y NDVI < 0.60.

Este script la aplica retroactivamente a los eventos YA ANOTADOS contra
ortofoto y mide cuanto mejora la precision y cuantos eventos reales se pierden.
Los eventos del ultimo anho de la serie no tienen t+1: esa es la servidumbre
de la regla (la vigilancia pasa a tener un anho de retardo), y se cuenta
aparte, no se esconde.

Uso:
    python scripts/regla_dos_veranos.py
"""
import pathlib

import numpy as np
import pandas as pd
from scipy import stats

RAIZ = pathlib.Path(__file__).resolve().parent.parent
PROC = RAIZ / "datos" / "procesado"
VAL = PROC / "validacion_persistencia"

CAIDA_MIN = 0.18
SUELO = 0.60
REALES = {"confirmado", "en_otro_intervalo"}  # reemplazo visto, aunque el
                                              # intervalo baile un vuelo


def jeffreys(k, n):
    lo = stats.beta.ppf(0.025, k + 0.5, n - k + 0.5)
    hi = stats.beta.ppf(0.975, k + 0.5, n - k + 0.5)
    return lo, hi


if __name__ == "__main__":
    serie = pd.read_csv(PROC / "s2" / "serie_ndvi_rodal.csv",
                        encoding="utf-8-sig")
    anhos = sorted(int(c[5:]) for c in serie.columns if c.startswith("ndvi_"))

    # el mismo efecto-anho que en detecta_eventos.py: anomalia de la mediana
    med_anho = {a: serie[f"ndvi_{a}"].median() for a in anhos}
    base_zona = float(np.median(list(med_anho.values())))
    corr = {a: med_anho[a] - base_zona for a in anhos}

    v_corr = {f.OBJECTID_12: {a: getattr(f, f"ndvi_{a}") - corr[a]
                              for a in anhos}
              for f in serie.itertuples()}

    def sostenido(oid, t):
        """None si no hay t+1 (fin de serie); si no, True/False."""
        t = int(t)
        v = v_corr[oid]
        if t + 1 not in v or not np.isfinite(v[t + 1]):
            return None
        previos = [v[a] for a in anhos if a < t and np.isfinite(v[a])][-2:]
        techo = max(previos)
        return (techo - v[t + 1] >= CAIDA_MIN) and (v[t + 1] < SUELO)

    m = pd.read_csv(VAL / "muestra.csv", encoding="utf-8-sig")
    veredictos = pd.read_csv(VAL / "veredictos.csv", encoding="utf-8-sig")
    d = m.merge(veredictos[["id", "veredicto"]], on="id")
    ev = d[d.estado == "evento"].copy()
    ev["sostenido"] = [sostenido(f.OBJECTID_12, f.anho_evento)
                       for f in ev.itertuples()]
    ev["real"] = ev.veredicto.isin(REALES)

    ctrl = ev[ev.anho_evento == 2018]
    ev = ev[ev.anho_evento != 2018]

    print("REGLA DE LOS DOS VERANOS sobre los eventos anotados (sin 2018)\n")
    sin_t1 = ev[ev.sostenido.isna()]
    print(f"  sin verano siguiente todavia (anho {max(anhos)}): "
          f"{len(sin_t1)} eventos -> la regla no puede opinar (retardo de 1 anho)")
    de_ellos = sin_t1.real.sum()
    print(f"    de ellos, reales segun la anotacion: {de_ellos}/{len(sin_t1)}\n")

    eva = ev[ev.sostenido.notna()].copy()
    tabla = pd.crosstab(eva.sostenido.map({True: "sostenido", False: "rebota"}),
                        eva.real.map({True: "real (visto)", False: "no visto"}))
    print(tabla.to_string(), "\n")

    k0, n0 = eva.real.sum(), len(eva)
    lo0, hi0 = jeffreys(k0, n0)
    print(f"  precision SIN la regla (eventos evaluables): {k0}/{n0} = "
          f"{100*k0/n0:.1f}%  IC95 [{100*lo0:.1f}% - {100*hi0:.1f}%]")

    s = eva[eva.sostenido == True]  # noqa: E712
    k1, n1 = s.real.sum(), len(s)
    if n1:
        lo1, hi1 = jeffreys(k1, n1)
        print(f"  precision CON la regla:                      {k1}/{n1} = "
              f"{100*k1/n1:.1f}%  IC95 [{100*lo1:.1f}% - {100*hi1:.1f}%]")
    perdidos = eva[(eva.sostenido == False) & eva.real]  # noqa: E712
    print(f"  eventos reales que la regla descarta (coste): "
          f"{len(perdidos)}/{int(k0)}")
    for f in perdidos.itertuples():
        print(f"    {f.id}  rodal {f.OBJECTID_12}  {f.sp:<24} "
              f"{int(f.anho_evento)}  fccarb {f.fccarb}")

    if len(ctrl):
        cs = ctrl[ctrl.sostenido.notna()]
        print(f"\n  cicatrices de 2018 (verdad documentada): "
              f"{int((cs.sostenido == True).sum())}/{len(cs)} sostenidas")  # noqa: E712

    # y sobre la comarca entera: que dejaria en pie la regla
    p = pd.read_csv(PROC / "metricas" / "persistencia_ifn.csv",
                    encoding="utf-8-sig")
    todos = p[p.estado == "evento"].copy()
    todos["sostenido"] = [sostenido(f.OBJECTID_12, f.anho_evento)
                          for f in todos.itertuples()]
    print(f"\nCOMARCA ENTERA ({len(todos)} eventos del detector):")
    print(f"  sostenidos: {int((todos.sostenido == True).sum())}"  # noqa: E712
          f"  rebotan: {int((todos.sostenido == False).sum())}"  # noqa: E712
          f"  sin t+1 aun: {int(todos.sostenido.isna().sum())}")
    por_anho = todos.groupby("anho_evento").sostenido.apply(
        lambda g: f"{int((g == True).sum())}/{len(g)}")  # noqa: E712
    print("  sostenidos por anho: " +
          "  ".join(f"{int(a)}:{v}" for a, v in por_anho.items()))
