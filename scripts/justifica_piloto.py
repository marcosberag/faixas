"""Comprueba, con la capa completa de Galicia, si A Paradanta es buena zona piloto."""
import pathlib

import geopandas as gpd
import numpy as np
import pandas as pd

RAIZ = pathlib.Path(__file__).resolve().parent.parent
CRUDO = RAIZ / "datos" / "crudo"
PILOTO = ["Arbo", "A Cañiza", "Covelo", "Crecente"]

nuc = gpd.read_file(CRUDO / "FaixaProteccion50m" / "FaixaProteccion50m.shp")
ill = gpd.read_file(CRUDO / "FaixaProteccion50m_Illadas" / "FaixaProteccion50m_Illadas.shp")

print("=== cobertura de la capa en Galicia")
concellos_capa = set(nuc["NOMECONCEL"]) | set(ill["NOMECONCEL"])
print(f"  concellos con faixas publicadas: {len(concellos_capa)} de 313 en Galicia "
      f"({len(concellos_capa)/313:.0%})")
print(f"  registros: {len(nuc):,} nucleos + {len(ill):,} illadas")

falta = [c for c in PILOTO if c not in concellos_capa]
print(f"  los 4 concellos piloto estan en la capa: {'SI' if not falta else 'NO ' + str(falta)}")

# --- superficie de franja por concello --------------------------------------
todo = pd.concat([
    nuc.assign(capa="nucleos")[["NOMECONCEL", "PROVINCIA", "capa", "geometry"]],
    ill.assign(capa="illadas")[["NOMECONCEL", "PROVINCIA", "capa", "geometry"]],
])
todo = gpd.GeoDataFrame(todo, crs=nuc.crs)
todo["ha"] = todo.geometry.area / 1e4

por_concello = todo.groupby("NOMECONCEL").agg(
    ha=("ha", "sum"), n=("ha", "size"),
    provincia=("PROVINCIA", "first")).sort_values("ha", ascending=False)

print(f"\n=== superficie de franja por concello (n={len(por_concello)})")
print(f"  mediana {por_concello['ha'].median():,.0f} ha | "
      f"media {por_concello['ha'].mean():,.0f} | "
      f"max {por_concello['ha'].max():,.0f} ({por_concello.index[0]})")

print("\n  los 4 piloto:")
for c in PILOTO:
    if c not in por_concello.index:
        continue
    fila = por_concello.loc[c]
    pct = (por_concello["ha"] < fila["ha"]).mean()
    print(f"    {c:<12} {fila['ha']:>7,.0f} ha  ({fila['n']:>3} poligonos)  "
          f"percentil {pct:.0%} de Galicia")

sub = por_concello.loc[[c for c in PILOTO if c in por_concello.index]]
print(f"\n  total piloto: {sub['ha'].sum():,.0f} ha "
      f"({sub['ha'].sum()/por_concello['ha'].sum():.2%} de la franja gallega)")

# --- proporcion nucleos / illadas: mide dispersion del poblamiento -----------
print("\n=== reparto nucleos vs illadas (dispersion del poblamiento)")
rep = todo.groupby(["NOMECONCEL", "capa"])["ha"].sum().unstack(fill_value=0)
rep["pct_illadas"] = rep["illadas"] / (rep["illadas"] + rep["nucleos"])
print(f"  Galicia: mediana {rep['pct_illadas'].median():.1%} de la franja en illadas")
for c in PILOTO:
    if c in rep.index:
        v = rep.loc[c, "pct_illadas"]
        pct = (rep["pct_illadas"] < v).mean()
        print(f"    {c:<12} {v:>5.1%}  (percentil {pct:.0%})")

# --- tamano de los poligonos: fragmentacion ---------------------------------
print("\n=== fragmentacion (area mediana por poligono suelto)")
expl = todo.explode(index_parts=False)
expl["a"] = expl.geometry.area
gal = expl["a"].median()
pil = expl[expl["NOMECONCEL"].isin(PILOTO)]["a"].median()
print(f"  Galicia: {gal:,.0f} m2 | piloto: {pil:,.0f} m2  "
      f"({pil/gal:.2f}x la mediana gallega)")

# --- provincias --------------------------------------------------------------
print("\n=== reparto por provincia")
print(todo.groupby("PROVINCIA")["ha"].sum().sort_values(ascending=False).to_string())
