from typing import ClassVar

import numpy as np
import pytest

from asistente import audio, config


class StreamFalso:
    """Stream que entrega un frame al arrancar, con el valor de su número de instancia."""

    instancias: ClassVar[list["StreamFalso"]] = []
    fallos_pendientes: ClassVar[int] = 0

    def __init__(self, **kwargs) -> None:
        if StreamFalso.fallos_pendientes:
            StreamFalso.fallos_pendientes -= 1
            raise audio.sd.PortAudioError("dispositivo no disponible")
        self._callback = kwargs["callback"]
        self.cerrado = False
        StreamFalso.instancias.append(self)

    def start(self) -> None:
        valor = len(StreamFalso.instancias)
        self._callback(np.full((config.FRAME, 1), valor, dtype=np.int16), config.FRAME, None, None)

    def stop(self) -> None:
        pass

    def close(self) -> None:
        self.cerrado = True


@pytest.fixture
def entorno(monkeypatch):
    StreamFalso.instancias = []
    StreamFalso.fallos_pendientes = 0
    estado = {"dispositivo": 1}
    monkeypatch.setattr(audio.sd, "InputStream", StreamFalso)
    monkeypatch.setattr(audio, "_refrescar_portaudio", lambda: None)
    monkeypatch.setattr(audio, "_nombre_entrada", lambda: "Micrófono falso")
    monkeypatch.setattr(audio, "entrada_por_defecto", lambda: estado["dispositivo"])
    monkeypatch.setattr(audio.time, "sleep", lambda _: None)
    return estado


def test_lee_frames_del_dispositivo_actual(entorno):
    with audio.Microfono(tiempo_espera=0.05) as mic:
        assert mic.leer()[0] == 1
        assert mic.cambios == 0


def test_reabre_al_cambiar_el_microfono_predeterminado(entorno):
    with audio.Microfono(tiempo_espera=0.05) as mic:
        assert mic.leer()[0] == 1
        entorno["dispositivo"] = 2  # p. ej. se conectan los AirPods
        assert mic.leer()[0] == 2
        assert mic.cambios == 1
        assert StreamFalso.instancias[0].cerrado


def test_reabre_si_el_dispositivo_deja_de_responder(entorno):
    with audio.Microfono(tiempo_espera=0.05) as mic:
        assert mic.leer()[0] == 1
        # No llegan más frames: la lectura no se cuelga y reabre.
        assert mic.leer()[0] == 2
        assert mic.cambios == 1


def test_reintenta_si_el_dispositivo_no_esta_disponible(entorno):
    with audio.Microfono(tiempo_espera=0.05) as mic:
        mic.leer()
        entorno["dispositivo"] = 2
        StreamFalso.fallos_pendientes = 3  # AirPods aún conectándose
        assert mic.leer()[0] == 2
        assert mic.cambios == 1


def test_vaciar_descarta_audio_acumulado(entorno):
    with audio.Microfono(tiempo_espera=0.05) as mic:
        mic.vaciar()
        assert mic._cola.empty()
