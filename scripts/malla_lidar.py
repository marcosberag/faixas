"""Construye la malla de bloques LiDAR de 1x1 km y la cruza con las faixas.

El PNOA sirve el LiDAR en bloques de 1x1 km alineados a multiplos de 1000 m en
EPSG:25829. El nombre del fichero codifica la esquina NOROESTE en kilometros:

    PNOA-2024-GAL-558-4674-H29-NPC01.LAZ
                  |    |    |    +-- nivel de clasificacion
                  |    |    +------- huso 29 (EPSG:25829)
                  |    +------------ Y de la esquina NW / 1000
                  +----------------- X de la esquina NW / 1000

    -> cubre X [558000, 559000], Y [4673000, 4674000]

Comprobado empiricamente contra el buscador del CNIG: el punto (558500, 4673500)
devuelve la hoja 558-4674 y el punto (558500, 4672500) la 558-4673.

Salida: un GPKG con la malla recortada a los bloques que tocan faixa, ordenados
por superficie de faixa dentro. De ahi se eligen los bloques del prototipo.
"""
import argparse
import pathlib

import geopandas as gpd
import pandas as pd
import shapely
from shapely.geometry import box

RAIZ = pathlib.Path(__file__).resolve().parent.parent
PROC = RAIZ / "datos" / "procesado"

LADO = 1000  # m


def carga_faixas(zona="paradanta"):
    """Union de las dos capas de faixa, con la etiqueta de origen."""
    capas = []
    for nombre in ("nucleos", "illadas"):
        gdf = gpd.read_file(PROC / f"faixas_{nombre}_{zona}_ok.gpkg")
        capas.append(gdf.assign(capa=nombre))
    return gpd.GeoDataFrame(pd.concat(capas, ignore_index=True), crs=capas[0].crs)


def malla(bounds):
    """Malla de 1 km alineada a multiplos de 1000, cubriendo bounds."""
    xmin, ymin, xmax, ymax = bounds
    x0 = int(xmin // LADO) * LADO
    y0 = int(ymin // LADO) * LADO
    x1 = int(xmax // LADO) * LADO + LADO
    y1 = int(ymax // LADO) * LADO + LADO
    filas = []
    for x in range(x0, x1, LADO):
        for y in range(y0, y1, LADO):
            filas.append({
                # el nombre del fichero usa la esquina NW, o sea y + LADO
                "nw_x": x // 1000,
                "nw_y": (y + LADO) // 1000,
                "geometry": box(x, y, x + LADO, y + LADO),
            })
    return filas


def nombre_bloque(nw_x, nw_y, anho=2024, nivel="NPC01"):
    return f"PNOA-{anho}-GAL-{nw_x}-{nw_y}-H29-{nivel}.LAZ"


def interseca(rejilla, gdf, cols):
    """Hectareas de cada geometria de gdf dentro de cada celda de la rejilla.

    Equivale a gpd.overlay(rejilla, gdf, how="intersection") + area, pero sin
    su patologia de escala: overlay contra un multipoligono PROVINCIAL disuelto
    (medio millon de vertices en UNA geometria) deja el indice espacial inutil
    y cada celda paga la geometria entera. A escala de comarca daba igual; en
    Pontevedra son horas.

    Aqui se explota en piezas de una sola parte primero, asi el indice
    discrimina de verdad, y la interseccion va vectorizada en shapely 2.
    """
    piezas = gdf[cols + ["geometry"]].explode(index_parts=False).reset_index(drop=True)
    pares = gpd.sjoin(rejilla[["nw_x", "nw_y", "geometry"]],
                      piezas[["geometry"]], predicate="intersects", how="inner")
    if not len(pares):
        return pd.DataFrame(columns=["nw_x", "nw_y"] + cols + ["ha"])
    izq = rejilla.geometry.loc[pares.index].to_numpy()
    der = piezas.geometry.loc[pares.index_right].to_numpy()
    ha = shapely.area(shapely.intersection(izq, der)) / 1e4
    out = pares[["nw_x", "nw_y"]].reset_index(drop=True)
    for c in cols:
        out[c] = piezas[c].loc[pares.index_right].to_numpy()
    out["ha"] = ha
    return out[out.ha > 0]


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--zona", default="paradanta",
                    help="sufijo de faixas_{capa}_{zona}_ok.gpkg")
    args = ap.parse_args()
    faixas = carga_faixas(args.zona)
    print(f"faixas: {len(faixas)} registros, {faixas.geometry.area.sum()/1e4:,.0f} ha, "
          f"EPSG:{faixas.crs.to_epsg()}")
    print(f"extension: {[round(v) for v in faixas.total_bounds]}")

    rejilla = gpd.GeoDataFrame(malla(faixas.total_bounds), crs=faixas.crs)
    print(f"malla completa: {len(rejilla)} bloques de 1 km2")

    # superficie de faixa dentro de cada bloque, por capa y total. Se disuelve
    # por capa ANTES de trocear: dos parroquias vecinas solapan en el borde y
    # sumar sin disolver contaria ese solape dos veces.
    disuelto = faixas[["capa", "geometry"]].dissolve(by="capa").reset_index()
    corte = interseca(rejilla, disuelto, ["capa"])
    pivote = (corte.pivot_table(index=["nw_x", "nw_y"], columns="capa",
                                values="ha", aggfunc="sum", fill_value=0.0)
              .rename(columns={"nucleos": "ha_nucleos", "illadas": "ha_illadas"}))
    for c in ("ha_nucleos", "ha_illadas"):
        if c not in pivote:
            pivote[c] = 0.0
    pivote["ha_faixa"] = pivote["ha_nucleos"] + pivote["ha_illadas"]

    # concello dominante del bloque, para poder elegir con criterio. Ojo: al
    # trocear, una parroquia deja VARIAS filas en la misma celda; hay que
    # sumarlas antes de comparar o el dominante sale por trozo, no por total.
    conc = (interseca(rejilla, faixas, ["NOMECONCEL", "PARROQUIA"])
            .groupby(["nw_x", "nw_y", "NOMECONCEL", "PARROQUIA"], as_index=False)
            .ha.sum())
    dom = (conc.sort_values("ha", ascending=False)
           .groupby(["nw_x", "nw_y"])[["NOMECONCEL", "PARROQUIA"]].first())
    n_parr = conc.groupby(["nw_x", "nw_y"])["PARROQUIA"].nunique().rename("n_parroquias")

    tabla = (pivote.join(dom).join(n_parr)
             .sort_values("ha_faixa", ascending=False).reset_index())
    tabla["bloque"] = [nombre_bloque(r.nw_x, r.nw_y) for r in tabla.itertuples()]
    tabla["geometry"] = [box(x * 1000, (y - 1) * 1000, (x + 1) * 1000, y * 1000)
                         for x, y in zip(tabla.nw_x, tabla.nw_y)]
    tabla = gpd.GeoDataFrame(tabla, crs=faixas.crs)

    print(f"\nbloques que tocan faixa: {len(tabla)} "
          f"({100*len(tabla)/len(rejilla):.0f} % de la malla)")
    print(f"suma de faixa cubierta: {tabla['ha_faixa'].sum():,.0f} ha "
          f"(control: {faixas.geometry.area.sum()/1e4:,.0f} ha)")
    print(f"mediana de faixa por bloque: {tabla['ha_faixa'].median():.1f} ha")

    print("\ntop 12 por superficie de faixa:")
    cab = f"  {'bloque':<34} {'faixa':>7} {'nucleo':>7} {'illada':>7}  concello"
    print(cab)
    for r in tabla.head(12).itertuples():
        print(f"  {r.bloque:<34} {r.ha_faixa:>6.1f}h {r.ha_nucleos:>6.1f}h "
              f"{r.ha_illadas:>6.1f}h  {r.NOMECONCEL} / {r.PARROQUIA}")

    print("\ntop 5 por superficie de faixa de illadas:")
    for r in tabla.nlargest(5, "ha_illadas").itertuples():
        print(f"  {r.bloque:<34} {r.ha_faixa:>6.1f}h {r.ha_nucleos:>6.1f}h "
              f"{r.ha_illadas:>6.1f}h  {r.NOMECONCEL} / {r.PARROQUIA}")

    salida = PROC / f"malla_lidar_{args.zona}.gpkg"
    tabla.to_file(salida, driver="GPKG")
    tabla.drop(columns="geometry").to_csv(PROC / f"malla_lidar_{args.zona}.csv",
                                          index=False, encoding="utf-8")
    print(f"\n-> {salida.relative_to(RAIZ)}  (+ .csv)")

    # cuanto costaria la comarca entera, a 50,8 MB por bloque (dato del CNIG)
    mb = len(tabla) * 50.81
    print(f"\nescala: {len(tabla)} bloques x ~50,8 MB = {mb/1024:.1f} GB de LAZ")
