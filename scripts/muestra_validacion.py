"""Genera la muestra de validacion manual para calibrar el umbral (fase 2).

POR QUE ASI, QUE ES LA MITAD DEL TRABAJO
-----------------------------------------

Lo que hay que calibrar es un umbral h*: por encima de el decimos "hay arbol".
Para elegirlo hace falta una VERDAD DE REFERENCIA independiente del LiDAR, y la
unica disponible sin ir al monte es la ortofoto del PNOA fotointerpretada a mano.

La unidad de validacion es el PUNTO, no el poligono. Se sortean puntos dentro de
la faixa, se mira la ortofoto en cada uno y se responde a una pregunta binaria:
"en este punto, ¿hay copa de arbol?". Con eso sale una matriz de confusion por
cada umbral candidato, y de ahi la tasa de falsos positivos, que es un compromiso
explicito de la propuesta.

Validar por poligono no serviria: una faixa de 20 ha no es "arbolada" o "no
arbolada", es un 37 % de algo. El punto es la unica unidad sobre la que un humano
puede dar una respuesta binaria fiable en tres segundos.

MUESTREO ESTRATIFICADO, no aleatorio simple
--------------------------------------------
Con muestreo aleatorio simple, la mayoria de los puntos caeria en zonas obvias
(prado raso o bosque cerrado) y casi ninguno en la franja de alturas donde el
umbral se juega de verdad, que son los 1-6 m. Se estratifica por bandas de altura
del CHM y se sobremuestrean las bandas de decision.

El precio de estratificar es que la muestra YA NO ES REPRESENTATIVA tal cual: hay
que reponderar. Cada punto lleva un peso

    peso_m2 = area_del_estrato / puntos_sorteados_en_el_estrato

que son los metros cuadrados de faixa que ese punto representa. Sumando pesos en
vez de contar puntos, las tasas vuelven a ser insesgadas. El peso va en el CSV y
`calibra_umbral.py` lo usa; no es opcional.

SEPARACION MINIMA de 15 m entre puntos
---------------------------------------
Dos puntos a 3 m suelen caer en la misma copa: no son dos observaciones, es una
contada dos veces, y estrecha los intervalos de confianza de mentira. Se impone
distancia minima. 15 m es algo mas que el diametro de copa tipico de un pino
adulto en Galicia.

LA ANOTACION ES CIEGA
----------------------
El CSV que sale de aqui lleva la altura del CHM, pero `anotador.py` no la enseña
hasta despues de responder, y baraja el orden. Si el que anota ve "8,3 m" antes de
decidir, ya no esta validando el CHM: lo esta confirmando. El sesgo de
confirmacion en fotointerpretacion esta bien documentado y aqui invalidaria justo
el numero que queremos publicar.

Uso:
    python scripts/muestra_validacion.py
    python scripts/muestra_validacion.py --n 200 --semilla 7
"""
import argparse
import pathlib

import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio
from rasterio.features import rasterize
from shapely.geometry import box

RAIZ = pathlib.Path(__file__).resolve().parent.parent
PROC = RAIZ / "datos" / "procesado"
LIDAR = PROC / "lidar"
SALIDA = PROC / "validacion"

SEMILLA = 20260817
SEP_MIN = 15.0  # m entre puntos de la muestra

# (limite inferior, limite superior, cuota). Las cuotas no son proporcionales al
# area: las bandas de 1 a 6 m son donde el umbral decide, y ahi hace falta
# resolucion aunque ocupen poca superficie. La reponderacion lo corrige despues.
ESTRATOS = [
    (0.0, 0.5, 40),    # suelo, prado, cultivo. Casi todo verdadero negativo
    (0.5, 1.5, 50),    # matorral bajo, herbazal alto
    (1.5, 2.5, 60),    # zona de decision
    (2.5, 4.0, 60),    # zona de decision
    (4.0, 6.0, 60),    # zona de decision
    (6.0, 10.0, 50),
    (10.0, 20.0, 50),
    (20.0, np.inf, 30),  # arbolado alto. Casi todo verdadero positivo
]


def universo(zona="paradanta"):
    """Todos los pixeles de CHM que caen dentro de faixa, con su altura.

    Devuelve un DataFrame con una fila por pixel: coordenadas del CENTRO (que es
    el punto que hay que mirar en la ortofoto), altura y de que bloque sale.

    Los CHM de todas las zonas comparten carpeta (A Paradanta esta DENTRO de
    Pontevedra), asi que se filtra por la malla de la zona.
    """
    faixas = gpd.GeoDataFrame(
        pd.concat([gpd.read_file(PROC / f"faixas_{n}_{zona}_ok.gpkg").assign(capa=n)
                   for n in ("nucleos", "illadas")], ignore_index=True),
        crs="EPSG:25829")

    malla = PROC / f"malla_lidar_{zona}.csv"
    quiero = ({b.replace(".LAZ", "_chm.tif") for b in pd.read_csv(malla).bloque}
              if malla.exists() else None)

    trozos = []
    for chm_path in sorted(LIDAR.glob("*_chm.tif")):
        if quiero is not None and chm_path.name not in quiero:
            continue
        with rasterio.open(chm_path) as s:
            h = s.read(1, masked=True)
            recuadro = box(*s.bounds)
            geos = [(g.intersection(recuadro), 1) for g in faixas.geometry
                    if g.intersects(recuadro)]
            if not geos:
                continue
            dentro = rasterize(geos, out_shape=s.shape, transform=s.transform,
                               fill=0, all_touched=False, dtype="uint8").astype(bool)
            dentro &= ~np.ma.getmaskarray(h)
            fil, col = np.nonzero(dentro)
            # centro del pixel: + 0,5 en las dos direcciones
            x, y = rasterio.transform.xy(s.transform, fil, col, offset="center")
            trozos.append(pd.DataFrame({
                "x": np.round(x, 2), "y": np.round(y, 2),
                "chm_m": np.round(np.asarray(h)[fil, col], 2),
                "bloque": chm_path.name[:-8],
            }))
    if not trozos:
        raise SystemExit("no hay CHM: corre antes pipeline_chm.py")
    return pd.concat(trozos, ignore_index=True)


def sortea(uni, escala, rng):
    """Muestreo estratificado con separacion minima. Devuelve el DataFrame."""
    elegidos = []
    xy = np.empty((0, 2))
    resumen = []

    for lo, hi, cuota in ESTRATOS:
        n = max(1, int(round(cuota * escala)))
        pool = uni[(uni.chm_m >= lo) & (uni.chm_m < hi)]
        area_ha = len(pool) / 1e4  # 1 pixel = 1 m2
        if pool.empty:
            resumen.append((lo, hi, 0, 0.0, 0.0))
            continue

        # se recorre el pool barajado y se acepta si esta lejos de lo ya aceptado.
        # Con pools de cientos de miles de pixeles no hace falta mirarlos todos:
        # se corta en cuanto hay cuota, y el limite evita el peor caso patologico
        # de un estrato diminuto y muy agrupado.
        orden = rng.permutation(len(pool))[: max(60 * n, 20000)]
        tomados = []
        for i in orden:
            if len(tomados) >= n:
                break
            f = pool.iloc[i]
            p = np.array([f.x, f.y])
            if len(xy) and np.min(np.hypot(*(xy - p).T)) < SEP_MIN:
                continue
            tomados.append(f)
            xy = np.vstack([xy, p])

        peso = area_ha * 1e4 / len(tomados)  # m2 de faixa que representa cada punto
        for f in tomados:
            elegidos.append({**f.to_dict(), "estrato": f"[{lo:g},{hi:g})",
                             "peso_m2": round(peso, 2)})
        resumen.append((lo, hi, len(tomados), area_ha, peso))

    m = pd.DataFrame(elegidos)
    print(f"  {'estrato':>14} {'area faixa':>12} {'puntos':>7} {'m2/punto':>10}")
    for lo, hi, n, ha, peso in resumen:
        print(f"  {f'[{lo:g}, {hi:g})':>14} {ha:>9.1f} ha {n:>7} {peso:>10.1f}")
    return m


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=400,
                    help="tamano de muestra objetivo (se reparte por cuotas)")
    ap.add_argument("--semilla", type=int, default=SEMILLA)
    args = ap.parse_args()

    SALIDA.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(args.semilla)

    uni = universo()
    print(f"universo: {len(uni):,} pixeles de faixa con CHM "
          f"({len(uni)/1e4:.1f} ha) en {uni.bloque.nunique()} bloques\n")

    escala = args.n / sum(c for _, _, c in ESTRATOS)
    m = sortea(uni, escala, rng)

    # id estable y orden de anotacion barajado: si se anotara por estratos, el que
    # anota aprenderia la secuencia ("van cinco seguidos de bosque") y responderia
    # por inercia
    m = m.reset_index(drop=True)
    m["id"] = [f"v{i:04d}" for i in range(len(m))]
    m["orden"] = rng.permutation(len(m))
    m = m.sort_values("orden").reset_index(drop=True)

    cols = ["id", "orden", "x", "y", "chm_m", "estrato", "peso_m2", "bloque"]
    m[cols].to_csv(SALIDA / "muestra.csv", index=False, encoding="utf-8-sig")
    gpd.GeoDataFrame(m[cols], geometry=gpd.points_from_xy(m.x, m.y),
                     crs="EPSG:25829").to_file(SALIDA / "muestra.gpkg")

    cob = 100 * m.peso_m2.sum() / len(uni)
    print(f"\n{len(m)} puntos, semilla {args.semilla}, separacion minima {SEP_MIN:g} m")
    print(f"control de pesos: suman {m.peso_m2.sum()/1e4:.1f} ha "
          f"vs {len(uni)/1e4:.1f} ha de universo ({cob:.1f} %)")
    print(f"-> {(SALIDA / 'muestra.csv').relative_to(RAIZ)}")
    print(f"-> {(SALIDA / 'muestra.gpkg').relative_to(RAIZ)}")
