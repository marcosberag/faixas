"""Compara la anotacion sobre ortofoto historica con el detector de eventos.

Se corre cuando datos/procesado/validacion_persistencia/anotacion.csv existe
(descargado del anotador y guardado EN ESA carpeta).

COMO SE COMPARA UN ANHO CON UN INTERVALO. El detector fecha el evento en el
verano t (la compuesta S2 donde aparece la caida), o sea que el cambio ocurrio
entre el verano t-1 y el t. Los vuelos del PNOA cortan el tiempo en 2010, 2014,
2017, 2020 y 2023, y de ahi a "hoy" lo cubren los visuales de Sentinel-2. Un
evento de anho t "cae" en el intervalo de vuelos que lo contiene; si t coincide
con un anho de vuelo (no se sabe si el vuelo fue antes o despues de la corta),
valen los dos intervalos que tocan ese borde.

QUE SE MIDE:
  - EVENTOS del detector: confirmado (el anotador ve reemplazo en un intervalo
    compatible), en_otro_intervalo (ve cambio pero en otra epoca), no_visto
    (el anotador dice que no hay reemplazo) y dudoso. La precision se calcula
    sin los dudosos, con IC de Jeffreys. Los controles de 2018 (cicatrices
    documentadas de los incendios de octubre de 2017) se reportan aparte:
    si fallan, el problema es del protocolo, no del detector.
  - PERSISTENTES del detector: un "si" del anotador SOLO cuenta como falso
    negativo si el cambio esta en 2017 o despues; un cambio en 2010-2017 es el
    hueco pre-Sentinel, que esta declarado y NO es fallo del detector — pero
    se contabiliza aparte porque si erosiona la etiqueta del IFN 2010.

Uso:
    python scripts/valida_persistencia.py
"""
import pathlib

import numpy as np
import pandas as pd
from scipy import stats

RAIZ = pathlib.Path(__file__).resolve().parent.parent
VAL = RAIZ / "datos" / "procesado" / "validacion_persistencia"

CORTES = (2010, 2014, 2017, 2020, 2023, 2100)
PRE_S2 = {"2010-2014", "2014-2017"}   # el hueco declarado, invisible para S2


def nombre(a, b):
    return f"{a}-{'hoy' if b == 2100 else b}"


def intervalos_esperados(t):
    t = int(t)
    return {nombre(a, b) for a, b in zip(CORTES, CORTES[1:]) if a <= t <= b}


def jeffreys(k, n):
    if n == 0:
        return (np.nan, np.nan)
    return (stats.beta.ppf(0.025, k + 0.5, n - k + 0.5),
            stats.beta.ppf(0.975, k + 0.5, n - k + 0.5))


def veredicto_evento(f):
    if f.respuesta == "dudoso":
        return "dudoso"
    if f.respuesta == "no":
        return "no_visto"
    vistos = set(f.intervalos.split("|")) if isinstance(f.intervalos, str) else set()
    return "confirmado" if vistos & intervalos_esperados(f.anho_evento) \
        else "en_otro_intervalo"


def veredicto_persistente(f):
    if f.respuesta == "dudoso":
        return "dudoso"
    if f.respuesta == "no":
        return "confirmado"
    vistos = set(f.intervalos.split("|")) if isinstance(f.intervalos, str) else set()
    return "evento_pre_s2" if vistos <= PRE_S2 else "falso_negativo"


if __name__ == "__main__":
    m = pd.read_csv(VAL / "muestra.csv", encoding="utf-8-sig")
    a = pd.read_csv(VAL / "anotacion.csv", encoding="utf-8-sig")
    d = m.merge(a, on="id", how="left", validate="1:1")
    sin = d.respuesta.isna().sum()
    if sin:
        raise SystemExit(f"faltan {sin} hojas por anotar: termina antes de validar")

    # ---- eventos -----------------------------------------------------------
    ev = d[d.estado == "evento"].copy()
    ev["veredicto"] = ev.apply(veredicto_evento, axis=1)
    control = ev[ev.anho_evento == 2018]
    resto = ev[ev.anho_evento != 2018]

    print("EVENTOS DEL DETECTOR contra el ojo sobre la serie historica")
    print(f"\n  controles de 2018 (cicatrices documentadas del 15-O de 2017):")
    for v, g in control.groupby("veredicto"):
        print(f"    {v:<18} {len(g)}")

    print(f"\n  el resto de eventos ({len(resto)}), que son los que deciden:")
    for v, g in resto.groupby("veredicto"):
        print(f"    {v:<18} {len(g):>3}   "
              f"({', '.join(g.id + '/' + g.anho_evento.astype(int).astype(str))})")

    util = resto[resto.veredicto != "dudoso"]
    k = (util.veredicto == "confirmado").sum()
    lo, hi = jeffreys(k, len(util))
    print(f"\n  PRECISION del detector (sin 2018, sin dudosos): "
          f"{k}/{len(util)} = {k/len(util):.1%}  IC95 [{lo:.1%} - {hi:.1%}]")

    ralos = util[util.fccarb < 50]
    if len(ralos):
        kr = (ralos.veredicto == "confirmado").sum()
        print(f"  en rodales ralos (FCCARB<50), la zona sospechosa: "
              f"{kr}/{len(ralos)} confirmados")
    post = util[util.anho_evento > 2024]
    if len(post):
        kp = (post.veredicto == "confirmado").sum()
        print(f"  avisos de vigencia (evento posterior al vuelo LiDAR): "
              f"{kp}/{len(post)} confirmados")

    # ---- persistentes ------------------------------------------------------
    pe = d[d.estado == "persistente"].copy()
    pe["veredicto"] = pe.apply(veredicto_persistente, axis=1)
    print(f"\nPERSISTENTES DEL DETECTOR ({len(pe)} en la muestra):")
    for v, g in pe.groupby("veredicto"):
        print(f"    {v:<18} {len(g):>3}   ({', '.join(g.id)})")

    util_p = pe[pe.veredicto != "dudoso"]
    fn = (util_p.veredicto == "falso_negativo").sum()
    lo_f, hi_f = jeffreys(fn, len(util_p))
    print(f"\n  FALSOS NEGATIVOS (cambio 2017+ que el detector no vio): "
          f"{fn}/{len(util_p)} = {fn/len(util_p):.1%}  IC95 [{lo_f:.1%} - {hi_f:.1%}]")
    pre = (util_p.veredicto == "evento_pre_s2").sum()
    print(f"  eventos del hueco 2010-2017 (no son fallo, pero erosionan la "
          f"etiqueta): {pre}/{len(util_p)}")

    # ---- que le hace esto al titular ---------------------------------------
    # el 97,4 % de persistencia en faixa se corrige con lo medido: los falsos
    # negativos se lo comen por abajo; la parte de eventos que eran falsos
    # positivos se lo devuelve por arriba. Cota deliberadamente pesimista.
    share_ev = 1 - 0.974
    lo_t = 0.974 * (1 - hi_f)
    hi_t = min(1.0, 0.974 + share_ev * (1 - lo))
    print(f"\n  el titular '97,4 % persistente en faixa' queda acotado en "
          f"[{lo_t:.1%} - {hi_t:.1%}]")
    print("  (pre-S2 aparte: esa erosion es de la etiqueta IFN, no del detector)")

    filas = pd.concat([ev, pe])[
        ["id", "OBJECTID_12", "estado", "anho_evento", "respuesta",
         "intervalos", "veredicto", "fccarb", "ha_faixa", "en_faixa"]]
    filas.to_csv(VAL / "veredictos.csv", index=False, encoding="utf-8-sig")
    print(f"\n-> {(VAL / 'veredictos.csv').relative_to(RAIZ)}")
