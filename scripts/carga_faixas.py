"""Carga los shapefiles oficiales de faixas, filtra la zona piloto y verifica.

Los shapefiles salen del visor del Plan Basico Autonomico:
  https://visorgis.cmati.xunta.es/cdix/descargas/faixas_xestion_biomasa/
Es la unica via que sirve geometrias: el servicio ArcGIS REST las tiene capadas.
Ver docs/02-walkthrough.md.
"""
import pathlib

import geopandas as gpd

RAIZ = pathlib.Path(__file__).resolve().parent.parent
CRUDO = RAIZ / "datos" / "crudo"
PROC = RAIZ / "datos" / "procesado"
PROC.mkdir(parents=True, exist_ok=True)

CAPAS = {
    "nucleos": CRUDO / "FaixaProteccion50m" / "FaixaProteccion50m.shp",
    "illadas": CRUDO / "FaixaProteccion50m_Illadas" / "FaixaProteccion50m_Illadas.shp",
}
# OJO: articulo pospuesto, igual que en la API.
CONCELLOS = ["Arbo", "Cañiza, A", "Covelo", "Crecente"]
# Recuentos obtenidos de la API ArcGIS, para contrastar.
ESPERADO = {"nucleos": 49, "illadas": 52}


def campo_concello(gdf):
    """El shapefile no usa los mismos nombres de campo que la API REST."""
    for cand in ("NOMECONCEL", "CONCELLO", "Concello", "NOMECONCELLO"):
        if cand in gdf.columns:
            return cand
    for c in gdf.columns:
        if "concel" in c.lower():
            return c
    raise KeyError(f"sin campo concello en {list(gdf.columns)}")


for nombre, ruta in CAPAS.items():
    print(f"\n=== {nombre}  ({ruta.name})")
    gdf = gpd.read_file(ruta)
    print(f"  registros totales en Galicia: {len(gdf):,}")
    print(f"  CRS: {gdf.crs}  ->  EPSG:{gdf.crs.to_epsg()}")
    print(f"  campos: {[c for c in gdf.columns if c != 'geometry']}")

    col = campo_concello(gdf)
    # el shapefile puede escribir el nombre sin articulo pospuesto: mirar ambos
    variantes = set(CONCELLOS) | {"A Cañiza"}
    presentes = sorted(v for v in gdf[col].unique()
                       if any(k in str(v) for k in ("Arbo", "añiza", "Covelo", "Crecente")))
    print(f"  campo concello: '{col}'  valores piloto encontrados: {presentes}")
    piloto = gdf[gdf[col].isin(variantes | set(presentes))].copy()
    print(f"  zona piloto: {len(piloto)} registros "
          f"(la API decia {ESPERADO[nombre]}) "
          f"{'OK' if len(piloto) == ESPERADO[nombre] else '<-- NO CUADRA'}")

    for c in sorted(piloto[col].unique()):
        print(f"    {c:<14} {(piloto[col] == c).sum():>3}")

    piloto["area_ha"] = piloto.geometry.area / 10_000
    print(f"  superficie total: {piloto['area_ha'].sum():,.0f} ha")
    print(f"  extension: {[round(v) for v in piloto.total_bounds]}")
    print(f"  geometrias validas: {piloto.geometry.is_valid.sum()}/{len(piloto)}")

    salida = PROC / f"faixas_{nombre}_paradanta.gpkg"
    piloto.to_file(salida, driver="GPKG")
    print(f"  -> {salida.relative_to(RAIZ)}")

# --- verificacion del ancho de 50 m ---------------------------------------
# Cada poligono de "illadas" deberia ser el buffer de 50 m de una edificacion.
# Erosionando 50 m deberia quedar solo la huella del edificio, o casi nada.
print("\n=== verificacion: la banda mide 50 m?")
ill = gpd.read_file(PROC / "faixas_illadas_paradanta.gpkg")
ill = ill.explode(index_parts=False).reset_index(drop=True)
ill["a"] = ill.geometry.area
for _, f in ill.nsmallest(6, "a").iterrows():
    g = f.geometry
    linea = [f"  area {g.area:>9,.0f} m2 |"]
    for d in (40, 48, 50, 52, 60):
        r = g.buffer(-d)
        linea.append(f" -{d}m: {'vacio' if r.is_empty else format(r.area, ',.0f') + ' m2'}")
    print("".join(linea))
