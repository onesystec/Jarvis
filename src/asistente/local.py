import http.client
import json
import os
import secrets
import shutil
import socket
import subprocess
import sys
import tempfile
import time
from collections.abc import Callable, Iterator, Sequence
from datetime import datetime
from pathlib import Path

from . import config
from .frases import Diferida, dividir_en_frases
from .integridad import sha256


class _ConexionUnix(http.client.HTTPConnection):
    def __init__(self, ruta: str, tiempo: float) -> None:
        super().__init__("localhost", timeout=tiempo)
        self._ruta = ruta

    def connect(self) -> None:
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.sock.settimeout(self.timeout)
        self.sock.connect(self._ruta)


class ModeloLocal:
    """Modelo de lenguaje que corre en este equipo y solo existe mientras hace falta.

    Se lanza `llama-server` bajo demanda, escuchando en un socket Unix dentro de una carpeta privada (0700) y con
    clave en archivo; se verifica el SHA-256 del modelo antes de cargarlo y se cierra al terminar la conversación.
    Un proceso guardián lo apaga si el asistente muere sin cerrarlo.
    """

    def __init__(self, modelo: Path | None = None, binario: str | None = None, sha: str | None = None) -> None:
        self._modelo = modelo or config.MODELO_LOCAL
        self._binario = binario or config.LLAMA_SERVER
        self._sha = sha or config.SHA256_MODELO_LOCAL
        self._verificado = False
        self._proceso: subprocess.Popen | None = None
        self._carpeta: Path | None = None
        self._clave = ""

    def disponible(self) -> bool:
        return config.LOCAL_ACTIVO and self._modelo.is_file() and Path(self._binario).is_file()

    @property
    def activo(self) -> bool:
        return self._proceso is not None and self._proceso.poll() is None

    # --- ciclo de vida -------------------------------------------------------------------------

    def _arrancar(self) -> None:
        if not self._verificado:
            if sha256(self._modelo) != self._sha:
                raise RuntimeError("El hash del modelo local no coincide; el archivo fue alterado.")
            self._verificado = True
        self.liberar()
        carpeta = Path(tempfile.mkdtemp(prefix="jv."))  # corta: la ruta del socket no puede pasar de ~100 caracteres
        os.chmod(carpeta, 0o700)
        self._clave = secrets.token_urlsafe(24)
        archivo_clave = carpeta / "clave"
        descriptor = os.open(archivo_clave, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, "w") as f:
            f.write(self._clave)
        try:
            self._proceso = subprocess.Popen(
                [
                    self._binario, "-m", str(self._modelo),
                    "--host", str(carpeta / "llm.sock"),
                    "--api-key-file", str(archivo_clave),
                    "--no-webui", "-c", str(config.LOCAL_CONTEXTO), "-np", "1", "-ngl", "99",
                ],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            self._carpeta = carpeta
            subprocess.Popen(
                [sys.executable, "-m", "asistente.vigilante", str(os.getpid()), str(self._proceso.pid), str(carpeta)],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            self._esperar_listo()
        except BaseException:
            self.liberar()
            raise

    def _esperar_listo(self) -> None:
        limite = time.monotonic() + config.LOCAL_ESPERA_ARRANQUE_S
        while time.monotonic() < limite:
            if not self.activo:
                raise RuntimeError("El modelo local se cerró al arrancar.")
            try:
                conexion = _ConexionUnix(str(self._carpeta / "llm.sock"), 2.0)
                conexion.request("GET", "/health", headers={"Authorization": f"Bearer {self._clave}"})
                if conexion.getresponse().status == 200:
                    return
            except (OSError, http.client.HTTPException):
                pass
            time.sleep(0.2)
        raise RuntimeError("El modelo local tardó demasiado en arrancar.")

    def liberar(self) -> None:
        """Cierra el servidor y libera la memoria."""
        proceso, self._proceso = self._proceso, None
        if proceso is not None and proceso.poll() is None:
            proceso.terminate()
            try:
                proceso.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proceso.kill()
                proceso.wait()
        if self._carpeta is not None:
            shutil.rmtree(self._carpeta, ignore_errors=True)
            self._carpeta = None

    # --- respuestas ----------------------------------------------------------------------------

    def _trozos(self, mensajes: list[dict]) -> Iterator[str]:
        cuerpo = {
            "messages": mensajes,
            "stream": True,
            "max_tokens": config.LOCAL_MAX_TOKENS,
            "temperature": 0.4,
        }
        conexion = _ConexionUnix(str(self._carpeta / "llm.sock"), 60.0)
        try:
            conexion.request(
                "POST",
                "/v1/chat/completions",
                json.dumps(cuerpo),
                {"Content-Type": "application/json", "Authorization": f"Bearer {self._clave}"},
            )
            respuesta = conexion.getresponse()
            if respuesta.status != 200:
                raise RuntimeError(f"El modelo local respondió {respuesta.status}.")
            for linea in respuesta:
                linea = linea.decode("utf-8", errors="replace").strip()
                if not linea.startswith("data:") or linea.endswith("[DONE]"):
                    continue
                try:
                    delta = json.loads(linea[5:])["choices"][0]["delta"].get("content")
                except (ValueError, KeyError, IndexError) as error:
                    raise RuntimeError("Respuesta ilegible del modelo local.") from error
                if delta:
                    yield delta
        except (OSError, http.client.HTTPException) as error:
            raise RuntimeError(f"No pude hablar con el modelo local: {error}") from error
        finally:
            conexion.close()

    def frases(
        self,
        mensajes: list[dict],
        usar_herramienta: Callable[[str, dict], str] | None = None,
        recuerdos: Sequence[str] = (),
        web: bool = False,
        marcar_externo: Callable[[], None] | None = None,
    ) -> Iterator[str | Diferida]:
        """Responde por frases, igual que `ClienteClaude.frases`, pero sin salir del equipo y sin herramientas."""
        if not self.activo:
            yield config.LOCAL_AVISO
            self._arrancar()
        ahora = datetime.now().astimezone()
        sistema = config.INSTRUCCIONES_LOCAL + f"\n\nFecha y hora actuales: {ahora:%Y-%m-%d %H:%M} ({ahora.tzname()})."
        if recuerdos:
            sistema += config.PREFIJO_RECUERDOS + "\n".join(f"- {r}" for r in recuerdos)
        yield from dividir_en_frases(self._trozos([{"role": "system", "content": sistema}, *mensajes]))
