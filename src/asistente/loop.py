from .audio import Microfono, grabar_frase
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
        while True:
            if not activacion.detectada(mic.leer()):
                continue

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
