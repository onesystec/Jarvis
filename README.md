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

Tras «Hey Járvis» y el «Dígame», órdenes directas: «abre Safari», «cierra Spotify» (pide confirmación), «sube el volumen», «pon el volumen al 40», «silencia», «qué hora es» y «adiós» para cerrar. Lo demás se consulta a Claude solo si lo apruebas.

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
