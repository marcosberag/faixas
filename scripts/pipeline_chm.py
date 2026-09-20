"""De un bloque LAZ del PNOA a MDT, MDS y CHM, con PDAL. Cronometrado por etapas.

QUE HACE CADA COSA, porque el pipeline no es obvio si no vienes de LiDAR
-----------------------------------------------------------------------

El LiDAR mide la altura del primer objeto que encuentra el laser. Para saber la
altura de la VEGETACION hace falta restar la del terreno, y el terreno no viene
dado: hay que deducirlo de la propia nube separando que puntos tocaron suelo y
cuales tocaron copa, tejado o coche.

  MDT  modelo digital del terreno: la superficie del suelo desnudo.
  MDS  modelo digital de superficies: lo mas alto que hay en cada punto.
  CHM  = MDS - MDT: altura de la vegetacion sobre el suelo. Es lo que medimos.

1. `filters.assign` borra la clasificacion del fichero. Galicia esta publicada en
   NPC01 (clasificacion automatica provisional, sin revision manual) y el plan de
   trabajo dice no fiarse de ella. La rehacemos entera.

2. `filters.elm` (Extended Local Minimum) marca como ruido los puntos que quedan
   absurdamente por debajo de sus vecinos. Son errores de multitrayecto: el laser
   rebota y "ve" un suelo falso 10 m mas abajo. Si no se quitan, SMRF los toma por
   terreno y hunde el MDT en un cono alrededor, inflando el CHM.

3. `filters.outlier` quita ruido aislado por estadistica de vecinos (pajaros,
   aerosoles, puntos sueltos en el aire). Sin esto el MDS se dispara a 200 m en
   pixeles sueltos.

4. `filters.smrf` es la clasificacion de suelo de verdad. Simple Morphological
   Filter (Pingel et al. 2013):
     - rasteriza el minimo de Z en celdas de `cell` metros,
     - le aplica una apertura morfologica con ventanas cada vez mas grandes hasta
       `window` celdas: lo que se "come" la apertura es un objeto que sobresale
       (arbol, casa), lo que sobrevive es terreno,
     - y compara cada punto con esa superficie provisional.
   Parametros:
     `slope`     pendiente maxima que admite como terreno natural. El umbral de
                 corte crece con slope x tamano de ventana, asi que subirlo evita
                 que una ladera empinada se confunda con un objeto. Galicia tiene
                 relieve fuerte, por eso 0,20 y no el 0,15 por defecto de PDAL.
     `threshold` tolerancia vertical fija (m) al decidir si un punto es suelo.
     `scalar`    cuanto pesa la pendiente local en esa tolerancia.
     `window`    tamano maximo del objeto (m) que se puede recortar. Tiene que
                 superar el ancho de la copa mas grande, o el centro de una masa
                 arbolada densa se queda clasificado como suelo.

5. MDT: solo los puntos que SMRF ha llamado suelo, interpolados por IDW. Bajo
   bosque cerrado llegan pocos retornos al suelo, asi que hay huecos y hay que
   rellenarlos: `window_size` es el radio en pixeles al que se busca para taparlos.

6. MDS: el maximo de Z de los primeros retornos. El primer retorno es el eco mas
   alto de cada pulso, o sea la copa.

7. CHM = MDS - MDT, con rasterio. Se hace fuera de PDAL porque son dos rasteres ya
   alineados a la misma rejilla (los dos writers reciben el mismo origen y tamano)
   y restarlos es una operacion de numpy.

SOBRE EL SOLAPE, Y POR QUE HAY QUE FILTRAR ANTES DE NADA
--------------------------------------------------------
El bloque trae 17,5 M de puntos, 17,5 pts/m2. El 64 % son clase 12: solape entre
pasadas del avion. Quitandolos quedan 6,2 pts/m2, y quedandose ademas con un solo
retorno por pulso, 4,95 pts/m2 — exactamente los 5 pts/m2 que anuncia la ficha del
CNIG. El flag `Overlap` de LAS 1.4 esta a cero en estos ficheros: el solape se
marca con la clase 12 al estilo antiguo, asi que hay que filtrar por clase.

Se descartan. Dos motivos:

  - Tecnico. `elm`, `outlier` y `smrf` no son streamables: cargan la nube entera
    en memoria y construyen un KD-tree encima. Con 17,5 M de puntos eso se come
    varios GB y PDAL revienta en un portatil normal. Filtrando primero con
    `filters.expression`, que si es streamable, solo entran ~5 M de puntos.
  - De fondo. La clase 12 la pone la geometria del vuelo (que zona cubren dos
    pasadas), no el clasificador morfologico, asi que descartarla no es "fiarse
    de NPC01". Y evita mezclar dos pasadas con calibraciones ligeramente
    distintas en el mismo pixel.

Ademas, cada rama se queda con el retorno que le interesa, que reduce otro tanto:
el suelo es siempre el ULTIMO eco de un pulso, y la copa el PRIMERO.

Uso:
    python scripts/pipeline_chm.py                       # todos los bloques bajados
    python scripts/pipeline_chm.py <fichero.LAZ>
    python scripts/pipeline_chm.py <fichero.LAZ> --res 0.5
"""
import json
import os
import pathlib
import subprocess
import sys
import time

import numpy as np
import rasterio

RAIZ = pathlib.Path(__file__).resolve().parent.parent
CRUDO = RAIZ / "datos" / "crudo" / "lidar"
PROC = RAIZ / "datos" / "procesado" / "lidar"

# PDAL vive en un entorno conda aparte: en Windows no hay wheel de pip y compilar
# libpdal no compensa. Ver docs/02-walkthrough.md.
# Se llama al binario directo en vez de a `micromamba run`, que se come el stderr y
# convierte cualquier fallo de PDAL en un codigo de salida sin explicacion.
ENV_PDAL = pathlib.Path.home() / ".local" / "micromamba" / "envs" / "pdal"


def _pdal_exe():
    """Ruta del ejecutable de PDAL.

    Prioridad: la variable de entorno PDAL_EXE (para instalaciones en rutas no
    estandar). Si no, layout estandar del env conda segun plataforma: Windows
    usa Library/bin/pdal.exe; Linux y macOS usan bin/pdal.
    """
    override = os.environ.get("PDAL_EXE")
    if override:
        return pathlib.Path(override)
    exe = "pdal.exe" if os.name == "nt" else "pdal"
    return ENV_PDAL / ("Library/bin" if os.name == "nt" else "bin") / exe


PDAL_EXE = _pdal_exe()
PDAL_BIN = PDAL_EXE.parent

EPSG = "EPSG:25829"
RES = 1.0  # m de pixel

# Parametros SMRF. No son los de PDAL por defecto: `slope` sube de 0,15 a 0,20 por
# el relieve gallego y `window` baja de 18 a 16 m.
SMRF = {"cell": 1.0, "slope": 0.20, "window": 16.0, "threshold": 0.45, "scalar": 1.25}


def pdal(args, etiqueta):
    """Ejecuta pdal en el entorno conda y devuelve los segundos que ha tardado."""
    if not PDAL_EXE.exists():
        raise RuntimeError(
            f"no encuentro {PDAL_EXE}. Crea el entorno con:\n"
            f"  micromamba create -y -p {ENV_PDAL} -c conda-forge pdal gdal")
    entorno = dict(os.environ)
    entorno["PATH"] = f"{PDAL_BIN}{os.pathsep}{entorno.get('PATH','')}"
    t0 = time.perf_counter()
    r = subprocess.run([str(PDAL_EXE), *args], env=entorno,
                       capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    seg = time.perf_counter() - t0
    if r.returncode != 0:
        print((r.stdout or "")[-3000:])
        print((r.stderr or "")[-3000:])
        raise RuntimeError(f"pdal fallo en {etiqueta} (codigo {r.returncode})")
    return seg


def rejilla(nw_x, nw_y, res):
    """Rejilla exacta del bloque: X [nw_x, nw_x+1] km, Y [nw_y-1, nw_y] km.

    Se dan origen y tamano en vez de `bounds` a proposito: con `bounds`, PDAL
    cuenta los dos extremos y saca 1001x1001 pixeles en vez de 1000x1000, y al
    mosaicar bloques vecinos esa fila de mas los solapa y los desalinea.
    """
    return {"origin_x": nw_x * 1000, "origin_y": (nw_y - 1) * 1000,
            "width": int(1000 / res), "height": int(1000 / res),
            "resolution": res}


def bloque_de(nombre):
    """PNOA-2024-GAL-559-4674-H29-NPC01.LAZ -> (559, 4674)"""
    p = nombre.split("-")
    return int(p[3]), int(p[4])


def pipeline_mdt(laz, salida, malla, res):
    return [
        {"type": "readers.las", "filename": str(laz),
         # el fichero declara EPSG:25829 en un GeoKey VLR, pero al ser formato de
         # punto 8 (LAS 1.4) PDAL exige el SRS en WKT y lo lee vacio. Se fuerza.
         "override_srs": EPSG},
        # streamable, y va primero a proposito: recorta 17,5 M de puntos a ~5 M
        # antes de que ningun filtro los cargue en memoria. Ultimo retorno porque
        # el eco del suelo es siempre el ultimo del pulso.
        {"type": "filters.expression",
         "expression": "Classification != 12 && ReturnNumber == NumberOfReturns"},
        {"type": "filters.assign", "value": "Classification = 0"},
        {"type": "filters.elm"},
        {"type": "filters.outlier", "method": "statistical", "mean_k": 8,
         "multiplier": 2.5},
        # elm y outlier marcan lo que descartan como clase 7: SMRF debe ignorarlo
        {"type": "filters.smrf", "ignore": "Classification[7:7]", **SMRF},
        {"type": "filters.expression", "expression": "Classification == 2"},
        {"type": "writers.gdal", "filename": str(salida), "gdaldriver": "GTiff",
         "output_type": "idw", "radius": res * 2.0,
         # bajo bosque cerrado llegan pocos retornos al suelo: hay que rellenar
         "window_size": 12, **malla,
         "nodata": -9999, "data_type": "float32",
         "gdalopts": "COMPRESS=DEFLATE,PREDICTOR=3,TILED=YES"},
    ]


def pipeline_mds(laz, salida, malla, res):
    return [
        {"type": "readers.las", "filename": str(laz), "override_srs": EPSG},
        # mismo filtro streamable que en el MDT, pero quedandose con el PRIMER
        # retorno de cada pulso, que es el eco de la copa
        {"type": "filters.expression",
         "expression": "Classification != 12 && ReturnNumber == 1"},
        {"type": "filters.assign", "value": "Classification = 0"},
        {"type": "filters.outlier", "method": "statistical", "mean_k": 8,
         "multiplier": 2.5},
        # fuera lo que outlier haya marcado como ruido (lo marca como clase 7)
        {"type": "filters.expression", "expression": "Classification != 7"},
        {"type": "writers.gdal", "filename": str(salida), "gdaldriver": "GTiff",
         "output_type": "max", "radius": res * 1.5,
         "window_size": 3, **malla,
         "nodata": -9999, "data_type": "float32",
         "gdalopts": "COMPRESS=DEFLATE,PREDICTOR=3,TILED=YES"},
    ]


def corre(laz, res=RES):
    laz = laz.resolve()  # PDAL resuelve las rutas relativas contra su propio cwd
    nw_x, nw_y = bloque_de(laz.name)
    malla = rejilla(nw_x, nw_y, res)
    sufijo = "" if res == 1.0 else f"_{res:g}m".replace(".", "")
    base = laz.stem
    PROC.mkdir(parents=True, exist_ok=True)
    mdt = PROC / f"{base}_mdt{sufijo}.tif"
    mds = PROC / f"{base}_mds{sufijo}.tif"
    chm = PROC / f"{base}_chm{sufijo}.tif"
    tmp = PROC / f"_pipeline_{base}.json"

    print(f"\n=== {laz.name}   {laz.stat().st_size/1e6:.1f} MB   pixel {res} m")
    tiempos = {}

    tmp.write_text(json.dumps(pipeline_mdt(laz, mdt, malla, res)), encoding="utf-8")
    tiempos["mdt"] = pdal(["pipeline", str(tmp)], "MDT")
    print(f"  MDT (elm + outlier + SMRF + IDW): {tiempos['mdt']:>7.1f} s")

    tmp.write_text(json.dumps(pipeline_mds(laz, mds, malla, res)), encoding="utf-8")
    tiempos["mds"] = pdal(["pipeline", str(tmp)], "MDS")
    print(f"  MDS (primeros retornos, max):     {tiempos['mds']:>7.1f} s")
    tmp.unlink()

    t0 = time.perf_counter()
    with rasterio.open(mdt) as a, rasterio.open(mds) as b:
        if a.transform != b.transform or a.shape != b.shape:
            raise RuntimeError("MDT y MDS no comparten rejilla")
        t = a.read(1, masked=True)
        s = b.read(1, masked=True)
        perfil = a.profile | {"compress": "deflate", "predictor": 3, "tiled": True}
        h = s - t
        # el CHM no puede ser negativo: donde el MDS cae por debajo del MDT es
        # ruido residual o interpolacion del terreno por encima de la copa
        h = np.ma.where(h < 0, 0.0, h)
        # ESCRITURA ATOMICA. La reanudacion de procesa_comarca.py da por hecho
        # el bloque con solo ver el fichero: un CHM truncado (corte de luz,
        # bateria agotada, Ctrl+C en el peor momento) se saltaria para siempre
        # y envenenaria las metricas en silencio. Con tmp + replace, o esta
        # entero o no esta.
        chm_tmp = chm.with_suffix(f".tmp{os.getpid()}.tif")
        with rasterio.open(chm_tmp, "w", **perfil) as dst:
            dst.write(h.filled(perfil["nodata"]).astype("float32"), 1)
            dst.set_band_description(1, "altura sobre el terreno (m)")
        os.replace(chm_tmp, chm)
    tiempos["chm"] = time.perf_counter() - t0
    print(f"  CHM (resta):                      {tiempos['chm']:>7.1f} s")

    n = h.count()
    total = h.size
    print(f"  huecos: MDT {100*t.mask.sum()/total:.2f} %  "
          f"MDS {100*s.mask.sum()/total:.2f} %  CHM {100*(total-n)/total:.2f} %")
    print(f"  altura: mediana {np.ma.median(h):.2f} m  p90 {np.percentile(h.compressed(),90):.1f} m  "
          f"max {h.max():.1f} m")
    for u in (2, 3, 5, 10):
        print(f"    sobre {u:>2} m: {100*(h > u).sum()/n:>5.1f} % del bloque")
    tiempos["total"] = sum(tiempos.values())
    print(f"  TOTAL {tiempos['total']:.1f} s  "
          f"({laz.stat().st_size/1e6/tiempos['total']:.1f} MB/s)")
    return {"bloque": laz.name, "mb": round(laz.stat().st_size / 1e6, 1),
            "res_m": res, **{f"s_{k}": round(v, 1) for k, v in tiempos.items()}}


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    res = RES
    if "--res" in sys.argv:
        res = float(sys.argv[sys.argv.index("--res") + 1])
        args = [a for a in args if a != str(res)]

    lazs = [pathlib.Path(a) for a in args] if args else sorted(CRUDO.glob("*.LAZ"))
    if not lazs:
        sys.exit("no hay LAZ en datos/crudo/lidar: corre antes descarga_lidar.py")

    filas = [corre(laz, res) for laz in lazs]

    import csv
    ruta = PROC / "tiempos_proceso.csv"
    nuevo = not ruta.exists()
    with open(ruta, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(filas[0]))
        if nuevo:
            w.writeheader()
        w.writerows(filas)

    tot = sum(f["s_total"] for f in filas)
    print(f"\n=== {len(filas)} bloques en {tot/60:.1f} min "
          f"({tot/len(filas):.0f} s/bloque)")
    print(f"    extrapolado a los 263 bloques de la comarca, en serie: "
          f"{263*tot/len(filas)/3600:.1f} h")
    print(f"-> {ruta.relative_to(RAIZ)}")
