import subprocess
import sys
from typing import Self

from .esfera_forma import ESTADOS


class Esfera:
    """Cliente de la esfera: lanza su proceso y le envía el estado del asistente.

    Si la esfera no arranca o se cae, el asistente sigue funcionando sin ella.
    """

    def __init__(self, activa: bool = True) -> None:
        self._proceso: subprocess.Popen | None = None
        if activa:
            try:
                self._proceso = subprocess.Popen(
                    [sys.executable, "-m", "asistente.esfera_ventana"], stdin=subprocess.PIPE, text=True
                )
            except OSError:
                self._proceso = None

    def estado(self, nombre: str) -> None:
        if nombre not in ESTADOS:
            raise ValueError(f"estado desconocido: {nombre}")
        if self._proceso is None or self._proceso.poll() is not None:
            return
        try:
            self._proceso.stdin.write(nombre + "\n")
            self._proceso.stdin.flush()
        except OSError:  # incluye BrokenPipeError
            self._proceso = None

    def cerrar(self) -> None:
        proceso, self._proceso = self._proceso, None
        if proceso is None:
            return
        try:
            proceso.stdin.close()  # EOF: la esfera se cierra sola
            proceso.wait(timeout=3)
        except (OSError, subprocess.TimeoutExpired):
            proceso.kill()

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *_exc) -> None:
        self.cerrar()
