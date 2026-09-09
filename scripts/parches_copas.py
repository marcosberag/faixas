"""Extrae el parche de ortofoto de cada copa de entrenamiento.

Un parche de 16x16 m (64x64 px a 0,25 m) centrado en el apice de la copa,
desde la cache local de descarga_orto25.py. Se guardan apilados en un .npy
uint8 con un indice CSV alineado fila a fila: extraer una vez, entrenar
muchas.

Los parches con mas del 20 % de negro (borde de bloque sin ortofoto) se
descartan y se anota cuantos.

Uso:
    python scripts/parches_copas.py
"""
import pathlib

import numpy as np
import pandas as pd
import rasterio
from rasterio.windows import Window

RAIZ = pathlib.Path(__file__).resolve().parent.parent
PROC = RAIZ / "datos" / "procesado"
COPAS = PROC / "copas"
ORTO25 = PROC / "orto25"

PX = 64          # 16 m a 0,25 m/px
RES = 0.25


def parches_de_bloque(ruta_tif, sub):
    """Parches de las copas `sub` (x, y) desde un GeoTIFF de bloque."""
    salida = np.zeros((len(sub), PX, PX, 3), "uint8")
    with rasterio.open(ruta_tif) as s:
        inv = ~s.transform
        for k, f in enumerate(sub.itertuples()):
            col, fila = inv * (f.x, f.y)
            c0, f0 = int(round(col)) - PX // 2, int(round(fila)) - PX // 2
            v = Window(c0, f0, PX, PX)
            a = s.read(window=v, boundless=True, fill_value=0)
            salida[k] = np.moveaxis(a, 0, 2)
    return salida


if __name__ == "__main__":
    m = pd.read_csv(COPAS / "entrenamiento.csv", encoding="utf-8-sig")
    faltan_orto = sorted(b for b in m.bloque.unique()
                         if not (ORTO25 / f"{b}.tif").exists())
    if faltan_orto:
        print(f"AVISO: {len(faltan_orto)} bloques sin ortofoto aun "
              f"(descarga_orto25.py sigue?); se extraen los demas")
        m = m[~m.bloque.isin(faltan_orto)]

    trozos, indices = [], []
    for b, sub in m.groupby("bloque"):
        trozos.append(parches_de_bloque(ORTO25 / f"{b}.tif", sub))
        indices.append(sub)
        print(f"  {b}  {len(sub):,}", flush=True)

    parches = np.concatenate(trozos)
    indice = pd.concat(indices, ignore_index=True)

    negros = (parches == 0).all(axis=3).mean(axis=(1, 2))
    vale = negros <= 0.2
    print(f"\n{int((~vale).sum())} parches descartados por borde negro")
    parches, indice = parches[vale], indice[vale].reset_index(drop=True)

    np.save(COPAS / "parches_entrenamiento.npy", parches)
    indice.to_csv(COPAS / "indice_entrenamiento.csv", index=False,
                  encoding="utf-8-sig")
    print(f"{len(indice):,} parches de {PX}x{PX} px "
          f"({parches.nbytes / 1e6:.0f} MB)")
    print(f"-> {(COPAS / 'parches_entrenamiento.npy').relative_to(RAIZ)}")
