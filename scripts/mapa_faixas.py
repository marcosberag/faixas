"""Ortofoto PNOA (WMS IGN) + faixas 50 m, recoloreadas a partir de la mascara alfa."""
import io
import json
import pathlib

import requests
from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont

BASE = ("https://ideg.xunta.gal/servizos/rest/services/PBA/"
        "Afeccions_Agropecuaria_Faixas/MapServer")
WMS = "https://www.ign.es/wms-inspire/pnoa-ma"
CONCELLOS = ["Arbo", "Cañiza, A", "Covelo", "Crecente"]
WHERE = "CONCELLO IN (" + ", ".join(f"'{c}'" for c in CONCELLOS) + ")"
SALIDA = pathlib.Path(__file__).parent

RELLENO = (255, 96, 0)      # naranja
BORDE = (255, 190, 60)      # amarillo calido
ALFA_RELLENO = 78


def ortofoto(caja, w, h):
    r = requests.get(WMS, params={
        "SERVICE": "WMS", "VERSION": "1.3.0", "REQUEST": "GetMap",
        "LAYERS": "OI.OrthoimageCoverage", "STYLES": "", "CRS": "EPSG:25829",
        "BBOX": "{},{},{},{}".format(*caja), "WIDTH": w, "HEIGHT": h,
        "FORMAT": "image/jpeg"}, timeout=180)
    r.raise_for_status()
    return Image.open(io.BytesIO(r.content)).convert("RGB")


def mascara_faixas(caja, w, h):
    """PNG transparente del servicio -> mascara binaria (L) de donde hay faixa."""
    ldef = json.dumps({"0": WHERE, "1": WHERE})
    r = requests.get(f"{BASE}/export", params={
        "bbox": "{},{},{},{}".format(*caja), "bboxSR": 25829, "imageSR": 25829,
        "size": f"{w},{h}", "layers": "show:0,1", "layerDefs": ldef,
        "transparent": "true", "format": "png32", "dpi": 96, "f": "image"},
        timeout=180)
    r.raise_for_status()
    alfa = Image.open(io.BytesIO(r.content)).convert("RGBA").split()[3]
    return alfa.point(lambda v: 255 if v > 40 else 0)


def pinta(base, masc, grosor):
    """Relleno translucido + contorno opaco, dejando ver la ortofoto."""
    img = base.convert("RGBA")

    capa = Image.new("RGBA", img.size, RELLENO + (0,))
    capa.putalpha(masc.point(lambda v: ALFA_RELLENO if v else 0))
    img = Image.alpha_composite(img, capa)

    interior = masc.filter(ImageFilter.MinFilter(grosor))
    contorno = ImageChops.subtract(masc, interior)
    linea = Image.new("RGBA", img.size, BORDE + (0,))
    linea.putalpha(contorno.point(lambda v: 255 if v else 0))
    return Image.alpha_composite(img, linea)


def fuente(px):
    for nom in ("segoeui.ttf", "arial.ttf", "DejaVuSans.ttf"):
        try:
            return ImageFont.truetype(nom, px)
        except OSError:
            continue
    return ImageFont.load_default()


def rotula(img, titulo, pie):
    d = ImageDraw.Draw(img)
    W, H = img.size
    barra = int(H * 0.125)
    d.rectangle([0, H - barra, W, H], fill=(11, 11, 13, 240))
    f1, f2 = fuente(int(barra * 0.33)), fuente(int(barra * 0.195))
    d.text((int(W * 0.026), H - barra + int(barra * 0.15)), titulo,
           font=f1, fill=(255, 255, 255))
    d.text((int(W * 0.026), H - barra + int(barra * 0.60)), pie,
           font=f2, fill=(165, 165, 172))
    # muestra de color junto al pie
    return img


def compone(caja, w, h, titulo, pie, destino, grosor=5):
    base = ortofoto(caja, w, h)
    masc = mascara_faixas(caja, w, h)
    img = pinta(base, masc, grosor)
    rotula(img, titulo, pie)
    img.convert("RGB").save(destino, quality=93)
    cobertura = sum(masc.point(lambda v: 1 if v else 0).getdata()) / (w * h)
    print(f"-> {destino.name}  {w}x{h}  faixa cubre {cobertura:.1%} del encuadre")


BBOX = [548731.0, 4661398.0, 567278.0, 4685317.0]

cx, cy = (BBOX[0] + BBOX[2]) / 2, (BBOX[1] + BBOX[3]) / 2
W, H = 1600, 900
med = max((BBOX[2] - BBOX[0]) / W, (BBOX[3] - BBOX[1]) / H) * 1.06
pan = (cx - med * W / 2, cy - med * H / 2, cx + med * W / 2, cy + med * H / 2)
compone(pan, W, H,
        "A Paradanta: las franjas de protección de 50 m",
        "Capa oficial de la Xunta sobre ortofoto PNOA (IGN) · EPSG:25829",
        SALIDA / "post_1_comarca.jpg", grosor=3)

ZOOM = (558731.0, 4665398.0, 560731.0, 4667398.0)
zx, zy = (ZOOM[0] + ZOOM[2]) / 2, (ZOOM[1] + ZOOM[3]) / 2
lado = 1400.0
compone((zx - lado / 2, zy - lado / 2, zx + lado / 2, zy + lado / 2), 1200, 1200,
        "Dentro de la franja no debería haber arbolado",
        "1,4 km de lado · A Paradanta (Pontevedra) · ortofoto PNOA (IGN)",
        SALIDA / "post_2_zoom.jpg", grosor=7)
