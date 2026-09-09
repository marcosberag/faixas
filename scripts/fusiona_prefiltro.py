"""Fusiona la anotacion humana con los «no» delegados al prefiltro de Claude.

La validacion provincial (fase 7) no se anoto entera a mano. `anotador_prefiltrado.py`
descarto del anotador humano los puntos que el prefiltro de Claude marco «no» claro,
apoyandose en la asimetria medida en el piloto de la fase 6 (kappa 0,51 global, pero
cero arboles humanos entre sus «no»). El humano anoto el resto.

Este script cierra ese circulo: reconstruye `anotacion.csv` con los 150 puntos de la
muestra a partir de

    muestra.csv            <- el orden canonico (columna `orden`)
    claude_prefiltro.csv   <- id, clase_claude
    anotacion_humana.csv   <- lo que descargo el anotador humano

Los delegados entran como clase «no», sin tipo y con ms=0, que es la marca que los
distingue despues. El orden de filas es el de `muestra.csv`: NO es cosmetico, los
bordes del IC bootstrap de `valida_producto.py` dependen del orden.

Aviso que hay que arrastrar a la publicacion: la clase de los 16 delegados es una
asuncion declarada, no verificada en esta muestra. El humano no los vio, asi que
aqui no hay forma de medir si el prefiltro acerto. Lo que sostiene la delegacion es
la asimetria medida en el piloto, sobre otra muestra.

Uso:
    python scripts/fusiona_prefiltro.py --dir validacion_pontevedra --verifica
    python scripts/fusiona_prefiltro.py --dir validacion_pontevedra
"""
import argparse
import pathlib

import pandas as pd

RAIZ = pathlib.Path(__file__).resolve().parent.parent

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", default="validacion_pontevedra")
    ap.add_argument("--verifica", action="store_true",
                    help="no escribe: compara con el anotacion.csv que ya existe")
    args = ap.parse_args()
    VAL = RAIZ / "datos" / "procesado" / args.dir

    m = pd.read_csv(VAL / "muestra.csv", encoding="utf-8-sig").sort_values("orden")
    pre = pd.read_csv(VAL / "claude_prefiltro.csv")
    hum = pd.read_csv(VAL / "anotacion_humana.csv")

    assert set(pre.id) == set(m.id), "el prefiltro no cubre la muestra entera"

    delegados = set(pre.loc[pre.clase_claude == "no", "id"])
    esperados = set(m.id) - delegados

    # Tres guardias. Cualquiera de las tres, en silencio, mueve la tasa de FP:
    sobra = set(hum.id) - set(m.id)
    assert not sobra, f"el CSV humano trae ids que no son de esta muestra: {sorted(sobra)}"
    invadidos = set(hum.id) & delegados
    assert not invadidos, (
        f"el humano anoto {len(invadidos)} puntos delegados al prefiltro: {sorted(invadidos)}. "
        "Si son suyos de verdad, quitalos de claude_prefiltro.csv; si es que se anoto el "
        "HTML completo por error, usa anotador.py y no este camino")
    faltan = esperados - set(hum.id)
    assert not faltan, (
        f"faltan {len(faltan)} puntos por anotar a mano: {sorted(faltan)[:10]}"
        f"{' ...' if len(faltan) > 10 else ''}")

    clases = dict(zip(hum.id, hum.clase))
    tipos = dict(zip(hum.id, hum.get("tipo", pd.Series(dtype=object))))
    ms = dict(zip(hum.id, hum.ms))

    filas = [{"id": i,
              "clase": clases.get(i, "no"),
              "tipo": tipos.get(i, ""),
              "ms": ms.get(i, 0)}
             for i in m.id]
    out = pd.DataFrame(filas)
    out["ms"] = out.ms.astype(int)

    print(f"{len(m)} puntos: {len(esperados)} anotados a mano, "
          f"{len(delegados)} delegados al prefiltro como «no»")
    print("reparto final:", out.clase.value_counts().to_dict())

    ruta = VAL / "anotacion.csv"
    texto = out.to_csv(index=False, lineterminator="\n")

    if args.verifica:
        if not ruta.exists():
            raise SystemExit(f"no existe {ruta}, nada que verificar")
        viejo = ruta.read_text(encoding="utf-8-sig").replace("\r\n", "\n")
        if viejo == texto:
            print(f"OK: reproduce {ruta.name} exactamente")
        else:
            v = pd.read_csv(ruta, encoding="utf-8-sig")
            if list(v.id) == list(out.id) and list(v.clase) == list(out.clase):
                print("OK: mismo orden y mismas clases (difiere solo el formateo del CSV)")
            else:
                raise SystemExit("DISCREPA en ids o clases con el anotacion.csv existente")
    else:
        ruta.write_text(texto, encoding="utf-8")
        print(f"-> {ruta.relative_to(RAIZ)}")
