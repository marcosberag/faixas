"""Anotador reducido por el prefiltro de Claude (fase 7, validacion provincial).

El piloto de la fase 6 midio a Claude como segundo anotador: kappa 0,51 con el
humano (no lo sustituye), pero con error ASIMETRICO — cero arboles humanos entre
sus «no». Eso lo habilita como prefiltro: sus «no» claros se descartan de la
carga del anotador humano, y todo lo demas (sus «arbol» y sus «dudoso») se
anota a mano igual que siempre.

Este script lee `claude_prefiltro.csv` (id, clase_claude) de la carpeta de la
muestra y genera `anotador_prefiltrado.html` SOLO con los puntos no descartados,
reutilizando la pagina de anotador.py sin tocarla. La firma del localStorage es
distinta, asi que no se mezcla con el anotador completo.

Al validar: el CSV humano descargado se combina con los «no» del prefiltro para
reconstruir la anotacion completa de la muestra (los puntos prefiltrados entran
como clase «no»), y el numero de puntos delegados al prefiltro se declara.

Uso:
    python scripts/anotador_prefiltrado.py --dir validacion_pontevedra
"""
import argparse
import json
import pathlib
import sys

import pandas as pd

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from anotador import PAGINA

RAIZ = pathlib.Path(__file__).resolve().parent.parent

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", default="validacion_pontevedra")
    args = ap.parse_args()
    VAL = RAIZ / "datos" / "procesado" / args.dir

    m = pd.read_csv(VAL / "muestra.csv", encoding="utf-8-sig").sort_values("orden")
    pre = pd.read_csv(VAL / "claude_prefiltro.csv")
    assert set(pre.id) == set(m.id), "el prefiltro no cubre la muestra entera"

    fuera = set(pre.loc[pre.clase_claude == "no", "id"])
    quedan = m[~m.id.isin(fuera)]
    print(f"{len(m)} puntos; el prefiltro descarta {len(fuera)} «no» claros; "
          f"quedan {len(quedan)} para el anotador humano")

    datos = [{"id": f.id} for f in quedan.itertuples()]
    firma = f"pre{len(quedan)}-{int(quedan.chm_m.sum() * 100) % 1000000}"
    html = (PAGINA
            .replace("__DATOS__", json.dumps(datos, separators=(",", ":")))
            .replace("__FIRMA__", firma)
            .replace("__PIDE_TIPO__", "false"))
    salida = VAL / "anotador_prefiltrado.html"
    salida.write_text(html, encoding="utf-8")
    print(f"-> {salida.relative_to(RAIZ)}")
    print(f"\nabrelo con doble clic:\n  {salida}")
