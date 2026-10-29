from collections.abc import Callable
from datetime import datetime

import anthropic

from . import config
from .reglas import Respuesta, interpretar


class Cerebro:
    """Decide si una orden se resuelve en local o se consulta a Claude (con aprobación)."""

    def __init__(self, nube=None, confirmar: Callable[[], bool] | None = None) -> None:
        self._nube = nube
        self._confirmar = confirmar or (lambda: False)
        self._historial: list[dict] = []

    def pensar(self, texto: str, ahora: datetime | None = None) -> Respuesta:
        local = interpretar(texto, ahora)
        if local is not None:
            return local

        if self._nube is None:
            return Respuesta("No tengo configurada la conexión con Claude, señor.")
        if config.APROBAR_ANTES_DE_NUBE and not self._confirmar():
            return Respuesta("Entendido, no lo envío.")

        mensajes = [*self._historial[-config.HISTORIAL_MAX_MENSAJES :], {"role": "user", "content": texto}]
        try:
            texto_respuesta = self._nube.responder(mensajes)
        except anthropic.AuthenticationError:
            return Respuesta("La clave de Claude no es válida, señor.")
        except anthropic.APIConnectionError:
            return Respuesta("No puedo conectarme con Claude ahora mismo.")
        except anthropic.APIError:
            return Respuesta("Claude no pudo responder esta vez.")

        if not texto_respuesta:
            return Respuesta("Claude no devolvió ninguna respuesta.")
        self._historial += [{"role": "user", "content": texto}, {"role": "assistant", "content": texto_respuesta}]
        return Respuesta(texto_respuesta)
