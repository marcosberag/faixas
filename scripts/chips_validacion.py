"""Descarga la ortofoto del PNOA y recorta un chip por punto de la muestra.

Dos pasos:

1. MOSAICO. Un GeoTIFF de ortofoto por bloque, a 0,125 m/pixel. El WMS del IGN
   corta las peticiones en 4096 px, asi que se pide troceado y se cose. Se cachea
   en disco: bajarlo cuesta un par de minutos por bloque y no hay motivo para
   repetirlo.

   0,125 m/px y no los 0,15 m nativos de la ortofoto es a proposito: 8 pixeles de
   ortofoto por pixel de CHM, exacto y sin desfase. Con 0,15 m el km sale a
   6666,67 px y la rejilla no cierra. Sobremuestrear no inventa detalle, pero
   mantener la alineacion exacta evita un error de medio pixel al recortar, que a
   40 m de chip es visible.

   EL MOSAICO SE PASA DEL BLOQUE 32 m POR CADA LADO. Sin ese margen, todo punto
   de la muestra a menos de 20 m del borde del km sale con media imagen en negro
   y no se puede fotointerpretar. Son un 8 % de los puntos, y no se pueden tirar
   sin sesgar: el borde del bloque LiDAR es una linea arbitraria que no tiene
   nada que ver con donde hay arbolado.

2. CHIPS. Tres imagenes por punto de la muestra:

   `chips/`      40 x 40 m, rejilla de 10 m. Es el que se juzga.
   `chips_ctx/`  120 x 120 m, rejilla de 20 m, con el recuadro de 40 m marcado.
                 Para desempatar por el patron de alrededor.
   `chips_chm/`  el CHM del mismo recuadro. NO se enseña durante la anotacion.

   Las tres llevan una mira con el centro HUECO: si tapara el punto habria que
   adivinar que hay debajo, que es justo lo que se pregunta.

   LA REJILLA METRICA NO ES DECORACION. En una foto aerea sin coches ni edificios
   cerca no hay forma de saber si una mancha mide dos metros o veinte, y esa es
   exactamente la diferencia entre un pino joven y una mata de tojo — la frontera
   que el criterio de anotacion pide vigilar. Con cuadrados de tamano conocido
   encima, el ojo se calibra solo. El circulo de la mira mide 3 m de diametro
   reales y sirve de segunda referencia.

   El chip de CHM se guarda para `revisa_discrepancias.py`, que se corre cuando la
   anotacion ya esta cerrada. Durante la anotacion no se enseña nunca: ver la
   explicacion del sesgo de confirmacion en `muestra_validacion.py`.

Uso:
    python scripts/chips_validacion.py
    python scripts/chips_validacion.py --solo-mosaico
"""
import argparse
import io
import pathlib
import time

import numpy as np
import pandas as pd
import rasterio
import requests
from PIL import Image, ImageDraw
from rasterio.windows import from_bounds

RAIZ = pathlib.Path(__file__).resolve().parent.parent
PROC = RAIZ / "datos" / "procesado"
LIDAR = PROC / "lidar"
VAL = PROC / "validacion"
ORTO = RAIZ / "datos" / "crudo" / "ortofoto"

WMS_PNOA = "https://www.ign.es/wms-inspire/pnoa-ma"
RES_ORTO = 0.125          # m/px. 8 px de ortofoto por pixel de CHM

# Dos encuadres del mismo punto. El de 40 m es el que se juzga; el de 120 m sirve
# para desempatar por el patron de alrededor (una plantacion en lineas no se
# parece a una mancha de matorral). No sesga: es la misma pregunta con mas
# contexto, y en fotointerpretacion tener el zoom out a mano es lo normal.
LADO_CHIP = 40
PX_CHIP = int(LADO_CHIP / RES_ORTO)          # 320
LADO_CTX = 120
PX_CTX = 480                                  # 0,25 m/px: basta para el patron
REJILLA = 10                                  # m entre lineas en el chip
REJILLA_CTX = 20
MIRA_M = 3.0              # diametro real del circulo de la mira, en metros

# el mosaico tiene que dar de si para el encuadre grande: 60 m desde el centro
MARGEN = 64               # m que el mosaico se pasa del bloque por cada lado
# 1128 m a 0,125 m/px son 9024 px, que se parten en 4x4 teselas de 2256 px
# exactos. La division tiene que dar entero o las teselas no casan al coserlas,
# y 2256 esta comodamente por debajo del limite de 4096 px del servicio.
N_TESELAS = 4
PX_MOSAICO = int((1000 + 2 * MARGEN) / RES_ORTO)
PX_TESELA = PX_MOSAICO // N_TESELAS
assert PX_TESELA * N_TESELAS == PX_MOSAICO and PX_TESELA <= 4096
assert MARGEN >= LADO_CTX / 2, "el encuadre grande se sale del mosaico"


def tesela(x0, y0, lado, px):
    """Un trozo cuadrado de ortofoto del WMS. Devuelve un array pxXpxX3."""
    r = requests.get(WMS_PNOA, timeout=300, params={
        "SERVICE": "WMS", "VERSION": "1.3.0", "REQUEST": "GetMap",
        "LAYERS": "OI.OrthoimageCoverage", "STYLES": "", "CRS": "EPSG:25829",
        # WMS 1.3.0 con CRS proyectado: el BBOX va minx,miny,maxx,maxy
        "BBOX": f"{x0},{y0},{x0+lado},{y0+lado}",
        "WIDTH": px, "HEIGHT": px, "FORMAT": "image/jpeg",
    })
    r.raise_for_status()
    # el servicio devuelve los errores con HTTP 200 y un XML dentro, asi que el
    # codigo de estado no sirve para saber si ha ido bien
    if "image" not in r.headers.get("Content-Type", ""):
        raise RuntimeError(f"el WMS devolvio {r.text[:300]}")
    a = np.asarray(Image.open(io.BytesIO(r.content)).convert("RGB"))
    if a.shape[:2] != (px, px):
        raise RuntimeError(f"esperaba {px}x{px}, llego {a.shape}")
    return a


def mosaico(bloque):
    """GeoTIFF de ortofoto del bloque mas MARGEN por cada lado. Cacheado."""
    ORTO.mkdir(parents=True, exist_ok=True)
    ruta = ORTO / f"{bloque}_orto.tif"
    if ruta.exists():
        return ruta

    p = bloque.split("-")
    # el nombre del LAZ codifica la esquina NOROESTE del km, no la suroeste
    x_o, y_n = int(p[3]) * 1000 - MARGEN, int(p[4]) * 1000 + MARGEN
    y_s = y_n - (1000 + 2 * MARGEN)
    lado_t = PX_TESELA * RES_ORTO
    lienzo = np.zeros((PX_MOSAICO, PX_MOSAICO, 3), "uint8")

    print(f"  bajando {bloque}", end="", flush=True)
    t0 = time.perf_counter()
    for i in range(N_TESELAS):        # columnas, de oeste a este
        for j in range(N_TESELAS):    # filas, de sur a norte
            a = tesela(x_o + i * lado_t, y_s + j * lado_t, lado_t, PX_TESELA)
            # el array va de norte a sur, asi que la fila j=0 (la del sur) es la
            # de abajo del lienzo
            fila = (N_TESELAS - 1 - j) * PX_TESELA
            lienzo[fila:fila + PX_TESELA, i * PX_TESELA:(i + 1) * PX_TESELA] = a
            print(".", end="", flush=True)

    perfil = {
        "driver": "GTiff", "height": PX_MOSAICO, "width": PX_MOSAICO, "count": 3,
        "dtype": "uint8", "crs": "EPSG:25829",
        "transform": rasterio.transform.from_origin(x_o, y_n, RES_ORTO, RES_ORTO),
        "compress": "JPEG", "jpeg_quality": 90, "photometric": "YCBCR",
        "tiled": True, "blockxsize": 512, "blockysize": 512,
    }
    with rasterio.open(ruta, "w", **perfil) as dst:
        dst.write(np.moveaxis(lienzo, 2, 0))
    print(f" {time.perf_counter()-t0:.0f} s  {ruta.stat().st_size/1e6:.1f} MB")
    return ruta


def mira(im, lado_m, rejilla_m=None, recuadro_m=None):
    """Mira, rejilla metrica y barra de escala sobre un chip cuadrado.

    LA REJILLA ES LA PIEZA IMPORTANTE. En una foto aerea sin referencias
    familiares no hay forma de saber si lo que se ve mide dos metros o veinte, y
    sin eso no se puede distinguir un pino joven de una mata de tojo. Con
    cuadrados de tamano conocido encima, el ojo se calibra solo en cuanto los ve.

    El circulo de la mira mide MIRA_M metros de diametro reales, asi que tambien
    sirve de referencia: lo que llena el circulo mide tres metros.
    """
    px = im.size[0]
    ppm = px / lado_m          # pixeles por metro
    c = px / 2
    capa = Image.new("RGBA", im.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(capa)

    if rejilla_m:
        # tenue: tiene que dar escala sin competir con lo que hay que mirar
        for k in range(1, int(round(lado_m / rejilla_m))):
            p = k * rejilla_m * ppm
            d.line([p, 0, p, px], fill=(255, 255, 255, 60), width=1)
            d.line([0, p, px, p], fill=(255, 255, 255, 60), width=1)

    if recuadro_m:                      # marca el encuadre del chip pequeno
        r = recuadro_m * ppm / 2
        d.rectangle([c - r, c - r, c + r, c + r],
                    outline=(255, 255, 60, 150), width=2)

    hueco = MIRA_M * ppm / 2
    largo = 4.2 * ppm
    # negro grueso debajo y amarillo fino encima: se ve sobre copa oscura y sobre
    # camino claro, que es donde mas cuesta
    for color, ancho in (((0, 0, 0, 210), 5), ((255, 255, 60, 255), 2)):
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            d.line([c + dx * hueco, c + dy * hueco,
                    c + dx * (hueco + largo), c + dy * (hueco + largo)],
                   fill=color, width=ancho)
        d.ellipse([c - hueco, c - hueco, c + hueco, c + hueco],
                  outline=color, width=max(1, ancho - 3))

    # barra de escala de una casilla de rejilla, abajo a la izquierda
    if rejilla_m:
        b = rejilla_m * ppm
        x0, y0 = 0.06 * px, px - 0.055 * px
        d.line([x0, y0, x0 + b, y0], fill=(0, 0, 0, 210), width=6)
        d.line([x0, y0, x0 + b, y0], fill=(255, 255, 255, 255), width=3)
        for x in (x0, x0 + b):          # topes
            d.line([x, y0 - 5, x, y0 + 5], fill=(255, 255, 255, 255), width=3)
        d.text((x0, y0 - 19), f"{rejilla_m:g} m", fill=(255, 255, 255, 255),
               stroke_width=2, stroke_fill=(0, 0, 0, 220))

    return Image.alpha_composite(im.convert("RGBA"), capa).convert("RGB")


def colorea_chm(h, px=PX_CHIP):
    """El recorte de CHM en la misma escala viridis 0-30 m de los paneles."""
    from matplotlib import cm
    v = np.clip(np.nan_to_num(h, nan=0.0) / 30.0, 0, 1)
    rgb = (cm.viridis(v)[:, :, :3] * 255).astype("uint8")
    return Image.fromarray(rgb).resize((px, px), Image.NEAREST)


def recorta(src, x, y, lado_m, px_destino):
    """Ventana cuadrada centrada en (x, y) leida de un raster abierto."""
    v = from_bounds(x - lado_m / 2, y - lado_m / 2,
                    x + lado_m / 2, y + lado_m / 2, transform=src.transform)
    v = v.round_offsets().round_lengths()
    return src.read(window=v, boundless=True, fill_value=0,
                    out_shape=(src.count, px_destino, px_destino))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--solo-mosaico", action="store_true")
    args = ap.parse_args()

    m = pd.read_csv(VAL / "muestra.csv", encoding="utf-8-sig")
    bloques = sorted(m.bloque.unique())
    print(f"{len(m)} puntos en {len(bloques)} bloques")

    ortos = {b: mosaico(b) for b in bloques}
    if args.solo_mosaico:
        raise SystemExit(0)

    dir_orto = VAL / "chips"
    dir_ctx = VAL / "chips_ctx"
    dir_chm = VAL / "chips_chm"
    for d in (dir_orto, dir_ctx, dir_chm):
        d.mkdir(exist_ok=True)

    print("\nrecortando chips")
    t0 = time.perf_counter()
    huecos = []
    for b in bloques:
        sub = m[m.bloque == b]
        with rasterio.open(ortos[b]) as so, rasterio.open(LIDAR / f"{b}_chm.tif") as sc:
            for _, f in sub.iterrows():
                a = recorta(so, f.x, f.y, LADO_CHIP, PX_CHIP)
                # el relleno del recorte es negro puro, que en una ortofoto real
                # no aparece: sirve para detectar que el mosaico no llegaba
                negro = float((a.max(axis=0) == 0).mean())
                if negro > 0.01:
                    huecos.append((f.id, negro))
                mira(Image.fromarray(np.moveaxis(a, 0, 2)), LADO_CHIP, REJILLA) \
                    .save(dir_orto / f"{f.id}.jpg", quality=82, optimize=True)

                a = recorta(so, f.x, f.y, LADO_CTX, PX_CTX)
                mira(Image.fromarray(np.moveaxis(a, 0, 2)), LADO_CTX, REJILLA_CTX,
                     recuadro_m=LADO_CHIP) \
                    .save(dir_ctx / f"{f.id}.jpg", quality=78, optimize=True)

                h = recorta(sc, f.x, f.y, LADO_CHIP, LADO_CHIP)[0].astype("float32")
                h[h < -1000] = 0  # nodata
                mira(colorea_chm(h), LADO_CHIP, REJILLA) \
                    .save(dir_chm / f"{f.id}.png", optimize=True)
        print(f"  {b}  {len(sub)} puntos")

    if huecos:
        print(f"\n  AVISO: {len(huecos)} chips con hueco negro. Sube MARGEN.")
        for i, n in huecos[:5]:
            print(f"    {i}  {100*n:.0f} % de la imagen")

    mb = sum(p.stat().st_size for d in (dir_orto, dir_ctx, dir_chm)
             for p in d.iterdir()) / 1e6
    print(f"\n{3*len(m)} imagenes en {time.perf_counter()-t0:.0f} s, {mb:.1f} MB")
    print(f"-> {dir_orto.relative_to(RAIZ)}  ({LADO_CHIP} m, rejilla {REJILLA} m)")
    print(f"-> {dir_ctx.relative_to(RAIZ)}  ({LADO_CTX} m, rejilla {REJILLA_CTX} m)")
    print(f"-> {dir_chm.relative_to(RAIZ)}")
