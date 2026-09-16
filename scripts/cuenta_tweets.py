"""Cuenta los caracteres de cada tweet de un guion de hilo al estilo de X.

Reglas de X: la mayoria de los caracteres latinos, la puntuacion general y los
espacios cuentan 1; emojis, flechas, simbolos y CJK cuentan 2; cualquier URL
cuenta 23 sea cual sea su longitud. El limite es 280.

El guion es el markdown de salidas/hilo/: cada tweet es el bloque de lineas
que empiezan por "> " bajo una cabecera "**N · ...**". Las lineas en blanco
citadas ("> " a secas) son saltos de parrafo.

Uso:
    python scripts/cuenta_tweets.py salidas/hilo/hilo_pontevedra.md
"""
import re
import sys

LIMITE = 280
URL = re.compile(r"https?://\S+|\b[a-z0-9.-]+\.(?:com|es|gal|org|net)(?:/\S*)?", re.I)
RANGOS_1 = ((0, 4351), (8192, 8205), (8208, 8223), (8242, 8247))


def peso(c):
    o = ord(c)
    return 1 if any(a <= o <= b for a, b in RANGOS_1) else 2


def longitud_x(texto):
    texto = texto.strip()
    urls = URL.findall(texto)
    sin = URL.sub("", texto)
    return sum(peso(c) for c in sin) + 23 * len(urls)


def tweets(md):
    actual, titulo, salida = [], None, []
    for linea in md.splitlines() + [""]:
        m = re.match(r"\*\*(\d+[a-z]?) · (.+?)\*\*", linea)
        if m:
            if actual:
                salida.append((titulo, "\n".join(actual)))
            titulo, actual = m.group(1) + " · " + m.group(2), []
        elif linea.startswith(">"):
            actual.append(linea[1:].lstrip(" "))
        elif actual and linea.strip() == "" and titulo is not None:
            salida.append((titulo, "\n".join(actual)))
            actual, titulo = [], None
    return salida


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    md = open(sys.argv[1], encoding="utf-8").read()
    peor = 0
    for titulo, texto in tweets(md):
        n = longitud_x(texto)
        peor = max(peor, n)
        marca = "OK " if n <= LIMITE else "!!!"
        print(f"{marca} {n:>3}  {titulo}")
    print("\ntodos dentro del límite" if peor <= LIMITE else f"\nHAY TWEETS LARGOS (máx {peor})")
    sys.exit(0 if peor <= LIMITE else 1)
