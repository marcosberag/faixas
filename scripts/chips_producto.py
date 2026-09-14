"""Chips de ortofoto para la muestra del producto, punto a punto contra el WMS.

La fase 2 montaba un mosaico por bloque (9024x9024 px) y recortaba de ahi. Valia
porque los 400 puntos caian en 3 bloques. La muestra del producto esta repartida
por ~150 bloques: mosaicarlos todos serian gigas de ortofoto para usar el 0,2 %
de cada uno. Aqui se pide al WMS la ventana justa de cada punto (dos peticiones
por punto: encuadre de 40 m y contexto de 120 m).

Todo lo demas — mira, rejilla metrica, escala, panel de CHM — se importa de
chips_validacion.py para que los chips sean IDENTICOS a los de la fase 2: mismo
encuadre, misma rejilla de 10 m, misma mira de 3 m. El criterio del anotador se
calibro con aquellos; cambiar el formato seria meter una variable nueva.

Es reanudable: los chips ya en disco no se repiten.

Uso:
    python scripts/chips_producto.py
"""
import pathlib
import sys
import time

import pandas as pd
import rasterio
from PIL import Image

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from chips_validacion import (LADO_CHIP, LADO_CTX, PX_CHIP, PX_CTX, REJILLA,
                              REJILLA_CTX, colorea_chm, mira, recorta, tesela)

def tesela_con_reintentos(x0, y0, lado, px, intentos=4):
    """El WMS del IGN suelta 502 esporadicos: sobre 500 peticiones toca alguno
    seguro, y no puede costar la corrida. Espera creciente entre intentos."""
    for i in range(intentos):
        try:
            return tesela(x0, y0, lado, px)
        except Exception as e:
            if i == intentos - 1:
                raise
            espera = 10 * (i + 1)
            print(f"    WMS fallo ({e}); reintento en {espera} s", flush=True)
            time.sleep(espera)


RAIZ = pathlib.Path(__file__).resolve().parent.parent
LIDAR = RAIZ / "datos" / "procesado" / "lidar"
VAL = RAIZ / "datos" / "procesado" / "validacion_producto"

if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", default="validacion_producto",
                    help="subcarpeta de datos/procesado con muestra.csv")
    VAL = RAIZ / "datos" / "procesado" / ap.parse_args().dir

    m = pd.read_csv(VAL / "muestra.csv", encoding="utf-8-sig")
    dir_orto, dir_ctx, dir_chm = VAL / "chips", VAL / "chips_ctx", VAL / "chips_chm"
    for d in (dir_orto, dir_ctx, dir_chm):
        d.mkdir(exist_ok=True)

    pend = m[[not (dir_orto / f"{f}.jpg").exists() for f in m.id]]
    print(f"{len(m)} puntos, {len(m)-len(pend)} con chip, {len(pend)} pendientes")

    t0 = time.perf_counter()
    huecos = []
    for k, (_, f) in enumerate(pend.iterrows(), 1):
        a = tesela_con_reintentos(f.x - LADO_CHIP / 2, f.y - LADO_CHIP / 2, LADO_CHIP, PX_CHIP)
        negro = float((a.max(axis=2) == 0).mean())
        if negro > 0.01:
            huecos.append((f.id, negro))
        mira(Image.fromarray(a), LADO_CHIP, REJILLA) \
            .save(dir_orto / f"{f.id}.jpg", quality=82, optimize=True)

        a = tesela_con_reintentos(f.x - LADO_CTX / 2, f.y - LADO_CTX / 2, LADO_CTX, PX_CTX)
        mira(Image.fromarray(a), LADO_CTX, REJILLA_CTX, recuadro_m=LADO_CHIP) \
            .save(dir_ctx / f"{f.id}.jpg", quality=78, optimize=True)

        with rasterio.open(LIDAR / f"{f.bloque}_chm.tif") as sc:
            h = recorta(sc, f.x, f.y, LADO_CHIP, LADO_CHIP)[0].astype("float32")
        h[h < -1000] = 0
        mira(colorea_chm(h), LADO_CHIP, REJILLA) \
            .save(dir_chm / f"{f.id}.png", optimize=True)

        if k % 25 == 0:
            ritmo = (time.perf_counter() - t0) / k
            print(f"  {k}/{len(pend)}  ({ritmo:.1f} s/punto, "
                  f"~{ritmo*(len(pend)-k)/60:.0f} min restantes)", flush=True)

    if huecos:
        print(f"\nAVISO: {len(huecos)} chips con hueco negro (WMS sin dato):")
        for i, n in huecos[:8]:
            print(f"  {i}  {100*n:.0f} % negro")
    print(f"\n{len(pend)} puntos en {(time.perf_counter()-t0)/60:.1f} min")
    print(f"-> {dir_orto.relative_to(RAIZ)}")
