from . import config
from .audio import Microfono, grabar_frase, rms
from .stt import transcribir
from .tts import hablar
from .wake import PalabraActivacion


def responder(texto: str) -> str:
    # Fase 1: solo repite lo entendido. En la Fase 2 aquí entra el cerebro.
    return f"Escuché: {texto}"


def ejecutar() -> None:
    activacion = PalabraActivacion()
    with Microfono() as mic:
        hablar("Sistemas en línea.")
        mic.vaciar()
        print("Escuchando. Di «Hey Jarvis». Ctrl+C para salir.")
        frames = 0
        cambios = mic.cambios
        while True:
            frame = mic.leer()
            if mic.cambios != cambios:
                cambios = mic.cambios
                activacion.reiniciar()  # el audio previo era de otro micrófono
            puntaje = activacion.puntaje(frame)
            frames += 1
            if frames % 4 == 0:
                # Medidor en vivo: nivel 0 constante significa que el micrófono no llega.
                print(f"\r  nivel {rms(frame):6.0f}   activación {puntaje:.2f} / {config.UMBRAL_ACTIVACION}  ", end="", flush=True)
            if puntaje < config.UMBRAL_ACTIVACION:
                continue

            print()
            hablar("Dígame.")
            mic.vaciar()
            activacion.reiniciar()

            audio = grabar_frase(mic)
            if audio is None:
                continue

            texto = transcribir(audio)
            if not texto:
                continue
            print(f"> {texto}")
            hablar(responder(texto))
            mic.vaciar()
            activacion.reiniciar()
