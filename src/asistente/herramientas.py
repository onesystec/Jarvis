import difflib
import re
import subprocess
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from . import archivos, auditoria, config, sistema
from .memoria import Memoria, MemoriaError, interpretar_memoria
from .reglas import normalizar
from .temporizadores import Temporizadores, describir, interpretar_temporizador

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
    dicho = normalizar(nombre)
    objetivo = normalizar(_ALIAS.get(dicho, nombre))
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
    if len(parecidas) == 1:
        return parecidas[0]
    # El reconocimiento de voz se equivoca con los nombres («canculadora»): se acepta lo muy parecido.
    # Los alias en español cuentan como nombres posibles. Para cerrar apps se pide confirmación igualmente.
    conocidos = {**{clave: real for clave, real in instaladas.items()}}
    for alias, ingles in _ALIAS.items():
        if normalizar(ingles) in instaladas:
            conocidos.setdefault(alias, instaladas[normalizar(ingles)])
    cercanos = difflib.get_close_matches(dicho, list(conocidos), n=1, cutoff=0.8)
    return conocidos[cercanos[0]] if cercanos else None


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


_EJECUTORES: dict[str, Callable] = {
    "abrir_app": abrir_app,
    "cerrar_app": cerrar_app,
    "volumen": volumen,
    "musica": sistema.musica,
    "bateria": sistema.bateria,
}
_HERRAMIENTAS_DE_MEMORIA = ("recordar", "olvidar", "olvidar_todo", "recuerdos")
_SIN_MEMORIA = "La memoria no está disponible, señor."


def interpretar_orden(texto: str) -> Orden | None:
    """Reconoce órdenes directas sobre el Mac. Solo patrones explícitos, nada de adivinar."""
    if (memoria := interpretar_memoria(texto)) is not None:
        return Orden(*memoria)
    t = normalizar(texto)
    if m := re.fullmatch(r"(?:jarvis )?(?:abre|abrir|abra|muestrame) (?:el |la |un |una )?(?:archivo|documento|fichero|pdf) (?:de |llamado |que se llama )?(.+)", t):
        return Orden("abrir_archivo", m[1])
    if m := re.fullmatch(r"(?:jarvis )?(?:busca|buscame|encuentra|encuentrame) (?:el |la |un |una )?(?:archivo|documento|fichero|pdf)s? (?:de |llamado |que se llama )?(.+)", t):
        return Orden("buscar_archivos", m[1])
    if (temporizador := interpretar_temporizador(texto)) is not None:
        return Orden(*temporizador)
    if (de_sistema := sistema.interpretar_sistema(t)) is not None:
        return Orden(*de_sistema)
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


def _texto_entre(entrada: dict, campo: str, minimo: int, maximo: int) -> str | None:
    valor = entrada.get(campo)
    if isinstance(valor, str) and minimo <= len(valor.strip()) <= maximo:
        return valor.strip()
    return None


def orden_desde_claude(nombre: str, entrada: object) -> Orden | None:
    """Convierte una petición de herramienta de Claude en una Orden, validando todo: viene de un modelo."""
    if not isinstance(entrada, dict):
        return None
    if nombre in ("abrir_app", "cerrar_app"):
        app = _texto_entre(entrada, "nombre", 1, 60)
        return Orden(nombre, app) if app else None
    if nombre == "recordar":
        hecho = _texto_entre(entrada, "texto", 3, config.MEMORIA_MAX_CARACTERES)
        return Orden(nombre, hecho) if hecho else None
    if nombre == "olvidar":
        tema = _texto_entre(entrada, "tema", 2, 100)
        return Orden(nombre, tema) if tema else None
    if nombre in ("abrir_archivo", "leer_archivo"):
        archivo = _texto_entre(entrada, "nombre", 1, 120)
        return Orden(nombre, archivo) if archivo else None
    if nombre == "buscar_archivos":
        consulta = _texto_entre(entrada, "consulta", 1, 120)
        return Orden(nombre, consulta) if consulta else None
    if nombre == "temporizador":
        segundos = entrada.get("segundos")
        etiqueta = entrada.get("etiqueta", "")
        if isinstance(segundos, int) and not isinstance(segundos, bool) and 1 <= segundos <= config.TEMPORIZADOR_MAX_S and isinstance(etiqueta, str):
            return Orden(nombre, (segundos, etiqueta.strip()[:100]))
        return None
    if nombre in ("cancelar_temporizador", "temporizadores", "bateria"):
        return Orden(nombre)
    if nombre == "musica":
        accion = entrada.get("accion")
        return Orden(nombre, accion) if accion in ("reproducir", "pausar", "siguiente", "anterior", "que_suena") else None
    if nombre == "volumen":
        accion = entrada.get("accion")
        if accion in ("subir", "bajar", "silenciar"):
            return Orden("volumen", accion)
        nivel = entrada.get("nivel")
        if accion == "fijar" and isinstance(nivel, int) and not isinstance(nivel, bool) and 0 <= nivel <= 100:
            return Orden("volumen", nivel)
    return None


def _plural(n: int) -> str:
    return f"{n} recuerdo" if n == 1 else f"{n} recuerdos"


class Herramientas:
    """Ejecuta órdenes respetando los permisos por herramienta y dejando rastro en la auditoría."""

    def __init__(
        self,
        permisos: dict[str, str] | None = None,
        auditar: Callable[..., None] = auditoria.registrar,
        ejecutores: dict[str, Callable] | None = None,
        buscar: Callable[[str], str | None] = buscar_app,
        memoria: Memoria | None = None,
        temporizadores: Temporizadores | None = None,
        carpetas: tuple[Path, ...] | None = None,
    ) -> None:
        self._permisos = permisos if permisos is not None else config.PERMISOS
        self._auditar = auditar
        self._memoria = memoria
        self.temporizadores = temporizadores if temporizadores is not None else Temporizadores()
        self._carpetas = carpetas
        self._ejecutores = (
            ejecutores
            if ejecutores is not None
            else {**_EJECUTORES, **self._ejecutores_de_memoria(), **self._ejecutores_de_temporizadores(), **self._ejecutores_de_archivos()}
        )
        self._buscar = buscar

    # --- memoria -----------------------------------------------------------------------------

    def _ejecutores_de_memoria(self) -> dict[str, Callable]:
        def recordar(texto: str) -> str:
            if self._memoria is None:
                return _SIN_MEMORIA
            try:
                return "Anotado, señor." if self._memoria.recordar(texto) else "Eso ya lo tenía anotado, señor."
            except MemoriaError as error:
                return str(error)

        def olvidar(tema: str) -> str:
            if self._memoria is None:
                return _SIN_MEMORIA
            return f"Listo, he olvidado {_plural(self._memoria.olvidar(tema))}, señor."

        def olvidar_todo(_argumento: None) -> str:
            if self._memoria is None:
                return _SIN_MEMORIA
            return f"Listo, he olvidado {_plural(self._memoria.olvidar_todo())}, señor."

        def recuerdos(_argumento: None) -> str:
            if self._memoria is None:
                return _SIN_MEMORIA
            hechos = [h.texto for h in self._memoria.hechos]
            if not hechos:
                return "No tengo nada anotado todavía, señor."
            recientes = hechos[-5:]
            resto = len(hechos) - len(recientes)
            texto = f"Tengo anotado: {'; '.join(recientes)}."
            return texto + (f" Y {resto} más." if resto else "")

        return {"recordar": recordar, "olvidar": olvidar, "olvidar_todo": olvidar_todo, "recuerdos": recuerdos}

    # --- temporizadores y archivos -------------------------------------------------------------

    def _ejecutores_de_temporizadores(self) -> dict[str, Callable]:
        def crear(argumento: tuple[int, str]) -> str:
            segundos, etiqueta = argumento
            try:
                self.temporizadores.crear(segundos, etiqueta)
            except ValueError:
                return "No puedo programar eso, señor."
            if etiqueta:
                return f"De acuerdo, le avisaré en {describir(segundos)}."
            return f"Temporizador de {describir(segundos)} en marcha."

        def cancelar(_argumento: None) -> str:
            n = self.temporizadores.cancelar()
            return "No hay temporizadores activos, señor." if n == 0 else f"Cancelado{'s' if n > 1 else ''}: {n} temporizador{'es' if n > 1 else ''}."

        def pendientes(_argumento: None) -> str:
            activos = self.temporizadores.pendientes()
            if not activos:
                return "No hay temporizadores activos, señor."
            return "; ".join(f"faltan {describir(restante)}" + (f" para {t.etiqueta}" if t.etiqueta else "") for t, restante in activos) + "."

        return {"temporizador": crear, "cancelar_temporizador": cancelar, "temporizadores": pendientes}

    def _ejecutores_de_archivos(self) -> dict[str, Callable]:
        def buscar(consulta: str) -> str:
            hallados = archivos.buscar(consulta, carpetas=self._carpetas)
            if not hallados:
                return "No encontré nada así en sus carpetas autorizadas, señor."
            return "Encontré: " + "; ".join(r.name for r in hallados) + "."

        def abrir(ruta: Path) -> str:
            _ejecutar([config.OPEN, str(ruta)])
            return f"Abriendo {ruta.name}."

        def leer(ruta: Path) -> str:
            try:
                return archivos.leer(ruta, self._carpetas)
            except PermissionError:
                return "Ese archivo no se puede leer, señor."

        return {"buscar_archivos": buscar, "abrir_archivo": abrir, "leer_archivo": leer}

    # --- ejecución ---------------------------------------------------------------------------

    @staticmethod
    def _para_auditoria(herramienta: str, argumento: object) -> object:
        """Lo que se escribe en el registro: de la memoria solo el tamaño, para no dejar lo anotado en claro."""
        if herramienta in ("recordar", "olvidar"):
            return f"<{len(str(argumento))} caracteres>"
        if isinstance(argumento, Path):
            return argumento.name  # nunca la ruta completa
        return argumento

    def _preparar(self, orden: Orden) -> tuple[object, str, tuple[str, str] | None]:
        """Resuelve el argumento real. Devuelve (argumento, pregunta de confirmación, (respuesta, decisión) si no procede)."""
        herramienta, argumento = orden.herramienta, orden.argumento
        if herramienta in ("abrir_app", "cerrar_app"):
            app = self._buscar(str(argumento))
            if app is None:
                return argumento, "", (f"No encuentro la aplicación {argumento}, señor.", "no_encontrada")
            if herramienta == "cerrar_app" and normalizar(app) in config.APPS_PROTEGIDAS:
                return app, "", (f"No puedo cerrar {app}, señor.", "bloqueada")
            return app, f"¿Confirma que cierre {app}?", None
        if herramienta in ("abrir_archivo", "leer_archivo"):
            extensiones = config.ARCHIVOS_EXT_ABRIR if herramienta == "abrir_archivo" else config.ARCHIVOS_EXT_LEER
            hallados = archivos.buscar(str(argumento), extensiones, self._carpetas)
            if not hallados:
                return argumento, "", ("No encuentro ese archivo en sus carpetas autorizadas, señor.", "no_encontrado")
            if len(hallados) > 1:
                return argumento, "", (f"Encontré varios: {', '.join(r.name for r in hallados[:4])}. Dígame cuál, señor.", "ambiguo")
            if herramienta == "leer_archivo":
                return hallados[0], f"¿Confirma que lea «{hallados[0].name}» y envíe su contenido a Claude?", None
            return hallados[0], "¿Lo hago?", None
        if herramienta == "olvidar" and self._memoria is not None:
            n = len(self._memoria.coincidencias(str(argumento)))
            if n == 0:
                return argumento, "", ("No tengo nada anotado sobre eso, señor.", "no_procede")
            return argumento, f"¿Confirma que olvide {_plural(n)} sobre «{argumento}»?", None
        if herramienta == "olvidar_todo" and self._memoria is not None:
            n = len(self._memoria.hechos)
            if n == 0:
                return argumento, "", ("No tengo nada anotado, señor.", "no_procede")
            return argumento, f"¿Confirma que olvide los {_plural(n)} que tengo sobre usted?", None
        return argumento, "¿Lo hago?", None

    def ejecutar(self, orden: Orden, confirmar: Callable[[str], bool]) -> str:
        herramienta = orden.herramienta
        nivel = self._permisos.get(herramienta, "desactivada")
        if nivel not in ("libre", "confirmar"):
            self._auditar(herramienta=herramienta, argumento=self._para_auditoria(herramienta, orden.argumento), decision="desactivada")
            return "Esa función está desactivada, señor."

        argumento, pregunta, rechazo = self._preparar(orden)
        visible = self._para_auditoria(herramienta, argumento)
        if rechazo is not None:
            respuesta, decision = rechazo
            self._auditar(herramienta=herramienta, argumento=visible, decision=decision)
            return respuesta

        decision = "libre"
        if nivel == "confirmar":
            aprobada = confirmar(pregunta)
            decision = "aprobada" if aprobada else "rechazada"
            if not aprobada:
                self._auditar(herramienta=herramienta, argumento=visible, decision=decision)
                return "Entendido, no lo hago."

        # Se audita antes de actuar: si el registro falla, la acción no se ejecuta.
        self._auditar(herramienta=herramienta, argumento=visible, decision=decision)
        try:
            resultado = self._ejecutores[herramienta](argumento)
        except (subprocess.SubprocessError, OSError):
            self._auditar(herramienta=herramienta, argumento=visible, resultado="error")
            return "No pude completar la acción, señor."
        self._auditar(herramienta=herramienta, argumento=visible, resultado="ok")
        return resultado
