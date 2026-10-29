from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
MODELO_WHISPER = RAIZ / "models" / "ggml-small.bin"

# Rutas absolutas: nunca se resuelven ejecutables a través del PATH.
WHISPER_CLI = "/opt/homebrew/bin/whisper-cli"
SAY = "/usr/bin/say"
AFPLAY = "/usr/bin/afplay"

# Voz principal: Kokoro (local, ONNX). Se verifica el SHA-256 al cargar.
MODELO_KOKORO = RAIZ / "models" / "kokoro-v1.0.onnx"
VOCES_KOKORO = RAIZ / "models" / "voices-v1.0.bin"
SHA256_KOKORO = "7d5df8ecf7d4b1878015a32686053fd0eebe2bc377234608764cc0ef3636a6c5"
SHA256_VOCES = "bca610b8308e8d99f32e6fe4197e7ec01679264efed0cac9140fe9c29f1fbf7d"
VOZ_KOKORO = "em_alex"  # masculinas en español: em_alex, em_santa
VELOCIDAD_VOZ = 1.0

# Cerebro: reglas locales primero; Claude solo con aprobación del usuario.
MODELO_CLAUDE = "claude-haiku-5-5"
MAX_TOKENS_CLAUDE = 300
TIEMPO_MAX_CLAUDE_S = 30.0
APROBAR_ANTES_DE_NUBE = True
HISTORIAL_MAX_MENSAJES = 8  # lo único que viaja a la nube además de la pregunta actual
SERVICIO_CLAVE = "asistente-anthropic"
SECURITY = "/usr/bin/security"
INSTRUCCIONES_CLAUDE = (
    "Eres Jarvis, un asistente de voz personal que habla en español. "
    "Tus respuestas se leen en voz alta: máximo tres frases cortas, sin markdown, "
    "sin listas, sin emojis ni símbolos. Trata al usuario con cortesía y llámalo señor. "
    "Tú no ejecutas acciones: abrir o cerrar aplicaciones y ajustar el volumen lo hace el sistema "
    "local solo con órdenes directas («abre Safari», «sube el volumen»). "
    "Archivos, navegador y el resto todavía no están disponibles; "
    "si te lo piden, dilo con claridad en vez de fingirlo."
)

# Herramientas del Mac. Cada una tiene un permiso propio:
#   "libre"       se ejecuta al momento
#   "confirmar"   pide un «sí» hablado antes de ejecutarse
#   "desactivada" (o ausente) se rechaza
PERMISOS = {
    "abrir_app": "libre",
    "cerrar_app": "confirmar",
    "volumen": "libre",
}
OPEN = "/usr/bin/open"
OSASCRIPT = "/usr/bin/osascript"
PASO_VOLUMEN = 10
APPS_PROTEGIDAS = {"terminal", "finder", "claude"}  # cerrarlas tumbaría al asistente o al sistema
CARPETAS_APPS = (
    Path("/Applications"),
    Path("/Applications/Utilities"),
    Path("/System/Applications"),
    Path("/System/Applications/Utilities"),
    Path.home() / "Applications",
)

# Esfera flotante que indica que el asistente está activo (esquina superior derecha).
ESFERA_ACTIVA = True
ESFERA_LADO = 260  # puntos; la silueta ocupa ~60 % y el resto es resplandor
ESFERA_MARGEN = 8  # separación del borde de la pantalla

DATOS = RAIZ / "data"
AUDITORIA = DATOS / "auditoria.jsonl"

# Respaldo si faltan los modelos de Kokoro.
VOZ = "Reed (Español (México))"
IDIOMA = "es"

FRECUENCIA = 16_000
FRAME = 1_280  # 80 ms, el tamaño que espera openWakeWord
MODELO_ACTIVACION = "hey_jarvis"
UMBRAL_ACTIVACION = 0.4  # medido: «hey jarvis» a la inglesa 0.46-0.99; conversación normal 0.00

ESPERA_MICROFONO_S = 1.0  # sin audio durante este tiempo = dispositivo caído; se reabre
UMBRAL_VOZ = 500  # RMS int16 a partir del cual hay voz; ajustar según el micrófono
ESPERA_MAX_S = 5.0  # cuánto esperar a que empiece a hablar tras la activación
SILENCIO_FIN_S = 1.0  # silencio que da por terminada la frase
FRASE_MAX_S = 15.0
