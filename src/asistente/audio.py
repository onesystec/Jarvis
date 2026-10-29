from typing import Self

import numpy as np
import sounddevice as sd

from . import config

_S_POR_FRAME = config.FRAME / config.FRECUENCIA


class Microfono:
    def __enter__(self) -> Self:
        self._stream = sd.InputStream(
            samplerate=config.FRECUENCIA,
            channels=1,
            dtype="int16",
            blocksize=config.FRAME,
        )
        self._stream.start()
        return self

    def __exit__(self, *_) -> None:
        self._stream.stop()
        self._stream.close()

    def leer(self) -> np.ndarray:
        datos, _ = self._stream.read(config.FRAME)
        return datos[:, 0].copy()

    def vaciar(self) -> None:
        # Descarta lo acumulado mientras el asistente hablaba, para no oírse a sí mismo.
        pendiente = self._stream.read_available
        if pendiente:
            self._stream.read(pendiente)


def rms(frame: np.ndarray) -> float:
    return float(np.sqrt(np.mean(frame.astype(np.float32) ** 2)))


def grabar_frase(mic) -> np.ndarray | None:
    espera_max = int(config.ESPERA_MAX_S / _S_POR_FRAME)
    silencio_fin = int(config.SILENCIO_FIN_S / _S_POR_FRAME)
    frase_max = int(config.FRASE_MAX_S / _S_POR_FRAME)

    frames = []
    hablando = False
    silencio = 0
    for i in range(frase_max):
        frame = mic.leer()
        frames.append(frame)
        if rms(frame) >= config.UMBRAL_VOZ:
            hablando = True
            silencio = 0
        elif hablando:
            silencio += 1
            if silencio >= silencio_fin:
                break
        elif i >= espera_max:
            return None
    return np.concatenate(frames) if hablando else None
