import numpy as np

from asistente import config
from asistente.wake import PalabraActivacion


def test_silencio_y_ruido_no_activan():
    activacion = PalabraActivacion()
    rng = np.random.default_rng(0)
    for _ in range(50):
        frame = rng.integers(-300, 300, config.FRAME, dtype=np.int16)
        assert not activacion.detectada(frame)
