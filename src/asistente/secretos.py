import getpass
import subprocess

from . import config


def obtener_clave() -> str | None:
    """Lee la clave de Anthropic del Keychain de macOS; None si no existe."""
    resultado = subprocess.run(
        [config.SECURITY, "find-generic-password", "-s", config.SERVICIO_CLAVE, "-a", getpass.getuser(), "-w"],
        capture_output=True,
        text=True,
        timeout=15,
        check=False,  # código distinto de 0 = no hay clave guardada
    )
    if resultado.returncode != 0:
        return None
    return resultado.stdout.strip() or None
