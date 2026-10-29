import hashlib
from pathlib import Path


def sha256(ruta: Path) -> str:
    h = hashlib.sha256()
    with ruta.open("rb") as archivo:
        while bloque := archivo.read(1 << 20):
            h.update(bloque)
    return h.hexdigest()
