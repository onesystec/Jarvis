import hashlib
import subprocess
import tempfile
from pathlib import Path

import numpy as np

from . import config
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


def hablar(texto: str, voz: str | None = None) -> None:
    texto = texto.strip()
    if not texto:
        return
    if not (config.MODELO_KOKORO.exists() and config.VOCES_KOKORO.exists()):
        _hablar_sistema(texto)
        return
    muestras, frecuencia = _cargar_kokoro().create(
        texto, voice=voz or config.VOZ_KOKORO, speed=config.VELOCIDAD_VOZ, lang="es"
    )
    pcm = (np.clip(muestras, -1.0, 1.0) * 32767).astype(np.int16)
    # afplay sigue siempre la salida predeterminada del sistema (altavoces o AirPods).
    with tempfile.TemporaryDirectory(prefix="asistente-") as carpeta:
        ruta = Path(carpeta) / "voz.wav"
        guardar_wav(ruta, pcm, frecuencia)
        subprocess.run([config.AFPLAY, str(ruta)], check=True, timeout=120)
