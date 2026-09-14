"""Cruza el IFN con las faixas: cuanto del arbolado detectado esta realmente prohibido.

Cierra el agujero que dejo la fase 2. El CHM dice «aqui hay algo alto»; la ley solo
prohibe 7 taxones arboreos y exime al resto (disp. ad. 3a.3). Sin separar una cosa
de otra, el ranking de parroquias no ordena lo que dice ordenar.

LA CLASIFICACION ES LITERAL, ESPECIE A ESPECIE
-----------------------------------------------
Nada de agrupar por genero ni por «perennifolia contra caducifolia», que es la
simplificacion que estuvo a punto de colarse en la fase 2 y es FALSA en los dos
sentidos:

  - `Pinus pinea` y `Pinus nigra` son pinos y NO estan en la lista. Agrupar por
    genero Pinus los prohibiria de mas.
  - `Quercus suber` (alcornoque) y `Laurus nobilis` (laurel) son perennifolias y
    SI estan exentas. El corte legal no es la fenologia, es la lista.
  - `Robinia pseudoacacia` se llama «falsa acacia» y no es una Acacia: es Robinia,
    no esta en la lista y esta EXENTA. El nombre comun enganha.

Por eso `LEGAL` enumera las 29 especies que aparecen en la comarca una por una, y
el script ABORTA si el IFN trae alguna que no este en el diccionario. Un `.get(sp,
False)` habria dejado que cualquier especie nueva entrase como exenta en silencio,
que es el error que mas caro sale: rebaja el incumplimiento sin avisar.

LA OCUPACION SE USA COMO FRACCION, NO COMO ETIQUETA
-----------------------------------------------------
412 de los 658 poligonos tienen dos o tres especies. `O1`,`O2`,`O3` son DECIMAS de
ocupacion (suman 8, 9 o 10, nunca 100). Un rodal con pino 6 y roble 3 no es «un
pinar»: es 2/3 prohibido. Se calcula

    frac_prohibida = suma(Oi de la lista) / suma(Oi)

y se aplica como factor continuo. Etiquetar el poligono por su especie dominante
inflaria el incumplimiento en los rodales mixtos, que aqui son la mayoria.

LO QUE ESTA CORRECCION NO ARREGLA
----------------------------------
El IFN4 de Galicia es de 2010 y el LiDAR de 2024: catorce anhos. El error no esta
repartido al azar, se concentra en el eucaliptal, que se corta a turno de 12-15
anhos. Y el IFN es cartografia de rodal: dentro de la faixa, que es una banda de
50 m pegada a las casas, la mezcla fina (un castanho de aldea en medio del pinar)
queda por debajo de su unidad minima. Ambas cosas van declaradas en la salida.

Uso:
    python scripts/especie_faixas.py
"""
import pathlib

import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio
from rasterio.errors import WindowError
from rasterio.features import rasterize
from rasterio.windows import Window, from_bounds
from shapely.geometry import box

RAIZ = pathlib.Path(__file__).resolve().parent.parent
PROC = RAIZ / "datos" / "procesado"
LIDAR = PROC / "lidar"
SALIDA = PROC / "metricas"

# Ley 3/2007, disposicion adicional tercera. True = prohibida en la faixa.
# Las 7 arboreas de la lista son: Pinus pinaster, P. sylvestris, P. radiata,
# Pseudotsuga menziesii, Acacia dealbata, A. melanoxylum y Eucalyptus spp.
LEGAL = {
    # --- de la lista ---------------------------------------------------
    "Pinus_pinaster": True,
    "Pinus_sylvestris": True,
    "Pinus_radiata": True,
    "Pseudotsuga_menziesii": True,
    "Acacia_dealbata": True,
    "Acacia_melanoxylon": True,      # la ley lo escribe «melanoxylum»
    "Eucalyptus_globulus": True,     # la lista dice «Eucalyptus spp»: todo el genero
    "Eucalyptus_nitens": True,
    "Eucalyptus_camaldulensis": True,
    "Acacia_spp": True,              # ver AMBIGUAS abajo
    # --- exentas por el punto 3 -----------------------------------------
    "Quercus_robur": False,
    "Quercus_suber": False,          # perennifolia, pero NO esta en la lista
    "Quercus_pyrenaica": False,
    "Quercus_rubra": False,
    "Castanea_sativa": False,
    "Betula_alba": False,
    "Betula_spp": False,
    "Alnus_glutinosa": False,
    "Salix_spp": False,
    "Salix_atrocinerea": False,
    "Fraxinus_angustifolia": False,
    "Corylus_avellana": False,
    "Acer_pseudoplatanus": False,
    "Acer_negundo": False,
    "Arbutus_unedo_": False,         # perennifolia y exenta
    "Laurus_nobilis": False,         # perennifolia y exenta
    "Platanus_hispanica": False,
    "Sambucus_nigra": False,
    "Robinia_pseudoacacia": False,   # «falsa acacia»: es Robinia, no Acacia
    # --- aparecen al salir de A Paradanta (IFN de la provincia entera) ----
    # Genero Eucalyptus: la lista dice «Eucalyptus spp», entra todo.
    "Eucalyptus_viminalis": True,
    "Eucalyptus_gomphocephalus": True,
    "Eucaliptus_spp": True,          # el IFN lo escribe asi, con una sola «p»
    "Mezcla_de_eucaliptos": True,
    # Coniferas que NO estan en la lista. La disposicion nombra tres pinos
    # (pinaster, sylvestris, radiata) y el pino de Oregon: ninguna otra.
    "Pinus_pinea": False,            # pino manso: NO listado
    "Picea_abies": False,
    "Chamaecyparis_lawsoniana": False,
    "Cupressus_arizonica": False,
    "Cupressus_macrocarpa": False,
    "Otras_coníferas": True,    # sin determinar: ver AMBIGUAS
    # Frondosas no listadas: exentas por el punto 3.
    "Acer_platanoides": False,
    "Crataegus_monogyna": False,
    "Fraxinus_excelsior": False,
    "Ilex_aquifolium": False,
    "Juglans_regia": False,
    "Populus_nigra": False,
    "Populus_x_canadensis": False,
    "Prunus_avium": False,
    "Prunus_spp": False,
    "Pyrus_spp": False,
    "Salix_alba": False,
    "Salix_caprea": False,
}

# especies cuya adscripcion es discutible; se recalcula todo sin ellas para ver
# si mueven algo. `Acacia_spp` sin determinar: la ley solo lista dealbata y
# melanoxylum, pero en Galicia esas dos son practicamente todas las acacias, asi
# que contarla como prohibida es lo que haria un inspector.
# `Otras_coníferas` es la misma situacion en la provincia: una conifera sin
# determinar puede ser radiata, sylvestris o pino de Oregon (listadas) o un
# cipres o una picea (exentas). Se cuenta como prohibida porque el error caro
# aqui es el falso negativo —saltarse un pinar— y el mecanismo de AMBIGUAS
# permite ver cuanto mueve.
AMBIGUAS = ("Acacia_spp", "Otras_coníferas")


def frac_prohibida(g, ambiguas_prohibidas=True):
    """Fraccion de la ocupacion arborea que corresponde a especies de la lista."""
    num = np.zeros(len(g))
    den = np.zeros(len(g))
    for i in (1, 2, 3):
        sp = g[f"NOMBRE_SP{i}"].fillna("").str.strip()
        oc = g[f"O{i}"].fillna(0).to_numpy(float)
        mal = np.array([
            LEGAL[s] and (ambiguas_prohibidas or s not in AMBIGUAS)
            for s in sp.where(sp != "", "Quercus_robur")   # relleno inocuo: oc=0
        ])
        num += np.where(sp.to_numpy() != "", oc * mal, 0)
        den += np.where(sp.to_numpy() != "", oc, 0)
    return np.divide(num, den, out=np.zeros_like(num), where=den > 0)


def comprueba_catalogo(g):
    sp = pd.concat([g[f"NOMBRE_SP{i}"] for i in (1, 2, 3)]).fillna("").str.strip()
    faltan = sorted({s for s in sp.unique() if s and s not in LEGAL})
    if faltan:
        raise SystemExit(
            "el IFN trae especies que no estan clasificadas en LEGAL:\n  "
            + "\n  ".join(faltan)
            + "\n\nNo se clasifican solas. Hay que mirarlas una a una contra la\n"
              "disposicion adicional tercera y anhadirlas al diccionario. Dejarlas\n"
              "caer como exentas por defecto rebajaria el incumplimiento en silencio.")


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--zona", default="paradanta",
                    help="sufijo de las capas de la zona")
    args = ap.parse_args()
    # vacio para la zona piloto: los CSV que ya consumen ranking_final.py y el
    # visor no cambian de nombre
    suf = "" if args.zona == "paradanta" else f"_{args.zona}"
    ifn = gpd.read_file(PROC / f"ifn_especies_{args.zona}.gpkg")
    comprueba_catalogo(ifn)
    ifn["f_mal"] = frac_prohibida(ifn)
    ifn["f_mal_sin_amb"] = frac_prohibida(ifn, ambiguas_prohibidas=False)
    ifn["ha"] = ifn.geometry.area / 1e4

    print(f"IFN4 2010: {len(ifn)} poligonos, {ifn.ha.sum():,.0f} ha\n")
    print("composicion del MONTE de la comarca (toda la superficie del IFN):")
    tot = ifn.ha.sum()
    print(f"  de la lista (prohibida) {(ifn.f_mal * ifn.ha).sum():>9,.0f} ha  "
          f"({100*(ifn.f_mal*ifn.ha).sum()/tot:>5.1f} %)")
    print(f"  exenta                  {((1-ifn.f_mal) * ifn.ha).sum():>9,.0f} ha  "
          f"({100*((1-ifn.f_mal)*ifn.ha).sum()/tot:>5.1f} %)")

    # ---- 1. contraste contra lo que se anoto a ojo -------------------------
    # De aqui sale p_mal_d, la cota ALTA del arbolado disperso (seccion 3). Cada
    # zona la toma de SU muestra anotada, igual que ranking_final.py toma su tasa
    # de FP: hasta el 14-09-2026 se leia siempre la del piloto, y Pontevedra
    # heredaba en silencio el 72,2 % de A Paradanta (con su propia muestra sale
    # 78,0 %). Sin muestra propia se usa la del piloto, pero avisando.
    val = PROC / ("validacion" if args.zona == "paradanta"
                  else f"validacion_{args.zona}")
    if not (val / "anotacion.csv").exists():
        print(f"\nAVISO: no hay {val.name}/anotacion.csv. La cota alta del disperso"
              "\n  sale de la muestra del PILOTO (A Paradanta), que no es de esta zona.")
        val = PROC / "validacion"
    print(f"\nmuestra anotada para el contraste y la cota del disperso: {val.name}/")
    m = pd.read_csv(val / "muestra.csv", encoding="utf-8-sig")
    a = pd.read_csv(val / "anotacion.csv")
    d = m.merge(a, on="id", validate="one_to_one")
    pts = gpd.GeoDataFrame(d, geometry=gpd.points_from_xy(d.x, d.y),
                           crs=ifn.crs)
    cru = gpd.sjoin(pts, ifn[["NOMBRE_SP1", "f_mal", "FCCARB", "geometry"]],
                    how="left", predicate="within")
    cru = cru[~cru.index.duplicated(keep="first")]

    dentro = cru.NOMBRE_SP1.notna()
    print(f"\nCRUCE CON LA MUESTRA: {int(dentro.sum())} de {len(cru)} puntos caen "
          "dentro de un rodal del IFN")
    arb = cru[(cru.clase == "arbol") & dentro]
    print(f"  de los {int((cru.clase == 'arbol').sum())} anotados como arbol, "
          f"{len(arb)} tienen especie del IFN")
    if len(arb):
        w = arb.peso_m2.to_numpy()
        print(f"  ponderado por superficie: {100*np.average(arb.f_mal, weights=w):.1f} % "
              "de ese arbolado es especie PROHIBIDA")
        print("\n  especie principal donde tu anotaste arbol:")
        for k, v in (arb.assign(ha=arb.peso_m2 / 1e4).groupby("NOMBRE_SP1")
                     .ha.sum().sort_values(ascending=False).head(8).items()):
            print(f"    {k:<28} {v:>6.1f} ha  "
                  f"{'PROHIBIDA' if LEGAL[k.strip()] else 'exenta'}")

    # el unico contraste posible con la fotointerpretacion: los 10 «frondosa»
    fro = cru[(cru.clase == "arbol") & (cru.tipo == "frondosa") & dentro]
    if len(fro):
        ok = int((fro.f_mal < 0.5).sum())
        print(f"\n  control: de los {len(fro)} puntos que anotaste «frondosa "
              f"caducifolia», el IFN da especie mayoritariamente exenta en {ok}.")
        if ok < len(fro):
            print("    Los que no cuadran son rodales mixtos o cambio desde 2010;")
            print("    con esta n no se puede concluir mas que eso.")

    # ---- 2. la faixa contra el monte --------------------------------------
    faixas = []
    for nombre in ("nucleos", "illadas"):
        f = gpd.read_file(PROC / f"faixas_{nombre}_{args.zona}_ok.gpkg")
        faixas.append(f.assign(capa=nombre))
    faixas = gpd.GeoDataFrame(pd.concat(faixas, ignore_index=True), crs=ifn.crs)

    # el dissolve es necesario (nucleos e illadas se solapan y duplicarian
    # superficie), pero el overlay contra el multipoligono disuelto ENTERO es la
    # trampa de escala de la fase 7: en la provincia son ~500k vertices, el
    # indice espacial no filtra nada y cada rodal paga la geometria completa
    # (horas). Troceado en piezas de una parte, cada interseccion es local y el
    # dissolve posterior por rodal recompone exactamente el resultado de antes.
    piezas = (faixas[["geometry"]].dissolve()
              .explode(index_parts=False).reset_index(drop=True))
    # la union provincial suelta esquirlas de linea/punto donde dos poligonos
    # casi se tocan; overlay rechaza tipos mixtos y su area es cero: fuera
    piezas = piezas[piezas.geometry.geom_type == "Polygon"].reset_index(drop=True)
    inter = gpd.overlay(
        ifn[["f_mal", "f_mal_sin_amb", "NOMBRE_SP1", "geometry"]]
        .reset_index(names="rid"), piezas, how="intersection")
    inter = (inter.dissolve(by="rid", aggfunc={
        "f_mal": "first", "f_mal_sin_amb": "first", "NOMBRE_SP1": "first"})
        .reset_index(drop=True))
    inter["ha"] = inter.geometry.area / 1e4
    tf = inter.ha.sum()
    print(f"\nDENTRO DE LA FAIXA: {tf:,.0f} ha de rodal del IFN")
    print(f"  de la lista (prohibida) {(inter.f_mal * inter.ha).sum():>8,.0f} ha  "
          f"({100*(inter.f_mal*inter.ha).sum()/tf:>5.1f} %)")
    print(f"  exenta                  {((1-inter.f_mal) * inter.ha).sum():>8,.0f} ha  "
          f"({100*((1-inter.f_mal)*inter.ha).sum()/tf:>5.1f} %)")
    d_amb = 100 * ((inter.f_mal - inter.f_mal_sin_amb) * inter.ha).sum() / tf
    print(f"  sensibilidad a las especies ambiguas ({', '.join(AMBIGUAS)}): "
          f"{d_amb:+.2f} pp")

    print("\n  especie principal dentro de la faixa:")
    for k, v in (inter.groupby("NOMBRE_SP1").ha.sum()
                 .sort_values(ascending=False).head(10).items()):
        print(f"    {k:<28} {v:>7.0f} ha ({100*v/tf:>5.1f} %)  "
              f"{'PROHIBIDA' if LEGAL[k.strip()] else 'exenta'}")

    inter.to_file(PROC / f"ifn_en_faixa_{args.zona}.gpkg", driver="GPKG")

    # ---- 3. el arbolado que el IFN no cartografia --------------------------
    # el IFN mapea monte arbolado, no arboles sueltos. Dentro de la faixa —una
    # banda de 50 m pegada a las casas— eso deja fuera justo el arbolado de
    # aldea y de ribera, que es donde vive la frondosa exenta
    cru["en_ifn"] = dentro
    arbo = cru[cru.clase == "arbol"]
    ha_d = arbo[arbo.en_ifn].peso_m2.sum() / 1e4
    ha_f = arbo[~arbo.en_ifn].peso_m2.sum() / 1e4
    p_mal_d = np.average(arbo[arbo.en_ifn].f_mal,
                         weights=arbo[arbo.en_ifn].peso_m2)
    print(f"\nEL ARBOLADO QUE EL IFN NO VE")
    print(f"  dentro de rodal  {ha_d:>5.1f} ha ({100*ha_d/(ha_d+ha_f):>4.1f} %) — "
          f"{100*p_mal_d:.1f} % prohibida, medido")
    print(f"  fuera de rodal   {ha_f:>5.1f} ha ({100*ha_f/(ha_d+ha_f):>4.1f} %) — "
          "composicion NO medida")
    tip = arbo[~arbo.en_ifn]
    tip = tip[tip.tipo.isin(("frondosa", "pino", "eucalipto", "acacia"))]
    if len(tip):
        print(f"    indicio: de los {len(tip)} puntos de fuera de rodal que si "
              f"llevan tipo, {int((tip.tipo == 'frondosa').sum())} son frondosa.")
        print("    Es n pequenha y fotointerpretada, pero apunta a que el arbolado")
        print("    disperso tiene MAS exenta que el monte. No se usa como cifra.")

    lo = 100 * (ha_d * p_mal_d) / (ha_d + ha_f)          # el disperso, todo exento
    hi = 100 * p_mal_d                                    # el disperso, igual que el monte
    print(f"\n  => del arbolado detectado en faixa, entre el {lo:.0f} % y el "
          f"{hi:.0f} % es especie PROHIBIDA")
    print(f"     (cota baja: todo el disperso exento; cota alta: el disperso se")
    print(f"      comporta como el monte. La verdad esta dentro, no se sabe donde)")
    print(f"     y por tanto el indicador de la fase 2 sobrestima el incumplimiento")
    print(f"     entre un {100/hi*100-100:.0f} % y un {100/lo*100-100:.0f} %.")

    # ---- 4. indicador corregido por parroquia ------------------------------
    print("\nRECALCULANDO EL RANKING con la correccion de especie...", flush=True)
    cal = pd.read_csv(PROC / "validacion" / "calibracion_resumen.csv",
                      encoding="utf-8-sig").iloc[0]
    u = float(cal.umbral_youden_m)
    faixas["faixa_id"] = [f"{c[:3]}-{i}" for i, c in enumerate(faixas.capa)]

    filas = []
    malla = PROC / f"malla_lidar_{args.zona}.csv"
    quiero = ({b.replace(".LAZ", "_chm.tif") for b in pd.read_csv(malla).bloque}
              if malla.exists() else None)
    for chm_path in sorted(LIDAR.glob("*_chm.tif")):
        if quiero is not None and chm_path.name not in quiero:
            continue
        with rasterio.open(chm_path) as src:
            rec = box(*src.bounds)
            area_px = src.res[0] * src.res[1]
            for _, f in faixas[faixas.intersects(rec)].iterrows():
                trozo = f.geometry.intersection(rec)
                if trozo.is_empty or trozo.area < area_px:
                    continue
                ven = from_bounds(*trozo.bounds, transform=src.transform)
                ven = ven.round_offsets().round_lengths()
                try:
                    ven = ven.intersection(Window(0, 0, src.width, src.height))
                except WindowError:
                    # trozo que roza el borde: ventana de 0 filas/columnas
                    # (<1 pixel; el bloque vecino mide ese trozo entero)
                    continue
                if ven.width < 1 or ven.height < 1:
                    continue
                dat = src.read(1, window=ven, masked=True)
                tr = src.window_transform(ven)
                msk = rasterize([(trozo, 1)], out_shape=dat.shape, transform=tr,
                                fill=0, all_touched=False, dtype="uint8").astype(bool)
                val = msk & ~np.ma.getmaskarray(dat)
                alto = val & (np.asarray(dat) > u)
                if not alto.any():
                    continue
                # fraccion prohibida del IFN, rasterizada a la misma rejilla
                cerca = ifn[ifn.intersects(trozo)]
                fmal = (rasterize([(g, v) for g, v in
                                   zip(cerca.geometry, cerca.f_mal)],
                                  out_shape=dat.shape, transform=tr, fill=0.0,
                                  all_touched=False, dtype="float32")
                        if len(cerca) else np.zeros(dat.shape, "float32"))
                hay = (rasterize([(g, 1) for g in cerca.geometry],
                                 out_shape=dat.shape, transform=tr, fill=0,
                                 all_touched=False, dtype="uint8").astype(bool)
                       if len(cerca) else np.zeros(dat.shape, bool))
                filas.append({
                    "concello": f.NOMECONCEL, "parroquia": f.PARROQUIA,
                    "ha_faixa": val.sum() * area_px / 1e4,
                    "ha_arbolado": alto.sum() * area_px / 1e4,
                    "ha_en_rodal": (alto & hay).sum() * area_px / 1e4,
                    "ha_prohibida": float(fmal[alto].sum()) * area_px / 1e4,
                })

    det = pd.DataFrame(filas)
    agg = det.groupby(["concello", "parroquia"], as_index=False).sum(numeric_only=True)
    agg["ha_dispersa"] = agg.ha_arbolado - agg.ha_en_rodal
    agg["ha_prohibida_hi"] = agg.ha_prohibida + agg.ha_dispersa * p_mal_d
    for c, n in (("ha_arbolado", "pct_arbolado"), ("ha_prohibida", "pct_prohibida_lo"),
                 ("ha_prohibida_hi", "pct_prohibida_hi")):
        agg[n] = (100 * agg[c] / agg.ha_faixa).round(2)
    agg = agg.sort_values("ha_prohibida", ascending=False)
    SALIDA.mkdir(parents=True, exist_ok=True)
    agg.round(3).to_csv(SALIDA / f"metricas_parroquia_especie{suf}.csv", index=False,
                        encoding="utf-8-sig")

    T = agg[["ha_faixa", "ha_arbolado", "ha_prohibida", "ha_prohibida_hi"]].sum()
    print(f"\n  sobre {T.ha_faixa:.0f} ha de faixa medida:")
    print(f"    arbolado > {u:g} m          {T.ha_arbolado:>6.1f} ha "
          f"({100*T.ha_arbolado/T.ha_faixa:>5.1f} %)")
    print(f"    de especie prohibida    {T.ha_prohibida:>6.1f} a "
          f"{T.ha_prohibida_hi:.1f} ha ({100*T.ha_prohibida/T.ha_faixa:.1f} a "
          f"{100*T.ha_prohibida_hi/T.ha_faixa:.1f} %)")

    print(f"\n  {'parroquia':<34}{'faixa':>7}{'arbol':>7}{'prohib.':>9}{'% faixa':>9}")
    for _, r in agg.head(10).iterrows():
        print(f"  {r.parroquia[:32]:<34}{r.ha_faixa:>6.1f}h{r.ha_arbolado:>6.1f}h"
              f"{r.ha_prohibida:>7.1f}-{r.ha_prohibida_hi:<4.0f}"
              f"{r.pct_prohibida_lo:>6.1f}-{r.pct_prohibida_hi:<4.0f}")

    # ---- 5. lo que de verdad justifica la fase: el orden cambia -----------
    agg["r_bruto"] = agg.pct_arbolado.rank(ascending=False).astype(int)
    agg["r_corr"] = agg.pct_prohibida_lo.rank(ascending=False).astype(int)
    rho = agg.pct_arbolado.corr(agg.pct_prohibida_lo, method="spearman")
    mueve = int((agg.r_bruto != agg.r_corr).sum())
    print(f"\nEL RANKING NO SOLO SE ESCALA, SE REORDENA")
    print(f"  {'parroquia':<32}{'% arbol':>9}{'% prohib':>10}{'puesto':>10}")
    for _, r in agg.sort_values("r_bruto").iterrows():
        flecha = (f"{r.r_bruto} -> {r.r_corr}"
                  + ("" if r.r_bruto == r.r_corr else f" ({r.r_bruto-r.r_corr:+d})"))
        print(f"  {r.parroquia[:30]:<32}{r.pct_arbolado:>8.1f}%"
              f"{r.pct_prohibida_lo:>9.1f}%{flecha:>13}")
    print(f"\n  Spearman entre los dos ordenes: {rho:.2f} · "
          f"cambian de puesto {mueve} de {len(agg)}")
    print("  Con esta n (pocas parroquias, solo los bloques ya procesados) la cifra")
    print("  es indicativa. Lo que no es indicativo es la direccion: mandar a un")
    print("  inspector por el indicador sin corregir lo manda al sitio equivocado.")

    print(f"\n-> {(PROC / f'ifn_en_faixa_{args.zona}.gpkg').relative_to(RAIZ)}")
    print(f"-> {(SALIDA / f'metricas_parroquia_especie{suf}.csv').relative_to(RAIZ)}")
