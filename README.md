# Jarvis

Asistente de voz local-first para macOS, inspirado en JARVIS. Todo el audio se procesa en el equipo.

## Estado

En desarrollo. Hecho: palabra de activación, transcripción local, voz de salida, micrófono que sigue al dispositivo predeterminado (AirPods o micrófono del Mac), cerebro híbrido (reglas locales y Claude con aprobación hablada) y primeras herramientas del Mac con permisos y auditoría, memoria cifrada, más herramientas del Mac búsqueda web aislada y un modo privado con modelo local. Todas las fases del plan están completas.

## Cómo funciona

| Etapa | Tecnología | Dónde corre |
|---|---|---|
| Palabra de activación («Hey Jarvis») | openWakeWord | Local |
| Voz a texto | whisper.cpp (modelo `small`) | Local |
| Texto a voz | Kokoro (`em_alex`) | Local |

La palabra de activación está entrenada con pronunciación inglesa: di «Hey Járvis» con algo de energía.

## Requisitos

- macOS en Apple Silicon (probado en un MacBook Air M2 con 8 GB)
- Python 3.13, [uv](https://docs.astral.sh/uv/) y Homebrew

```bash
brew install uv whisper-cpp portaudio llama.cpp
uv sync
```

## Modelos

Los modelos no están en el repositorio. Se guardan en `models/` y el asistente comprueba su SHA-256 (definido en `src/asistente/config.py`) antes de cargarlos.

- Whisper: `ggml-small.bin` de [ggerganov/whisper.cpp](https://huggingface.co/ggerganov/whisper.cpp)
- Kokoro: `kokoro-v1.0.onnx` y `voices-v1.0.bin` de [thewh1teagle/kokoro-onnx](https://github.com/thewh1teagle/kokoro-onnx/releases/tag/model-files-v1.0)
- Activación: `uv run python -c "from openwakeword.utils import download_models; download_models(model_names=['hey_jarvis'])"`

## Uso

Ejecútalo desde **Terminal.app** (otros terminales integrados pueden no tener permiso de micrófono y reciben silencio). Pon el volumen de entrada de macOS al máximo.

```bash
uv run asistente
```

Otros comandos: `hablar`, `transcribir`, `diagnosticar`, `microfono` y `voces`.

## Conversación

Di «Hey Járvis»; tras un tintineo ya escucha. Después puedes seguir hablando sin repetir la activación: espera tu siguiente frase unos 7 segundos y, si hay silencio, la conversación termina y la esfera se desvanece.

- **Órdenes directas, en local:** «abre Safari», «cierra Spotify» (pide confirmación), «sube el volumen», «pon el volumen al 40», «silencia», «qué hora es».
- **Todo lo demás lo conversa Claude**, que además puede usar las herramientas del Mac (siempre con sus permisos y confirmaciones), de modo que entiende frases libres como «ponme el sonido un poco más bajo».
- **Permiso de nube:** se pregunta una vez al empezar cada conversación («¿Puedo consultar a Claude…?»). «No uses Claude» lo revoca y «usa Claude» lo devuelve. `APROBACION_NUBE` en `config.py` admite `siempre`, `conversacion` o `nunca`. Al terminar la conversación se olvida lo hablado y el permiso.
- **Cerrar:** «adiós», «hasta luego» o «eso es todo» terminan la conversación; «apágate» cierra el asistente.
- **Rapidez:** Claude responde en streaming y la voz empieza por la primera frase mientras se sintetizan las siguientes.

## Memoria

Jarvis recuerda lo que le pidas entre sesiones. Todo queda en un solo archivo cifrado, `data/memoria.enc` (Fernet: AES más firma HMAC, con la librería `cryptography`), escrito de forma atómica y con permisos 600. La clave se crea la primera vez y vive en el Keychain de macOS (servicio `asistente-memoria`); si se pierde, la memoria no se puede recuperar. Un archivo que no se puede descifrar nunca se sobrescribe.

- **Anotar:** «recuerda que mi hermana se llama Ana», «anota que…», «acuérdate de que…». También puede anotar Claude cuando se lo pides en una frase libre.
- **Consultar:** «¿qué recuerdas de mí?».
- **Borrar:** «olvida lo de mi hermana» y «olvida todo»; ambos piden confirmación y dicen cuántos recuerdos borrarán.
- **Qué sale del equipo:** lo anotado solo viaja a Claude cuando hablas con él, después de tu permiso de la conversación, y el aviso lo dice («…y lo que tengo anotado sobre usted»). `MEMORIA_A_NUBE = False` en `src/asistente/config.py` lo mantiene siempre en local.
- **Auditoría:** el registro guarda que se anotó o se borró algo y su tamaño, nunca el texto.
- Límites: 200 recuerdos de hasta 200 caracteres.

## Más herramientas del Mac

Todas con su permiso en `PERMISOS` y su registro de auditoría.

- **Temporizadores y avisos:** «pon un temporizador de diez minutos», «avísame en media hora que saque la pizza», «¿cuánto falta?», «cancela el temporizador». Cuando vencen, Jarvis suena y lo dice en voz alta, aunque no estés en conversación.
- **Música:** «pausa la música», «pon música», «siguiente canción», «¿qué suena?». Controla Spotify si está abierto y, si no, la app Música. La primera vez macOS pide permiso de Automatización.
- **Batería:** «¿cuánta batería tengo?».
- **Archivos (solo lectura):** «busca el archivo informe», «abre el archivo ideas». Solo ve las carpetas de `ARCHIVOS_CARPETAS` (Documentos, Descargas y Escritorio; macOS pedirá permiso de acceso la primera vez). Se ignoran los ocultos y los enlaces que apuntan fuera, y solo se abren documentos: nunca aplicaciones, scripts ni instaladores. Claude puede además leer archivos de texto, siempre tras una confirmación hablada porque su contenido le llega a él.
- **Contenido externo = solo mirar:** cuando Claude ha leído un archivo, durante el resto de la conversación solo puede buscar o leer; no puede cambiar el volumen, anotar recuerdos ni abrir aplicaciones por su cuenta, porque el archivo podría traer instrucciones escondidas. Tu propia voz sigue mandando con normalidad.

## Búsqueda web

Jarvis puede consultar internet («¿cómo va el dólar?», «¿qué tiempo hará mañana?»), pero **nunca navega desde tu Mac**: la búsqueda la ejecuta Anthropic en sus servidores (herramienta `web_search` de la API de Claude) y a tu equipo solo llega el texto de la respuesta. Así no hay navegador local, ni cookies, ni sesiones iniciadas, ni acceso a tu red; el aislamiento es total por construcción.

- **Permiso:** va incluido en el de la conversación, y el aviso lo dice: «…que además puede buscar en internet». «No busques en internet» lo revoca en esa conversación y «ya puedes buscar en internet» lo devuelve.
- **Aviso mientras busca:** «Un momento, lo busco en internet», porque la búsqueda tarda unos segundos (la primera frase de la respuesta llega a los ~5 s).
- **Contenido externo = solo mirar:** lo que traen las páginas se trata como dato, nunca como orden. Tras una búsqueda Claude no puede cambiar el volumen, anotar recuerdos ni abrir apps por su cuenta durante esa conversación (tu propia voz sigue mandando), y las respuestas basadas en la web quedan anotadas en el historial para que Claude no dude de ellas después.
- **Coste:** unos 0,01 US$ por búsqueda más los tokens de los resultados; máximo 2 búsquedas por respuesta (`WEB_BUSQUEDAS_MAX`).
- **Ajustes en `src/asistente/config.py`:** `WEB_BUSQUEDA = False` la desactiva; `WEB_UBICACION` fija tu ciudad para resultados locales (por ejemplo el tiempo). También sirve decirle a Jarvis «recuerda que vivo en…».
- **Límites:** busca y lee resultados; no abre una URL concreta, no hace clic ni inicia sesión en sitios.

## Modo privado (modelo local)

Para conversar sin que nada salga del equipo, Jarvis puede usar un modelo pequeño que corre en tu Mac: Qwen2.5-1.5B-Instruct (cuantizado Q4_K_M, 1,12 GB, licencia Apache 2.0) con `llama.cpp`.

- **Cuándo se usa:** si dices «habla en privado» o «modo privado» (se sale con «sal del modo privado»); si respondes que no a la consulta a Claude (esa misma pregunta se contesta en privado); y si no hay clave de Claude.
- **Bajo demanda:** el servidor (`llama-server`) solo existe durante la conversación y se cierra al terminar. Un guardián (`asistente.vigilante`) lo apaga también si el asistente muere de golpe. Mientras corre ocupa ~1,3 GB de RAM, así que en un Mac de 8 GB la primera respuesta puede tardar unos segundos.
- **Seguridad:** el servidor escucha en un socket Unix dentro de una carpeta privada (0700) con clave en un archivo 0600, no en la red; el SHA-256 del modelo se verifica antes de cargarlo. Lo hablado en privado tiene su propio historial y nunca viaja a Claude. Los recuerdos de la memoria sí se usan, porque aquí no salen del equipo.
- **Límites, sin adornos:** es rápido (primer token en menos de medio segundo) pero poco fiable con los hechos: se equivoca en cuentas, inventa datos y cuenta mal los chistes. No tiene herramientas, ni búsqueda web, ni archivos. Úsalo para charlar y para temas privados, no para decidir con cifras.
- **Instalación del modelo:** el archivo va en `models/` (fuera de git):

```bash
curl -L -o models/qwen2.5-1.5b-instruct-q4_k_m.gguf https://huggingface.co/Qwen/Qwen2.5-1.5B-Instruct-GGUF/resolve/main/qwen2.5-1.5b-instruct-q4_k_m.gguf
```

Con `LOCAL_ACTIVO = False` en `src/asistente/config.py` se desactiva. Requiere `brew install llama.cpp`.

## Esfera

Una esfera translúcida y flotante vive arriba a la derecha desde que arranca el asistente: tenue y tranquila mientras espera, y más viva e intensa al activarse (escuchando, pensando, hablando). Así siempre se ve que Jarvis está en marcha, sin esperar a que se detecte «Hey Járvis». Es una ventana de AppKit sin bordes ni fondo, que no recibe clics ni roba el foco, y corre en un proceso aparte que se cierra con el asistente. En espera gasta ~5 % de un núcleo. `ESFERA_SIEMPRE_VISIBLE = False` en `src/asistente/config.py` hace que solo aparezca durante la conversación, y `ESFERA_ACTIVA = False` la desactiva. Para dibujarla se usa `pyobjc-framework-Cocoa`.

## Herramientas y permisos

Cada herramienta tiene un permiso en `PERMISOS` (`src/asistente/config.py`): `libre`, `confirmar` (pide un «sí» hablado) o `desactivada`. Las órdenes se reconocen en local con patrones explícitos, nunca las decide Claude, y las aplicaciones se resuelven contra las instaladas. Antes de ejecutar se escribe un registro en `data/auditoria.jsonl` (solo legible por el usuario, fuera de git); si no se puede escribir, la acción no se ejecuta.

## Seguridad

- Dependencias fijadas con hash en `uv.lock` y auditadas con `pip-audit`.
- El audio solo existe en un directorio temporal privado mientras se procesa y se borra al terminar.
- Los ejecutables del sistema se llaman por ruta absoluta y sin shell.

## Desarrollo

```bash
uv run pytest
uv run ruff check .
uv run pip-audit
```
