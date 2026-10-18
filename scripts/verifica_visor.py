"""Comprueba cobertura, cotas y coherencia de todos los archivos publicados.

Solo biblioteca estandar: no necesita los rasteres ni los geopaquetes.
"""
import csv
import base64
import hashlib
import json
import math
import pathlib

RAIZ = pathlib.Path(__file__).resolve().parent.parent
SITIO = RAIZ / "salidas" / "visor" / "pontevedra"
MET = RAIZ / "datos" / "procesado" / "metricas"


def lee(nombre):
    with (SITIO / nombre).open(encoding="utf-8") as f:
        return json.load(f, parse_constant=lambda s: (_ for _ in ()).throw(
            ValueError(f"JSON no valido: {s}")))


def filas(nombre):
    with (MET / nombre).open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def verifica():
    m = lee("manifest.json")
    r = filas("ranking_final_pontevedra.csv")
    claves = {(p["concello"], p["parroquia"]): p for p in r}
    assert len(claves) == len(r) == m["n_parroquias"] == 563
    assert len(m["concellos"]) == m["n_concellos"] == 54
    assert {c["concello"] for c in m["concellos"]} == {p["concello"] for p in r}
    campos = ["ha_medida", "ha_arbolado", "ha_sobre_35m", "ha_prohibida_min",
              "ha_prohibida_max", "ha_prohibida_punto_medio"]
    vistas = set()
    for f in lee("datos/parroquias.geojson")["features"]:
        p = f["properties"]
        if p["puesto"] is None:
            assert p["ha_prohibida_min"] is None, "Sin datos convertido en cero"
            continue
        key = p["NOMECONCEL"], p["PARROQUIA"]
        assert key not in vistas
        vistas.add(key)
        original = claves[key]
        assert int(p["puesto"]) == int(original["puesto"])
        for campo in campos:
            assert math.isclose(p[campo], float(original[campo]), abs_tol=1e-6), (key, campo)
        assert p["ha_prohibida_min"] <= p["ha_prohibida_max"]
        assert f["geometry"] is not None
    assert vistas == claves.keys(), "Faltan parroquias en el mapa"
    for campo, total in m["totales"].items():
        assert math.isclose(total, sum(float(p[campo]) for p in r), abs_tol=1e-5)

    ids = set()
    tipos = {"eucaliptal_35m", "rodal_ifn", "disperso_copas"}
    n_areas = 0
    for c in m["concellos"]:
        d = lee(c["archivo"])
        assert len(d["puntos"]["features"]) == c["puntos"]
        local = set()
        for f in d["puntos"]["features"]:
            p = f["properties"]
            assert p["NOMECONCEL"] == c["concello"]
            assert p["tipo"] in tipos and p["ha"] > 0
            assert p["id_punto"] not in ids
            ids.add(p["id_punto"]); local.add(p["id_punto"])
            x, y = f["geometry"]["coordinates"]
            assert -9.5 < x < -7.5 and 41.5 < y < 43.5
            assert c["bbox"][0] - 1e-6 <= x <= c["bbox"][2] + 1e-6
            assert c["bbox"][1] - 1e-6 <= y <= c["bbox"][3] + 1e-6
        for f in d["areas"]["features"]:
            assert f["properties"]["id_punto"] in local
            assert f["geometry"]["type"] in {"Polygon", "MultiPolygon"}
            n_areas += 1
    assert len(ids) == m["n_puntos"]
    for nombre in ("ranking_final_pontevedra.csv", "ranking_final_concello_pontevedra.csv",
                   "puntos_inspeccion_pontevedra.csv"):
        assert (MET / nombre).read_bytes() == (SITIO / nombre).read_bytes(), nombre
    for nombre in ("index.html", "visor.css", "visor.js"):
        assert (SITIO / nombre).read_bytes() == (RAIZ / "scripts" / "web" / nombre).read_bytes()
    hashes = {"leaflet.js": "20nQCchB9co0qIjJZRGuk2/Z9VM+kNiyxNV1lvTlZBo=",
              "leaflet.css": "p4NxAoJBhIIN+hmNHrzRCf9tD/miZyoHS5obTRR9BMY="}
    for nombre, esperado in hashes.items():
        contenido = (SITIO / "vendor" / "leaflet" / nombre).read_bytes()
        assert base64.b64encode(hashlib.sha256(contenido).digest()).decode() == esperado
    # Comprobar los recursos locales sin depender de la disponibilidad del CDN.
    for origen in (RAIZ / "scripts" / "web" / "vendor").rglob("*"):
        if origen.is_file():
            destino = SITIO / "vendor" / origen.relative_to(RAIZ / "scripts" / "web" / "vendor")
            assert destino.read_bytes() == origen.read_bytes(), origen.name
    assert (SITIO / "vendor" / "leaflet" / "LICENSE").exists()
    assert (SITIO / ".nojekyll").exists()
    print(f"OK: {len(vistas)} parroquias, {len(m['concellos'])} concellos, "
          f"{len(ids)} puntos y {n_areas} manchas; cotas identicas al ranking validado.")


if __name__ == "__main__":
    verifica()
