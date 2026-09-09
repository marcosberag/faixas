"""Segmentacion de copas individuales sobre el CHM, bloque a bloque.

Del pixel a la copa: maximos locales del CHM suavizado como semillas y
watershed sobre el CHM invertido, enmascarado al arbolado (>5,5 m, el umbral
calibrado de la fase 2). Es el metodo clasico de deteccion de apices (Popescu,
Chen...), determinista y sin GPU. A 1 m de pixel y 5 pts/m2 no se pretende
delinear la copa perfecta: se pretende UNA unidad-arbol georreferenciada a la
que colgarle un parche de ortofoto y una especie.

Parametros declarados (no tocar sin recalibrar el conteo):
  - suavizado gaussiano sigma=1 px: quita el ruido de pixel sin fundir apices
  - distancia minima entre apices: 2 px (2 m). En eucaliptal joven denso
    subsegmenta poco; en robledal viejo puede partir una copa grande en dos.
    Se declara: el conteo es de APICES, no de troncos.
  - area minima de copa: 3 px (3 m2)

Salida: un CSV por bloque en datos/procesado/copas/ con x, y (apice), h_max,
h_media, area_m2. Reanudable: los bloques ya hechos no se rehacen.

Uso:
    python scripts/copas_chm.py
"""
import pathlib
import time

import numpy as np
import pandas as pd
import rasterio
from scipy import ndimage as ndi
from skimage.feature import peak_local_max
from skimage.segmentation import watershed

RAIZ = pathlib.Path(__file__).resolve().parent.parent
LIDAR = RAIZ / "datos" / "procesado" / "lidar"
COPAS = RAIZ / "datos" / "procesado" / "copas"

UMBRAL = 5.5      # m, el umbral calibrado de arbolado (fase 2)
SIGMA = 1.0       # px, suavizado del CHM antes de buscar apices
DIST_MIN = 2      # px, separacion minima entre apices
AREA_MIN = 3      # px (m2), copa minima


def copas_bloque(ruta_chm):
    with rasterio.open(ruta_chm) as s:
        chm = s.read(1)
        tr = s.transform
    chm = np.where(np.isfinite(chm) & (chm > -1000), chm, 0).astype("float32")
    chm[chm < 0] = 0

    suave = ndi.gaussian_filter(chm, sigma=SIGMA)
    masa = suave > UMBRAL
    if not masa.any():
        return pd.DataFrame()

    picos = peak_local_max(suave, min_distance=DIST_MIN, labels=masa,
                           exclude_border=False)
    if not len(picos):
        return pd.DataFrame()
    semillas = np.zeros(chm.shape, dtype="int32")
    semillas[tuple(picos.T)] = np.arange(1, len(picos) + 1)
    etiquetas = watershed(-suave, semillas, mask=masa)

    ids = np.arange(1, len(picos) + 1)
    area = ndi.sum_labels(np.ones_like(chm), etiquetas, ids)
    h_max = ndi.maximum(chm, etiquetas, ids)
    h_med = ndi.mean(chm, etiquetas, ids)
    filas, cols = picos[:, 0], picos[:, 1]
    xs, ys = rasterio.transform.xy(tr, filas, cols)

    d = pd.DataFrame({"x": np.round(xs, 1), "y": np.round(ys, 1),
                      "h_max": np.round(h_max, 2),
                      "h_media": np.round(h_med, 2),
                      "area_m2": area.astype(int)})
    return d[(d.area_m2 >= AREA_MIN) & (d.h_max >= UMBRAL)]


if __name__ == "__main__":
    COPAS.mkdir(parents=True, exist_ok=True)
    bloques = sorted(LIDAR.glob("*_chm.tif"))
    # OJO: solo los CSV por bloque. En la carpeta conviven los agregados
    # (entrenamiento, disperso_clasificado, oos_predicciones, indice_*), que
    # no son bloques y no tienen columna `x`: colarlos revienta el recuento.
    hechos = {p.stem for p in COPAS.glob("PNOA-*.csv")}
    pendientes = [b for b in bloques
                  if b.stem.replace("_chm", "") not in hechos]
    print(f"{len(bloques)} bloques, {len(pendientes)} pendientes")

    t0 = time.perf_counter()
    total = 0
    for k, b in enumerate(pendientes, 1):
        nombre = b.stem.replace("_chm", "")
        d = copas_bloque(b)
        d.to_csv(COPAS / f"{nombre}.csv", index=False)
        total += len(d)
        if k % 20 == 0 or k == len(pendientes):
            media = (time.perf_counter() - t0) / k
            print(f"  {k}/{len(pendientes)}  {media:.1f} s/bloque  "
                  f"{total:,} copas nuevas", flush=True)

    csvs = sorted(COPAS.glob("PNOA-*.csv"))
    n = sum(len(pd.read_csv(c, usecols=["x"])) for c in csvs)
    print()
    print(f"{n:,} copas en {len(csvs):,} bloques -> {COPAS.relative_to(RAIZ)}")
