"""Geometría y estados de la esfera. Matemática pura: no depende de AppKit."""

import math
from dataclasses import dataclass


@dataclass(frozen=True)
class Parametros:
    amplitud: float  # cuánto se deforma el contorno
    velocidad: float  # ritmo de la animación
    brillo: float  # intensidad del resplandor
    pulso: float  # latido del radio
    presencia: float = 1.0  # opacidad a la que se queda la esfera en este estado (0 = oculta)


ESTADOS: dict[str, Parametros] = {
    "reposo": Parametros(0.6, 0.5, 0.7, 0.0, 0.0),  # oculta
    "espera": Parametros(0.5, 0.45, 0.85, 0.0, 0.42),  # siempre presente, tenue y tranquila
    "escuchando": Parametros(0.7, 1.0, 1.0, 0.012),
    "pensando": Parametros(1.0, 2.4, 1.3, 0.0),
    "hablando": Parametros(1.4, 1.5, 1.15, 0.05),
}

# (k, amplitud, velocidad angular, fase): ondulaciones que superpuestas dan el aspecto de líquido
_ARMONICOS = (
    (2, 0.050, 0.9, 0.0),
    (3, 0.038, -1.3, 1.7),
    (5, 0.022, 2.1, 4.0),
    (7, 0.010, -2.9, 2.2),
)


def mezclar(a: Parametros, b: Parametros, k: float) -> Parametros:
    """Interpolación de a hacia b; k en [0, 1]."""
    return Parametros(
        a.amplitud + (b.amplitud - a.amplitud) * k,
        a.velocidad + (b.velocidad - a.velocidad) * k,
        a.brillo + (b.brillo - a.brillo) * k,
        a.pulso + (b.pulso - a.pulso) * k,
        a.presencia + (b.presencia - a.presencia) * k,
    )


def radio_en(theta: float, fase: float, amplitud: float, desfase: float = 0.0) -> float:
    return 1.0 + amplitud * sum(a * math.sin(k * theta + w * fase + f + desfase) for k, a, w, f in _ARMONICOS)


def _punto(theta: float, fase: float, amplitud: float, pulso: float, desfase: float) -> tuple[float, float]:
    escala = (1.0 + pulso * math.sin(fase * 4.0)) * radio_en(theta, fase, amplitud, desfase)
    return escala * math.cos(theta), escala * math.sin(theta)


def contorno(fase: float, amplitud: float, pulso: float = 0.0, n: int = 96, desfase: float = 0.0) -> list[tuple[float, float]]:
    """Puntos de la silueta sobre un círculo de radio 1."""
    return [_punto(2 * math.pi * i / n, fase, amplitud, pulso, desfase) for i in range(n)]


def arco(centro: float, semiancho: float, fase: float, amplitud: float, pulso: float = 0.0, n: int = 24, desfase: float = 0.0) -> list[tuple[float, float]]:
    """Tramo de la silueta alrededor de un ángulo; sirve para los destellos del borde."""
    return [_punto(centro - semiancho + 2 * semiancho * i / (n - 1), fase, amplitud, pulso, desfase) for i in range(n)]


def centros_de_destello(fase: float) -> list[float]:
    """Ángulos donde brilla el borde; giran despacio y a distinta velocidad."""
    return [1.1 + 0.55 * fase, 3.4 - 0.38 * fase, 5.2 + 0.27 * fase]
