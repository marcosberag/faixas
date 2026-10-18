"""Exporta el visor provincial estatico, con detalle bajo demanda por concello.

Entrada: ranking validado y puntos/areas generados con puntos_inspeccion.py
--zona pontevedra. No recalcula ni modifica las metricas del producto.
"""
import datetime
import json
import pathlib
import shutil

import geopandas as gpd
import numpy as np
import pandas as pd

RAIZ = pathlib.Path(__file__).resolve().parent.parent
PROC = RAIZ / "datos" / "procesado"
MET = PROC / "metricas"
WEB = pathlib.Path(__file__).parent / "web"


def limpia(valor):
    if isinstance(valor, dict):
        return {k: limpia(v) for k, v in valor.items()}
    if isinstance(valor, (list, tuple)):
        return [limpia(v) for v in valor]
    if isinstance(valor, float):
        return round(valor, 6) if np.isfinite(valor) else None
    return valor


def escribe(ruta, datos):
    ruta.write_text(json.dumps(limpia(datos), ensure_ascii=False,
                              separators=(",", ":"), allow_nan=False), encoding="utf-8")


def geojson(g):
    return json.loads(g.to_crs(4326).to_json(drop_id=True, na="null"))


def genera(zona):
    salida = RAIZ / "salidas" / "visor" / zona
    datos = salida / "datos"
    datos.mkdir(parents=True, exist_ok=True)
    suf = f"_{zona}"
    ranking = pd.read_csv(MET / f"ranking_final{suf}.csv", encoding="utf-8-sig")
    concellos = pd.read_csv(MET / f"ranking_final_concello{suf}.csv", encoding="utf-8-sig")
    fx = gpd.GeoDataFrame(pd.concat([
        gpd.read_file(PROC / f"faixas_{n}_{zona}_ok.gpkg")
        for n in ("nucleos", "illadas")], ignore_index=True), crs=25829)
    print("Disolviendo franjas por parroquia...", flush=True)
    parroquias = fx.dissolve(by=["NOMECONCEL", "PARROQUIA"]).reset_index()
    parroquias = parroquias.merge(
        ranking, left_on=["NOMECONCEL", "PARROQUIA"],
        right_on=["concello", "parroquia"], how="left", validate="one_to_one")
    sin_mapa = ranking.merge(parroquias[["concello", "parroquia"]],
                            on=["concello", "parroquia"], how="left", indicator=True)
    assert (sin_mapa._merge == "both").all(), "Hay parroquias medidas sin geometria"
    # Conservar las franjas sin ranking, como sin datos (nunca como cero).
    columnas = ["NOMECONCEL", "PARROQUIA", "puesto", "ha_medida", "ha_arbolado",
                "ha_sobre_35m", "ha_prohibida_min", "ha_prohibida_max",
                "ha_prohibida_punto_medio", "geometry"]
    parroquias = parroquias[columnas]
    parroquias.geometry = parroquias.geometry.simplify(10, preserve_topology=True)
    escribe(datos / "parroquias.geojson", geojson(parroquias))

    puntos = gpd.read_file(MET / f"puntos_inspeccion{suf}.gpkg")
    areas = gpd.read_file(MET / f"areas_inspeccion{suf}.gpkg")
    # La mancha se simplifica para visualizacion: la superficie publicada sigue
    # siendo la original. No sustituye a una delimitacion catastral.
    areas.geometry = areas.geometry.buffer(3).buffer(-3).simplify(2.5)
    areas = areas[~areas.geometry.is_empty]
    manifest_concellos = []
    for i, fila in enumerate(concellos.to_dict("records")):
        nombre = fila["concello"]
        slug = f"concello-{i + 1:02d}"
        p = puntos[puntos.NOMECONCEL == nombre]
        a = areas[areas.NOMECONCEL == nombre]
        a = a[["id_punto", "tipo", "ha", "PARROQUIA", "NOMECONCEL", "geometry"]]
        escribe(datos / f"{slug}.json", {"puntos": geojson(p), "areas": geojson(a)})
        g = parroquias[parroquias.NOMECONCEL == nombre]
        # Incluir manchas transfronterizas atribuidas por superficie: su ancla
        # puede quedar al otro lado del limite del concello.
        limites = [g.to_crs(4326).total_bounds]
        if len(p):
            limites.append(p.to_crs(4326).total_bounds)
        if len(a):
            limites.append(a.to_crs(4326).total_bounds)
        arr = np.array(limites)
        bbox = [float(arr[:, 0].min()), float(arr[:, 1].min()),
                float(arr[:, 2].max()), float(arr[:, 3].max())]
        manifest_concellos.append({**fila, "archivo": f"datos/{slug}.json", "bbox": bbox,
                                   "puntos": len(p),
                                   "parroquias": int((ranking.concello == nombre).sum())})

    cal = pd.read_csv(PROC / f"validacion_{zona}" / "resumen_producto.csv").iloc[0]
    manifest = {"version": 1, "zona": zona, "titulo": "Pontevedra",
                "generado_el": datetime.date.today().isoformat(),
                "fecha_resultados": "2026-09-14", "vuelo_lidar": 2024,
                "n_parroquias": len(ranking), "n_concellos": len(concellos),
                "n_puntos": len(puntos), "tasa_fp": float(cal.tasa_fp),
                "tasa_fp_lo": float(cal.tasa_fp_lo), "tasa_fp_hi": float(cal.tasa_fp_hi),
                "totales": {c: float(ranking[c].sum()) for c in
                            ("ha_medida", "ha_arbolado", "ha_sobre_35m",
                             "ha_prohibida_min", "ha_prohibida_max")},
                "concellos": manifest_concellos}
    escribe(salida / "manifest.json", manifest)
    for nombre in ("index.html", "visor.css", "visor.js"):
        shutil.copyfile(WEB / nombre, salida / nombre)
    shutil.copytree(WEB / "vendor", salida / "vendor", dirs_exist_ok=True)
    for nombre in (f"ranking_final{suf}.csv", f"ranking_final_concello{suf}.csv",
                   f"puntos_inspeccion{suf}.csv"):
        shutil.copyfile(MET / nombre, salida / nombre)
    (salida / ".nojekyll").touch()
    print(f"{len(ranking)} parroquias, {len(concellos)} concellos, {len(puntos)} puntos")
    print(f"Salida: {salida}")
    print(f"Tamano total: {sum(f.stat().st_size for f in salida.rglob('*') if f.is_file()) / 1e6:.1f} MB")
