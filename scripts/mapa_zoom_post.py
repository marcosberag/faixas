"""Version del zoom sin barra de pie: limpia y con atribucion minima."""
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

RELLENO, BORDE, ALFA = (255, 96, 0), (255, 190, 60), 78
ZC = ((558731.0 + 560731.0) / 2, (4665398.0 + 4667398.0) / 2)
LADO, PX = 1400.0, 1200
CAJA = (ZC[0] - LADO / 2, ZC[1] - LADO / 2, ZC[0] + LADO / 2, ZC[1] + LADO / 2)


def ortofoto():
    r = requests.get(WMS, params={
        "SERVICE": "WMS", "VERSION": "1.3.0", "REQUEST": "GetMap",
        "LAYERS": "OI.OrthoimageCoverage", "STYLES": "", "CRS": "EPSG:25829",
        "BBOX": "{},{},{},{}".format(*CAJA), "WIDTH": PX, "HEIGHT": PX,
        "FORMAT": "image/jpeg"}, timeout=180)
    r.raise_for_status()
    return Image.open(io.BytesIO(r.content)).convert("RGB")


def mascara():
    r = requests.get(f"{BASE}/export", params={
        "bbox": "{},{},{},{}".format(*CAJA), "bboxSR": 25829, "imageSR": 25829,
        "size": f"{PX},{PX}", "layers": "show:0,1",
        "layerDefs": json.dumps({"0": WHERE, "1": WHERE}),
        "transparent": "true", "format": "png32", "dpi": 96, "f": "image"},
        timeout=180)
    r.raise_for_status()
    a = Image.open(io.BytesIO(r.content)).convert("RGBA").split()[3]
    return a.point(lambda v: 255 if v > 40 else 0)


def fuente(px):
    for nom in ("segoeui.ttf", "arial.ttf", "DejaVuSans.ttf"):
        try:
            return ImageFont.truetype(nom, px)
        except OSError:
            continue
    return ImageFont.load_default()


def sombra(d, xy, txt, f, col=(255, 255, 255), alfa_s=150):
    x, y = xy
    for dx, dy in ((1, 1), (2, 2)):
        d.text((x + dx, y + dy), txt, font=f, fill=(0, 0, 0, alfa_s))
    d.text((x, y), txt, font=f, fill=col)


base = ortofoto()
masc = mascara()

img = base.convert("RGBA")
capa = Image.new("RGBA", img.size, RELLENO + (0,))
capa.putalpha(masc.point(lambda v: ALFA if v else 0))
img = Image.alpha_composite(img, capa)
contorno = ImageChops.subtract(masc, masc.filter(ImageFilter.MinFilter(7)))
linea = Image.new("RGBA", img.size, BORDE + (0,))
linea.putalpha(contorno.point(lambda v: 255 if v else 0))
img = Image.alpha_composite(img, linea)

limpia = img.copy()
limpia.convert("RGB").save(SALIDA / "post_zoom_limpia.jpg", quality=93)
print("-> post_zoom_limpia.jpg (sin ningun texto)")

# --- version con atribucion minima + barra de escala ----------------------
con = img.copy()
d = ImageDraw.Draw(con, "RGBA")
f = fuente(19)
m = 22

# barra de escala de 200 m abajo a la derecha
esc_m = 200.0
esc_px = int(esc_m / (LADO / PX))
x1, y1 = PX - m, PX - m - 6
x0 = x1 - esc_px
d.line([(x0, y1), (x1, y1)], fill=(255, 255, 255, 235), width=3)
for x in (x0, x1):
    d.line([(x, y1 - 6), (x, y1 + 6)], fill=(255, 255, 255, 235), width=3)
t = "200 m"
w = d.textlength(t, font=f)
sombra(d, (x1 - w, y1 - 30), t, f)

sombra(d, (m, PX - m - 24),
       "franxas: Xunta de Galicia · ortofoto PNOA 2023 © IGN", fuente(18),
       col=(255, 255, 255))

con.convert("RGB").save(SALIDA / "post_zoom_atribucion.jpg", quality=93)
print("-> post_zoom_atribucion.jpg (atribucion + escala, sin barra negra)")
