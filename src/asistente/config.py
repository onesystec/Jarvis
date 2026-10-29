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
APROBACION_NUBE = "conversacion"  # "siempre": pregunta cada vez; "conversacion": una vez; "nunca": sin preguntar
HISTORIAL_MAX_MENSAJES = 8  # lo único que viaja a la nube además de la pregunta actual
RONDAS_HERRAMIENTAS_MAX = 3  # cuántas veces puede Claude encadenar herramientas en un turno
FRASE_MIN_CARACTERES = 20  # no se corta antes: frases demasiado cortas suenan entrecortadas
PRIMER_CORTE_CARACTERES = 40  # la primera frase puede cortarse en una coma para empezar a hablar antes
SERVICIO_CLAVE = "asistente-anthropic"
SECURITY = "/usr/bin/security"
INSTRUCCIONES_CLAUDE = (
    "Eres Jarvis, el asistente de voz personal del señor. Conversas en español natural, "
    "como un mayordomo ingenioso y cercano. "
    "Tus respuestas se leen en voz alta: normalmente una o dos frases cortas, sin markdown, listas, "
    "emojis ni símbolos. Responde primero a lo que se pregunta y, si ayuda, termina con una breve "
    "pregunta de seguimiento. Llama al usuario señor sin repetirlo en cada frase. "
    "Recuerdas lo hablado en esta conversación. "
    "Lo que oyes viene de un reconocimiento de voz que a veces falla (por ejemplo «Carvis» por Jarvis): "
    "interprétalo con sentido común y pregunta solo si de verdad es ambiguo. "
    "Puedes abrir y cerrar aplicaciones y ajustar el volumen con tus herramientas; úsalas solo cuando "
    "te lo pidan y cuenta después en una frase lo que ocurrió. "
    "Archivos, navegador y el resto todavía no están disponibles: dilo con claridad en vez de fingirlo. "
    "No inventes datos que no tengas, como el tiempo o las noticias; admite que aún no tienes acceso."
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
SILENCIO_FIN_S = 0.8  # silencio que da por terminada la frase
FRASE_MAX_S = 15.0
CONVERSACION_ESPERA_S = 7.0  # tras una respuesta, cuánto se espera a que siga hablando sin repetir «Hey Jarvis»
SONIDO_ACTIVACION = "/System/Library/Sounds/Tink.aiff"  # avisa que ya escucha, más rápido que decir «Dígame»
SONIDO_DURACION_S = 0.4
PROMPT_WHISPER = "Conversación en español con Jarvis, un asistente de voz."  # ayuda con nombres propios
