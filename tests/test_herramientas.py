import json
import subprocess

import pytest

from asistente import auditoria
from asistente.cerebro import Cerebro
from asistente.herramientas import (
    Herramientas,
    Orden,
    buscar_app,
    interpretar_orden,
    volumen,
)

PERMISOS = {"abrir_app": "libre", "cerrar_app": "confirmar", "volumen": "libre"}


class Banco:
    """Herramientas con ejecutores y auditoría falsos: nada toca el Mac."""

    def __init__(self, permisos=PERMISOS, app="Safari", fallo=None) -> None:
        self.eventos: list[dict] = []
        self.hechas: list[tuple] = []

        def ejecutor(nombre):
            def hacer(argumento):
                self.hechas.append((nombre, argumento))
                if fallo:
                    raise fallo
                return f"{nombre} hecho."

            return hacer

        self.herramientas = Herramientas(
            permisos=permisos,
            auditar=lambda **campos: self.eventos.append(campos),
            ejecutores={n: ejecutor(n) for n in ("abrir_app", "cerrar_app", "volumen")},
            buscar=lambda _nombre: app,
        )


def test_ordenes_reconocidas():
    assert interpretar_orden("Abre Safari") == Orden("abrir_app", "safari")
    assert interpretar_orden("abre el calendario") == Orden("abrir_app", "calendario")
    assert interpretar_orden("Cierra Spotify.") == Orden("cerrar_app", "spotify")
    assert interpretar_orden("sube el volumen") == Orden("volumen", "subir")
    assert interpretar_orden("baja el volumen") == Orden("volumen", "bajar")
    assert interpretar_orden("pon el volumen al 40") == Orden("volumen", 40)
    assert interpretar_orden("volumen 250") == Orden("volumen", 100)
    assert interpretar_orden("silencia el mac") == Orden("volumen", "silenciar")


def test_lo_que_no_es_una_orden_no_se_interpreta():
    assert interpretar_orden("cuéntame un chiste") is None
    assert interpretar_orden("qué es el volumen de un cubo") is None


def test_libre_se_ejecuta_y_se_audita_antes_y_despues():
    banco = Banco()
    texto = banco.herramientas.ejecutar(Orden("abrir_app", "safari"), lambda _: False)
    assert texto == "abrir_app hecho."
    assert banco.hechas == [("abrir_app", "Safari")]
    assert [e.get("decision") or e.get("resultado") for e in banco.eventos] == ["libre", "ok"]


def test_cerrar_pide_confirmacion_y_respeta_el_no():
    banco = Banco()
    preguntas = []

    def no(pregunta):
        preguntas.append(pregunta)
        return False

    texto = banco.herramientas.ejecutar(Orden("cerrar_app", "safari"), no)
    assert "no lo hago" in texto
    assert banco.hechas == []
    assert preguntas == ["¿Confirma que cierre Safari?"]
    assert banco.eventos[-1]["decision"] == "rechazada"


def test_cerrar_con_si_se_ejecuta():
    banco = Banco()
    banco.herramientas.ejecutar(Orden("cerrar_app", "safari"), lambda _: True)
    assert banco.hechas == [("cerrar_app", "Safari")]
    assert banco.eventos[0]["decision"] == "aprobada"


def test_herramienta_desactivada_o_desconocida_se_rechaza():
    banco = Banco(permisos={"abrir_app": "desactivada"})
    assert "desactivada" in banco.herramientas.ejecutar(Orden("abrir_app", "safari"), lambda _: True)
    assert "desactivada" in banco.herramientas.ejecutar(Orden("borrar_todo"), lambda _: True)
    assert banco.hechas == []


def test_apps_protegidas_no_se_cierran_ni_preguntan():
    banco = Banco(app="Terminal")
    preguntas = []
    texto = banco.herramientas.ejecutar(Orden("cerrar_app", "terminal"), lambda p: preguntas.append(p) or True)
    assert "No puedo cerrar Terminal" in texto
    assert banco.hechas == [] and preguntas == []


def test_app_inexistente():
    banco = Banco(app=None)
    assert "No encuentro" in banco.herramientas.ejecutar(Orden("abrir_app", "fantasma"), lambda _: True)
    assert banco.hechas == []


def test_si_la_auditoria_falla_no_se_ejecuta():
    banco = Banco()

    def auditar_roto(**_campos):
        raise OSError("disco lleno")

    banco.herramientas._auditar = auditar_roto
    with pytest.raises(OSError):
        banco.herramientas.ejecutar(Orden("abrir_app", "safari"), lambda _: True)
    assert banco.hechas == []


def test_un_fallo_del_comando_no_tumba_al_asistente():
    banco = Banco(fallo=subprocess.CalledProcessError(1, "open"))
    texto = banco.herramientas.ejecutar(Orden("abrir_app", "safari"), lambda _: True)
    assert "No pude" in texto
    assert banco.eventos[-1]["resultado"] == "error"


def test_el_cerebro_resuelve_ordenes_sin_nube():
    banco = Banco()

    class NubeProhibida:
        def responder(self, _mensajes):
            raise AssertionError("una orden local no debe salir a la nube")

    cerebro = Cerebro(NubeProhibida(), confirmar=lambda _: True, herramientas=banco.herramientas)
    assert cerebro.pensar("abre safari").texto == "abrir_app hecho."


def test_volumen_sube_baja_y_se_acota():
    puestos = []
    assert volumen("subir", actual=lambda: 95, fijar=puestos.append) == "Volumen al 100 por ciento."
    assert volumen("bajar", actual=lambda: 5, fijar=puestos.append) == "Volumen al 0 por ciento."
    assert volumen(40, fijar=puestos.append) == "Volumen al 40 por ciento."
    assert puestos == [100, 0, 40]
    assert "No puedo leer" in volumen("subir", actual=lambda: None, fijar=puestos.append)


def test_buscar_app_por_nombre_alias_y_prefijo(tmp_path):
    for nombre in ("Safari", "Calendar", "Google Chrome", "Notes"):
        (tmp_path / f"{nombre}.app").mkdir()
    carpetas = (tmp_path, tmp_path / "no-existe")
    assert buscar_app("SAFARI", carpetas) == "Safari"
    assert buscar_app("calendario", carpetas) == "Calendar"
    assert buscar_app("google", carpetas) == "Google Chrome"
    assert buscar_app("fantasma", carpetas) is None
    assert buscar_app("", carpetas) is None


def test_auditoria_escribe_jsonl_privado(tmp_path):
    ruta = tmp_path / "datos" / "auditoria.jsonl"
    auditoria.registrar(ruta, herramienta="volumen", argumento=40, decision="libre")
    auditoria.registrar(ruta, herramienta="volumen", argumento=40, resultado="ok")
    lineas = [json.loads(linea) for linea in ruta.read_text().splitlines()]
    assert [linea.get("decision") or linea.get("resultado") for linea in lineas] == ["libre", "ok"]
    assert "ts" in lineas[0]
    assert ruta.stat().st_mode & 0o777 == 0o600
    assert ruta.parent.stat().st_mode & 0o777 == 0o700
