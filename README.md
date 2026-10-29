# Jarvis

Asistente de voz local-first para macOS, inspirado en JARVIS. Todo el audio se procesa en el equipo.

## Estado

En desarrollo. Hecho: palabra de activación, transcripción local, voz de salida, micrófono que sigue al dispositivo predeterminado (AirPods o micrófono del Mac), cerebro híbrido (reglas locales y Claude con aprobación hablada) y primeras herramientas del Mac con permisos y auditoría. Pendiente: memoria cifrada, modelo local y navegador aislado.

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
brew install uv whisper-cpp portaudio
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
