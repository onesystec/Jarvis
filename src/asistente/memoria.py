import json
import os
import re
import tempfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken

from . import config
from .reglas import normalizar

_VACIAS = {"que", "del", "los", "las", "una", "uno", "unos", "unas", "mis", "con", "por", "para", "sobre", "eso", "esto", "mio", "mia"}

_RECORDAR = re.compile(
    r"^\W*(?:jarvis\W+)?(?:recuerda|anota|apunta|acu[eé]rdate|memoriza)(?:\s+(?:de\s+que|que|lo\s+siguiente|esto))?\W*\s+(.{3,})$",
    re.IGNORECASE | re.DOTALL,
)
_OLVIDAR = re.compile(
    r"^\W*(?:jarvis\W+)?olvida(?:te)?(?:\s+(?:de|lo\s+de|lo\s+que|que|eso\s+de|eso))?\s+(.{2,})$",
    re.IGNORECASE | re.DOTALL,
)
_OLVIDAR_TODO = re.compile(r"^(?:jarvis )?olvida(?:te)? (?:de )?(?:todo|todos los recuerdos|todo lo que (?:sabes|tienes|recuerdas)(?: de mi| sobre mi)?)$")
_LISTAR = re.compile(r"\b(?:que|cuanto) (?:recuerdas|sabes (?:de|sobre) mi|tienes (?:anotado|guardado|apuntado)|has anotado)\b|\blo que (?:recuerdas|sabes de mi|tienes anotado)\b")


class MemoriaError(Exception):
    """La memoria no se puede abrir o está llena; el asistente sigue sin ella."""


@dataclass(frozen=True)
class Hecho:
    id: int
    texto: str
    creado: str


class Memoria:
    """Hechos anotados por el usuario, guardados cifrados (Fernet: AES + HMAC) en un solo archivo.

    Un archivo que no se puede descifrar (clave distinta, alterado) nunca se sobrescribe.
    """

    def __init__(self, ruta: Path, clave: bytes) -> None:
        self._ruta = ruta
        self._fernet = Fernet(clave)
        self._hechos: list[Hecho] = []
        self._siguiente = 1
        self._cargar()

    def _cargar(self) -> None:
        if not self._ruta.exists():
            return
        try:
            datos = json.loads(self._fernet.decrypt(self._ruta.read_bytes()))
            self._hechos = [Hecho(int(h["id"]), str(h["texto"]), str(h["creado"])) for h in datos["hechos"]]
        except (InvalidToken, ValueError, KeyError, TypeError) as error:
            raise MemoriaError("No pude descifrar la memoria: la clave no coincide o el archivo fue alterado.") from error
        self._siguiente = max((h.id for h in self._hechos), default=0) + 1

    def _guardar(self) -> None:
        carga = {"version": 1, "hechos": [{"id": h.id, "texto": h.texto, "creado": h.creado} for h in self._hechos]}
        cifrado = self._fernet.encrypt(json.dumps(carga, ensure_ascii=False).encode())
        self._ruta.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        # Se escribe en un temporal privado y se reemplaza de golpe: un corte no deja la memoria a medias.
        descriptor, temporal = tempfile.mkstemp(dir=self._ruta.parent, prefix=".memoria-")
        try:
            with os.fdopen(descriptor, "wb") as archivo:
                archivo.write(cifrado)
                archivo.flush()
                os.fsync(archivo.fileno())
            os.chmod(temporal, 0o600)
            os.replace(temporal, self._ruta)
        except BaseException:
            Path(temporal).unlink(missing_ok=True)
            raise

    @property
    def hechos(self) -> list[Hecho]:
        return list(self._hechos)

    def recordar(self, texto: str) -> Hecho | None:
        """Anota un hecho. None si ya estaba anotado."""
        texto = " ".join(texto.split()).strip(" .,;")
        if len(texto) < 3:
            raise MemoriaError("No entendí qué debo recordar, señor.")
        if len(texto) > config.MEMORIA_MAX_CARACTERES:
            raise MemoriaError("Eso es demasiado largo para anotarlo, señor.")
        if any(normalizar(h.texto) == normalizar(texto) for h in self._hechos):
            return None
        if len(self._hechos) >= config.MEMORIA_MAX_HECHOS:
            raise MemoriaError("La memoria está llena, señor. Pídame que olvide algo primero.")
        hecho = Hecho(self._siguiente, texto, datetime.now().astimezone().isoformat(timespec="seconds"))
        self._hechos.append(hecho)
        self._siguiente += 1
        self._guardar()
        return hecho

    def coincidencias(self, tema: str) -> list[Hecho]:
        palabras = [p for p in normalizar(tema).split() if len(p) > 2 and p not in _VACIAS]
        if not palabras:
            return []
        return [h for h in self._hechos if all(p in normalizar(h.texto) for p in palabras)]

    def olvidar(self, tema: str) -> int:
        borrar = {h.id for h in self.coincidencias(tema)}
        if borrar:
            self._hechos = [h for h in self._hechos if h.id not in borrar]
            self._guardar()
        return len(borrar)

    def olvidar_todo(self) -> int:
        borrados, self._hechos = len(self._hechos), []
        if borrados:
            self._guardar()
        return borrados

    def para_nube(self) -> list[str]:
        """Lo más reciente primero hasta el tope de caracteres; se devuelve en orden cronológico."""
        elegidos, usados = [], 0
        for hecho in reversed(self._hechos):
            usados += len(hecho.texto)
            if usados > config.MEMORIA_PROMPT_MAX_CARACTERES:
                break
            elegidos.append(hecho.texto)
        return elegidos[::-1]


def interpretar_memoria(texto: str) -> tuple[str, str | None] | None:
    """Reconoce «recuerda que…», «olvida…» y «qué recuerdas». Devuelve (herramienta, argumento)."""
    t = normalizar(texto)
    if _OLVIDAR_TODO.fullmatch(t):
        return "olvidar_todo", None
    if _LISTAR.search(t):
        return "recuerdos", None
    if m := _RECORDAR.match(texto.strip()):
        return "recordar", m[1].strip(" .,;")
    if m := _OLVIDAR.match(texto.strip()):
        return "olvidar", m[1].strip(" .,;")
    return None
