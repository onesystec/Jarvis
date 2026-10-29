import json
import os
from datetime import datetime
from pathlib import Path

from . import config


def registrar(ruta: Path | None = None, **campos) -> None:
    """Añade una línea al registro de auditoría (JSONL, solo legible por el usuario).

    Si no se puede escribir, la excepción sube: una acción que no se puede auditar no se ejecuta.
    """
    ruta = ruta or config.AUDITORIA
    ruta.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    linea = json.dumps({"ts": datetime.now().astimezone().isoformat(timespec="seconds"), **campos}, ensure_ascii=False, default=str)
    descriptor = os.open(ruta, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o600)
    with os.fdopen(descriptor, "a", encoding="utf-8") as archivo:
        archivo.write(linea + "\n")
