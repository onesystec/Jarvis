import numpy as np
from openwakeword.model import Model

from . import config


class PalabraActivacion:
    def __init__(self) -> None:
        self._modelo = Model(
            wakeword_models=[config.MODELO_ACTIVACION],
            inference_framework="onnx",
        )

    def detectada(self, frame: np.ndarray) -> bool:
        puntajes = self._modelo.predict(frame)
        return max(puntajes.values()) >= config.UMBRAL_ACTIVACION

    def reiniciar(self) -> None:
        self._modelo.reset()
