import stat

import pytest
from cryptography.fernet import Fernet

from asistente import config, loop
from asistente.cerebro import (
    PREGUNTA_NUBE_CON_RECUERDOS,
    PREGUNTA_NUBE_CONVERSACION,
    Cerebro,
)
from asistente.herramientas import (
    Herramientas,
    Orden,
    interpretar_orden,
    orden_desde_claude,
)
from asistente.memoria import Memoria, MemoriaError, interpretar_memoria
from asistente.reglas import Respuesta

from .test_cerebro import Confirmador, NubeFalsa, decir


@pytest.fixture
def clave():
    return Fernet.generate_key()


@pytest.fixture
def memoria(tmp_path, clave):
    return Memoria(tmp_path / "datos" / "memoria.enc", clave)


def test_se_guarda_cifrada_y_se_recupera(tmp_path, clave):
    ruta = tmp_path / "datos" / "memoria.enc"
    Memoria(ruta, clave).recordar("mi hermana se llama Ana")
    crudo = ruta.read_bytes()
    assert b"Ana" not in crudo and b"hermana" not in crudo  # nada legible en disco
    assert [h.texto for h in Memoria(ruta, clave).hechos] == ["mi hermana se llama Ana"]
    assert stat.S_IMODE(ruta.stat().st_mode) == 0o600
    assert stat.S_IMODE(ruta.parent.stat().st_mode) == 0o700


def test_con_otra_clave_o_alterada_no_se_abre_ni_se_sobrescribe(tmp_path, clave):
    ruta = tmp_path / "memoria.enc"
    Memoria(ruta, clave).recordar("dato importante")
    original = ruta.read_bytes()
    with pytest.raises(MemoriaError):
        Memoria(ruta, Fernet.generate_key())
    ruta.write_bytes(original[:-4] + b"AAAA")
    with pytest.raises(MemoriaError):
        Memoria(ruta, clave)
    assert ruta.read_bytes() == original[:-4] + b"AAAA"  # intacto: nunca se pisa lo que no se puede leer


def test_no_deja_temporales_tras_guardar(memoria):
    memoria.recordar("uno")
    memoria.recordar("dos más")
    assert [p.name for p in memoria._ruta.parent.iterdir()] == ["memoria.enc"]


def test_duplicados_y_limites(memoria, monkeypatch):
    assert memoria.recordar("me gusta el café") is not None
    assert memoria.recordar("Me gusta el CAFÉ.") is None  # mismo dato
    with pytest.raises(MemoriaError, match="largo"):
        memoria.recordar("x" * (config.MEMORIA_MAX_CARACTERES + 1))
    with pytest.raises(MemoriaError):
        memoria.recordar(" . ")
    monkeypatch.setattr(config, "MEMORIA_MAX_HECHOS", 2)
    memoria.recordar("segundo dato")
    with pytest.raises(MemoriaError, match="llena"):
        memoria.recordar("tercer dato")


def test_olvidar_por_tema(memoria):
    memoria.recordar("mi hermana se llama Ana")
    memoria.recordar("me gusta el café sin azúcar")
    assert [h.texto for h in memoria.coincidencias("de mi hermana")] == ["mi hermana se llama Ana"]
    assert memoria.coincidencias("de") == []  # sin palabras con contenido no borra nada
    assert memoria.olvidar("hermana") == 1
    assert [h.texto for h in memoria.hechos] == ["me gusta el café sin azúcar"]
    assert memoria.olvidar_todo() == 1 and memoria.hechos == []


def test_para_nube_respeta_el_tope_y_el_orden(memoria, monkeypatch):
    for i in range(5):
        memoria.recordar(f"dato número {i}")
    monkeypatch.setattr(config, "MEMORIA_PROMPT_MAX_CARACTERES", 30)
    assert memoria.para_nube() == ["dato número 3", "dato número 4"]  # lo más reciente, en orden


@pytest.mark.parametrize(
    ("frase", "esperado"),
    [
        ("Recuerda que mi hermana se llama Ana.", ("recordar", "mi hermana se llama Ana")),
        ("Jarvis, anota que el wifi es casa123", ("recordar", "el wifi es casa123")),
        ("Acuérdate de que el jueves tengo dentista", ("recordar", "el jueves tengo dentista")),
        ("olvida lo de mi hermana", ("olvidar", "mi hermana")),
        ("olvida todo", ("olvidar_todo", None)),
        ("Olvida todo lo que sabes de mí", ("olvidar_todo", None)),
        ("¿Qué recuerdas de mí?", ("recuerdos", None)),
        ("qué tienes anotado", ("recuerdos", None)),
        ("recuérdame comprar pan", None),
        ("¿recuerdas lo que hablamos ayer?", None),
        ("cuéntame un chiste", None),
    ],
)
def test_comandos_de_voz(frase, esperado):
    assert interpretar_memoria(frase) == esperado


def test_las_ordenes_de_memoria_llegan_al_interprete():
    assert interpretar_orden("recuerda que vivo en Santiago") == Orden("recordar", "vivo en Santiago")
    assert interpretar_orden("abre safari") == Orden("abrir_app", "safari")


def herramientas_con(memoria):
    eventos = []
    return Herramientas(auditar=lambda **c: eventos.append(c), memoria=memoria), eventos


def test_recordar_y_listar_por_herramientas(memoria):
    h, _ = herramientas_con(memoria)
    assert h.ejecutar(Orden("recuerdos"), lambda _: True) == "No tengo nada anotado todavía, señor."
    assert h.ejecutar(Orden("recordar", "mi perro se llama Rocky"), lambda _: False) == "Anotado, señor."
    assert "ya lo tenía" in h.ejecutar(Orden("recordar", "mi perro se llama Rocky"), lambda _: False)
    assert "mi perro se llama Rocky" in h.ejecutar(Orden("recuerdos"), lambda _: False)


def test_la_auditoria_no_guarda_lo_anotado(memoria):
    h, eventos = herramientas_con(memoria)
    h.ejecutar(Orden("recordar", "la clave del wifi es casa123"), lambda _: True)
    assert "casa123" not in str(eventos)
    assert any("caracteres" in str(e.get("argumento")) for e in eventos)


def test_olvidar_pide_confirmacion_y_cuenta_lo_que_borra(memoria):
    h, _ = herramientas_con(memoria)
    memoria.recordar("mi hermana se llama Ana")
    preguntas = []

    assert "no lo hago" in h.ejecutar(Orden("olvidar", "hermana"), lambda p: preguntas.append(p) or False)
    assert len(memoria.hechos) == 1 and "1 recuerdo" in preguntas[0]
    assert "he olvidado 1 recuerdo" in h.ejecutar(Orden("olvidar", "hermana"), lambda _: True)
    assert memoria.hechos == []


def test_olvidar_algo_que_no_existe_no_pregunta(memoria):
    h, _ = herramientas_con(memoria)
    preguntas = []
    texto = h.ejecutar(Orden("olvidar", "dentista"), lambda p: preguntas.append(p) or True)
    assert "nada anotado" in texto and preguntas == []


def test_olvidar_todo_pide_confirmacion(memoria):
    h, _ = herramientas_con(memoria)
    memoria.recordar("uno uno")
    memoria.recordar("dos dos")
    assert "no lo hago" in h.ejecutar(Orden("olvidar_todo"), lambda _: False)
    assert len(memoria.hechos) == 2
    assert "he olvidado 2 recuerdos" in h.ejecutar(Orden("olvidar_todo"), lambda _: True)


def test_sin_memoria_las_herramientas_avisan():
    h, _ = herramientas_con(None)
    for orden in (Orden("recordar", "algo"), Orden("olvidar", "algo"), Orden("olvidar_todo"), Orden("recuerdos")):
        assert "no está disponible" in h.ejecutar(orden, lambda _: True)


def test_orden_desde_claude_valida_la_memoria():
    assert orden_desde_claude("recordar", {"texto": " mi cumpleaños es el 3 de mayo "}) == Orden(
        "recordar", "mi cumpleaños es el 3 de mayo"
    )
    assert orden_desde_claude("olvidar", {"tema": "cumpleaños"}) == Orden("olvidar", "cumpleaños")
    for malo in (
        ("recordar", {"texto": "x"}),
        ("recordar", {"texto": "y" * (config.MEMORIA_MAX_CARACTERES + 1)}),
        ("recordar", {"texto": 7}),
        ("olvidar", {}),
        ("olvidar_todo", {}),  # Claude no puede borrarlo todo: solo lo pide el usuario
        ("recuerdos", {}),
    ):
        assert orden_desde_claude(*malo) is None, malo


def cerebro_con(memoria, confirmar=None):
    nube = NubeFalsa()
    confirmar = confirmar or Confirmador(True)
    return Cerebro(nube, confirmar, Herramientas(auditar=lambda **_: None, memoria=memoria), memoria), nube, confirmar


def test_los_recuerdos_viajan_a_claude_y_el_aviso_lo_dice(memoria):
    memoria.recordar("mi hermana se llama Ana")
    cerebro, nube, confirmar = cerebro_con(memoria)
    decir(cerebro.pensar("hola"))
    assert nube.recuerdos == [["mi hermana se llama Ana"]]
    assert confirmar.preguntas == [PREGUNTA_NUBE_CON_RECUERDOS]


def test_sin_recuerdos_el_aviso_es_el_de_siempre(memoria):
    cerebro, nube, confirmar = cerebro_con(memoria)
    decir(cerebro.pensar("hola"))
    assert nube.recuerdos == [[]] and confirmar.preguntas == [PREGUNTA_NUBE_CONVERSACION]


def test_si_se_desactiva_el_envio_los_recuerdos_no_salen(memoria, monkeypatch):
    monkeypatch.setattr(config, "MEMORIA_A_NUBE", False)
    memoria.recordar("mi hermana se llama Ana")
    cerebro, nube, confirmar = cerebro_con(memoria)
    decir(cerebro.pensar("hola"))
    assert nube.recuerdos == [[]] and confirmar.preguntas == [PREGUNTA_NUBE_CONVERSACION]


def test_recordar_por_voz_no_sale_a_la_nube(memoria):
    cerebro, nube, confirmar = cerebro_con(memoria)
    assert cerebro.pensar("recuerda que mi perro se llama Rocky").texto == "Anotado, señor."
    assert nube.llamadas == [] and confirmar.preguntas == []
    assert [h.texto for h in memoria.hechos] == ["mi perro se llama Rocky"]


def test_la_memoria_sobrevive_a_nueva_conversacion(memoria):
    cerebro, nube, _ = cerebro_con(memoria)
    cerebro.pensar("recuerda que mi perro se llama Rocky")
    cerebro.nueva_conversacion()
    decir(cerebro.pensar("hola"))
    assert nube.recuerdos == [["mi perro se llama Rocky"]]  # el historial se olvida; lo anotado no


def test_si_la_memoria_falla_el_asistente_arranca_sin_ella(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(config, "MEMORIA", tmp_path / "memoria.enc")
    (tmp_path / "memoria.enc").write_bytes(b"basura")
    monkeypatch.setattr(loop, "clave_memoria", lambda: Fernet.generate_key())
    assert loop._abrir_memoria() is None
    assert "Memoria desactivada" in capsys.readouterr().out
    assert (tmp_path / "memoria.enc").read_bytes() == b"basura"


def test_respuesta_sigue_siendo_simple():
    assert Respuesta("hola").frases is None
