"""Embeddings CNN de los parches de copa (plan B del clasificador de especie).

MobileNetV3-small preentrenado en ImageNet, sin la capa final: cada parche de
64x64 px se reescala a 224 y sale un vector de 576 rasgos aprendidos. En CPU
(i5) rinde ~40-80 parches/s: los 24k del entrenamiento son ~10 min.

entrena_copas.py --cnn los concatena con los rasgos clasicos. Si el plan A
(rasgos a mano) ya supera el liston, esto queda como comprobacion de techo.

Uso:
    python scripts/embeddings_copas.py                       # entrenamiento
    python scripts/embeddings_copas.py --parches otro.npy --salida otro_emb.npy
"""
import argparse
import pathlib
import time

import numpy as np
import torch
from torchvision.models import MobileNet_V3_Small_Weights, mobilenet_v3_small

RAIZ = pathlib.Path(__file__).resolve().parent.parent
COPAS = RAIZ / "datos" / "procesado" / "copas"

LOTE = 64

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--parches", default=str(COPAS / "parches_entrenamiento.npy"))
    ap.add_argument("--salida", default=str(COPAS / "embeddings_entrenamiento.npy"))
    args = ap.parse_args()

    parches = np.load(args.parches)
    print(f"{len(parches):,} parches")

    pesos = MobileNet_V3_Small_Weights.IMAGENET1K_V1
    red = mobilenet_v3_small(weights=pesos)
    red.classifier = torch.nn.Identity()   # nos quedamos con el embedding (576)
    red.eval()
    media = torch.tensor([0.485, 0.456, 0.406]).view(1, 3, 1, 1)
    desv = torch.tensor([0.229, 0.224, 0.225]).view(1, 3, 1, 1)

    salida = np.zeros((len(parches), 576), "float32")
    t0 = time.perf_counter()
    with torch.no_grad():
        for i in range(0, len(parches), LOTE):
            x = torch.from_numpy(parches[i:i + LOTE]).permute(0, 3, 1, 2).float() / 255
            x = torch.nn.functional.interpolate(x, size=224, mode="bilinear",
                                                antialias=True)
            x = (x - media) / desv
            salida[i:i + LOTE] = red(x).numpy()
            if (i // LOTE) % 40 == 0:
                v = (i + LOTE) / (time.perf_counter() - t0)
                print(f"  {i + LOTE:,}/{len(parches):,}  {v:.0f} parches/s",
                      flush=True)

    np.save(args.salida, salida)
    print(f"-> {args.salida}  ({salida.nbytes / 1e6:.0f} MB, "
          f"{time.perf_counter() - t0:.0f} s)")
