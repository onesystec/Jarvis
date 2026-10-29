from datetime import datetime
from unittest.mock import MagicMock

import anthropic

from asistente.cerebro import Cerebro
from asistente.reglas import es_afirmativo, interpretar, normalizar

LUNES = datetime(2026, 10, 26, 14, 5)


class NubeFalsa:
    def __init__(self, respuesta="Respuesta de Claude.", error=None) -> None:
        self.respuesta = respuesta
        self.error = error
        self.llamadas: list[list[dict]] = []

    def responder(self, mensajes):
        self.llamadas.append(list(mensajes))
        if self.error:
            raise self.error
        return self.respuesta


def test_normalizar_quita_tildes_y_signos():
    assert normalizar("¿Qué HORA es?") == "que hora es"


def test_hora_y_fecha_se_resuelven_en_local():
    assert interpretar("¿Qué hora es?", LUNES).texto == "Son las 2 y 5."
    assert interpretar("qué día es hoy", LUNES).texto == "Hoy es lunes 26 de octubre de 2026."
    assert interpretar("hora en punto?", datetime(2026, 1, 1, 13, 0)) is None  # no inventa reglas
    assert interpretar("qué hora es", datetime(2026, 1, 1, 13, 0)).texto == "Es la 1 en punto."


def test_despedida_cierra_el_asistente():
    assert interpretar("adiós Jarvis").salir


def test_afirmativo_y_negativo():
    assert es_afirmativo("Sí, adelante")
    assert not es_afirmativo("no, mejor no")
    assert not es_afirmativo("")


def test_lo_simple_no_sale_a_la_nube():
    nube = NubeFalsa()
    cerebro = Cerebro(nube, confirmar=lambda _: True)
    assert cerebro.pensar("qué hora es", LUNES).texto.startswith("Son las")
    assert nube.llamadas == []


def test_sin_aprobacion_no_se_envia_nada():
    nube = NubeFalsa()
    cerebro = Cerebro(nube, confirmar=lambda _: False)
    assert "no lo envío" in cerebro.pensar("cuéntame un chiste").texto
    assert nube.llamadas == []


def test_con_aprobacion_se_envia_solo_la_conversacion():
    nube = NubeFalsa()
    cerebro = Cerebro(nube, confirmar=lambda _: True)
    assert cerebro.pensar("cuéntame un chiste").texto == "Respuesta de Claude."
    assert nube.llamadas == [[{"role": "user", "content": "cuéntame un chiste"}]]


def test_el_historial_se_acota_y_alterna_roles():
    nube = NubeFalsa()
    cerebro = Cerebro(nube, confirmar=lambda _: True)
    for i in range(10):
        cerebro.pensar(f"pregunta {i}")
    enviados = nube.llamadas[-1]
    assert len(enviados) <= 9
    assert enviados[0]["role"] == "user"
    assert [m["role"] for m in enviados[:2]] == ["user", "assistant"]


def test_sin_clave_avisa_en_vez_de_fallar():
    assert "no tengo configurada" in Cerebro(None).pensar("hola").texto.lower()


def test_errores_de_la_api_no_tumban_al_asistente():
    peticion = MagicMock()
    respuesta = MagicMock(status_code=401, headers={}, request=peticion)
    for error, esperado in [
        (anthropic.APIConnectionError(request=peticion), "conectarme"),
        (anthropic.AuthenticationError("mala clave", response=respuesta, body=None), "no es válida"),
    ]:
        cerebro = Cerebro(NubeFalsa(error=error), confirmar=lambda _: True)
        assert esperado in cerebro.pensar("hola").texto
