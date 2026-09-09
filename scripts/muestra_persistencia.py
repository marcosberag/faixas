"""Muestra para validar el detector de eventos contra la ortofoto historica.

El detector de `detecta_eventos.py` esta montado y SIN VALIDAR. Como todo en
este proyecto, no entra en el producto hasta contrastarlo con una verdad
independiente: aqui, la serie de ortofotos del PNOA historico (2010, 2014,
2017, 2020, 2023 — comprobado que son los anhos con vuelo en la zona) mas el
visual de Sentinel-2 de 2024 y 2026 para el tramo posterior al ultimo vuelo.
Que exista vuelo de 2010 es un regalo: es el anho de la etiqueta del IFN.

COMPOSICION, deliberada y no proporcional:
  - TODOS los eventos que no son de 2018 (los 2018 son las cicatrices de los
    incendios de octubre de 2017, con verdad documentada: de esos entran solo
    unos pocos como control positivo). Son pocos y son los que deciden si el
    detector vale, asi que se miran todos.
  - Una muestra de persistentes, cargada hacia los que tocan faixa, que son
    los que sostienen el 97,4 % del titular. Un persistente con corta visible
    en la serie es un falso negativo del detector... o un evento de 2010-2016,
    anterior a la serie S2: por eso el anotador pregunta EN QUE INTERVALO se
    ve el cambio, no solo si se ve.

MISMO PROTOCOLO CIEGO de siempre: el CSV lleva el veredicto del detector
(estado, anho_evento, caida) porque hace falta para la comparacion, pero el
HTML de anotacion NO lo ensenha. Los ids van barajados para que el orden no
delate la clase. Limitacion declarada: el anotador ya ha visto el mapa de
eventos y el panel del rodal 86265, asi que la ceguera es parcial en esos.

Uso:
    python scripts/muestra_persistencia.py
"""
import pathlib

import geopandas as gpd
import numpy as np
import pandas as pd

RAIZ = pathlib.Path(__file__).resolve().parent.parent
PROC = RAIZ / "datos" / "procesado"
VAL = PROC / "validacion_persistencia"

SEMILLA = 20260819
N_CONTROL_2018 = 6      # cicatrices de incendio documentadas: control positivo
N_PERSIS_FAIXA = 20
N_PERSIS_FUERA = 6
LADO_MIN, LADO_MAX = 240, 600   # m de encuadre, adaptado al tamanho del rodal

if __name__ == "__main__":
    rng = np.random.default_rng(SEMILLA)
    per = pd.read_csv(PROC / "metricas" / "persistencia_ifn.csv",
                      encoding="utf-8-sig")
    ifn = gpd.read_file(PROC / "ifn_especies_paradanta.gpkg")
    ifn = ifn.set_index("OBJECTID_12")

    d = per[per.estado.isin(("evento", "persistente"))].copy()
    d["en_faixa"] = d.ha_faixa > 0.01

    ev = d[d.estado == "evento"]
    ev_resto = ev[ev.anho_evento != 2018]
    ev_2018 = ev[ev.anho_evento == 2018]
    control = ev_2018.sample(N_CONTROL_2018, random_state=rng.integers(2**31))

    pe = d[d.estado == "persistente"]
    p_fx = pe[pe.en_faixa].sample(N_PERSIS_FAIXA,
                                  random_state=rng.integers(2**31))
    p_no = pe[~pe.en_faixa].sample(N_PERSIS_FUERA,
                                   random_state=rng.integers(2**31))

    m = pd.concat([ev_resto, control, p_fx, p_no], ignore_index=True)

    # encuadre y centro por rodal: punto representativo (siempre dentro) y lado
    # proporcional al tamanho, para que el rodal no sea ni una mota ni se salga
    geo = ifn.geometry.loc[m.OBJECTID_12]
    m["x"] = geo.representative_point().x.round(0).values
    m["y"] = geo.representative_point().y.round(0).values
    lado = 2.0 * np.sqrt(geo.area.values)
    m["lado"] = (np.clip(lado, LADO_MIN, LADO_MAX) // 20 * 20).astype(int)
    m["fccarb"] = ifn.FCCARB.loc[m.OBJECTID_12].values

    # barajar y numerar: el orden no puede delatar la clase
    m = m.sample(frac=1, random_state=rng.integers(2**31)).reset_index(drop=True)
    m.insert(0, "id", [f"v{i+1:03d}" for i in range(len(m))])

    cols = ["id", "OBJECTID_12", "sp", "fccarb", "x", "y", "lado",
            "ha_faixa", "en_faixa", "estado", "anho_evento", "caida"]
    VAL.mkdir(parents=True, exist_ok=True)
    m[cols].to_csv(VAL / "muestra.csv", index=False, encoding="utf-8-sig")

    print(f"{len(m)} rodales en la muestra (semilla {SEMILLA}):")
    print(f"  eventos no-2018 (todos):   {len(ev_resto):>3}")
    print(f"  eventos 2018 (control):    {len(control):>3} de {len(ev_2018)}")
    print(f"  persistentes en faixa:     {len(p_fx):>3} de {pe.en_faixa.sum()}")
    print(f"  persistentes fuera:        {len(p_no):>3} de {(~pe.en_faixa).sum()}")
    print(f"\neventos de la muestra por anho: "
          f"{m[m.estado=='evento'].anho_evento.value_counts().sort_index().to_dict()}")
    print(f"encuadres: {sorted(m.lado.unique())} m")
    print(f"-> {(VAL / 'muestra.csv').relative_to(RAIZ)}")
