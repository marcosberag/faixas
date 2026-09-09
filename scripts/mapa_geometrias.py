"""Mapa de las geometrias ya descargadas, dibujadas en local (sin el servicio)."""
import pathlib

import geopandas as gpd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D

RAIZ = pathlib.Path(__file__).resolve().parent.parent
PROC = RAIZ / "datos" / "procesado"
SAL = RAIZ / "salidas"
SAL.mkdir(exist_ok=True)

nuc = gpd.read_file(PROC / "faixas_nucleos_paradanta_ok.gpkg")
ill = gpd.read_file(PROC / "faixas_illadas_paradanta_ok.gpkg")

fig, ax = plt.subplots(figsize=(11, 13), facecolor="#0d0d10")
ax.set_facecolor("#0d0d10")

nuc.plot(ax=ax, facecolor="#ff6000", edgecolor="#ffbe3c", linewidth=0.35, alpha=0.75)
ill.plot(ax=ax, facecolor="#00b4d8", edgecolor="#90e0ef", linewidth=0.35, alpha=0.75)

# contorno por concello
disuelto = nuc.dissolve(by="NOMECONCEL")
for nombre, fila in disuelto.iterrows():
    c = fila.geometry.centroid
    ax.annotate(nombre, (c.x, c.y), color="white", fontsize=11, ha="center",
                weight="bold", alpha=0.85)

ax.set_title("A Paradanta: franjas de protección de 50 m\n"
             f"{len(nuc)} núcleos + {len(ill)} edificaciones aisladas · "
             f"{(nuc.geometry.area.sum()+ill.geometry.area.sum())/1e4:,.0f} ha · EPSG:25829",
             color="white", fontsize=13, pad=16)
ax.legend(handles=[
    Line2D([0], [0], marker="s", color="none", markerfacecolor="#ff6000",
           markersize=11, label=f"Núcleos de población ({nuc.geometry.area.sum()/1e4:,.0f} ha)"),
    Line2D([0], [0], marker="s", color="none", markerfacecolor="#00b4d8",
           markersize=11, label=f"Edificaciones aisladas ({ill.geometry.area.sum()/1e4:,.0f} ha)"),
], loc="lower right", facecolor="#1a1a20", edgecolor="none", labelcolor="white")

ax.set_axis_off()
ax.set_aspect("equal")
plt.tight_layout()
destino = SAL / "faixas_geometrias_paradanta.png"
plt.savefig(destino, dpi=135, facecolor="#0d0d10", bbox_inches="tight")
print(f"-> {destino}")
print(f"   nucleos {len(nuc)} ({nuc.geometry.area.sum()/1e4:,.0f} ha), "
      f"illadas {len(ill)} ({ill.geometry.area.sum()/1e4:,.0f} ha)")
print(f"   parroquias distintas: {nuc['CODPARRO'].nunique()}")
