import threading

import numpy as np
import pytest

from asistente import tts
from asistente.frases import Diferida


@pytest.fixture
def voz_falsa(monkeypatch):
    eventos: list[str] = []
    monkeypatch.setattr(tts, "_hay_kokoro", lambda: True)
    monkeypatch.setattr(tts, "_cargar_kokoro", lambda: None)
    monkeypatch.setattr(tts, "_sintetizar", lambda texto, voz: (np.zeros(10, dtype=np.int16), 24000))
    monkeypatch.setattr(tts, "_reproducir", lambda ruta: eventos.append(f"suena {ruta.name}"))
    return eventos


def test_dice_las_frases_en_orden(voz_falsa):
    avisos = []
    dichas = tts.hablar_frases(["uno", " ", "dos"], al_decir=lambda: avisos.append("aviso"))
    assert dichas == ["uno", "dos"]
    assert len(voz_falsa) == 2
    assert avisos == ["aviso", "aviso"]


def test_las_acciones_diferidas_corren_en_el_hilo_principal_tras_lo_anterior(voz_falsa):
    hilos = []

    def accion():
        voz_falsa.append("acción")
        hilos.append(threading.current_thread())
        return "ok"

    def frases():
        yield "uno"
        diferida = Diferida(accion)
        yield diferida
        assert diferida.esperar() == "ok"
        yield "dos"

    assert tts.hablar_frases(frases()) == ["uno", "dos"]
    assert [e.split()[0] for e in voz_falsa] == ["suena", "acción", "suena"]
    assert hilos == [threading.current_thread()]


def test_un_fallo_al_sintetizar_se_avisa_sin_colgarse(voz_falsa, monkeypatch):
    def falla(texto, voz):
        raise ValueError("modelo roto")

    monkeypatch.setattr(tts, "_sintetizar", falla)
    with pytest.raises(RuntimeError, match="No pude generar la voz"):
        tts.hablar_frases(["uno", "dos"])


def test_un_fallo_al_reproducir_libera_las_acciones_pendientes(voz_falsa, monkeypatch):
    def falla(ruta):
        raise OSError("sin audio")

    monkeypatch.setattr(tts, "_reproducir", falla)

    def frases():
        yield "uno"
        diferida = Diferida(lambda: "nunca")
        yield diferida
        diferida.esperar()
        yield "dos"

    with pytest.raises(OSError):
        tts.hablar_frases(frases())
