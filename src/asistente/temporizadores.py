import re
import time
from collections.abc import Callable
from dataclasses import dataclass

from . import config
from .reglas import normalizar

_UNIDADES = {
    "cero": 0, "un": 1, "uno": 1, "una": 1, "dos": 2, "tres": 3, "cuatro": 4, "cinco": 5, "seis": 6, "siete": 7,
    "ocho": 8, "nueve": 9, "diez": 10, "once": 11, "doce": 12, "trece": 13, "catorce": 14, "quince": 15,
    "dieciseis": 16, "diecisiete": 17, "dieciocho": 18, "diecinueve": 19, "veinte": 20, "veintiun": 21,
    "veintiuno": 21, "veintiuna": 21, "veintidos": 22, "veintitres": 23, "veinticuatro": 24, "veinticinco": 25,
    "veintiseis": 26, "veintisiete": 27, "veintiocho": 28, "veintinueve": 29,
}  # fmt: skip
_DECENAS = {"treinta": 30, "cuarenta": 40, "cincuenta": 50, "sesenta": 60, "setenta": 70, "ochenta": 80, "noventa": 90}
_FACTOR = {"segundo": 1, "minuto": 60, "hora": 3600}
_RELLENO = {"que", "de", "para", "a", "el", "la", "lo"}


@dataclass
class Temporizador:
    id: int
    vence: float
    segundos: int
    etiqueta: str = ""


def _numero(tokens: list[str], i: int) -> tuple[int, int] | None:
    """Número (en cifras o en palabras) que empieza en tokens[i]: (valor, índice siguiente)."""
    if i >= len(tokens):
        return None
    token = tokens[i]
    if token.isdigit():
        return int(token), i + 1
    if token in _DECENAS:
        if i + 2 < len(tokens) and tokens[i + 1] == "y" and 0 < _UNIDADES.get(tokens[i + 2], 0) < 10:
            return _DECENAS[token] + _UNIDADES[tokens[i + 2]], i + 3
        return _DECENAS[token], i + 1
    if token in _UNIDADES:
        return _UNIDADES[token], i + 1
    return None


def _duracion(tokens: list[str]) -> tuple[int, int, int] | None:
    """Primera duración que aparece: (segundos, índice donde empieza, índice donde termina)."""
    for inicio in range(len(tokens)):
        total, i = 0, inicio
        while i < len(tokens):
            if tokens[i : i + 2] == ["media", "hora"]:
                total, i = total + 1800, i + 2
            elif tokens[i : i + 3] == ["cuarto", "de", "hora"]:
                total, i = total + 900, i + 3
            elif (numero := _numero(tokens, i)) and numero[1] < len(tokens) and tokens[numero[1]].rstrip("s") in _FACTOR:
                valor, j = numero
                unidad = tokens[j].rstrip("s")
                total, i = total + valor * _FACTOR[unidad], j + 1
                if unidad == "hora" and tokens[i : i + 2] == ["y", "media"]:
                    total, i = total + 1800, i + 2
                elif unidad == "hora" and tokens[i : i + 2] == ["y", "cuarto"]:
                    total, i = total + 900, i + 2
                elif unidad == "minuto" and tokens[i : i + 2] == ["y", "medio"]:
                    total, i = total + 30, i + 2
            elif i > inicio and tokens[i] == "y" and (tokens[i + 1 : i + 2] and _numero(tokens, i + 1) or tokens[i + 1 : i + 3] == ["media", "hora"]):
                i += 1  # «una hora y diez minutos»
            else:
                break
        if total > 0:
            return total, inicio, i
    return None


def interpretar_duracion(texto: str) -> int | None:
    resultado = _duracion(normalizar(texto).split())
    return resultado[0] if resultado else None


def describir(segundos: int) -> str:
    horas, resto = divmod(int(segundos), 3600)
    minutos, seg = divmod(resto, 60)
    partes = [
        f"{n} {nombre if n == 1 else nombre + 's'}"
        for n, nombre in ((horas, "hora"), (minutos, "minuto"), (seg, "segundo"))
        if n
    ]
    return " y ".join(partes) if len(partes) < 3 else f"{partes[0]}, {partes[1]} y {partes[2]}"


def interpretar_temporizador(texto: str) -> tuple[str, object] | None:
    """Órdenes de voz de temporizadores. Devuelve (herramienta, argumento) o None."""
    t = normalizar(texto)
    palabras = t.split()
    objeto = re.search(r"\b(temporizador(?:es)?|cronometro|alarma|recordatorio)\b", t)
    if objeto and re.search(r"\b(cancela|quita|elimina|deten|detén|para|apaga|borra)\b", t):
        return "cancelar_temporizador", None
    if (objeto and re.search(r"\bcuanto (falta|queda)\b|\b(que|cuales|cuantos)\b.*\b(hay|tengo|quedan)\b", t)) or re.fullmatch(
        r"(?:jarvis )?cuanto (falta|queda)( ya)?", t
    ):
        return "temporizadores", None
    encontrado = _duracion(palabras)
    if not encontrado:
        return None
    segundos, _inicio, fin = encontrado
    if objeto:
        return "temporizador", (segundos, "")
    if re.match(r"(?:jarvis )?(avisame|recuerdame|dime|recordame) (?:en|dentro de|a los)\b", t):
        etiqueta = [p for p in palabras[fin:]]
        while etiqueta and etiqueta[0] in _RELLENO:
            etiqueta.pop(0)
        return "temporizador", (segundos, " ".join(etiqueta))
    return None


class Temporizadores:
    """Cuenta atrás en memoria; el bucle principal consulta `vencidos()` y avisa en voz alta."""

    def __init__(self, reloj: Callable[[], float] = time.monotonic) -> None:
        self._reloj = reloj
        self._activos: list[Temporizador] = []
        self._siguiente = 1

    def crear(self, segundos: int, etiqueta: str = "") -> Temporizador:
        if not 1 <= segundos <= config.TEMPORIZADOR_MAX_S:
            raise ValueError("Duración fuera de rango.")
        if len(self._activos) >= config.TEMPORIZADORES_MAX:
            raise ValueError("Hay demasiados temporizadores activos.")
        temporizador = Temporizador(self._siguiente, self._reloj() + segundos, int(segundos), etiqueta.strip()[:100])
        self._siguiente += 1
        self._activos.append(temporizador)
        return temporizador

    def cancelar(self) -> int:
        cancelados, self._activos = len(self._activos), []
        return cancelados

    def vencidos(self) -> list[Temporizador]:
        ahora = self._reloj()
        listos = [t for t in self._activos if t.vence <= ahora]
        if listos:
            self._activos = [t for t in self._activos if t.vence > ahora]
        return sorted(listos, key=lambda t: t.vence)

    def pendientes(self) -> list[tuple[Temporizador, int]]:
        ahora = self._reloj()
        return sorted(((t, max(1, round(t.vence - ahora))) for t in self._activos), key=lambda par: par[1])
