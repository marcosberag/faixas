"""Hoja de referencia para distinguir tipo de copa en la ortofoto.

Se genera con ejemplos reales de la zona piloto, para tenerla al lado mientras se
anota. Responde a la pregunta secundaria del anotador: de que tipo es la copa, y
sobre todo si la especie esta en la lista prohibida o exenta.

CUIDADO CON LA ACACIA. Es una frondosa Y ESTA PROHIBIDA (disp. ad. 3a.1), asi que
no vale agrupar por botanica: hay que agrupar por estatus legal. Esa confusion se
llevo por delante la primera version de las categorias del anotador.

DOS AVISOS QUE VAN IMPRESOS EN LA PROPIA HOJA
----------------------------------------------

1. Los ejemplos son FOTOINTERPRETACION ORIENTATIVA, no verdad de campo. Nadie ha
   ido a mirar esos arboles. Se eligen por rasgos objetivos — altura del CHM,
   forma de copa, patron de plantacion — y sirven para calibrar el ojo, no como
   etiqueta definitiva.

2. Los ejemplos NO salen de la muestra de validacion. Estan a mas de 60 m de
   cualquier punto sorteado. Si salieran de la muestra serian respuestas dadas de
   antemano, y la pregunta de tipo dejaria de medir nada.

La altura es el rasgo mas fiable, porque no depende del ojo: en Galicia solo el
eucalipto pasa de 35 m con regularidad.

Uso:
    python scripts/chuleta_especie.py
"""
import pathlib
import sys

import matplotlib
import numpy as np
import rasterio
from PIL import Image

matplotlib.use("Agg")
from matplotlib import pyplot as plt
from matplotlib.patches import Rectangle

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from chips_validacion import recorta  # noqa: E402

RAIZ = pathlib.Path(__file__).resolve().parent.parent
ORTO = RAIZ / "datos" / "crudo" / "ortofoto"
LIDAR = RAIZ / "datos" / "procesado" / "lidar"
SALIDAS = RAIZ / "salidas"

LADO, PX = 50, 460

# Elegidas a mano sobre la zona piloto, lejos de la muestra. La `lectura` dice POR
# QUE se interpreta asi, que es lo que hay que aprender: la etiqueta sola no
# ensena a mirar.
FICHAS = [
    dict(grupo="PINO — de la lista", legal=False,
         x=549694, y=4678554, bloque="PNOA-2024-GAL-549-4679-H29-NPC01",
         lectura="Copas pequeñas y numerosas, puntiagudas. Textura granulada\n"
                 "fina y verde oscuro apagado. En el CHM, muchas copas del\n"
                 "mismo tamaño y altura pareja (27–31 m): masa regular."),
    dict(grupo="EUCALIPTO — de la lista", legal=False,
         x=562304, y=4667876, bloque="PNOA-2024-GAL-562-4668-H29-NPC01",
         lectura="51 m de altura. EN GALICIA NADA MÁS LLEGA AHÍ.\n"
                 "Copa rala y despeinada, verde azulado, se ve suelo entre\n"
                 "pies. Sombras larguísimas. La altura basta para decidir."),
    dict(grupo="EUCALIPTO joven — de la lista", legal=False,
         x=549754, y=4678160, bloque="PNOA-2024-GAL-549-4679-H29-NPC01",
         lectura="Picos sueltos de 41 m sobresaliendo de una masa de 25.\n"
                 "Ese perfil dentado, con pies muy altos aislados, es\n"
                 "típico de eucaliptal sobre rebrote de cepa."),
    dict(grupo="FRONDOSA — EXENTA", legal=True,
         x=559660, y=4673298, bloque="PNOA-2024-GAL-559-4674-H29-NPC01",
         lectura="Bosquete de copas redondeadas y anchas sobre pasto seco.\n"
                 "Textura mullida, de brócoli. Borde neto contra el prado.\n"
                 "Altura moderada (26–30 m). Patrón de soto."),
    dict(grupo="FRONDOSA — EXENTA", legal=True,
         x=562482, y=4667128, bloque="PNOA-2024-GAL-562-4668-H29-NPC01",
         lectura="Copas grandes individualizadas, verde claro y cálido.\n"
                 "Cada copa se distingue de la vecina. Sin alineación.\n"
                 "14–23 m: rango de castaño y roble."),
    dict(grupo="FRONDOSA de ribera — EXENTA", legal=True,
         x=559120, y=4673816, bloque="PNOA-2024-GAL-559-4674-H29-NPC01",
         lectura="Copas anchas siguiendo el borde de una pista y un linde,\n"
                 "en franja estrecha y no en masa. Aliso, fresno y sauce\n"
                 "van así: en línea, en fondo de valle o junto al agua."),
]

ALTO_FIG = 13.0
ANCHO_FIG = 19.0
ANCHO_O = .185                                     # la ortofoto, en fraccion de figura
ALTO_O = ANCHO_O * ANCHO_FIG / ALTO_FIG            # cuadrada de verdad
ANCHO_H, ALTO_H = .0916 * 19 / ANCHO_FIG, .145 * 12.6 / ALTO_FIG
COL = .323                        # separacion entre columnas
FILA_Y = (.630, .240)             # borde inferior de cada fila de imagenes


def ficha(fig, f, fila, col):
    """Una ficha: ortofoto grande, CHM al lado y la lectura debajo de las dos.

    Se posiciona con coordenadas de figura y no con `subplots` porque las tres
    piezas tienen tamanos distintos y hay que poder poner el texto abarcando el
    ancho de las dos imagenes; con el texto colgado del eje del CHM se desbordaba
    por los lados y se montaba sobre la ortofoto de al lado.
    """
    x0, y0 = .035 + col * COL, FILA_Y[fila]
    ax_o = fig.add_axes([x0, y0, ANCHO_O, ALTO_O])
    ax_h = fig.add_axes([x0 + ANCHO_O + .022, y0 + (ALTO_O - ALTO_H) / 2,
                         ANCHO_H, ALTO_H])

    with rasterio.open(ORTO / f"{f['bloque']}_orto.tif") as so:
        a = recorta(so, f["x"], f["y"], LADO, PX)
    ax_o.imshow(Image.fromarray(np.moveaxis(a, 0, 2)))
    color = "#2f855a" if f["legal"] else "#c53030"
    ax_o.set_title(f["grupo"], fontsize=13, color=color, fontweight="bold",
                   pad=7, loc="left")
    # rejilla de 10 m, la misma que llevan los chips del anotador
    for k in range(1, LADO // 10):
        p = k * 10 * PX / LADO
        ax_o.axvline(p, color="w", lw=.5, alpha=.3)
        ax_o.axhline(p, color="w", lw=.5, alpha=.3)
    ax_o.add_patch(Rectangle((0, 0), 1, 1, transform=ax_o.transAxes,
                             fill=False, ec=color, lw=3.5))

    with rasterio.open(LIDAR / f"{f['bloque']}_chm.tif") as sc:
        h = recorta(sc, f["x"], f["y"], LADO, LADO)[0].astype("float32")
    h[h < -1000] = 0
    ax_h.imshow(h, cmap="viridis", vmin=0, vmax=45)
    ax_h.set_title(f"CHM · máx {h.max():.0f} m", fontsize=10)

    fig.text(x0, y0 - .017, f["lectura"], ha="left", va="top", fontsize=9.5,
             family="monospace", color="#2a2a2a", linespacing=1.5)
    for a in (ax_o, ax_h):
        a.set_xticks([])
        a.set_yticks([])


if __name__ == "__main__":
    fig = plt.figure(figsize=(ANCHO_FIG, ALTO_FIG))
    fig.suptitle("Cómo se ve cada tipo de copa desde arriba — zona piloto de A Paradanta",
                 fontsize=18, y=.975)
    fig.text(.5, .947, "Recuadros de 50 × 50 m con rejilla de 10 m, la misma de los chips.   "
             "Rojo = especie de la lista prohibida   ·   Verde = frondosa exenta "
             "(disp. ad. 3ª.3)", ha="center", fontsize=11.5, color="#555")

    for k, f in enumerate(FICHAS):
        ficha(fig, f, *divmod(k, 3))

    fig.text(.5, .142,
             "LA ALTURA ES EL RASGO MÁS FIABLE, porque no depende del ojo: en Galicia solo el eucalipto pasa de 35 m con regularidad.\n"
             "Mide la sombra con la rejilla si dudas.   ·   Pino 20–25 m   ·   Eucalipto 30–50 m   ·   Castaño y roble 15–20 m   ·   Acacia 8–12 m",
             ha="center", va="center", fontsize=12, color="#1a1a1a",
             fontweight="semibold",
             bbox=dict(boxstyle="round,pad=0.7", fc="#fff6d6", ec="#d9c689"))

    # sin foto a proposito: no hay ningun rodal de acacia confirmado en la zona
    # piloto, y poner uno mal etiquetado propagaria el error a las 400
    # anotaciones. El aviso sin imagen es peor chuleta y mejor dato.
    fig.text(.5, .075,
             "OJO CON LA ACACIA (mimosa, Acacia dealbata): es una FRONDOSA y ESTÁ PROHIBIDA — es la trampa de esta clasificación.\n"
             "Manta continua de grano muy fino, plateada o azulada, sin copas individuales ni huecos. Invade taludes, bordes de pista y zonas quemadas,\n"
             "sin límite recto de parcela. Si dudas entre acacia y eucalipto da igual para la ley: las dos están en la lista. No la marques como frondosa.",
             ha="center", va="center", fontsize=10.5, color="#7a2620",
             bbox=dict(boxstyle="round,pad=0.6", fc="#fdeceb", ec="#e0a9a4"))

    fig.text(.5, .006, va="bottom",
             s="Ejemplos elegidos por fotointerpretación sobre rasgos objetivos (altura, forma de copa, patrón). NO son verdad de campo: nadie ha ido a mirar esos árboles.\n"
             "Ninguno pertenece a la muestra de validación — todos están a más de 60 m de cualquier punto sorteado.   Si no lo ves claro al anotar, la respuesta es «no distinguible».\n"
             "Ortofoto PNOA sept-2023 · LiDAR PNOA 2024 · IGN/CNIG (CC-BY 4.0)",
             ha="center", fontsize=8.5, color="#666")

    SALIDAS.mkdir(exist_ok=True)
    out = SALIDAS / "chuleta_tipo_copa.png"
    fig.savefig(out, dpi=105)
    plt.close(fig)
    print(f"-> {out.relative_to(RAIZ)}  ({out.stat().st_size/1e6:.1f} MB)")
