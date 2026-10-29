import contextlib
import queue
import time
from typing import Self

import numpy as np
import sounddevice as sd

from . import config
from .dispositivos import entrada_por_defecto

_S_POR_FRAME = config.FRAME / config.FRECUENCIA


def _refrescar_portaudio() -> None:
    # PortAudio guarda la lista de dispositivos al iniciar; hay que reiniciarlo
    # para ver AirPods conectados o desconectados después.
    sd._terminate()
    sd._initialize()


def _nombre_entrada() -> str:
    return sd.query_devices(kind="input")["name"]


class Microfono:
    """Micrófono que sigue al dispositivo de entrada predeterminado de macOS.

    Si se cambia de AirPods al micrófono del Mac (o al revés), o el dispositivo
    deja de responder, se reabre solo y reintenta hasta tener uno disponible.
    """

    def __init__(self, tiempo_espera: float = config.ESPERA_MICROFONO_S) -> None:
        self._tiempo_espera = tiempo_espera
        self._stream = None
        self._cola: queue.Queue = queue.Queue(maxsize=100)
        self._dispositivo = None
        self.cambios = 0

    def __enter__(self) -> Self:
        self._abrir(refrescar=False)
        return self

    def __exit__(self, *_) -> None:
        self._cerrar()

    def _callback(self, datos, _frames, _tiempo, _estado) -> None:
        try:
            self._cola.put_nowait(datos[:, 0].copy())
        except queue.Full:
            pass  # el consumidor va atrasado; se descarta audio viejo

    def _cerrar(self) -> None:
        if self._stream is None:
            return
        # El dispositivo pudo haber desaparecido (AirPods desconectados).
        with contextlib.suppress(sd.PortAudioError, OSError):
            self._stream.stop()
            self._stream.close()
        self._stream = None

    def _abrir(self, refrescar: bool) -> None:
        espera = 0.5
        while True:
            try:
                if refrescar:
                    _refrescar_portaudio()
                self._dispositivo = entrada_por_defecto()
                self._cola = queue.Queue(maxsize=100)
                self._stream = sd.InputStream(
                    samplerate=config.FRECUENCIA,
                    channels=1,
                    dtype="int16",
                    blocksize=config.FRAME,
                    callback=self._callback,
                )
                self._stream.start()
                print(f"\n  Micrófono: {_nombre_entrada()}", flush=True)
                return
            except (sd.PortAudioError, OSError, ValueError) as error:
                self._cerrar()
                refrescar = True
                print(f"\n  Micrófono no disponible ({error}); reintentando…", flush=True)
                time.sleep(espera)
                espera = min(espera * 2, 3.0)

    def _reabrir(self, motivo: str) -> None:
        print(f"\n  {motivo}; cambiando de micrófono…", flush=True)
        self._cerrar()
        self.cambios += 1
        self._abrir(refrescar=True)

    def leer(self) -> np.ndarray:
        while True:
            if entrada_por_defecto() != self._dispositivo:
                self._reabrir("Cambió el micrófono predeterminado")
            try:
                return self._cola.get(timeout=self._tiempo_espera)
            except queue.Empty:
                self._reabrir("El micrófono dejó de responder")

    def vaciar(self) -> None:
        # Descarta lo acumulado mientras el asistente hablaba, para no oírse a sí mismo.
        while True:
            try:
                self._cola.get_nowait()
            except queue.Empty:
                return


def rms(frame: np.ndarray) -> float:
    return float(np.sqrt(np.mean(frame.astype(np.float32) ** 2)))


def grabar_frase(mic, espera_max_s: float = config.ESPERA_MAX_S) -> np.ndarray | None:
    espera_max = int(espera_max_s / _S_POR_FRAME)
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
