import re
import subprocess
import tempfile
import wave
from pathlib import Path

import numpy as np

from . import config

_MARCAS = re.compile(r"\[[^\]]*\]|\([^)]*\)")


def guardar_wav(ruta: Path, audio: np.ndarray, frecuencia: int = config.FRECUENCIA) -> None:
    with wave.open(str(ruta), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(frecuencia)
        w.writeframes(audio.astype(np.int16).tobytes())


def _limpiar(salida: str) -> str:
    # Whisper emite marcas como [BLANK_AUDIO] o (música) cuando no hay voz.
    return " ".join(_MARCAS.sub(" ", salida).split())


def transcribir_archivo(ruta: Path) -> str:
    resultado = subprocess.run(
        [
            config.WHISPER_CLI,
            "-m", str(config.MODELO_WHISPER),
            "-l", config.IDIOMA,
            "--prompt", config.PROMPT_WHISPER,
            "-nt", "-np",
            "-f", str(ruta),
        ],
        capture_output=True,
        text=True,
        check=True,
        timeout=60,
    )
    texto = _limpiar(resultado.stdout)
    # Sin voz, Whisper a veces devuelve la propia pista de contexto: no es lo que dijo el usuario.
    if texto.lower().strip(" .¡!¿?") in config.PROMPT_WHISPER.lower():
        return ""
    return texto


def transcribir(audio: np.ndarray) -> str:
    # El audio vive solo en un directorio temporal privado (0700) y se borra al salir.
    with tempfile.TemporaryDirectory(prefix="asistente-") as carpeta:
        ruta = Path(carpeta) / "voz.wav"
        guardar_wav(ruta, audio)
        return transcribir_archivo(ruta)
