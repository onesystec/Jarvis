from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
MODELO_WHISPER = RAIZ / "models" / "ggml-small.bin"

# Rutas absolutas: nunca se resuelven ejecutables a través del PATH.
WHISPER_CLI = "/opt/homebrew/bin/whisper-cli"
SAY = "/usr/bin/say"

# Voz principal: Kokoro (local, ONNX). Se verifica el SHA-256 al cargar.
MODELO_KOKORO = RAIZ / "models" / "kokoro-v1.0.onnx"
VOCES_KOKORO = RAIZ / "models" / "voices-v1.0.bin"
SHA256_KOKORO = "7d5df8ecf7d4b1878015a32686053fd0eebe2bc377234608764cc0ef3636a6c5"
SHA256_VOCES = "bca610b8308e8d99f32e6fe4197e7ec01679264efed0cac9140fe9c29f1fbf7d"
VOZ_KOKORO = "em_alex"  # masculinas en español: em_alex, em_santa
VELOCIDAD_VOZ = 1.0

# Respaldo si faltan los modelos de Kokoro.
VOZ = "Reed (Español (México))"
IDIOMA = "es"

FRECUENCIA = 16_000
FRAME = 1_280  # 80 ms, el tamaño que espera openWakeWord
MODELO_ACTIVACION = "hey_jarvis"
UMBRAL_ACTIVACION = 0.4  # medido: «hey jarvis» a la inglesa 0.46-0.99; conversación normal 0.00

UMBRAL_VOZ = 500  # RMS int16 a partir del cual hay voz; ajustar según el micrófono
ESPERA_MAX_S = 5.0  # cuánto esperar a que empiece a hablar tras la activación
SILENCIO_FIN_S = 1.0  # silencio que da por terminada la frase
FRASE_MAX_S = 15.0
