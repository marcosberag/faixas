"""Muestra para validar el PRODUCTO final fuera de muestra (fase 4).

En que se diferencia de muestra_validacion.py, que es de donde importa todo:

  - EXCLUYE los 3 bloques del piloto. La fase 2 calibro el umbral con puntos de
    esos bloques: reutilizarlos aqui seria validar el producto con los datos que
    lo entrenaron. Los 260 restantes son terreno virgen.
  - El umbral ya esta FIJADO (5,5 m), asi que las cuotas cambian de objetivo:
    la fase 2 sobremuestreaba los 1-6 m para ELEGIR umbral; aqui se sobremuestrea
    por encima de 5,5 m, que es donde vive la tasa de falsos positivos del
    producto (fraccion de lo SEnALADO que no es arbol).
  - Estrato nuevo >= 35 m: valida el suelo estructural del eucalipto. Pocos
    puntos: la pregunta es solo "¿es un arbol enorme o un artefacto?".
  - Ids con prefijo p (p0000...) para que nunca se mezclen con los v de fase 2.

Uso:
    python scripts/muestra_producto.py
"""
import pathlib
import sys

import geopandas as gpd
import numpy as np

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import muestra_validacion as mv

RAIZ = pathlib.Path(__file__).resolve().parent.parent
SALIDA = RAIZ / "datos" / "procesado" / "validacion_producto"

SEMILLA = 20260819
PILOTO = ("PNOA-2024-GAL-559-4674-H29-NPC01",
          "PNOA-2024-GAL-562-4668-H29-NPC01",
          "PNOA-2024-GAL-549-4679-H29-NPC01")

ESTRATOS = [
    (0.0, 2.0, 40),      # negativo claro: controla omision gruesa
    (2.0, 5.5, 60),      # bajo el umbral: aqui se miden las omisiones
    (5.5, 8.0, 60),      # recien senalado: aqui vive la tasa de FP
    (8.0, 15.0, 45),
    (15.0, 35.0, 30),
    (35.0, np.inf, 15),  # el suelo del eucalipto: ¿arbol enorme o artefacto?
]

if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--zona", default="paradanta")
    ap.add_argument("--n", type=int, default=None,
                    help="tamanho de muestra: escala las cuotas proporcionalmente")
    ap.add_argument("--semilla", type=int, default=None)
    args = ap.parse_args()

    if args.zona != "paradanta":
        # cada territorio, su carpeta: el HTML del anotador y el CSV descargado
        # tienen que vivir juntos o se pisan (ya paso una vez, fase 2 vs fase 4)
        SALIDA = RAIZ / "datos" / "procesado" / f"validacion_{args.zona}"
        SEMILLA = 20260822
        # fuera de A Paradanta no hay nada que excluir: la calibracion no vio
        # ninguno de esos bloques, todo el territorio es virgen
        PILOTO = ()
    if args.semilla:
        SEMILLA = args.semilla
    if args.n:
        f = args.n / sum(c for _, _, c in ESTRATOS)
        ESTRATOS = [(a, b, max(1, round(c * f))) for a, b, c in ESTRATOS]

    SALIDA.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(SEMILLA)

    uni = mv.universo(args.zona)
    antes = len(uni)
    if PILOTO:
        uni = uni[~uni.bloque.isin(PILOTO)].reset_index(drop=True)
        print(f"universo: {antes:,} px; sin los 3 bloques del piloto quedan "
              f"{len(uni):,} ({len(uni)/1e4:.1f} ha en {uni.bloque.nunique()} bloques)\n")
    else:
        print(f"universo: {len(uni):,} px ({len(uni)/1e4:.1f} ha en "
              f"{uni.bloque.nunique()} bloques)\n")

    # sortea() lee las cuotas del modulo: se le ponen las de aqui
    mv.ESTRATOS = ESTRATOS
    m = mv.sortea(uni, 1.0, rng)

    m = m.reset_index(drop=True)
    m["id"] = [f"p{i:04d}" for i in range(len(m))]
    m["orden"] = rng.permutation(len(m))
    m = m.sort_values("orden").reset_index(drop=True)

    cols = ["id", "orden", "x", "y", "chm_m", "estrato", "peso_m2", "bloque"]
    m[cols].to_csv(SALIDA / "muestra.csv", index=False, encoding="utf-8-sig")
    gpd.GeoDataFrame(m[cols], geometry=gpd.points_from_xy(m.x, m.y),
                     crs="EPSG:25829").to_file(SALIDA / "muestra.gpkg")

    print(f"\n{len(m)} puntos, semilla {SEMILLA}, en {m.bloque.nunique()} bloques")
    print(f"control de pesos: suman {m.peso_m2.sum()/1e4:.1f} ha "
          f"vs {len(uni)/1e4:.1f} ha de universo")
    print(f"-> {(SALIDA / 'muestra.csv').relative_to(RAIZ)}")
