from collections.abc import Callable, Iterator
from datetime import datetime

import anthropic

from . import config
from .frases import Diferida
from .herramientas import Herramientas, interpretar_orden, orden_desde_claude
from .memoria import Memoria
from .reglas import (
    Respuesta,
    interpretar,
    pide_modo_privado,
    pide_permitir_nube,
    pide_permitir_web,
    pide_revocar_nube,
    pide_revocar_web,
    pide_salir_de_privado,
)

# Con contenido externo en la conversación, Claude solo puede mirar: nada que cambie cosas por iniciativa suya.
_SOLO_LECTURA = frozenset({"buscar_archivos", "leer_archivo", "temporizadores", "bateria"})
_BLOQUEO = "Bloqueado: hay contenido externo en esta conversación y, por seguridad, solo puedo mirar, no actuar."




class Cerebro:
    """Decide si algo se resuelve en local, con una herramienta, o se consulta a Claude (con aprobación)."""

    def __init__(
        self,
        nube=None,
        confirmar: Callable[[str], bool] | None = None,
        herramientas: Herramientas | None = None,
        memoria: Memoria | None = None,
        local=None,
    ) -> None:
        self._local = local  # modelo que corre en este equipo (ver local.ModeloLocal); None si no hay
        self._nube = nube
        self._confirmar = confirmar or (lambda _pregunta: False)
        self._herramientas = herramientas or Herramientas()
        self._memoria = memoria
        self._historial: list[dict] = []
        self._historial_privado: list[dict] = []  # lo hablado en privado nunca viaja a la nube
        self._privado = False
        self._permiso_nube: bool | None = None  # decisión del usuario para esta conversación
        self._contaminado = False  # ya entró contenido externo (un archivo o una página) en el contexto de Claude
        self._web_revocada = False
        self._externo_turno = False  # en el turno en curso se consultó la web o un archivo

    def nueva_conversacion(self) -> None:
        """Olvida lo hablado y el permiso: cada conversación empieza de cero."""
        self._historial.clear()
        self._historial_privado.clear()
        self._privado = False
        self._permiso_nube = None
        self._contaminado = False
        self._web_revocada = False

    def pensar(self, texto: str, ahora: datetime | None = None) -> Respuesta:
        local = interpretar(texto, ahora)
        if local is not None:
            return local

        if pide_revocar_nube(texto):
            self._permiso_nube = False
            return Respuesta("De acuerdo, no usaré Claude en esta conversación.")
        if pide_revocar_web(texto):
            self._web_revocada = True
            return Respuesta("De acuerdo, no buscaré en internet en esta conversación.")
        if pide_permitir_web(texto):
            self._web_revocada = False
            return Respuesta("De acuerdo, puedo buscar en internet.")
        if pide_permitir_nube(texto):
            self._permiso_nube = True
            return Respuesta("De acuerdo, puedo usar Claude.")

        orden = interpretar_orden(texto)
        if orden is not None:
            return Respuesta(self._herramientas.ejecutar(orden, self._confirmar))

        if pide_salir_de_privado(texto):  # primero la salida: «sal del modo privado» también contiene «modo privado»
            self._privado = False
            return Respuesta("De acuerdo, vuelvo al modo normal.")
        if pide_modo_privado(texto):
            if not self._local_disponible():
                return Respuesta("El modelo local no está disponible, señor.")
            self._privado = True
            return Respuesta("De acuerdo, esta conversación queda en privado: nada sale de este equipo.")

        # Sin Claude (privado, sin clave o sin permiso) se conversa con el modelo local, si lo hay.
        if self._local_disponible() and (self._privado or self._nube is None or self._permiso_nube is False):
            return Respuesta("", frases=self._conversar_local(texto))
        if self._nube is None:
            return Respuesta("No tengo configurada la conexión con Claude, señor.")
        negativa = self._pedir_permiso()
        if negativa is not None:
            if self._local_disponible():  # dijo que no a Claude: se resuelve en privado en lugar de dejarlo sin respuesta
                return Respuesta("", frases=self._conversar_local(texto, "De acuerdo, lo resuelvo en privado, aquí en el equipo."))
            return negativa

        mensajes = [*self._historial[-config.HISTORIAL_MAX_MENSAJES :], {"role": "user", "content": texto}]
        return Respuesta("", frases=self._conversar(texto, mensajes))

    def _pedir_permiso(self) -> Respuesta | None:
        """None si se puede consultar a Claude; si no, la respuesta que explica por qué no."""
        modo = config.APROBACION_NUBE
        if modo == "nunca":
            return None
        if modo == "siempre":
            return None if self._confirmar(self._aviso(por_conversacion=False)) else Respuesta("Entendido, no lo envío.")
        if self._permiso_nube is None:
            self._permiso_nube = self._confirmar(self._aviso(por_conversacion=True))
            if not self._permiso_nube:
                return Respuesta("Entendido, no usaré Claude en esta conversación.")
        if self._permiso_nube is False:
            return Respuesta("Sin Claude solo puedo resolver órdenes locales, señor. Dígame «usa Claude» si cambia de opinión.")
        return None

    def _recuerdos(self) -> list[str]:
        return self._memoria.para_nube() if self._memoria is not None and config.MEMORIA_A_NUBE else []

    def _local_disponible(self) -> bool:
        return self._local is not None and self._local.disponible()

    def terminar_conversacion(self) -> None:
        """Libera la memoria del modelo local en cuanto termina la conversación."""
        if self._local is not None:
            self._local.liberar()

    def _conversar_local(self, texto: str, intro: str = "") -> Iterator[str]:
        if intro:
            yield intro
        mensajes = [*self._historial_privado[-config.HISTORIAL_MAX_MENSAJES :], {"role": "user", "content": texto}]
        recuerdos = self._memoria.para_nube() if self._memoria is not None else []  # aquí no salen del equipo
        dichas: list[str] = []
        try:
            for frase in self._local.frases(mensajes, recuerdos=recuerdos):
                if isinstance(frase, str):
                    dichas.append(frase)
                    yield frase
        except RuntimeError:
            yield "El modelo local no está disponible ahora mismo, señor."
            return
        escritas = [d for d in dichas if d != config.LOCAL_AVISO]
        if escritas:
            self._historial_privado += [{"role": "user", "content": texto}, {"role": "assistant", "content": " ".join(escritas)}]

    def _web_activa(self) -> bool:
        return self._nube is not None and config.WEB_BUSQUEDA and not self._web_revocada

    def _marcar_externo(self) -> None:
        self._contaminado = True
        self._externo_turno = True

    def _aviso(self, por_conversacion: bool) -> str:
        """Lo que se pregunta antes de usar Claude: dice con claridad qué viaja y si puede buscar en internet."""
        enviado = "lo que hablemos" if por_conversacion else "su pregunta"
        if self._recuerdos():
            enviado += " y lo que tengo anotado sobre usted"
        busca = ", que además puede buscar en internet" if self._web_activa() else ""
        if por_conversacion:
            return f"Para conversar necesito consultar a Claude{busca}. Enviaré {enviado}. ¿Le parece bien?"
        return f"Esto necesita consultar a Claude{busca}. Enviaré {enviado}. ¿Lo envío?"

    def _usar_herramienta(self, nombre: str, entrada: dict) -> str:
        if self._contaminado and nombre not in _SOLO_LECTURA:
            return _BLOQUEO
        orden = orden_desde_claude(nombre, entrada)
        if orden is None:
            return "Petición de herramienta no válida."
        resultado = self._herramientas.ejecutar(orden, self._confirmar)
        if nombre == "leer_archivo" and resultado.startswith("[Contenido de"):
            self._marcar_externo()
        return resultado

    def _conversar(self, texto: str, mensajes: list[dict]) -> Iterator[str | Diferida]:
        dichas: list[str] = []
        self._externo_turno = False
        try:
            for frase in self._nube.frases(mensajes, self._usar_herramienta, self._recuerdos(), self._web_activa(), self._marcar_externo):
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
        # Al historial va lo que Claude escribió (sin el aviso «un momento»), con una nota si consultó fuentes:
        # sin ella, en el turno siguiente Claude duda de cifras que sí verificó.
        escritas = [d for d in dichas if d != config.WEB_AVISO]
        if self._externo_turno and escritas:
            escritas.append(config.NOTA_FUENTE_EXTERNA)
        self._historial += [{"role": "user", "content": texto}, {"role": "assistant", "content": " ".join(escritas) or " ".join(dichas)}]
