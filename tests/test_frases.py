import threading

from asistente.frases import Diferida, dividir_en_frases, limpiar


def test_une_frases_cortas_y_corta_en_las_completas():
    trozos = ["Hola, señor. ¿Cómo ", "está usted hoy? Muy bien."]
    assert list(dividir_en_frases(trozos)) == ["Hola, señor. ¿Cómo está usted hoy?", "Muy bien."]


def test_emite_la_primera_frase_antes_de_recibir_el_resto():
    emitidas = []

    def trozos():
        yield "Claro que sí, señor, con mucho gusto le cuento. "
        emitidas.append("llegó el primer trozo")
        yield "Después sigo con más detalles."

    resultado = []
    for frase in dividir_en_frases(trozos()):
        resultado.append((frase, list(emitidas)))
    assert resultado[0] == ("Claro que sí, señor, con mucho gusto le cuento.", [])


def test_la_primera_frase_larga_se_corta_en_una_coma():
    texto = "Claro señor, con muchísimo gusto le explico cómo funciona esto, y además más cosas."
    assert list(dividir_en_frases([texto])) == [
        "Claro señor, con muchísimo gusto le explico cómo funciona esto,",
        "y además más cosas.",
    ]


def test_los_decimales_no_cortan_la_frase():
    assert list(dividir_en_frases(["La temperatura es de 3.5 grados hoy en la ciudad."])) == [
        "La temperatura es de 3.5 grados hoy en la ciudad."
    ]


def test_se_quitan_los_simbolos_de_markdown():
    assert limpiar("**Hola**, `señor` #1") == "Hola, señor 1"
    assert list(dividir_en_frases(["**Listo** señor, ya está hecho. "])) == ["Listo señor, ya está hecho."]


def test_texto_vacio_no_emite_nada():
    assert list(dividir_en_frases(["", "  "])) == []


def test_diferida_devuelve_el_resultado_y_propaga_errores():
    ok = Diferida(lambda: "hecho")
    ok.ejecutar()
    assert ok.esperar() == "hecho"

    def falla():
        raise ValueError("mal")

    mala = Diferida(falla)
    mala.ejecutar()
    try:
        mala.esperar()
    except ValueError:
        pass
    else:
        raise AssertionError("debía propagar el error")


def test_diferida_cancelada_devuelve_none():
    nunca = Diferida(lambda: "x")
    assert nunca.esperar(cancelada=lambda: True) is None


def test_diferida_espera_a_que_otro_hilo_la_ejecute():
    d = Diferida(lambda: "ok")
    threading.Timer(0.05, d.ejecutar).start()
    assert d.esperar() == "ok"
