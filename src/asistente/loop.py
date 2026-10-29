import subprocess

from . import config
from .audio import Microfono, grabar_frase, rms
from .cerebro import Cerebro
from .esfera import Esfera
from .nube import ClienteClaude
from .reglas import es_afirmativo
from .secretos import obtener_clave
from .stt import transcribir
from .tts import hablar, hablar_frases
from .wake import PalabraActivacion

_ERRORES_DE_TURNO = (subprocess.SubprocessError, OSError, RuntimeError)


def _crear_nube():
    clave = obtener_clave()
    return ClienteClaude(clave) if clave else None


def _escuchar(mic, esfera: Esfera, espera_max_s: float = config.ESPERA_MAX_S) -> str:
    esfera.estado("escuchando")
    audio = grabar_frase(mic, espera_max_s)
    esfera.estado("pensando")
    return transcribir(audio) if audio is not None else ""


def _sonido_activacion() -> None:
    """Tintineo breve: avisa de que ya escucha, sin esperar a sintetizar una voz."""
    subprocess.run(
        [config.AFPLAY, "-t", str(config.SONIDO_DURACION_S), config.SONIDO_ACTIVACION], check=False, timeout=10
    )


def _conversar(mic, esfera: Esfera, cerebro: Cerebro) -> bool:
    """Atiende turnos seguidos sin pedir de nuevo «Hey Jarvis». True si hay que apagar el asistente."""
    cerebro.nueva_conversacion()
    esfera.estado("escuchando")
    _sonido_activacion()
    mic.vaciar()
    espera = config.ESPERA_MAX_S
    while True:
        try:
            texto = _escuchar(mic, esfera, espera)
            if len(texto) < 2:
                return False  # silencio: la conversación terminó
            print(f"> {texto}")
            respuesta = cerebro.pensar(texto)
            frases = respuesta.frases if respuesta.frases is not None else [respuesta.texto]
            dicho = hablar_frases(frases, al_decir=lambda: esfera.estado("hablando"))
            print(f"< {' '.join(dicho)}")
        except _ERRORES_DE_TURNO as error:
            # Un fallo en un turno no debe tumbar al asistente.
            print(f"  Error en el turno: {error}")
            return False
        if respuesta.salir:
            return True
        if respuesta.fin:
            return False
        mic.vaciar()  # lo que se oyó mientras hablaba era el propio asistente
        espera = config.CONVERSACION_ESPERA_S


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
        print("Escuchando. Di «Hey Jarvis» y habla; seguiré escuchando entre respuestas. «Adiós» termina la conversación y «apágate» cierra el asistente.")
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
            apagar = _conversar(mic, esfera, cerebro)
            esfera.estado("reposo")
            if apagar:
                return
            mic.vaciar()
            activacion.reiniciar()
