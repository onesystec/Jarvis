import math
import subprocess

import pytest

from asistente import esfera as modulo_esfera
from asistente.esfera import Esfera
from asistente.esfera_forma import ESTADOS, arco, centros_de_destello, contorno, mezclar


def test_contorno_es_casi_circular_y_cerrado():
    puntos = contorno(fase=1.3, amplitud=ESTADOS["escuchando"].amplitud)
    assert len(puntos) == 96
    radios = [math.hypot(x, y) for x, y in puntos]
    assert 0.8 < min(radios) and max(radios) < 1.2


def test_mas_amplitud_deforma_mas():
    def desviacion(amplitud):
        radios = [math.hypot(x, y) for x, y in contorno(2.0, amplitud)]
        return max(radios) - min(radios)

    assert desviacion(1.9) > desviacion(0.7) > desviacion(0.0) == pytest.approx(0.0)


def test_el_contorno_cambia_con_la_fase():
    assert contorno(0.0, 1.0) != contorno(0.5, 1.0)


def test_arco_sigue_la_silueta():
    fase, amplitud = 0.7, 1.0
    completo = contorno(fase, amplitud, n=96)
    tramo = arco(0.0, 0.2, fase, amplitud, n=5)
    assert len(tramo) == 5
    # el punto central del arco está en theta = 0, igual que el primer punto del contorno
    assert tramo[2] == pytest.approx(completo[0])
    assert len(centros_de_destello(0.0)) == 3


def test_mezclar_interpola():
    a, b = ESTADOS["reposo"], ESTADOS["hablando"]
    assert mezclar(a, b, 0.0) == a
    assert mezclar(a, b, 1.0) == b
    assert a.velocidad < mezclar(a, b, 0.5).velocidad < b.velocidad


class ProcesoFalso:
    def __init__(self, roto=False) -> None:
        self.roto = roto
        self.escrito: list[str] = []
        self.cerrado = False
        self.stdin = self

    def poll(self):
        return None

    def write(self, texto):
        if self.roto:
            raise BrokenPipeError
        self.escrito.append(texto)

    def flush(self):
        pass

    def close(self):
        self.cerrado = True

    def wait(self, timeout=None):
        pass

    def kill(self):
        pass


def _esfera_con(monkeypatch, proceso):
    monkeypatch.setattr(modulo_esfera.subprocess, "Popen", lambda *a, **k: proceso)
    return Esfera()


def test_envia_estados_y_cierra_por_eof(monkeypatch):
    proceso = ProcesoFalso()
    with _esfera_con(monkeypatch, proceso) as esfera:
        esfera.estado("escuchando")
        esfera.estado("reposo")
    assert proceso.escrito == ["escuchando\n", "reposo\n"]
    assert proceso.cerrado


def test_estado_desconocido_se_rechaza(monkeypatch):
    with pytest.raises(ValueError):
        _esfera_con(monkeypatch, ProcesoFalso()).estado("furioso")


def test_si_la_esfera_se_cae_el_asistente_sigue(monkeypatch):
    esfera = _esfera_con(monkeypatch, ProcesoFalso(roto=True))
    esfera.estado("escuchando")  # no lanza
    esfera.estado("hablando")
    esfera.cerrar()


def test_si_no_se_puede_lanzar_el_asistente_sigue(monkeypatch):
    def falla(*_a, **_k):
        raise OSError("sin ejecutable")

    monkeypatch.setattr(modulo_esfera.subprocess, "Popen", falla)
    esfera = Esfera()
    esfera.estado("escuchando")
    esfera.cerrar()


def test_desactivada_no_lanza_nada(monkeypatch):
    def prohibido(*_a, **_k):
        raise AssertionError("no debe lanzar procesos")

    monkeypatch.setattr(subprocess, "Popen", prohibido)
    Esfera(activa=False).estado("escuchando")


def test_la_vista_dibuja_con_fondo_transparente():
    pytest.importorskip("AppKit")
    from AppKit import NSBitmapImageRep
    from Foundation import NSMakeRect

    from asistente.esfera_ventana import VistaEsfera

    vista = VistaEsfera.alloc().initWithFrame_(NSMakeRect(0, 0, 200, 200))
    vista.fijar_estado("escuchando")
    vista.opacidad = 1.0
    representacion: NSBitmapImageRep = vista.bitmapImageRepForCachingDisplayInRect_(vista.bounds())
    vista.cacheDisplayInRect_toBitmapImageRep_(vista.bounds(), representacion)
    esquina = representacion.colorAtX_y_(1, 1)
    assert esquina.alphaComponent() == 0.0  # fuera de la esfera no hay nada
    hay_trazo = any(representacion.colorAtX_y_(x, 100).alphaComponent() > 0.3 for x in range(400))
    assert hay_trazo
