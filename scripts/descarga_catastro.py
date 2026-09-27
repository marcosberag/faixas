"""Huellas de edificio del Catastro (INSPIRE WFS) para la zona de faixas.

Para filtrar los falsos positivos de edificacion en las copas: un tejado a dos
aguas pasa el umbral de 5,5 m del CHM y el watershed lo delinea como "copa"
(se cazo uno de 229 m2 sobre una casa de 238 m2 de huella). La tasa de FP ya
los descuenta en agregado; esto los quita del mapa y de la fraccion de especie
del disperso, que es donde ensucian.

WFS INSPIRE de Catastro (BU:Building), por celdas de 1x1 km que tocan faixa,
en EPSG:25829 directo. Reanudable por celda. Salida unica deduplicada:
datos/procesado/edificios_catastro.gpkg

Las celdas que el WFS rechaza por tamano (las urbanas densas: "Area of
extension out of limits", o respuesta gigante que agota el timeout) se
resuelven solas: se trocean en 4 cuadrantes de 500 m y se concatenan; un
cuadrante que todavia desborda se vuelve a trocear (500 -> 250 -> 125 m).
Verificado en toda Pontevedra: 3.197/3.197 celdas, 243.583 edificios, cero
perdidos por descarga.

Uso:
    python scripts/descarga_catastro.py
"""
import io
import argparse
import pathlib
import time

import geopandas as gpd
import pandas as pd
import requests
from shapely.geometry import box

RAIZ = pathlib.Path(__file__).resolve().parent.parent
PROC = RAIZ / "datos" / "procesado"
CELDAS = PROC / "catastro_celdas"

URL = "http://ovc.catastro.meh.es/INSPIRE/wfsBU.aspx"
LADO = 1000        # celda de trabajo: 1x1 km (el WFS rechaza bbox de 2x2 km)
QUADRANTE = 500    # lado al que se trocea una celda que desborda
MIN_LADO = 125     # por debajo, un cuadrante que desborda se da por vacio
PAUSA = 12         # s entre peticiones al WFS (rate limit de Catastro)


VACIA = gpd.GeoDataFrame(geometry=[], crs="EPSG:25829")


class _Desborde(Exception):
    """El WFS rechaza el bbox: 'Area of extension out of limits'."""


def baja_bbox(x0, y0, lado, intentos=4):
    """Un bbox de `lado` m, o None si el servicio no responde tras `intentos`.

    Devuelve None en vez de propagar: el WFS del Catastro es un servicio publico
    y bajo carga da ReadTimeout. Que un timeout tumbe una corrida de horas es
    absurdo teniendo reanudacion — la celda se salta, NO se escribe su GPKG, y
    la siguiente pasada la reintenta.

    OJO: el ExceptionReport del servicio no distingue celda vacia de bbox
    desbordada. 'Area of extension out of limits' es el mensaje de desborde y
    eleva _Desborde; el resto se trata como celda sin edificios.
    """
    for t in range(1, intentos + 1):
        try:
            r = requests.get(URL, timeout=120, params={
                "service": "WFS", "version": "2.0.0", "request": "GetFeature",
                "typeNames": "BU:Building", "srsName": "EPSG::25829",
                "bbox": f"{x0},{y0},{x0+lado},{y0+lado},"
                        "urn:ogc:def:crs:EPSG::25829"})
            r.raise_for_status()
        except Exception as e:
            if t == intentos:
                print(f"    ({type(e).__name__}) bbox {x0}_{y0} SALTADO tras "
                      f"{intentos} intentos", flush=True)
                return None
            print(f"    ({type(e).__name__}, reintento {t})", flush=True)
            time.sleep(20 * t)
            continue
        if b"ExceptionReport" in r.content[:500]:
            if b"out of limits" in r.content[:500].lower():
                raise _Desborde(f"bbox {x0}_{y0} de {lado} m desborda el WFS")
            # celda sin edificios: el servicio devuelve excepcion vacia
            return VACIA.copy()
        try:
            return gpd.read_file(io.BytesIO(r.content))
        except IndexError:
            # otra variante de celda vacia: GML bien formado pero sin capa
            return VACIA.copy()


def baja_celda(x0, y0):
    """La celda de trabajo entera (1 km)."""
    return baja_bbox(x0, y0, LADO)


def celda_por_cuadrantes(x0, y0, lado=LADO, _prof=0):
    """La celda troceada en 4 cuadrantes de lado/2 y concatenada.

    Fallback automatico cuando el WFS desborda o la respuesta entera no llega.
    Un cuadrante que todavia desborda se vuelve a trocear (500 -> 250 -> 125 m;
    a 500 m no se conocen desbordes en toda Pontevedra). None si el servicio
    no responde ni troceada.
    """
    mlado = lado // 2
    partes = []
    for i, (cx, cy) in enumerate(((x0, y0), (x0 + mlado, y0),
                                  (x0, y0 + mlado), (x0 + mlado, y0 + mlado))):
        if i:
            time.sleep(PAUSA)
        try:
            g = baja_bbox(cx, cy, mlado)
        except _Desborde:
            if mlado <= MIN_LADO:
                print(f"    cuadrante {cx}_{cy} sigue desbordando a {mlado} m",
                      flush=True)
                g = VACIA.copy()
            else:
                g = celda_por_cuadrantes(cx, cy, mlado)
        if g is None:
            return None
        partes.append(g)
        print(f"    cuadrante {cx}_{cy}: {len(g)} features", flush=True)
    return gpd.GeoDataFrame(pd.concat(partes, ignore_index=True),
                            crs="EPSG:25829")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--zona", default="paradanta")
    ap.add_argument("--parcial", action="store_true",
                    help="escribe el agregado aunque falten celdas. Uselo solo a "
                         "sabiendas: filtrar con cobertura parcial mete un sesgo "
                         "espacial heterogeneo, peor que no filtrar")
    ap.add_argument("--trozo", default="0/1",
                    help="i/n: descarga las celdas con indice %% n == i. Con n>1 "
                         "NO agrega: relanzar sin --trozo cuando esten todas")
    args = ap.parse_args()
    suf = "" if args.zona == "paradanta" else "_" + args.zona
    CELDAS.mkdir(parents=True, exist_ok=True)

    faixas = gpd.GeoDataFrame(pd.concat(
        [gpd.read_file(PROC / f"faixas_{n}_{args.zona}_ok.gpkg")
         for n in ("nucleos", "illadas")], ignore_index=True),
        crs="EPSG:25829")
    x0, y0, x1, y1 = (int(v // LADO * LADO) for v in faixas.total_bounds)

    # Que celdas tocan faixa. NO disolver: con la provincia, un union_all() da un
    # multipoligono de medio millon de vertices y este bucle lo evalua celda a
    # celda (aqui serian ~8.600). Se pregunta al indice espacial, que ademas
    # descarta por bbox antes de tocar geometria.
    rejilla = [(x, y) for x in range(x0, x1 + LADO, LADO)
               for y in range(y0, y1 + LADO, LADO)]
    marcos = gpd.GeoDataFrame(
        # OJO con los nombres: `cx` es el indexador de coordenadas de GeoPandas
        # y una columna asi llamada no se puede leer como atributo.
        {"celda_x": [c[0] for c in rejilla], "celda_y": [c[1] for c in rejilla]},
        geometry=[box(x, y, x + LADO, y + LADO) for x, y in rejilla],
        crs="EPSG:25829")
    piezas = faixas.explode(index_parts=False).reset_index(drop=True)
    piezas = piezas[piezas.geometry.notna() & ~piezas.geometry.is_empty]
    tocan = gpd.sjoin(marcos, gpd.GeoDataFrame(geometry=piezas.geometry,
                                               crs=marcos.crs),
                      predicate="intersects", how="inner")
    celdas = sorted(set(zip(tocan.celda_x, tocan.celda_y)))
    print(f"{len(celdas)} celdas de {LADO} m tocan faixa en {args.zona} "
          f"(de {len(rejilla)} de la rejilla)", flush=True)

    trozo_i, trozo_n = (int(v) for v in args.trozo.split("/"))
    todas = celdas
    if trozo_n > 1:
        celdas = [c for k, c in enumerate(celdas) if k % trozo_n == trozo_i]
        print(f"  trozo {args.trozo}: {len(celdas)} celdas", flush=True)

    t0 = time.perf_counter()
    saltadas = []
    for k, (x, y) in enumerate(celdas, 1):
        ruta = CELDAS / f"{x}_{y}.gpkg"
        if ruta.exists():
            continue
        try:
            g = baja_celda(x, y)
        except _Desborde:
            print(f"    celda {x}_{y} desborda el WFS: subdividiendo en "
                  f"cuadrantes de {QUADRANTE} m", flush=True)
            g = celda_por_cuadrantes(x, y)
        if g is None:
            # sin respuesta entera (respuesta gigante o servicio caido):
            # los cuadrantes parten el problema en porciones que si caben
            print(f"    celda {x}_{y} sin respuesta entera: reintentando por "
                  "cuadrantes", flush=True)
            g = celda_por_cuadrantes(x, y)
        if g is None:
            saltadas.append((x, y))
            continue
        cols = [c for c in ("gml_id",) if c in g.columns]
        g[cols + ["geometry"]].to_file(ruta, driver="GPKG")
        if k % 15 == 0 or k == len(celdas):
            print(f"  {k}/{len(celdas)}  "
                  f"{(time.perf_counter()-t0)/k:.1f} s/celda", flush=True)

    # OJO: la carpeta de celdas es COMPARTIDA entre zonas (A Paradanta esta
    # DENTRO de Pontevedra), igual que la de los CHM. Un glob("*.gpkg") mezclaria
    # las celdas de todas las zonas descargadas hasta ahora y cambiaria en
    # silencio el resultado del piloto. Se agregan solo las celdas de esta zona.
    if saltadas:
        print()
        print(f"AVISO: {len(saltadas)} celdas saltadas por fallo del servicio. "
              "Relanzar para reintentarlas antes de fiarse del agregado.",
              flush=True)

    if trozo_n > 1:
        raise SystemExit(
            f"trozo {args.trozo} descargado. El agregado NO se hace por trozos "
            "(escribirian el mismo fichero a la vez): relanzar sin --trozo cuando "
            "terminen todos.")

    rutas = [CELDAS / f"{x}_{y}.gpkg" for x, y in todas]
    hay = [r for r in rutas if r.exists()]

    # El agregado solo se escribe COMPLETO. Un GPKG con un tercio de la provincia
    # es indistinguible de uno entero para quien lo lea, y filtrar tejados en un
    # tercio del territorio mete un sesgo espacial que no se puede declarar con
    # una cifra: peor que no filtrar. aplica_copas.py sabe correr sin el fichero.
    if len(hay) < len(rutas) and not args.parcial:
        raise SystemExit(
            f"faltan {len(rutas) - len(hay)} de {len(rutas)} celdas: NO se escribe "
            f"edificios_catastro{suf}.gpkg. Un agregado parcial pasaria por "
            "completo y filtrar solo parte del territorio sesga el mapa. Relanzar "
            "para completarlo, o --parcial a sabiendas.")

    partes = [gpd.read_file(r) for r in hay]
    todo = gpd.GeoDataFrame(pd.concat(partes, ignore_index=True),
                            crs="EPSG:25829")
    if "gml_id" in todo.columns:
        todo = todo.drop_duplicates("gml_id")
    todo.to_file(PROC / f"edificios_catastro{suf}.gpkg", driver="GPKG")
    print(f"{len(todo):,} edificios -> "
          f"{(PROC / ('edificios_catastro' + suf + '.gpkg')).relative_to(RAIZ)}")
