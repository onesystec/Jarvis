from collections.abc import Callable, Iterator
from datetime import datetime

import anthropic

from . import config
from .frases import Diferida
from .herramientas import Herramientas, interpretar_orden, orden_desde_claude
from .memoria import Memoria
from .reglas import Respuesta, interpretar, pide_permitir_nube, pide_revocar_nube

PREGUNTA_NUBE_SIEMPRE = "Esto necesita consultar a Claude. Solo enviaré su pregunta. ¿Lo envío?"
PREGUNTA_NUBE_CONVERSACION = "Para conversar necesito consultar a Claude. Solo enviaré lo que hablemos ahora. ¿Le parece bien?"
PREGUNTA_NUBE_CON_RECUERDOS = (
    "Para conversar necesito consultar a Claude. Enviaré lo que hablemos y lo que tengo anotado sobre usted. ¿Le parece bien?"
)


class Cerebro:
    """Decide si algo se resuelve en local, con una herramienta, o se consulta a Claude (con aprobación)."""

    def __init__(
        self,
        nube=None,
        confirmar: Callable[[str], bool] | None = None,
        herramientas: Herramientas | None = None,
        memoria: Memoria | None = None,
    ) -> None:
        self._nube = nube
        self._confirmar = confirmar or (lambda _pregunta: False)
        self._herramientas = herramientas or Herramientas()
        self._memoria = memoria
        self._historial: list[dict] = []
        self._permiso_nube: bool | None = None  # decisión del usuario para esta conversación

    def nueva_conversacion(self) -> None:
        """Olvida lo hablado y el permiso: cada conversación empieza de cero."""
        self._historial.clear()
        self._permiso_nube = None

    def pensar(self, texto: str, ahora: datetime | None = None) -> Respuesta:
        local = interpretar(texto, ahora)
        if local is not None:
            return local

        if pide_revocar_nube(texto):
            self._permiso_nube = False
            return Respuesta("De acuerdo, no usaré Claude en esta conversación.")
        if pide_permitir_nube(texto):
            self._permiso_nube = True
            return Respuesta("De acuerdo, puedo usar Claude.")

        orden = interpretar_orden(texto)
        if orden is not None:
            return Respuesta(self._herramientas.ejecutar(orden, self._confirmar))

        if self._nube is None:
            return Respuesta("No tengo configurada la conexión con Claude, señor.")
        negativa = self._pedir_permiso()
        if negativa is not None:
            return negativa

        mensajes = [*self._historial[-config.HISTORIAL_MAX_MENSAJES :], {"role": "user", "content": texto}]
        return Respuesta("", frases=self._conversar(texto, mensajes))

    def _pedir_permiso(self) -> Respuesta | None:
        """None si se puede consultar a Claude; si no, la respuesta que explica por qué no."""
        modo = config.APROBACION_NUBE
        if modo == "nunca":
            return None
        if modo == "siempre":
            return None if self._confirmar(self._pregunta(PREGUNTA_NUBE_SIEMPRE)) else Respuesta("Entendido, no lo envío.")
        if self._permiso_nube is None:
            self._permiso_nube = self._confirmar(self._pregunta(PREGUNTA_NUBE_CONVERSACION))
            if not self._permiso_nube:
                return Respuesta("Entendido, no usaré Claude en esta conversación.")
        if self._permiso_nube is False:
            return Respuesta("Sin Claude solo puedo resolver órdenes locales, señor. Dígame «usa Claude» si cambia de opinión.")
        return None

    def _recuerdos(self) -> list[str]:
        return self._memoria.para_nube() if self._memoria is not None and config.MEMORIA_A_NUBE else []

    def _pregunta(self, base: str) -> str:
        """El aviso de permiso dice con claridad si, además de la conversación, viajan los recuerdos."""
        if base == PREGUNTA_NUBE_CONVERSACION and self._recuerdos():
            return PREGUNTA_NUBE_CON_RECUERDOS
        return base

    def _usar_herramienta(self, nombre: str, entrada: dict) -> str:
        orden = orden_desde_claude(nombre, entrada)
        if orden is None:
            return "Petición de herramienta no válida."
        return self._herramientas.ejecutar(orden, self._confirmar)

    def _conversar(self, texto: str, mensajes: list[dict]) -> Iterator[str | Diferida]:
        dichas: list[str] = []
        try:
            for frase in self._nube.frases(mensajes, self._usar_herramienta, self._recuerdos()):
                if isinstance(frase, str):
                    dichas.append(frase)
                yield frase
        except anthropic.AuthenticationError:
            yield "La clave de Claude no es válida, señor."
            return
        except anthropic.APIConnectionError:
            yield "No puedo conectarme con Claude ahora mismo."
            return
        except anthropic.APIError:
            yield "Claude no pudo responder esta vez."
            return

        if not dichas:
            yield "Claude no devolvió ninguna respuesta."
            return
        self._historial += [{"role": "user", "content": texto}, {"role": "assistant", "content": " ".join(dichas)}]
