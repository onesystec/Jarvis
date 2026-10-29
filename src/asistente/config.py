from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
MODELO_WHISPER = RAIZ / "models" / "ggml-small.bin"

# Rutas absolutas: nunca se resuelven ejecutables a través del PATH.
WHISPER_CLI = "/opt/homebrew/bin/whisper-cli"
SAY = "/usr/bin/say"

VOZ = "Reed (Español (México))"
IDIOMA = "es"

FRECUENCIA = 16_000
FRAME = 1_280  # 80 ms, el tamaño que espera openWakeWord
MODELO_ACTIVACION = "hey_jarvis"
UMBRAL_ACTIVACION = 0.5

UMBRAL_VOZ = 500  # RMS int16 a partir del cual hay voz; ajustar según el micrófono
ESPERA_MAX_S = 5.0  # cuánto esperar a que empiece a hablar tras la activación
SILENCIO_FIN_S = 1.0  # silencio que da por terminada la frase
FRASE_MAX_S = 15.0
