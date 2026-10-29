import getpass
import subprocess

from cryptography.fernet import Fernet

from . import config


def _leer(servicio: str) -> str | None:
    resultado = subprocess.run(
        [config.SECURITY, "find-generic-password", "-s", servicio, "-a", getpass.getuser(), "-w"],
        capture_output=True,
        text=True,
        timeout=15,
        check=False,  # código distinto de 0 = no hay clave guardada
    )
    if resultado.returncode != 0:
        return None
    return resultado.stdout.strip() or None


def obtener_clave() -> str | None:
    """Lee la clave de Anthropic del Keychain de macOS; None si no existe."""
    return _leer(config.SERVICIO_CLAVE)


def clave_memoria() -> bytes:
    """Clave que cifra la memoria; se crea y guarda en el Keychain la primera vez.

    Al crearla viaja una vez como argumento de `security`, visible un instante para procesos
    del mismo usuario; no se vuelve a pasar por argumentos (la lectura usa la salida estándar).
    """
    existente = _leer(config.SERVICIO_MEMORIA)
    if existente:
        return existente.encode()
    nueva = Fernet.generate_key()
    subprocess.run(
        [config.SECURITY, "add-generic-password", "-s", config.SERVICIO_MEMORIA, "-a", getpass.getuser(), "-w", nueva.decode()],
        capture_output=True,
        timeout=15,
        check=True,
    )
    return nueva
