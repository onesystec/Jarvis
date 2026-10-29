"""Proceso guardián: si el asistente muere sin cerrar el modelo local, lo cierra él.

Uso: python -m asistente.vigilante <pid del asistente> <pid del servidor> <carpeta temporal>
"""

import os
import shutil
import signal
import sys
import time


def _vivo(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def vigilar(padre: int, hijo: int, carpeta: str, pausa: float = 2.0) -> None:
    while _vivo(padre) and _vivo(hijo):
        time.sleep(pausa)
    if _vivo(hijo):
        os.kill(hijo, signal.SIGTERM)
        for _ in range(20):
            if not _vivo(hijo):
                break
            time.sleep(0.25)
        else:
            os.kill(hijo, signal.SIGKILL)
    shutil.rmtree(carpeta, ignore_errors=True)


if __name__ == "__main__":
    signal.signal(signal.SIGINT, signal.SIG_IGN)  # sobrevive a Ctrl+C para poder limpiar
    vigilar(int(sys.argv[1]), int(sys.argv[2]), sys.argv[3])
