import re
import subprocess

from . import config


def ejecutar_comando(argumentos: list[str]) -> str:
    return subprocess.run(argumentos, check=True, capture_output=True, text=True, timeout=15).stdout


def _app_de_musica() -> str:
    """Spotify si está abierto; si no, la app Música de macOS."""
    abierto = subprocess.run([config.PGREP, "-x", "Spotify"], capture_output=True, check=False, timeout=5)
    return "Spotify" if abierto.returncode == 0 else "Music"


_ORDENES_MUSICA = {
    "reproducir": ("play", "Reproduciendo."),
    "pausar": ("pause", "Música en pausa."),
    "siguiente": ("next track", "Siguiente canción."),
    "anterior": ("previous track", "Canción anterior."),
}


def musica(accion: str) -> str:
    app = _app_de_musica()  # solo dos nombres fijos: nada del usuario entra en el script
    try:
        if accion == "que_suena":
            pista = ejecutar_comando(
                [config.OSASCRIPT, "-e", f'tell application "{app}" to (name of current track) & "|" & (artist of current track)']
            ).strip()
            titulo, _, artista = pista.partition("|")
            return f"Suena {titulo}, de {artista}." if artista else f"Suena {titulo}."
        if accion not in _ORDENES_MUSICA:
            return "No entendí qué hacer con la música, señor."
        comando, respuesta = _ORDENES_MUSICA[accion]
        ejecutar_comando([config.OSASCRIPT, "-e", f'tell application "{app}" to {comando}'])
        return respuesta
    except subprocess.CalledProcessError as error:
        if "-1743" in (error.stderr or ""):
            return (
                "Necesito permiso para controlar la música, señor. "
                "Puede darlo en Ajustes del Sistema, Privacidad y seguridad, Automatización."
            )
        return "No hay nada sonando ahora mismo, señor." if accion == "que_suena" else "No pude controlar la música, señor."


_BATERIA = re.compile(r"(\d+)%;\s*([^;]+);\s*(?:(\d+):(\d{2}) remaining)?")


def bateria(_argumento: object = None) -> str:
    salida = ejecutar_comando([config.PMSET, "-g", "batt"])
    m = _BATERIA.search(salida)
    if not m:
        return "Este equipo no tiene batería, señor."
    nivel, estado = m[1], m[2].strip()
    if estado in ("charging", "finishing charge"):
        return f"Tiene {nivel} por ciento de batería y se está cargando."
    if estado in ("charged", "AC attached"):
        return f"Tiene {nivel} por ciento de batería y está conectado a la corriente."
    restante = ""
    if m[3] is not None and (int(m[3]) or int(m[4])):
        restante = f"; quedan unas {int(m[3])} horas y {int(m[4])} minutos" if int(m[3]) else f"; quedan unos {int(m[4])} minutos"
    return f"Tiene {nivel} por ciento de batería y no está cargando{restante}."


def interpretar_sistema(t: str) -> tuple[str, object] | None:
    """Órdenes de voz de música y batería sobre el texto ya normalizado."""
    if re.search(r"\b(que|cual) (suena|cancion es|esta sonando)\b|\bque estoy escuchando\b", t):
        return "musica", "que_suena"
    if re.search(r"\b(siguiente|proxima) (cancion|tema|pista)\b|\bpasa (de|a la siguiente)\b|\bsalta (la|esta) (cancion|pista)\b", t):
        return "musica", "siguiente"
    if re.search(r"\b(cancion|tema|pista) (anterior|de antes)\b|\bvuelve a la anterior\b", t):
        return "musica", "anterior"
    if re.search(r"\b(pausa|pausar|deten|detener|para|parar)\b.*\b(musica|cancion|reproduccion)\b|\b(pausa|pausar)\b", t):
        return "musica", "pausar"
    if re.search(r"\b(pon|reproduce|reanuda|continua|continuar|activa)\b.*\b(musica|cancion)\b|\bdale play\b", t):
        return "musica", "reproducir"
    if re.search(r"\bbateria\b", t):
        return "bateria", None
    return None
