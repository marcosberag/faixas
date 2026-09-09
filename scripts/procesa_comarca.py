"""Fase 4: la comarca entera. Descarga, procesa y borra, bloque a bloque.

Por que existe este script en vez de correr descarga_lidar.py y pipeline_chm.py
del tiron: EL DISCO. Los 263 bloques son ~27 GB de LAZ y en esta maquina no
caben. Los rasteres de salida si (unos 7 MB por bloque, ~1,9 GB el total), asi
que el unico orden viable es streaming: bajar UN bloque, procesarlo, borrar el
LAZ y pasar al siguiente. El LiDAR es publico y se rebaja a 22 MB/s: borrar el
crudo no destruye nada que no se recupere en 15 segundos.

Tres cosas que una corrida de 13 horas necesita y el piloto no necesitaba:

  - REANUDACION. Si el CHM del bloque ya existe, se salta. Interrumpir con
    Ctrl+C y relanzar no repite trabajo. (Por eso los 3 bloques del piloto no
    se tocan: ya tienen CHM, y sus LAZ se quedan donde estan.)
  - SESION RENOVABLE. El JSESSIONID del CNIG no va a vivir 13 horas. Ante
    cualquier fallo de descarga se abre sesion nueva y se reintenta con
    espera creciente; ademas se renueva de oficio cada 25 bloques.
  - FALLO NO FATAL. Un bloque que falla 3 veces se apunta en el registro y se
    sigue con el siguiente. Al final se listan los fallidos; relanzar el
    script los reintenta solo (no tienen CHM, asi que no se saltan).

Y una guardia de disco: si quedan menos de 3 GB libres se para LIMPIAMENTE
antes de descargar el siguiente. Mejor una corrida a medias y reanudable que
un disco lleno.

El orden es el de la malla: por hectareas de faixa descendente. Asi lo que
mas pesa en el ranking se procesa primero y una corrida parcial ya es util.

Uso:
    python scripts/procesa_comarca.py            # todos los que falten
    python scripts/procesa_comarca.py --max 10   # solo los 10 primeros pendientes
"""
import argparse
import csv
import pathlib
import shutil
import sys
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import descarga_lidar as dl
import pipeline_chm as pc

RAIZ = pathlib.Path(__file__).resolve().parent.parent
PROC = RAIZ / "datos" / "procesado"
CRUDO = RAIZ / "datos" / "crudo" / "lidar"
LIDAR = PROC / "lidar"
MALLA = PROC / "malla_lidar_paradanta.csv"   # se puede cambiar con --malla
REGISTRO = LIDAR / "fase4_registro.csv"

MIN_LIBRE_GB = 3.0
MIN_BATERIA = 20    # % por debajo del cual se para si no esta enchufado
REINTENTOS = 3
RENUEVA_CADA = 25   # bloques entre renovaciones de sesion preventivas


def gb_libres():
    return shutil.disk_usage(RAIZ).free / 1e9


def bateria():
    """(porcentaje, enchufado) o (None, True) si no hay bateria que mirar.

    Con bateria la CPU baja de 1,9 a 1,7 GHz y el bloque pasa de 120 a 420 s:
    la provincia entera son 4,4 dias enchufado y 15,5 con bateria. Y dejar que
    se agote apaga el portatil de golpe, con lo que eso arrastre. Misma logica
    que la guardia de disco: parada limpia y reanudable, no un tajo.
    """
    try:
        import psutil
        b = psutil.sensors_battery()
    except Exception:
        return None, True
    if b is None:
        return None, True
    return b.percent, bool(b.power_plugged)


def descarga_con_reintentos(estado, nw_x, nw_y, ruta):
    """Baja el LAZ renovando sesion si hace falta. Devuelve (segundos, bytes)."""
    ultimo = None
    for intento in range(REINTENTOS):
        try:
            if estado["s"] is None:
                estado["s"] = dl.sesion()
            nombre, sec, mb = dl.busca_hoja(estado["s"], nw_x, nw_y)
            seg, n = dl.descarga(estado["s"], sec, ruta)
            if not dl.es_laz(ruta):
                ruta.unlink(missing_ok=True)
                raise RuntimeError(f"{nombre}: el CNIG devolvio algo que no es LAZ")
            return seg, n
        except Exception as e:  # red, sesion caducada, HTML de error del CNIG...
            ultimo = e
            estado["s"] = None          # la proxima vuelta abre sesion nueva
            espera = 15 * (intento + 1)
            print(f"    intento {intento+1}/{REINTENTOS} fallido: {e}")
            print(f"    espero {espera} s y renuevo sesion", flush=True)
            time.sleep(espera)
    raise RuntimeError(f"descarga agotada tras {REINTENTOS} intentos: {ultimo}")


def apunta(fila):
    nuevo = not REGISTRO.exists()
    with open(REGISTRO, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["bloque", "nw_x", "nw_y", "mb",
                                          "s_descarga", "s_proceso", "estado",
                                          "error"])
        if nuevo:
            w.writeheader()
        w.writerow(fila)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--max", type=int, default=None,
                    help="procesar como mucho N bloques pendientes")
    ap.add_argument("--malla", type=pathlib.Path, default=MALLA,
                    help="CSV de malla (p. ej. malla_lidar_pontevedra.csv)")
    args = ap.parse_args()
    MALLA = args.malla

    with open(MALLA, encoding="utf-8") as f:
        malla = list(csv.DictReader(f))

    pendientes = []
    for m in malla:
        chm = LIDAR / m["bloque"].replace(".LAZ", "_chm.tif")
        if not chm.exists():
            pendientes.append(m)
    hechos_antes = len(malla) - len(pendientes)
    if args.max:
        pendientes = pendientes[:args.max]

    print(f"{len(malla)} bloques en la malla, {hechos_antes} ya procesados, "
          f"{len(pendientes)} en esta corrida")
    print(f"disco libre: {gb_libres():.1f} GB (guardia a {MIN_LIBRE_GB:g} GB)\n",
          flush=True)
    if not pendientes:
        sys.exit(0)

    estado = {"s": None}
    fallos = []
    n_ok = 0
    t_inicio = time.time()
    for i, m in enumerate(pendientes, 1):
        nw_x, nw_y = int(m["nw_x"]), int(m["nw_y"])
        nombre = m["bloque"]
        ruta = CRUDO / nombre

        if gb_libres() < MIN_LIBRE_GB:
            print(f"\nPARADA LIMPIA: quedan {gb_libres():.1f} GB libres, por "
                  f"debajo de la guardia de {MIN_LIBRE_GB:g} GB.")
            print("Libera disco y relanza: la corrida se reanuda sola.")
            break

        pct, enchufado = bateria()
        if pct is not None and not enchufado and pct < MIN_BATERIA:
            print(f"\nPARADA LIMPIA: bateria al {pct:.0f} % y sin enchufar "
                  f"(guardia al {MIN_BATERIA} %).")
            print("Enchufa y relanza: la corrida se reanuda sola, y ademas "
                  "va 3,5 veces mas rapida enchufada.")
            break

        hechos = i - 1
        if hechos:
            ritmo = (time.time() - t_inicio) / hechos
            eta = ritmo * (len(pendientes) - hechos) / 3600
            progreso = f"[{i}/{len(pendientes)}  ~{eta:.1f} h restantes]"
        else:
            progreso = f"[{i}/{len(pendientes)}]"
        print(f"\n{progreso} {nombre}  ({float(m['ha_faixa']):.1f} ha de faixa)",
              flush=True)

        if i % RENUEVA_CADA == 0:
            estado["s"] = None

        fila = {"bloque": nombre, "nw_x": nw_x, "nw_y": nw_y, "mb": "",
                "s_descarga": "", "s_proceso": "", "estado": "", "error": ""}
        try:
            if ruta.exists() and dl.es_laz(ruta):
                print("  LAZ ya en disco, no se descarga")
                s_desc = 0.0
            else:
                s_desc, n = descarga_con_reintentos(estado, nw_x, nw_y, ruta)
                print(f"  descargado: {n/1e6:.1f} MB en {s_desc:.1f} s", flush=True)
            fila["mb"] = round(ruta.stat().st_size / 1e6, 1)
            fila["s_descarga"] = round(s_desc, 1)

            r = pc.corre(ruta)
            fila["s_proceso"] = r["s_total"]
            fila["estado"] = "ok"
            n_ok += 1

            # el crudo ya no hace falta: sin esto la corrida revienta el disco
            ruta.unlink()
        except KeyboardInterrupt:
            print("\ninterrumpido a mano: relanza para reanudar")
            raise
        except Exception as e:
            fila["estado"] = "fallo"
            fila["error"] = str(e)[:200]
            fallos.append(nombre)
            print(f"  FALLO (se sigue con el siguiente): {e}", flush=True)
        apunta(fila)

    horas = (time.time() - t_inicio) / 3600
    print(f"\n=== {n_ok} bloques procesados y {len(fallos)} fallidos "
          f"en {horas:.1f} h. Disco libre: {gb_libres():.1f} GB")
    if fallos:
        print("fallidos (relanzar el script los reintenta):")
        for f_ in fallos:
            print(f"  {f_}")
    print(f"-> {REGISTRO.relative_to(RAIZ)}")
