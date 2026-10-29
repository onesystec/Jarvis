from datetime import datetime
from unittest.mock import MagicMock

import anthropic
import pytest

from asistente import config
from asistente.cerebro import Cerebro
from asistente.reglas import es_afirmativo, interpretar, normalizar

LUNES = datetime(2026, 10, 26, 14, 5)


class NubeFalsa:
    def __init__(self, frases=("Respuesta de Claude.",), error=None) -> None:
        self.frases_a_decir = list(frases)
        self.error = error
        self.llamadas: list[list[dict]] = []

    def frases(self, mensajes, usar_herramienta):
        self.llamadas.append(list(mensajes))
        if self.error:
            raise self.error
        yield from self.frases_a_decir


class Confirmador:
    def __init__(self, respuesta=True) -> None:
        self.respuesta = respuesta
        self.preguntas: list[str] = []

    def __call__(self, pregunta: str) -> bool:
        self.preguntas.append(pregunta)
        return self.respuesta


def decir(respuesta) -> str:
    """Lo que se oiría: consume la respuesta si llega por frases."""
    return " ".join(respuesta.frases) if respuesta.frases is not None else respuesta.texto


def test_normalizar_quita_tildes_y_signos():
    assert normalizar("¿Qué HORA es?") == "que hora es"


def test_hora_y_fecha_se_resuelven_en_local():
    assert interpretar("¿Qué hora es?", LUNES).texto == "Son las 2 y 5."
    assert interpretar("qué día es hoy", LUNES).texto == "Hoy es lunes 26 de octubre de 2026."
    assert interpretar("hora en punto?", datetime(2026, 1, 1, 13, 0)) is None  # no inventa reglas
    assert interpretar("qué hora es", datetime(2026, 1, 1, 13, 0)).texto == "Es la 1 en punto."


def test_despedida_termina_la_conversacion_y_apagar_cierra_el_asistente():
    for frase in ("adiós Jarvis", "hasta luego", "eso es todo", "nada más, gracias"):
        respuesta = interpretar(frase)
        assert respuesta.fin and not respuesta.salir, frase
    assert interpretar("apágate").salir
    assert interpretar("ya está listo el informe?") is None  # «ya está» suelto no despide


def test_afirmativo_y_negativo():
    assert es_afirmativo("Sí, adelante")
    assert not es_afirmativo("no, mejor no")
    assert not es_afirmativo("")


def test_lo_simple_no_sale_a_la_nube():
    nube = NubeFalsa()
    confirmar = Confirmador()
    cerebro = Cerebro(nube, confirmar)
    assert cerebro.pensar("qué hora es", LUNES).texto.startswith("Son las")
    assert nube.llamadas == [] and confirmar.preguntas == []


def test_sin_permiso_no_se_envia_nada_y_no_se_vuelve_a_preguntar():
    nube = NubeFalsa()
    confirmar = Confirmador(False)
    cerebro = Cerebro(nube, confirmar)
    assert "no usaré Claude" in cerebro.pensar("cuéntame un chiste").texto
    assert "Sin Claude" in cerebro.pensar("y otro chiste").texto
    assert nube.llamadas == []
    assert len(confirmar.preguntas) == 1


def test_el_permiso_se_pide_una_vez_por_conversacion():
    nube = NubeFalsa()
    confirmar = Confirmador(True)
    cerebro = Cerebro(nube, confirmar)
    assert decir(cerebro.pensar("cuéntame un chiste")) == "Respuesta de Claude."
    assert decir(cerebro.pensar("otro más")) == "Respuesta de Claude."
    assert len(confirmar.preguntas) == 1
    assert nube.llamadas[0] == [{"role": "user", "content": "cuéntame un chiste"}]

    cerebro.nueva_conversacion()
    decir(cerebro.pensar("hola de nuevo"))
    assert len(confirmar.preguntas) == 2
    assert nube.llamadas[-1] == [{"role": "user", "content": "hola de nuevo"}]  # sin memoria de la anterior


def test_revocar_y_permitir_claude_por_voz():
    nube = NubeFalsa()
    confirmar = Confirmador(True)
    cerebro = Cerebro(nube, confirmar)
    decir(cerebro.pensar("hola"))
    assert "no usaré Claude" in cerebro.pensar("no uses Claude").texto
    assert "Sin Claude" in cerebro.pensar("cuéntame algo").texto
    assert "puedo usar Claude" in cerebro.pensar("usa Claude").texto
    assert decir(cerebro.pensar("cuéntame algo")) == "Respuesta de Claude."
    assert len(confirmar.preguntas) == 1


def test_modo_siempre_pregunta_cada_vez(monkeypatch):
    monkeypatch.setattr(config, "APROBACION_NUBE", "siempre")
    confirmar = Confirmador(True)
    cerebro = Cerebro(NubeFalsa(), confirmar)
    decir(cerebro.pensar("uno"))
    decir(cerebro.pensar("dos"))
    assert len(confirmar.preguntas) == 2


def test_modo_nunca_no_pregunta(monkeypatch):
    monkeypatch.setattr(config, "APROBACION_NUBE", "nunca")
    confirmar = Confirmador(False)
    assert decir(Cerebro(NubeFalsa(), confirmar).pensar("uno")) == "Respuesta de Claude."
    assert confirmar.preguntas == []


def test_la_respuesta_llega_por_frases():
    cerebro = Cerebro(NubeFalsa(frases=["Primera frase.", "Segunda frase."]), Confirmador())
    assert list(cerebro.pensar("hola").frases) == ["Primera frase.", "Segunda frase."]


def test_el_historial_se_acota_y_alterna_roles():
    nube = NubeFalsa()
    cerebro = Cerebro(nube, Confirmador())
    for i in range(10):
        decir(cerebro.pensar(f"pregunta {i}"))
    enviados = nube.llamadas[-1]
    assert len(enviados) <= 9
    assert enviados[0]["role"] == "user"
    assert [m["role"] for m in enviados[:2]] == ["user", "assistant"]


def test_sin_clave_avisa_en_vez_de_fallar():
    assert "no tengo configurada" in Cerebro(None).pensar("hola").texto.lower()


@pytest.mark.parametrize(
    ("error_de", "esperado"),
    [("conexion", "conectarme"), ("autenticacion", "no es válida"), ("api", "no pudo responder")],
)
def test_errores_de_la_api_no_tumban_al_asistente(error_de, esperado):
    peticion = MagicMock()
    respuesta = MagicMock(status_code=401, headers={}, request=peticion)
    errores = {
        "conexion": anthropic.APIConnectionError(request=peticion),
        "autenticacion": anthropic.AuthenticationError("mala clave", response=respuesta, body=None),
        "api": anthropic.APIError("fallo", request=peticion, body=None),
    }
    cerebro = Cerebro(NubeFalsa(error=errores[error_de]), Confirmador())
    assert esperado in decir(cerebro.pensar("hola"))


def test_una_respuesta_vacia_se_avisa():
    assert "no devolvió" in decir(Cerebro(NubeFalsa(frases=[]), Confirmador()).pensar("hola"))
