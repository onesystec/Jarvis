import re
import unicodedata
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime

_DIAS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
_MESES = [
    "enero", "febrero", "marzo", "abril", "mayo", "junio",
    "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
]

_AFIRMATIVAS = {"si", "claro", "adelante", "dale", "ok", "vale", "envialo", "hazlo", "correcto", "afirmativo"}
_NEGATIVAS = {"no", "cancela", "cancelalo", "espera", "nada", "negativo", "detente", "mejor"}


@dataclass
class Respuesta:
    texto: str
    salir: bool = False  # apagar el asistente
    fin: bool = False  # terminar la conversación (vuelve a esperar «Hey Jarvis»)
    frases: Iterable[str] | None = None  # respuesta que llega por partes y se va diciendo


def normalizar(texto: str) -> str:
    sin_tildes = "".join(
        c for c in unicodedata.normalize("NFD", texto.lower()) if unicodedata.category(c) != "Mn"
    )
    return " ".join(re.sub(r"[^a-z0-9ñ ]", " ", sin_tildes).split())


def es_afirmativo(texto: str) -> bool:
    palabras = set(normalizar(texto).split())
    return bool(palabras & _AFIRMATIVAS) and not (palabras & _NEGATIVAS)


def pide_revocar_nube(texto: str) -> bool:
    return bool(re.search(r"\b(no uses|no uses a|deja de usar|sin) claude\b", normalizar(texto)))


def pide_permitir_nube(texto: str) -> bool:
    return bool(re.search(r"\b(usa|puedes usar|ya puedes usar|activa) claude\b", normalizar(texto)))


def interpretar(texto: str, ahora: datetime | None = None) -> Respuesta | None:
    """Resuelve en local lo simple. Devuelve None si no hay regla que lo cubra."""
    ahora = ahora or datetime.now()
    t = normalizar(texto)

    if re.search(r"\b(apagate|apaga jarvis|desactivate|cierrate)\b", t):
        return Respuesta("Apagando sistemas, señor.", salir=True, fin=True)
    if re.search(r"\b(adios|hasta luego|hasta pronto|descansa|chao)\b", t) or re.fullmatch(
        r"(eso es todo|es todo|nada mas|ya es todo)( gracias)?( jarvis)?", t
    ):
        return Respuesta("Hasta luego, señor.", fin=True)
    if re.search(r"\bque hora es\b|\bdime la hora\b|\bla hora\b", t):
        prefijo = "Es la" if ahora.hour % 12 == 1 else "Son las"
        hora = ahora.hour % 12 or 12
        minutos = "en punto" if ahora.minute == 0 else f"y {ahora.minute}"
        return Respuesta(f"{prefijo} {hora} {minutos}.")
    if re.search(r"\bque dia es\b|\bque fecha es\b|\bfecha de hoy\b|\bque dia es hoy\b", t):
        return Respuesta(
            f"Hoy es {_DIAS[ahora.weekday()]} {ahora.day} de {_MESES[ahora.month - 1]} de {ahora.year}."
        )
    if re.fullmatch(r"(muchas )?gracias( jarvis)?", t):
        return Respuesta("A su servicio, señor.")
    return None
