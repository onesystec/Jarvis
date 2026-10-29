import subprocess

from . import config


def hablar(texto: str) -> None:
    texto = texto.strip()
    if not texto:
        return
    # "--" evita que un texto que empiece con "-" se interprete como opción.
    subprocess.run([config.SAY, "-v", config.VOZ, "--", texto], check=True, timeout=120)
