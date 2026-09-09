"""Recorta las faixas oficiales a una provincia y las deja listas para la malla.

El shapefile del PBA cubre Galicia entera; el piloto solo uso A Paradanta.
Para escalar: filtrar por PROVINCIA, reparar geometrias (el shapefile trae
auto-intersecciones, la MISMA trampa que repara_faixas.py cazo en el piloto)
y escribir faixas_{nucleos,illadas}_{zona}_ok.gpkg con el esquema que ya
esperan malla_lidar.py y metricas_faixas.py.

Uso:
    python scripts/prepara_provincia.py --provincia Pontevedra
"""
import argparse
import pathlib
import unicodedata

import geopandas as gpd
from shapely import make_valid

RAIZ = pathlib.Path(__file__).resolve().parent.parent
CRUDO = RAIZ / "datos" / "crudo"
PROC = RAIZ / "datos" / "procesado"

CAPAS = {"nucleos": "FaixaProteccion50m", "illadas": "FaixaProteccion50m_Illadas"}


def slug(s):
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    return s.lower().replace(" ", "_")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--provincia", required=True)
    args = ap.parse_args()
    zona = slug(args.provincia)

    for nombre, carpeta in CAPAS.items():
        g = gpd.read_file(CRUDO / carpeta)
        provs = sorted(g.PROVINCIA.dropna().unique())
        sel = g[g.PROVINCIA.str.strip().str.casefold()
                == args.provincia.strip().casefold()].copy()
        if not len(sel):
            raise SystemExit(f"provincia '{args.provincia}' no está; hay: {provs}")
        invalidas = (~sel.geometry.is_valid).sum()
        sel["geometry"] = sel.geometry.apply(make_valid)
        salida = PROC / f"faixas_{nombre}_{zona}_ok.gpkg"
        sel.to_file(salida, driver="GPKG")
        print(f"{nombre}: {len(sel)} registros ({invalidas} reparadas), "
              f"{sel.geometry.area.sum()/1e4:,.0f} ha -> {salida.name}")
