from asistente import config, loop
from asistente.reglas import Respuesta


class EsferaFalsa:
    def __init__(self) -> None:
        self.estados: list[str] = []

    def estado(self, nombre: str) -> None:
        self.estados.append(nombre)


class MicFalso:
    def __init__(self) -> None:
        self.vaciados = 0

    def vaciar(self) -> None:
        self.vaciados += 1


class CerebroFalso:
    def __init__(self, respuestas) -> None:
        self._respuestas = list(respuestas)
        self.conversaciones = 0
        self.oido: list[str] = []

    def nueva_conversacion(self) -> None:
        self.conversaciones += 1

    def terminar_conversacion(self) -> None:
        self.terminadas = getattr(self, "terminadas", 0) + 1

    def pensar(self, texto: str) -> Respuesta:
        self.oido.append(texto)
        return self._respuestas.pop(0)


def preparar(monkeypatch, escuchas):
    esperas: list[float] = []
    turnos = list(escuchas)

    def escuchar(_mic, _esfera, espera=config.ESPERA_MAX_S):
        esperas.append(espera)
        return turnos.pop(0)

    dicho: list[list[str]] = []
    monkeypatch.setattr(loop, "_escuchar", escuchar)
    monkeypatch.setattr(loop, "_sonido_activacion", lambda: None)
    monkeypatch.setattr(loop, "hablar_frases", lambda frases, **_k: dicho.append(list(frases)) or list(dicho[-1]))
    return esperas, dicho


def test_sigue_escuchando_hasta_que_hay_silencio(monkeypatch):
    esperas, dicho = preparar(monkeypatch, ["hola", "y qué tal", ""])
    cerebro = CerebroFalso([Respuesta("Buenas."), Respuesta("Bien, señor.")])
    apagar = loop._conversar(MicFalso(), EsferaFalsa(), cerebro)
    assert apagar is False
    assert cerebro.oido == ["hola", "y qué tal"]
    assert dicho == [["Buenas."], ["Bien, señor."]]
    assert esperas == [config.ESPERA_MAX_S, config.CONVERSACION_ESPERA_S, config.CONVERSACION_ESPERA_S]
    assert cerebro.conversaciones == 1


def test_adios_termina_la_conversacion_sin_apagar(monkeypatch):
    preparar(monkeypatch, ["adiós"])
    cerebro = CerebroFalso([Respuesta("Hasta luego, señor.", fin=True)])
    assert loop._conversar(MicFalso(), EsferaFalsa(), cerebro) is False


def test_apagate_pide_apagar(monkeypatch):
    preparar(monkeypatch, ["apágate"])
    cerebro = CerebroFalso([Respuesta("Apagando sistemas, señor.", salir=True, fin=True)])
    assert loop._conversar(MicFalso(), EsferaFalsa(), cerebro) is True


def test_un_fallo_de_turno_no_tumba_el_asistente(monkeypatch):
    preparar(monkeypatch, ["hola"])
    monkeypatch.setattr(loop, "hablar_frases", lambda *_a, **_k: (_ for _ in ()).throw(RuntimeError("sin voz")))
    cerebro = CerebroFalso([Respuesta("Buenas.")])
    assert loop._conversar(MicFalso(), EsferaFalsa(), cerebro) is False


def test_ruido_de_una_letra_no_cuenta_como_orden(monkeypatch):
    _esperas, dicho = preparar(monkeypatch, ["a"])
    cerebro = CerebroFalso([])
    assert loop._conversar(MicFalso(), EsferaFalsa(), cerebro) is False
    assert cerebro.oido == [] and dicho == []
