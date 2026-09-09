"""Compone NDVI de invierno y de verano con Sentinel-2, para separar por fenologia.

Tercera pata de la fase 3. El IFN da la especie pero es de 2010; esto mide lo que
habia en 2024, que es cuando se volo el LiDAR.

POR QUE LA FENOLOGIA VALE AQUI, Y COMO SE HA COMPROBADO
---------------------------------------------------------
El corte legal es una lista de 7 taxones, no «perennifolia contra caducifolia»:
`Quercus suber` y `Laurus nobilis` son perennifolias y estan EXENTAS. O sea que el
proxy fenologico no es el corte legal y usarlo sin mas seria un atajo.

Se ha medido contra el IFN antes de escribir una linea de esto: en la faixa de A
Paradanta el proxy acierta el **99,4 %** de la superficie, con 7,6 ha de
perennifolias exentas (alcornoque, madrono, laurel) y **cero** caducifolias
prohibidas. O sea que aqui el atajo es valido y el error que introduce es de un
orden de magnitud menor que todo lo demas. **Eso es cierto en A Paradanta y no en
general**: en un alcornocal el mismo proxy seria un desastre. Si el metodo se
lleva a otra comarca, hay que rehacer esta comprobacion, no heredarla.

DE DONDE SALEN LAS IMAGENES
----------------------------
Del STAC publico de Element84 sobre los COG de AWS. **No hace falta registrarse ni
autenticarse**, al contrario que el Copernicus Data Space, y se leen por rangos
HTTP: solo se descarga la ventana que interesa, no la escena entera.

    https://earth-search.aws.element84.com/v1

Toda la zona piloto cae dentro de un unico tile MGRS (29TNG), lo que ahorra tener
que mosaicar.

TRES COSAS QUE HAY QUE HACER BIEN O EL NDVI SALE MAL EN SILENCIO
------------------------------------------------------------------
1. **El offset del baseline 04.00, que aqui NO hay que aplicar aunque el STAC
   diga que si.** Desde 2022 los productos L2A de Copernicus traen los valores
   desplazados y la reflectancia es `DN * 0.0001 - 0.1`. El STAC de Element84
   declara `offset: -0.1` en `raster:bands`... pero los COG de `sentinel-cogs`
   ya vienen armonizados a la convencion antigua, asi que **el metadato miente**.

   Comprobado sobre datos, que es la unica forma de decidirlo:

   | | NDVI mediana | fuera de [-1, 1] |
   |---|---|---|
   | aplicando el offset | 1,299 | **71 %** |
   | sin aplicarlo | 0,679 | 0 % |

   La primera version de este script se fio del metadato y saco una caida de
   NDVI con mediana 1,89, que es imposible. Se detecto porque el NDVI esta
   acotado en [-1, 1] y 1,89 canta; si hubiera salido 0,6 habria pasado. Por eso
   ahora hay un `assert` de cordura: si mas del 1 % de los pixeles se sale del
   rango, el script aborta en vez de seguir.

2. **La mascara SCL.** Con una sola escena, una nube fina o una sombra de relieve
   se cuela como «caducifolia sin hoja». Se enmascaran nubes, sombras y nieve, y
   se componen VARIAS fechas por estacion tomando la MEDIANA. En febrero, a 42 de
   latitud y con este relieve, la sombra topografica es el riesgo serio.

3. **El CRS.** Sentinel-2 viene en EPSG:32629 (WGS84 / UTM 29N) y el proyecto va
   entero en EPSG:25829 (ETRS89 / UTM 29N). Son casi el mismo sistema —la
   diferencia en Galicia es de decimetros, muy por debajo del pixel de 10 m— pero
   «casi» no es «el mismo», asi que se reproyecta de verdad con `WarpedVRT` en vez
   de suponer que las rejillas coinciden. Es la unica reproyeccion del proyecto.

Uso:
    python scripts/descarga_s2.py
    python scripts/descarga_s2.py --escenas 5
"""
import argparse
import pathlib

import numpy as np
import rasterio
import requests
from rasterio.enums import Resampling
from rasterio.transform import from_origin
from rasterio.vrt import WarpedVRT
from rasterio.windows import from_bounds

RAIZ = pathlib.Path(__file__).resolve().parent.parent
PROC = RAIZ / "datos" / "procesado"
SALIDA = PROC / "s2"

STAC = "https://earth-search.aws.element84.com/v1/search"
BBOX_25829 = (548000, 4661000, 568000, 4686000)
BBOX_4326 = (-8.4106, 42.1018, -8.1836, 42.3186)
RES = 10.0
CRS = "EPSG:25829"

# ventanas fenologicas. El invierno se ciNe a la maxima defoliacion en Galicia y
# el verano se pega a las fechas del vuelo LiDAR (junio-julio de 2024)
ESTACIONES = {
    "invierno": "2023-12-01T00:00:00Z/2024-02-29T23:59:59Z",
    "verano":   "2024-06-15T00:00:00Z/2024-08-31T23:59:59Z",
}

# Scene Classification Layer: lo que NO se usa.
#  0 sin dato · 1 saturado · 2 sombra topografica/pixel oscuro · 3 sombra de nube
#  8 nube probable · 9 nube muy probable · 10 cirro · 11 nieve
# La 2 se descarta a proposito: en febrero con sol bajo la ladera norte se va a
# sombra y su NDVI cae, que es indistinguible de un arbol sin hoja
SCL_FUERA = (0, 1, 2, 3, 8, 9, 10, 11)

GDAL = {
    "GDAL_DISABLE_READDIR_ON_OPEN": "EMPTY_DIR",
    "CPL_VSIL_CURL_ALLOWED_EXTENSIONS": ".tif",
    "GDAL_HTTP_MAX_RETRY": "5",
    "GDAL_HTTP_RETRY_DELAY": "2",
}


def busca(rango, n, nube_max=10):
    r = requests.post(STAC, json={
        "collections": ["sentinel-2-l2a"], "bbox": list(BBOX_4326),
        "datetime": rango, "query": {"eo:cloud_cover": {"lt": nube_max}},
        "limit": 100}, timeout=90)
    r.raise_for_status()
    fs = r.json().get("features", [])
    fs.sort(key=lambda x: x["properties"]["eo:cloud_cover"])
    return fs[:n]


def rejilla():
    """Grid destino: 10 m, alineado a multiplos de 10 en EPSG:25829."""
    x0 = np.floor(BBOX_25829[0] / RES) * RES
    y1 = np.ceil(BBOX_25829[3] / RES) * RES
    w = int(np.ceil((BBOX_25829[2] - x0) / RES))
    h = int(np.ceil((y1 - BBOX_25829[1]) / RES))
    return from_origin(x0, y1, RES, RES), w, h


def lee(href, tr, w, h, remuestreo=Resampling.bilinear):
    """Lee un COG remoto reproyectado al grid destino."""
    with rasterio.open(f"/vsicurl/{href}") as src:
        with WarpedVRT(src, crs=CRS, transform=tr, width=w, height=h,
                       resampling=remuestreo) as vrt:
            return vrt.read(1)


def ndvi_escena(item, tr, w, h):
    """NDVI de una escena, con offset aplicado y SCL enmascarado. NaN donde no vale."""
    a = item["assets"]
    crudo = {k: lee(a[k]["href"], tr, w, h).astype("float32") for k in ("red", "nir")}
    scl = lee(a["scl"]["href"], tr, w, h, Resampling.nearest)

    ref = {}
    for k, v in crudo.items():
        rb = (a[k].get("raster:bands") or [{}])[0]
        # el offset declarado se ignora a proposito: ver el docstring. Estos COG
        # ya estan armonizados y restarlo mete el 71 % de los pixeles fuera de rango
        r = v * rb.get("scale", 1e-4)
        r[v == rb.get("nodata", 0)] = np.nan
        ref[k] = r

    den = ref["nir"] + ref["red"]
    with np.errstate(invalid="ignore", divide="ignore"):
        nd = (ref["nir"] - ref["red"]) / den
    nd[~np.isfinite(nd)] = np.nan
    nd[np.isin(scl, SCL_FUERA)] = np.nan

    # guardia de cordura: el NDVI vive en [-1, 1] y punto. Si se sale, algo va mal
    # en el escalado y es mejor parar que publicar un numero plausible y falso
    fuera = np.nanmean(np.abs(nd) > 1)
    if fuera > 0.01:
        raise SystemExit(
            f"el {100*fuera:.1f} % de los NDVI de {item['id']} cae fuera de [-1, 1].\n"
            "Eso es imposible: revisa el escalado de reflectancia antes de seguir.")
    return nd


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--escenas", type=int, default=3,
                    help="cuantas fechas se componen por estacion")
    args = ap.parse_args()

    SALIDA.mkdir(parents=True, exist_ok=True)
    tr, w, h = rejilla()
    print(f"rejilla destino: {w} x {h} px de {RES:g} m en {CRS}\n")

    perfil = dict(driver="GTiff", dtype="float32", count=1, width=w, height=h,
                  crs=CRS, transform=tr, nodata=np.nan, compress="deflate",
                  tiled=True, blockxsize=512, blockysize=512)

    compuestas = {}
    with rasterio.Env(**GDAL):
        for est, rango in ESTACIONES.items():
            items = busca(rango, args.escenas)
            if not items:
                raise SystemExit(f"sin escenas para {est} en {rango}")
            print(f"{est}: {len(items)} escenas")
            capas = []
            for it in items:
                p = it["properties"]
                nd = ndvi_escena(it, tr, w, h)
                val = 100 * np.isfinite(nd).mean()
                print(f"  {p['datetime'][:10]}  nube declarada {p['eo:cloud_cover']:>5.1f} %"
                      f"  ->  pixeles utiles {val:>5.1f} %", flush=True)
                capas.append(nd)

            # mediana y no media: una nube que la SCL no pilla es un valor extremo,
            # y la mediana de tres fechas la ignora mientras solo falle una
            comp = np.nanmedian(np.stack(capas), axis=0)
            compuestas[est] = comp
            hueco = 100 * np.isnan(comp).mean()
            print(f"  compuesta: {100-hueco:.1f} % con dato, mediana "
                  f"{np.nanmedian(comp):.3f}\n")
            with rasterio.open(SALIDA / f"ndvi_{est}.tif", "w", **perfil) as dst:
                dst.write(comp.astype("float32"), 1)

    # el indice que separa: cuanto pierde el NDVI del verano al invierno
    dif = compuestas["verano"] - compuestas["invierno"]
    with rasterio.open(SALIDA / "ndvi_caida.tif", "w", **perfil) as dst:
        dst.write(dif.astype("float32"), 1)

    ok = np.isfinite(dif)
    print(f"caida de NDVI verano->invierno: mediana {np.nanmedian(dif):.3f}, "
          f"p10 {np.nanpercentile(dif[ok], 10):.3f}, "
          f"p90 {np.nanpercentile(dif[ok], 90):.3f}")
    print(f"cobertura conjunta: {100*ok.mean():.1f} % de la ventana")
    for f in ("ndvi_invierno", "ndvi_verano", "ndvi_caida"):
        print(f"-> {(SALIDA / (f + '.tif')).relative_to(RAIZ)}")
