import subprocess

from . import config
from .audio import Microfono, grabar_frase, rms
from .cerebro import Cerebro
from .esfera import Esfera
from .nube import ClienteClaude
from .reglas import es_afirmativo
from .secretos import obtener_clave
from .stt import transcribir
from .tts import hablar
from .wake import PalabraActivacion


def _crear_nube():
    clave = obtener_clave()
    return ClienteClaude(clave) if clave else None


def _escuchar(mic, esfera: Esfera) -> str:
    esfera.estado("escuchando")
    audio = grabar_frase(mic)
    esfera.estado("pensando")
    return transcribir(audio) if audio is not None else ""


def ejecutar() -> None:
    with Esfera(config.ESFERA_ACTIVA) as esfera:
        _bucle(esfera)


def _bucle(esfera: Esfera) -> None:
    activacion = PalabraActivacion()
    nube = _crear_nube()
    with Microfono() as mic:

        def confirmar(pregunta: str) -> bool:
            esfera.estado("hablando")
            hablar(pregunta)
            mic.vaciar()
            return es_afirmativo(_escuchar(mic, esfera))

        cerebro = Cerebro(nube, confirmar)
        hablar("Sistemas en línea.")
        mic.vaciar()
        print("Claude: " + ("conectado" if nube else "sin clave (solo reglas locales)"))
        print("Escuchando. Di «Hey Jarvis» y, tras el «Dígame», una orden; «adiós» para cerrar. Ctrl+C también sale.")
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
            esfera.estado("escuchando")
            try:
                hablar("Dígame.")
                mic.vaciar()
                activacion.reiniciar()
                texto = _escuchar(mic, esfera)
                if texto:
                    print(f"> {texto}")
                    respuesta = cerebro.pensar(texto)
                    print(f"< {respuesta.texto}")
                    esfera.estado("hablando")
                    hablar(respuesta.texto)
                    if respuesta.salir:
                        return
            except (subprocess.SubprocessError, OSError, RuntimeError) as error:
                # Un fallo en un turno no debe tumbar al asistente.
                print(f"  Error en el turno: {error}")
            esfera.estado("reposo")
            mic.vaciar()
            activacion.reiniciar()
