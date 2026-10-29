import re
import unicodedata
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
    salir: bool = False


def normalizar(texto: str) -> str:
    sin_tildes = "".join(
        c for c in unicodedata.normalize("NFD", texto.lower()) if unicodedata.category(c) != "Mn"
    )
    return " ".join(re.sub(r"[^a-z0-9ñ ]", " ", sin_tildes).split())


def es_afirmativo(texto: str) -> bool:
    palabras = set(normalizar(texto).split())
    return bool(palabras & _AFIRMATIVAS) and not (palabras & _NEGATIVAS)


def interpretar(texto: str, ahora: datetime | None = None) -> Respuesta | None:
    """Resuelve en local lo simple. Devuelve None si no hay regla que lo cubra."""
    ahora = ahora or datetime.now()
    t = normalizar(texto)

    if re.search(r"\b(adios|hasta luego|apagate|descansa|hasta pronto)\b", t):
        return Respuesta("Hasta luego, señor.", salir=True)
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
