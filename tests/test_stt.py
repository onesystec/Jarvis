import subprocess

import pytest

from asistente import config
from asistente.stt import _limpiar, transcribir_archivo

requiere_modelo = pytest.mark.skipif(
    not config.MODELO_WHISPER.exists(), reason="falta el modelo de Whisper"
)


def test_limpiar_quita_marcas_de_whisper():
    assert _limpiar(" [BLANK_AUDIO]\n") == ""
    assert _limpiar("hola (música) mundo [ruido]") == "hola mundo"


@requiere_modelo
def test_transcribe_voz_sintetizada(tmp_path):
    wav = tmp_path / "frase.wav"
    subprocess.run(
        [config.SAY, "-v", config.VOZ, "-o", str(wav),
         "--file-format=WAVE", "--data-format=LEI16@16000",
         "--", "Enciende las luces del salón"],
        check=True,
    )
    texto = transcribir_archivo(wav).lower()
    assert "enciende" in texto and "salón" in texto
