import hashlib
import queue
import subprocess
import tempfile
import threading
from collections.abc import Callable, Iterable
from pathlib import Path

import numpy as np

from . import config
from .frases import Diferida
from .stt import guardar_wav

_kokoro = None


def _sha256(ruta: Path) -> str:
    h = hashlib.sha256()
    with ruta.open("rb") as f:
        while bloque := f.read(1 << 20):
            h.update(bloque)
    return h.hexdigest()


def _cargar_kokoro():
    global _kokoro
    if _kokoro is None:
        for ruta, esperado in (
            (config.MODELO_KOKORO, config.SHA256_KOKORO),
            (config.VOCES_KOKORO, config.SHA256_VOCES),
        ):
            if _sha256(ruta) != esperado:
                raise RuntimeError(f"El hash de {ruta.name} no coincide; el archivo fue alterado.")
        from kokoro_onnx import Kokoro

        _kokoro = Kokoro(str(config.MODELO_KOKORO), str(config.VOCES_KOKORO))
    return _kokoro


def _hablar_sistema(texto: str) -> None:
    # "--" evita que un texto que empiece con "-" se interprete como opción.
    subprocess.run([config.SAY, "-v", config.VOZ, "--", texto], check=True, timeout=120)


def _hay_kokoro() -> bool:
    return config.MODELO_KOKORO.exists() and config.VOCES_KOKORO.exists()


def _sintetizar(texto: str, voz: str | None) -> tuple[np.ndarray, int]:
    muestras, frecuencia = _cargar_kokoro().create(
        texto, voice=voz or config.VOZ_KOKORO, speed=config.VELOCIDAD_VOZ, lang="es"
    )
    return (np.clip(muestras, -1.0, 1.0) * 32767).astype(np.int16), frecuencia


def _reproducir(ruta: Path) -> None:
    # afplay sigue siempre la salida predeterminada del sistema (altavoces o AirPods).
    subprocess.run([config.AFPLAY, str(ruta)], check=True, timeout=120)


def hablar(texto: str, voz: str | None = None) -> None:
    hablar_frases([texto], voz)


def hablar_frases(
    frases: Iterable[str | Diferida], voz: str | None = None, al_decir: Callable[[], None] | None = None
) -> list[str]:
    """Dice las frases a medida que llegan: mientras suena una, se sintetiza la siguiente.

    `al_decir` se llama justo antes de cada frase. Las `Diferida` se ejecutan aquí, en el hilo
    principal, cuando ya sonó todo lo anterior. Devuelve lo que se dijo.
    """
    dichas: list[str] = []
    if not _hay_kokoro():
        for frase in frases:
            if isinstance(frase, Diferida):
                frase.ejecutar()
            elif frase.strip():
                if al_decir:
                    al_decir()
                _hablar_sistema(frase.strip())
                dichas.append(frase.strip())
        return dichas

    _cargar_kokoro()  # en este hilo: verifica los hashes antes de lanzar el hilo productor
    listas: queue.Queue = queue.Queue()
    parar = threading.Event()
    fallos: list[BaseException] = []
    diferidas: list[Diferida] = []

    def producir(carpeta: Path) -> None:
        try:
            for i, frase in enumerate(frases):
                if parar.is_set():
                    break
                if isinstance(frase, Diferida):
                    diferidas.append(frase)
                    listas.put(frase)
                    frase.esperar(parar.is_set)  # la generación sigue cuando el hilo principal la ejecuta
                    continue
                frase = frase.strip()
                if not frase:
                    continue
                pcm, frecuencia = _sintetizar(frase, voz)
                ruta = carpeta / f"{i}.wav"
                guardar_wav(ruta, pcm, frecuencia)
                listas.put((frase, ruta))
        except Exception as error:  # noqa: BLE001 - se re-lanza en el hilo principal como RuntimeError
            fallos.append(error)
        finally:
            listas.put(None)

    with tempfile.TemporaryDirectory(prefix="asistente-") as carpeta:
        productor = threading.Thread(target=producir, args=(Path(carpeta),), daemon=True)
        productor.start()
        try:
            while (item := listas.get()) is not None:
                if isinstance(item, Diferida):
                    item.ejecutar()
                    continue
                frase, ruta = item
                if al_decir:
                    al_decir()
                _reproducir(ruta)
                dichas.append(frase)
        finally:
            parar.set()
            for pendiente in diferidas:  # si algo falló, nadie las ejecutará: se libera a quien espera
                pendiente.hecha.set()
            productor.join(timeout=5)
    if fallos:
        raise RuntimeError(f"No pude generar la voz: {fallos[0]}") from fallos[0]
    return dichas
