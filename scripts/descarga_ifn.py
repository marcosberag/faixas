"""Descarga la capa de especies arboreas del IFN4 (2010) para la zona piloto.

Es la verdad de referencia de especie de la fase 3. Hizo falta porque la via que
estaba prevista se cayo: la subpregunta de tipo de copa del anotador solo se pudo
contestar en 25 de 87 arboles, con 15 «no distinguible» y cero de la lista
prohibida. La especie no se tipifica a ojo sobre ortofoto.

DE DONDE SALE, Y POR QUE DE AQUI Y NO DEL MITECO
-------------------------------------------------
El MFE25 del MITECO es la misma cartografia y es la fuente canonica, pero su WMS
(`wms.mapama.gob.es/sig/Biodiversidad/MFE`) devuelve una NullReferenceException
del servidor a cualquier GetCapabilities, y las paginas de descarga por provincia
pintan los enlaces con JavaScript, asi que no hay URL estable que citar.

La Xunta publica la misma informacion en su IDE como servicio ArcGIS REST, y ese
si funciona:

    https://ideg.xunta.gal/servizos/rest/services/UsosSolo/IFN_2010_EspeciesArboreas

Y a diferencia del servicio de faixas (que ignora `returnGeometry` y no devuelve
geometrias por ninguna via), este las devuelve sin pelea. Ademas viene ya en
EPSG:25829, o sea el CRS del proyecto: cero reproyecciones.

QUE TRAE CADA POLIGONO
-----------------------
Hasta tres especies con su ocupacion en decimas (`O1`,`O2`,`O3`: un 6 son seis
decimas de la fraccion arbolada, no un 6 %), la fraccion de cabida cubierta
arborea `FCCARB` en tanto por ciento, y el tipo de bosque.

LA FECHA ES EL PROBLEMA, Y HAY QUE DECIRLO
-------------------------------------------
El IFN4 de Galicia es de 2010 y el vuelo LiDAR de 2024: **catorce anhos**. La
especie dominante de un rodal es estable en un robledal y volatil en un
eucaliptal, que se corta a turno de 12-15 anhos y se replanta. O sea que el error
de esta referencia NO esta repartido al azar: se concentra justo en la especie
que mas importa acertar. Se usa igual, porque diez puntos fotointerpretados no
son alternativa, pero la limitacion va en portada y no en nota al pie.

Uso:
    python scripts/descarga_ifn.py
"""
import argparse
import pathlib
import time

import geopandas as gpd
import pandas as pd
import requests
from shapely.geometry import Polygon, MultiPolygon

RAIZ = pathlib.Path(__file__).resolve().parent.parent
CRUDO = RAIZ / "datos" / "crudo"
PROC = RAIZ / "datos" / "procesado"

URL = ("https://ideg.xunta.gal/servizos/rest/services/UsosSolo/"
       "IFN_2010_EspeciesArboreas/MapServer/0/query")
# el mismo de docs/01: extension de la zona piloto en EPSG:25829, con holgura.
# Con --zona se recalcula desde las faixas de esa zona (ver bbox_de_zona).
BBOX = (548000, 4660000, 568000, 4686000)
CRS = 25829
POR_PAGINA = 500          # el servicio admite 1000; 500 va mas fino con timeouts
ESPERA = 0.4              # s entre paginas, por educacion con un servicio publico


def bbox_de_zona(zona, holgura=2000):
    """Extension de las faixas de una zona, redondeada al km y con holgura."""
    cajas = [gpd.read_file(PROC / f"faixas_{n}_{zona}_ok.gpkg").total_bounds
             for n in ("nucleos", "illadas")]
    x0 = min(c[0] for c in cajas) - holgura
    y0 = min(c[1] for c in cajas) - holgura
    x1 = max(c[2] for c in cajas) + holgura
    y1 = max(c[3] for c in cajas) + holgura
    return (int(x0 // 1000) * 1000, int(y0 // 1000) * 1000,
            int(x1 // 1000 + 1) * 1000, int(y1 // 1000 + 1) * 1000)


def pagina(offset, campos="*", geom=True):
    p = {
        "where": "1=1",
        "geometry": ",".join(str(v) for v in BBOX),
        "geometryType": "esriGeometryEnvelope",
        "inSR": CRS, "outSR": CRS,
        "spatialRel": "esriSpatialRelIntersects",
        "outFields": campos,
        "returnGeometry": str(geom).lower(),
        "resultOffset": offset, "resultRecordCount": POR_PAGINA,
        "f": "json",
    }
    r = requests.get(URL, params=p, timeout=120)
    r.raise_for_status()
    j = r.json()
    if "error" in j:
        raise SystemExit(f"el servicio devuelve error: {j['error']}")
    return j.get("features", []), bool(j.get("exceededTransferLimit"))


def a_shapely(rings):
    """Anillos de ArcGIS a Polygon/MultiPolygon.

    ArcGIS no marca cual es hueco: lo dice el sentido de giro. Horario es
    exterior y antihorario es interior. Da igual que shapely no lo exija, porque
    si se meten todos como exteriores los huecos suman area en vez de restarla y
    la superficie de eucaliptal sale inflada.
    """
    def horario(a):
        return sum((b[0] - x[0]) * (b[1] + x[1]) for x, b in zip(a, a[1:])) > 0

    exteriores, huecos = [], []
    for a in rings:
        (exteriores if horario(a) else huecos).append(a)
    if not exteriores:                       # todo antihorario: no hay huecos
        exteriores, huecos = rings, []
    polis = []
    for e in exteriores:
        p = Polygon(e)
        dentro = [h for h in huecos if p.contains(Polygon(h).representative_point())]
        polis.append(Polygon(e, dentro))
    return polis[0] if len(polis) == 1 else MultiPolygon(polis)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--zona", default="paradanta",
                    help="sufijo de faixas_{capa}_{zona}_ok.gpkg; "
                         "con paradanta se conserva el bbox original")
    args = ap.parse_args()
    if args.zona != "paradanta":
        BBOX = bbox_de_zona(args.zona)
        print(f"bbox de {args.zona}: {BBOX}")
    CRUDO.mkdir(parents=True, exist_ok=True)
    PROC.mkdir(parents=True, exist_ok=True)

    n = requests.get(URL, params={
        "where": "1=1", "geometry": ",".join(str(v) for v in BBOX),
        "geometryType": "esriGeometryEnvelope", "inSR": CRS,
        "spatialRel": "esriSpatialRelIntersects",
        "returnCountOnly": "true", "f": "json"}, timeout=60).json()["count"]
    print(f"IFN4 2010, especies arboreas — {n} poligonos en {args.zona}\n")

    filas, off, t0 = [], 0, time.time()
    while True:
        fs, mas = pagina(off)
        for f in fs:
            g = f.get("geometry", {}).get("rings")
            if not g:
                continue
            filas.append({**f["attributes"], "geometry": a_shapely(g)})
        print(f"  {len(filas):>5} / {n}")
        off += POR_PAGINA
        if not fs or (len(filas) >= n and not mas):
            break
        time.sleep(ESPERA)

    if not filas:
        raise SystemExit("no ha venido ni un poligono: revisa el bbox o el servicio")

    gdf = gpd.GeoDataFrame(filas, crs=f"EPSG:{CRS}")
    for c in gdf.columns:
        if gdf[c].dtype == object and c != "geometry":
            gdf[c] = gdf[c].astype(str).str.strip()

    rotas = int((~gdf.geometry.is_valid).sum())
    if rotas:
        print(f"\n  {rotas} geometrias invalidas, reparando con make_valid")
        gdf.geometry = gdf.geometry.make_valid()

    salida = PROC / f"ifn_especies_{args.zona}.gpkg"
    gdf.to_file(salida, driver="GPKG")

    print(f"\n{len(gdf)} poligonos, {gdf.geometry.area.sum()/1e4:,.0f} ha, "
          f"en {time.time()-t0:.0f} s")
    print(f"FCC arborea: mediana {gdf.FCCARB.median():.0f} %, "
          f"nula en {int((gdf.FCCARB == 0).sum())} poligonos")

    print("\nespecie principal, por superficie:")
    sup = (gdf.assign(ha=gdf.geometry.area / 1e4)
           .groupby("NOMBRE_SP1").ha.sum().sort_values(ascending=False))
    for k, v in sup.head(15).items():
        print(f"  {k if k.strip() else '(vacio)':<32} {v:>8.0f} ha "
              f"({100*v/sup.sum():>5.1f} %)")

    print(f"\n-> {salida.relative_to(RAIZ)}")
