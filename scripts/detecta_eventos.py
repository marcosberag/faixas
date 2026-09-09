"""Detector de eventos de dosel por rodal del IFN, sobre la serie anual de NDVI.

Segunda pieza de la fase de persistencia. Logica: los arboles no cambian de
especie, asi que la etiqueta del IFN 2010 sigue valiendo hoy en los rodales que
NO han sufrido un evento de reemplazo. Este script decide, rodal a rodal, si la
serie 2017-2026 muestra ese evento.

EFECTO-ANHO DESCONTADO (v1.1): un verano seco baja el NDVI de TODA la zona a
la vez (2026: mediana 0,746 contra 0,79 tipico) y en los rodales ralos, donde
manda la hierba, eso dispara falsos eventos — se cazo uno mirando el panel del
rodal 86265: agosto marron, no corta. Antes de detectar se resta a cada anho la
anomalia de la mediana de zona. Una corta de verdad cae ADEMAS de lo que caiga
la zona, asi que la senal buena sobrevive a la correccion.

REGLA DE DETECCION (v1.1, deliberadamente simple y declarada):
    hay evento en el anho t si
        ndvi_t <= max(ndvi de los 2 anhos previos con dato) - 0.18
        y ademas ndvi_t < 0.60
    El dosel maduro aqui esta en 0,80-0,85; una corta baja la media del rodal
    muy por debajo de 0,60 salvo que sea parcial. Se exige tambien el suelo
    absoluto para que un anho nublado raro no dispare falsos eventos. El max
    de dos anhos previos resiste una compuesta mala aislada.

LO QUE NO VE, y queda declarado:
  - cortas PARCIALES de menos de ~un tercio del rodal (la media se diluye);
  - eventos de 2010-2016 (la serie S2 empieza en 2017): ese hueco se tapa con
    ortofoto historica del PNOA, no con esto;
  - y ninguna deteccion entra en el ranking hasta VALIDARLA contra ortofoto.

LA ASIMETRIA DEL EUCALIPTO: rebrota de cepa. Un eucaliptal cortado vuelve a ser
eucaliptal sin que nadie plante. Por eso un evento invalida sobre todo etiquetas
de NO-eucalipto (un pinar cortado en Galicia se replanta a menudo a eucalipto):
  - etiqueta eucalipto + evento  -> sigue prohibida (rebrote), y ojo VIGENCIA
  - etiqueta otra + evento       -> especie DESCONOCIDA desde el evento
Los eventos de 2025-2026 (posteriores al vuelo LiDAR de jun-jul 2024) son otra
cosa: el arbolado del ranking puede YA no estar. Se listan aparte como aviso de
vigencia, que es la parte de servicio de vigilancia.

Uso:
    python scripts/detecta_eventos.py
"""
import argparse
import pathlib
import sys

import geopandas as gpd
import shapely
import numpy as np
import pandas as pd

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from especie_faixas import LEGAL  # noqa: E402  la lista legal, especie a especie

RAIZ = pathlib.Path(__file__).resolve().parent.parent
PROC = RAIZ / "datos" / "procesado"

CAIDA_MIN = 0.18     # cuanto tiene que caer el NDVI respecto al techo previo
SUELO = 0.60         # y por debajo de que valor absoluto tiene que quedar
MIN_ANHOS = 6        # anhos con dato para opinar
MIN_PX = 6           # celdas de 10 m: por debajo, el rodal es una esquirla
ANHO_LIDAR = 2024

def ha_en_faixa(ifn, faixas):
    """Hectareas de cada rodal dentro de faixa, SIN disolver las faixas.

    Dos trampas juntas:

    1. `faixas.union_all()` y luego intersecar rodal a rodal es la trampa de
       escala ya medida tres veces en este proyecto: un multipoligono provincial
       de medio millon de vertices deja el indice espacial inutil y cada rodal
       paga la geometria entera. Se trocea y se cruza con sjoin.
    2. Pero NO se pueden sumar las areas de interseccion pieza a pieza: las
       capas de nucleos y de illadas SE SOLAPAN, y sumar contaria dos veces la
       zona comun. Por eso se unen antes las (pocas) piezas que tocan cada
       rodal, y se interseca contra esa union.
    """
    piezas = faixas.explode(index_parts=False).reset_index(drop=True)
    piezas = piezas[piezas.geometry.notna() & ~piezas.geometry.is_empty]
    geoms = piezas.geometry.values

    izq = ifn[["geometry"]].reset_index(drop=True).reset_index(names="i_rod")
    par = gpd.sjoin(izq, gpd.GeoDataFrame(geometry=piezas.geometry,
                                          crs=ifn.crs),
                    predicate="intersects", how="inner")
    ha = np.zeros(len(ifn))
    if par.empty:
        return ha
    rod = ifn.geometry.values
    for i, grupo in par.groupby("i_rod"):
        trozo = shapely.union_all(geoms[grupo.index_right.values])
        ha[i] = shapely.intersection(rod[i], trozo).area / 1e4
    return ha


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--zona", default="paradanta")
    args = ap.parse_args()
    suf = "" if args.zona == "paradanta" else "_" + args.zona

    serie = pd.read_csv(PROC / "s2" / f"serie_ndvi_rodal{suf}.csv",
                        encoding="utf-8-sig")
    anhos = sorted(int(c[5:]) for c in serie.columns if c.startswith("ndvi_"))
    ifn = gpd.read_file(PROC / f"ifn_especies_{args.zona}.gpkg")

    # hectareas de cada rodal DENTRO de faixa: es el peso que importa
    faixas = gpd.GeoDataFrame(pd.concat(
        [gpd.read_file(PROC / f"faixas_{n}_{args.zona}_ok.gpkg")
         for n in ("nucleos", "illadas")], ignore_index=True), crs=ifn.crs)
    ifn["ha_faixa"] = ha_en_faixa(ifn, faixas)

    d = serie.merge(ifn[["OBJECTID_12", "ha_faixa"]], on="OBJECTID_12")
    d["prohibida"] = d.sp.map(LEGAL)
    if d.prohibida.isna().any():
        raise SystemExit("especie sin clasificar en LEGAL: " +
                         ", ".join(d[d.prohibida.isna()].sp.unique()))
    d["es_euca"] = d.sp.str.startswith("Eucalyptus")

    # efecto-anho: anomalia de la mediana de zona (mediana entre rodales)
    med_anho = {a: d[f"ndvi_{a}"].median() for a in anhos}
    base_zona = float(np.median(list(med_anho.values())))
    print("efecto-anho descontado (anomalia de la mediana de zona):")
    print("  " + "  ".join(f"{a}:{med_anho[a]-base_zona:+.3f}" for a in anhos))
    print()

    filas = []
    for f in d.itertuples():
        v = np.array([getattr(f, f"ndvi_{a}") - (med_anho[a] - base_zona)
                      for a in anhos], dtype=float)
        con_dato = np.isfinite(v)
        if f.n_px < MIN_PX or con_dato.sum() < MIN_ANHOS:
            filas.append({"estado": "sin_dato", "anho_evento": None,
                          "caida": np.nan})
            continue
        evento, caida_max = None, 0.0
        for i in range(1, len(anhos)):
            if not con_dato[i]:
                continue
            previos = v[:i][con_dato[:i]][-2:]
            if not len(previos):
                continue
            caida = previos.max() - v[i]
            caida_max = max(caida_max, caida)
            if caida >= CAIDA_MIN and v[i] < SUELO and evento is None:
                evento = anhos[i]
        filas.append({"estado": "evento" if evento else "persistente",
                      "anho_evento": evento, "caida": round(caida_max, 3)})

    r = pd.concat([d, pd.DataFrame(filas)], axis=1)

    # que le pasa a la ETIQUETA de especie con el evento (asimetria del rebrote)
    def etiqueta(f):
        if f.estado != "evento":
            return "ifn_2010" if f.estado == "persistente" else "sin_serie"
        return "prohibida_rebrote" if f.es_euca else "desconocida"
    r["etiqueta"] = r.apply(etiqueta, axis=1)

    cols = ["OBJECTID_12", "sp", "prohibida", "n_px", "ha_faixa",
            "estado", "anho_evento", "caida", "etiqueta"]
    r[cols].round(3).to_csv(PROC / "metricas" / f"persistencia_ifn{suf}.csv",
                            index=False, encoding="utf-8-sig")

    en_fx = r[r.ha_faixa > 0.01]
    W = en_fx.ha_faixa.sum()
    print(f"{len(r)} rodales; {len(en_fx)} tocan faixa ({W:.0f} ha de rodal en faixa)\n")
    print("PERSISTENCIA, ponderada por hectareas de rodal dentro de faixa:")
    for est, g in en_fx.groupby("estado"):
        print(f"  {est:<12} {len(g):>4} rodales  {g.ha_faixa.sum():>7.1f} ha "
              f"({100*g.ha_faixa.sum()/W:.1f} %)")

    ev = en_fx[en_fx.estado == "evento"].sort_values("ha_faixa", ascending=False)
    if len(ev):
        print(f"\nEVENTOS por anho (rodales en faixa):")
        for a, g in ev.groupby("anho_evento"):
            print(f"  {int(a)}: {len(g):>3} rodales, {g.ha_faixa.sum():>6.1f} ha en faixa")

        mueve = ev[~ev.es_euca]
        print(f"\nimpacto sobre la ETIQUETA de especie:")
        print(f"  a DESCONOCIDA (no eucalipto cortado): {len(mueve)} rodales, "
              f"{mueve.ha_faixa.sum():.1f} ha en faixa")
        print(f"  rebrote de eucalipto (sigue prohibida): {len(ev)-len(mueve)} "
              f"rodales, {ev[ev.es_euca].ha_faixa.sum():.1f} ha en faixa")

        post = ev[ev.anho_evento > ANHO_LIDAR]
        if len(post):
            print(f"\nAVISO DE VIGENCIA — eventos POSTERIORES al vuelo LiDAR de {ANHO_LIDAR}:")
            print("  el arbolado que el ranking cuenta ahi puede YA no estar en pie:")
            for f in post.itertuples():
                print(f"    rodal {f.OBJECTID_12}  {f.sp:<24} {int(f.anho_evento)}  "
                      f"{f.ha_faixa:>5.1f} ha en faixa  caida {f.caida:.2f}")

    print("\nNADA de esto entra en el ranking todavia: primero se valida una")
    print("muestra de eventos y de persistentes contra la ortofoto historica")
    print("del PNOA, como todo lo demas en este proyecto.")
    print(f"-> datos/procesado/metricas/persistencia_ifn.csv")
