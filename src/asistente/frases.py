import re
import threading
from collections.abc import Callable, Iterable, Iterator

from . import config


class Diferida:
    """Acción que debe correr en el hilo principal, tras decir todo lo anterior (p. ej. una herramienta
    que pregunta «¿confirma?» en voz alta). Quien genera las frases espera a `hecha` para seguir."""

    def __init__(self, funcion: Callable[[], str]) -> None:
        self._funcion = funcion
        self.resultado: str | None = None
        self.error: BaseException | None = None
        self.hecha = threading.Event()

    def ejecutar(self) -> None:
        try:
            self.resultado = self._funcion()
        except BaseException as error:  # noqa: BLE001 - se re-lanza tal cual en quien la espera
            self.error = error
        finally:
            self.hecha.set()

    def esperar(self, cancelada: Callable[[], bool] = lambda: False) -> str | None:
        """Resultado de la acción, o None si se canceló antes de ejecutarse."""
        while not self.hecha.wait(0.2):
            if cancelada():
                return None
        if self.error is not None:
            raise self.error
        return self.resultado


_FIN_DE_FRASE = re.compile(r"[.!?…;]+[\"»”)]*\s")
_COMA = re.compile(r",\s")
_MARCAS = re.compile(r"[*_#`>~]")


def limpiar(frase: str) -> str:
    """Quita símbolos de markdown que la voz leería en alto."""
    return " ".join(_MARCAS.sub("", frase).split())


def _siguiente_corte(buffer: str, es_la_primera: bool) -> int | None:
    """Posición donde termina la próxima frase completa del buffer, o None si aún no hay."""
    desde = 0
    while m := _FIN_DE_FRASE.search(buffer, desde):
        if m.end() >= config.FRASE_MIN_CARACTERES:
            return m.end()
        desde = m.end()  # demasiado corta: se une con la siguiente
    if es_la_primera:
        # Para empezar a hablar antes, la primera frase larga se corta en una coma.
        for m in _COMA.finditer(buffer):
            if m.end() >= config.PRIMER_CORTE_CARACTERES:
                return m.end()
    return None


def dividir_en_frases(trozos: Iterable[str], limpiar_frase: Callable[[str], str] = limpiar) -> Iterator[str]:
    """Convierte un flujo de texto en frases completas a medida que van llegando."""
    buffer = ""
    primera = True
    for trozo in trozos:
        buffer += trozo
        while (corte := _siguiente_corte(buffer, primera)) is not None:
            frase, buffer = limpiar_frase(buffer[:corte]), buffer[corte:]
            if frase:
                primera = False
                yield frase
    if frase := limpiar_frase(buffer):
        yield frase
