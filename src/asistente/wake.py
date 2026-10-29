import numpy as np
from openwakeword.model import Model

from . import config


class PalabraActivacion:
    def __init__(self) -> None:
        self._modelo = Model(
            wakeword_models=[config.MODELO_ACTIVACION],
            inference_framework="onnx",
        )

    def puntaje(self, frame: np.ndarray) -> float:
        return max(self._modelo.predict(frame).values())

    def detectada(self, frame: np.ndarray) -> bool:
        return self.puntaje(frame) >= config.UMBRAL_ACTIVACION

    def reiniciar(self) -> None:
        self._modelo.reset()
