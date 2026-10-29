import numpy as np

from asistente import config
from asistente.audio import grabar_frase


class MicFalso:
    def __init__(self, amplitudes):
        self._amplitudes = iter(amplitudes)

    def leer(self):
        return np.full(config.FRAME, next(self._amplitudes), dtype=np.int16)


VOZ = config.UMBRAL_VOZ * 4
FRAMES_SILENCIO = int(config.SILENCIO_FIN_S * config.FRECUENCIA / config.FRAME)
FRAMES_ESPERA = int(config.ESPERA_MAX_S * config.FRECUENCIA / config.FRAME)


def test_corta_tras_el_silencio_final():
    mic = MicFalso([0, VOZ, VOZ] + [0] * (FRAMES_SILENCIO + 50))
    audio = grabar_frase(mic)
    assert len(audio) == (3 + FRAMES_SILENCIO) * config.FRAME


def test_devuelve_none_si_nadie_habla():
    mic = MicFalso([0] * (FRAMES_ESPERA + 10))
    assert grabar_frase(mic) is None
