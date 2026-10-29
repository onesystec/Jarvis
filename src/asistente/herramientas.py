import re
import subprocess
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from . import auditoria, config
from .reglas import normalizar

_ALIAS = {
    "calendario": "Calendar",
    "notas": "Notes",
    "mensajes": "Messages",
    "musica": "Music",
    "ajustes": "System Settings",
    "ajustes del sistema": "System Settings",
    "configuracion": "System Settings",
    "calculadora": "Calculator",
    "correo": "Mail",
    "fotos": "Photos",
    "mapas": "Maps",
    "recordatorios": "Reminders",
    "reloj": "Clock",
}


@dataclass(frozen=True)
class Orden:
    herramienta: str
    argumento: str | int | None = None


def buscar_app(nombre: str, carpetas: tuple[Path, ...] | None = None) -> str | None:
    """Resuelve lo que dijo el usuario a una aplicación instalada (nombre exacto del disco)."""
    objetivo = normalizar(_ALIAS.get(normalizar(nombre), nombre))
    if not objetivo:
        return None
    instaladas: dict[str, str] = {}
    for carpeta in carpetas or config.CARPETAS_APPS:
        try:
            entradas = list(carpeta.iterdir())
        except OSError:
            continue
        for entrada in entradas:
            if entrada.suffix == ".app" and not entrada.stem.startswith("-"):
                instaladas.setdefault(normalizar(entrada.stem), entrada.stem)
    if objetivo in instaladas:
        return instaladas[objetivo]
    parecidas = [real for clave, real in instaladas.items() if clave.startswith(objetivo)]
    return parecidas[0] if len(parecidas) == 1 else None


def _ejecutar(argumentos: list[str]) -> str:
    return subprocess.run(argumentos, check=True, capture_output=True, text=True, timeout=15).stdout


def abrir_app(nombre: str) -> str:
    _ejecutar([config.OPEN, "-a", nombre])
    return f"Abriendo {nombre}."


def cerrar_app(nombre: str) -> str:
    # El nombre viaja como argumento de AppleScript, nunca dentro del código.
    _ejecutar([config.OSASCRIPT, "-e", "on run argv", "-e", "tell application (item 1 of argv) to quit", "-e", "end run", nombre])
    return f"Cerrando {nombre}."


def _volumen_actual() -> int | None:
    try:
        return int(_ejecutar([config.OSASCRIPT, "-e", "output volume of (get volume settings)"]).strip())
    except ValueError:  # algunas salidas (HDMI...) no tienen volumen
        return None


def _fijar_volumen(nivel: int) -> None:
    _ejecutar([config.OSASCRIPT, "-e", f"set volume output volume {int(nivel)}"])


def volumen(
    accion: str | int,
    actual: Callable[[], int | None] = _volumen_actual,
    fijar: Callable[[int], None] = _fijar_volumen,
) -> str:
    if accion == "silenciar":
        _ejecutar([config.OSASCRIPT, "-e", "set volume output muted true"])
        return "Silenciado."
    if isinstance(accion, int):
        nuevo = accion
    else:
        base = actual()
        if base is None:
            return "No puedo leer el volumen de esta salida de audio, señor."
        nuevo = base + (config.PASO_VOLUMEN if accion == "subir" else -config.PASO_VOLUMEN)
    nuevo = max(0, min(100, nuevo))
    fijar(nuevo)
    return f"Volumen al {nuevo} por ciento."


_EJECUTORES: dict[str, Callable] = {"abrir_app": abrir_app, "cerrar_app": cerrar_app, "volumen": volumen}


def interpretar_orden(texto: str) -> Orden | None:
    """Reconoce órdenes directas sobre el Mac. Solo patrones explícitos, nada de adivinar."""
    t = normalizar(texto)
    articulo = r"(?: la aplicacion| el programa| la app| el| la)?"
    if m := re.fullmatch(rf"(?:jarvis )?(?:abre|abrir|abra|inicia|lanza){articulo} (.+)", t):
        return Orden("abrir_app", m[1])
    if m := re.fullmatch(rf"(?:jarvis )?(?:cierra|cerrar|cierre|termina){articulo} (.+)", t):
        return Orden("cerrar_app", m[1])
    if re.search(r"\b(silencia|silenciar|mutea|mutear)\b|\bquita el sonido\b", t):
        return Orden("volumen", "silenciar")
    if "volumen" in t:
        if m := re.search(r"\b(\d{1,3})\b", t):
            return Orden("volumen", min(int(m[1]), 100))
        if re.search(r"\b(sube|subir|aumenta|aumentar|mas)\b", t):
            return Orden("volumen", "subir")
        if re.search(r"\b(baja|bajar|disminuye|reduce|menos)\b", t):
            return Orden("volumen", "bajar")
    return None


class Herramientas:
    """Ejecuta órdenes respetando los permisos por herramienta y dejando rastro en la auditoría."""

    def __init__(
        self,
        permisos: dict[str, str] | None = None,
        auditar: Callable[..., None] = auditoria.registrar,
        ejecutores: dict[str, Callable] | None = None,
        buscar: Callable[[str], str | None] = buscar_app,
    ) -> None:
        self._permisos = permisos if permisos is not None else config.PERMISOS
        self._auditar = auditar
        self._ejecutores = ejecutores if ejecutores is not None else _EJECUTORES
        self._buscar = buscar

    def ejecutar(self, orden: Orden, confirmar: Callable[[str], bool]) -> str:
        nivel = self._permisos.get(orden.herramienta, "desactivada")
        if nivel not in ("libre", "confirmar"):
            self._auditar(herramienta=orden.herramienta, argumento=orden.argumento, decision="desactivada")
            return "Esa función está desactivada, señor."

        argumento = orden.argumento
        if orden.herramienta in ("abrir_app", "cerrar_app"):
            argumento = self._buscar(str(orden.argumento))
            if argumento is None:
                self._auditar(herramienta=orden.herramienta, argumento=orden.argumento, decision="no_encontrada")
                return f"No encuentro la aplicación {orden.argumento}, señor."
            if orden.herramienta == "cerrar_app" and normalizar(argumento) in config.APPS_PROTEGIDAS:
                self._auditar(herramienta=orden.herramienta, argumento=argumento, decision="bloqueada")
                return f"No puedo cerrar {argumento}, señor."

        decision = "libre"
        if nivel == "confirmar":
            aprobada = confirmar(f"¿Confirma que cierre {argumento}?" if orden.herramienta == "cerrar_app" else "¿Lo hago?")
            decision = "aprobada" if aprobada else "rechazada"
            if not aprobada:
                self._auditar(herramienta=orden.herramienta, argumento=argumento, decision=decision)
                return "Entendido, no lo hago."

        # Se audita antes de actuar: si el registro falla, la acción no se ejecuta.
        self._auditar(herramienta=orden.herramienta, argumento=argumento, decision=decision)
        try:
            resultado = self._ejecutores[orden.herramienta](argumento)
        except (subprocess.SubprocessError, OSError):
            self._auditar(herramienta=orden.herramienta, argumento=argumento, resultado="error")
            return "No pude completar la acción, señor."
        self._auditar(herramienta=orden.herramienta, argumento=argumento, resultado="ok")
        return resultado
