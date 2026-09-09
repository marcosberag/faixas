"""Descarga los poligonos de faixas de proteccion 50 m de la Xunta (ArcGIS REST).

Ojo: f=geojson devuelve geometry:null porque la capa tiene HasZ/HasM.
Usamos f=json (Esri JSON) + returnZ=false&returnM=false.

Salida: JSON crudo por capa en datos/crudo/ y un resumen por consola.
"""

import json
import pathlib
import sys

import requests

BASE = (
    "https://ideg.xunta.gal/servizos/rest/services/PBA/"
    "Afeccions_Agropecuaria_Faixas/MapServer"
)
CAPAS = {0: "nucleos", 1: "illadas"}
# OJO: el campo CONCELLO guarda el articulo pospuesto -> 'Cañiza, A', no 'A Cañiza'.
CONCELLOS = ["Arbo", "Cañiza, A", "Covelo", "Crecente"]
MAX_REC = 1000

RAIZ = pathlib.Path(__file__).resolve().parent.parent
DIR_CRUDO = RAIZ / "datos" / "crudo"


def where_concellos(concellos):
    valores = ", ".join("'{}'".format(c.replace("'", "''")) for c in concellos)
    return "CONCELLO IN ({})".format(valores)


def consulta_capa(capa, where):
    """Descarga todos los registros de una capa paginando con resultOffset."""
    features = []
    offset = 0
    campos_meta = None

    while True:
        params = {
            "where": where,
            "outFields": "*",
            "returnGeometry": "true",
            "returnZ": "false",
            "returnM": "false",
            "outSR": 25829,
            "resultOffset": offset,
            "resultRecordCount": MAX_REC,
            "f": "json",
        }
        r = requests.get(f"{BASE}/{capa}/query", params=params, timeout=120)
        r.raise_for_status()
        datos = r.json()

        if "error" in datos:
            raise RuntimeError(f"capa {capa}: {datos['error']}")

        lote = datos.get("features", [])
        features.extend(lote)
        if campos_meta is None:
            campos_meta = {
                "fields": datos.get("fields", []),
                "spatialReference": datos.get("spatialReference", {}),
                "geometryType": datos.get("geometryType"),
            }

        if not datos.get("exceededTransferLimit") or not lote:
            break
        offset += len(lote)

    return {**(campos_meta or {}), "features": features}


def revisa_geometrias(nombre, datos):
    """Verifica que las geometrias no vengan vacias (el fallo Z/M de ArcGIS)."""
    total = len(datos["features"])
    sin_geom = sum(
        1 for f in datos["features"] if not (f.get("geometry") or {}).get("rings")
    )
    anillos = sum(
        len((f.get("geometry") or {}).get("rings", [])) for f in datos["features"]
    )
    print(f"  {nombre}: {total} registros, {anillos} anillos, {sin_geom} sin geometria")
    if total and sin_geom == total:
        print("  !! todas las geometrias vienen vacias: revisar returnZ/returnM")
    return sin_geom


def main():
    DIR_CRUDO.mkdir(parents=True, exist_ok=True)
    where = where_concellos(CONCELLOS)
    print(f"WHERE: {where}\n")

    fallos = 0
    for capa, nombre in CAPAS.items():
        print(f"capa {capa} ({nombre})...")
        datos = consulta_capa(capa, where)
        fallos += revisa_geometrias(nombre, datos)

        destino = DIR_CRUDO / f"faixas_capa{capa}_{nombre}.json"
        destino.write_text(json.dumps(datos), encoding="utf-8")
        print(f"  -> {destino.relative_to(RAIZ)}")

        concellos_vistos = sorted(
            {f["attributes"].get("CONCELLO") for f in datos["features"]}
        )
        print(f"  concellos: {concellos_vistos}\n")

    return 1 if fallos else 0


if __name__ == "__main__":
    sys.exit(main())
