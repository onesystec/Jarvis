from types import SimpleNamespace as NS

import pytest

from asistente import config
from asistente.cerebro import _BLOQUEO, Cerebro
from asistente.frases import Diferida
from asistente.herramientas import Herramientas
from asistente.nube import ClienteClaude

from .test_cerebro import Confirmador, NubeFalsa, decir


def texto(t):
    return NS(type="text", text=t)


def inicio(tipo):
    return NS(type="content_block_start", content_block=NS(type=tipo))


class Flujo:
    def __init__(self, eventos, bloques, parada="end_turn"):
        self._eventos, self._final = eventos, NS(content=bloques, stop_reason=parada)

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def __iter__(self):
        return iter(self._eventos)

    def get_final_message(self):
        return self._final


class ClienteFalso:
    def __init__(self, flujos):
        self._flujos = list(flujos)
        self.llamadas: list[dict] = []
        self.messages = self

    def stream(self, **kwargs):
        self.llamadas.append({**kwargs, "messages": list(kwargs["messages"])})
        return self._flujos.pop(0)


def nube_con(*flujos):
    nube = ClienteClaude.__new__(ClienteClaude)
    nube._cliente = ClienteFalso(flujos)
    return nube


def respuesta_con_busqueda():
    eventos = [inicio("server_tool_use"), inicio("web_search_tool_result"), texto("Hoy el dólar cierra en 987 pesos."), texto(" Fuente reciente.")]
    bloques = [NS(type="server_tool_use"), NS(type="web_search_tool_result"), NS(type="text")]
    return Flujo(eventos, bloques)


def usar(_nombre, _entrada):
    return "ok"


def test_la_herramienta_web_solo_va_si_se_permite(monkeypatch):
    sin = nube_con(Flujo([texto("Hola, señor, ¿en qué le ayudo hoy?")], [NS(type="text")]))
    list(sin.frases([{"role": "user", "content": "hola"}], usar, web=False))
    assert all(h["name"] != "web_search" for h in sin._cliente.llamadas[0]["tools"])

    monkeypatch.setattr(config, "WEB_UBICACION", {"type": "approximate", "country": "CL"})
    con = nube_con(Flujo([texto("Hola, señor, ¿en qué le ayudo hoy?")], [NS(type="text")]))
    list(con.frases([{"role": "user", "content": "hola"}], usar, web=True))
    web = [h for h in con._cliente.llamadas[0]["tools"] if h["name"] == "web_search"]
    assert web == [{"type": config.WEB_HERRAMIENTA, "name": "web_search", "max_uses": config.WEB_BUSQUEDAS_MAX, "user_location": {"type": "approximate", "country": "CL"}}]


def test_avisa_mientras_busca_y_marca_el_contenido_externo():
    marcas = []
    nube = nube_con(respuesta_con_busqueda())
    frases = list(nube.frases([{"role": "user", "content": "dólar"}], usar, web=True, marcar_externo=lambda: marcas.append(1)))
    assert frases[0] == config.WEB_AVISO
    assert "987 pesos" in " ".join(frases[1:])
    assert marcas  # se marcó al llegar los resultados


def test_no_repite_el_aviso_si_ya_habia_dicho_algo():
    eventos = [texto("Voy a revisarlo en la red ahora mismo."), inicio("server_tool_use"), inicio("web_search_tool_result"), texto(" Son 987 pesos hoy.")]
    nube = nube_con(Flujo(eventos, [NS(type="text")]))
    frases = list(nube.frases([{"role": "user", "content": "dólar"}], usar, web=True))
    assert config.WEB_AVISO not in frases


def test_un_turno_pausado_se_reanuda_sin_mensaje_extra():
    pausado = Flujo([inicio("server_tool_use")], [NS(type="server_tool_use")], parada="pause_turn")
    fin = Flujo([texto("Ya lo tengo, señor: son 987 pesos.")], [NS(type="text")])
    nube = nube_con(pausado, fin)
    frases = list(nube.frases([{"role": "user", "content": "dólar"}], usar, web=True))
    segunda = nube._cliente.llamadas[1]["messages"]
    assert [m["role"] for m in segunda] == ["user", "assistant"]  # el servidor retoma solo, sin «continúa»
    assert "987" in " ".join(frases)


def test_tras_buscar_las_herramientas_locales_ya_estan_bloqueadas():
    """Claude lee la web y, en la misma respuesta, pide una herramienta: el bloqueo ya debe estar activo."""
    hechas = []
    herramientas = Herramientas(auditar=lambda **_: None, ejecutores={"volumen": lambda a: hechas.append(a) or "hecho"})
    cerebro = Cerebro(None, Confirmador(), herramientas)
    uso = NS(type="tool_use", id="t1", name="volumen", input={"accion": "subir"})
    flujo1 = Flujo(
        [inicio("server_tool_use"), inicio("web_search_tool_result")],
        [NS(type="server_tool_use"), NS(type="web_search_tool_result"), uso],
        parada="tool_use",
    )
    flujo2 = Flujo([texto("No puedo cambiar el volumen ahora, señor.")], [NS(type="text")])
    nube = nube_con(flujo1, flujo2)

    resultados = []
    for item in nube.frases([{"role": "user", "content": "x"}], cerebro._usar_herramienta, web=True, marcar_externo=cerebro._marcar_externo):
        if isinstance(item, Diferida):
            item.ejecutar()
    resultados = nube._cliente.llamadas[1]["messages"][-1]["content"]
    assert resultados[0]["content"] == _BLOQUEO
    assert hechas == []


def test_el_cerebro_pasa_web_y_aviso():
    nube = NubeFalsa()
    confirmar = Confirmador()
    cerebro = Cerebro(nube, confirmar)
    decir(cerebro.pensar("hola"))
    assert nube.web == [True]
    assert "buscar en internet" in confirmar.preguntas[0]
    assert callable(nube.marcar_externo)


def test_se_puede_desactivar_o_revocar_la_busqueda(monkeypatch):
    nube = NubeFalsa()
    cerebro = Cerebro(nube, Confirmador())
    decir(cerebro.pensar("hola"))
    assert "no buscaré en internet" in cerebro.pensar("no busques en internet").texto
    decir(cerebro.pensar("otra cosa"))
    assert nube.web == [True, False]
    assert "puedo buscar" in cerebro.pensar("ya puedes buscar en internet").texto
    decir(cerebro.pensar("y ahora"))
    assert nube.web[-1] is True
    cerebro.nueva_conversacion()
    cerebro._web_revocada = True
    cerebro.nueva_conversacion()
    assert cerebro._web_revocada is False  # cada conversación empieza con lo configurado

    monkeypatch.setattr(config, "WEB_BUSQUEDA", False)
    nube2, confirmar2 = NubeFalsa(), Confirmador()
    decir(Cerebro(nube2, confirmar2).pensar("hola"))
    assert nube2.web == [False] and "internet" not in confirmar2.preguntas[0]


def test_buscar_en_internet_no_se_confunde_con_el_permiso():
    nube = NubeFalsa()
    cerebro = Cerebro(nube, Confirmador())
    respuesta = cerebro.pensar("busca en internet el precio del dólar")
    assert respuesta.frases is not None  # se manda a Claude, no se traga como «activa la búsqueda»


def test_lo_que_trae_la_web_contamina_la_conversacion():
    cerebro = Cerebro(NubeFalsa(), Confirmador(), Herramientas(auditar=lambda **_: None, ejecutores={"volumen": lambda a: "hecho"}))
    assert cerebro._usar_herramienta("volumen", {"accion": "subir"}) == "hecho"
    cerebro._marcar_externo()
    assert cerebro._usar_herramienta("volumen", {"accion": "subir"}) == _BLOQUEO
    cerebro.nueva_conversacion()
    assert cerebro._usar_herramienta("volumen", {"accion": "subir"}) == "hecho"


@pytest.mark.parametrize(
    "frase",
    ["no busques en internet", "deja de buscar en la web", "sin internet por favor"],
)
def test_frases_para_revocar_la_busqueda(frase):
    from asistente.reglas import pide_revocar_web

    assert pide_revocar_web(frase)


def test_si_claude_se_queda_sin_espacio_o_rechaza_se_dice_en_voz_alta():
    for parada in ("max_tokens", "refusal"):
        nube = nube_con(Flujo([inicio("server_tool_use")], [NS(type="thinking")], parada=parada))
        frases = list(nube.frases([{"role": "user", "content": "x"}], usar, web=True))
        assert frases[-1].startswith("No pude responder") and len(frases) == 2  # el aviso de búsqueda y la disculpa


def test_se_pide_esfuerzo_bajo_y_margen_suficiente():
    nube = nube_con(Flujo([texto("Hola, señor, ¿en qué le ayudo hoy?")], [NS(type="text")]))
    list(nube.frases([{"role": "user", "content": "hola"}], usar))
    llamada = nube._cliente.llamadas[0]
    assert llamada["output_config"] == {"effort": config.ESFUERZO_CLAUDE}
    assert llamada["max_tokens"] >= 1024
    assert "Fecha y hora actuales" in llamada["system"]


def test_el_historial_anota_que_hubo_una_busqueda_y_no_guarda_el_aviso():
    nube = NubeFalsa(frases=["El dólar ronda los 985 pesos."])
    nube.busca = True
    cerebro = Cerebro(nube, Confirmador())
    decir(cerebro.pensar("¿cómo va el dólar?"))
    nube.busca = False
    decir(cerebro.pensar("¿y mañana?"))
    previo = nube.llamadas[1][1]["content"]
    assert previo == f"El dólar ronda los 985 pesos. {config.NOTA_FUENTE_EXTERNA}"
    assert config.WEB_AVISO not in previo


def test_sin_busqueda_el_historial_queda_limpio():
    nube = NubeFalsa(frases=["Los pulpos tienen tres corazones."])
    cerebro = Cerebro(nube, Confirmador())
    decir(cerebro.pensar("dato curioso"))
    decir(cerebro.pensar("otro"))
    assert nube.llamadas[1][1]["content"] == "Los pulpos tienen tres corazones."
