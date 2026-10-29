import subprocess

import numpy as np

from . import config
from .audio import Microfono, grabar_frase, rms
from .stt import transcribir
from .tts import hablar
from .wake import PalabraActivacion

_S_POR_FRAME = config.FRAME / config.FRECUENCIA
_VOCES_KOKORO = ["em_alex", "em_santa"]
_VOCES_SISTEMA = ["Reed (Español (México))"]


class _Reproduccion:
    """Micrófono falso que reproduce frames ya grabados."""

    def __init__(self, frames) -> None:
        self._frames = iter(frames)

    def leer(self):
        return next(self._frames)


def _grabar(mic, segundos: float):
    return [mic.leer() for _ in range(int(segundos / _S_POR_FRAME))]


def _traza(frames, cada_s: float = 0.4) -> str:
    por_bloque = max(1, int(cada_s / _S_POR_FRAME))
    return " ".join(
        f"{max(rms(f) for f in frames[i:i + por_bloque]):.0f}"
        for i in range(0, len(frames), por_bloque)
    )


def diagnosticar() -> None:
    activacion = PalabraActivacion()
    with Microfono() as mic:
        input("1/3 Ruido ambiente. Quédate en silencio y pulsa Enter... ")
        ruido = [rms(f) for f in _grabar(mic, 2)]
        print(f"Ruido ambiente: medio {sum(ruido) / len(ruido):.0f}, máximo {max(ruido):.0f}")

        for intento in range(1, 4):
            input(f"2/3 Activación {intento} de 3. Pulsa Enter y di «hey jarvis» al oír «ya»... ")
            hablar("Ya.")
            mic.vaciar()
            activacion.reiniciar()
            frames = _grabar(mic, 4)
            puntajes = [activacion.puntaje(f) for f in frames]
            print(
                f"Activación {intento}: puntaje máximo {max(puntajes):.2f} "
                f"(umbral {config.UMBRAL_ACTIVACION}), volumen pico {max(rms(f) for f in frames):.0f}"
            )

        input("3/3 Frase. Pulsa Enter y di «enciende las luces del salón y dime qué hora es» al oír «ya»... ")
        hablar("Ya.")
        mic.vaciar()
        frames = _grabar(mic, 7)
        print(f"Volumen por 0,4 s: {_traza(frames)}")
        print(f"Umbral de voz actual: {config.UMBRAL_VOZ}")
        audio = grabar_frase(_Reproduccion(frames))
        if audio is None:
            print("El segmentador NO detectó voz con el umbral actual.")
        else:
            segundos = len(audio) / config.FRECUENCIA
            print(f"El segmentador recortó {segundos:.1f} s de 7 s grabados.")
            print(f"Transcripción: {transcribir(audio)!r}")
        print(f"Transcripción de la grabación completa: {transcribir(np.concatenate(frames))!r}")


def vigilar_microfono(segundos: float = 60) -> None:
    """Muestra el nivel en vivo; sirve para comprobar el cambio entre AirPods y el Mac."""
    import time

    fin = time.monotonic() + segundos
    print(f"Vigilando {segundos:.0f} s. Cambia de micrófono cuando quieras (Ctrl+C para salir).")
    with Microfono() as mic:
        siguiente = 0.0
        while time.monotonic() < fin:
            frame = mic.leer()
            if time.monotonic() >= siguiente:
                print(f"\r  nivel {rms(frame):6.0f}   cambios {mic.cambios}  ", end="", flush=True)
                siguiente = time.monotonic() + 0.4
    print()


def probar_voces() -> None:
    frase = "Buenas tardes, señor. Sistemas en línea y listos para ayudarle."
    for voz in _VOCES_KOKORO:
        print(f"Kokoro {voz}")
        hablar(frase, voz=voz)
    for voz in _VOCES_SISTEMA:
        print(f"Sistema {voz}")
        subprocess.run([config.SAY, "-v", voz, "--", frase], check=True, timeout=60)
