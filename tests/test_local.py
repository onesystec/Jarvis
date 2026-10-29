import os
import stat
import subprocess
import sys
import threading
import time
from pathlib import Path

import pytest

from asistente import config, vigilante
from asistente.cerebro import Cerebro
from asistente.integridad import sha256
from asistente.local import ModeloLocal

from .test_cerebro import Confirmador, NubeFalsa, decir

SERVIDOR_FALSO = """#!/usr/bin/env python3
import json, os, socketserver, sys
from http.server import BaseHTTPRequestHandler

args = sys.argv[1:]
ruta = args[args.index("--host") + 1]
clave = open(args[args.index("--api-key-file") + 1]).read()
if os.environ.get("FALSO_SALIR"):
    sys.exit(3)

class H(BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def _autorizado(self):
        if self.headers.get("Authorization") != "Bearer " + clave:
            self.send_response(401); self.end_headers(); return False
        return True
    def do_GET(self):
        if self._autorizado():
            self.send_response(200); self.end_headers(); self.wfile.write(b'{"status":"ok"}')
    def do_POST(self):
        cuerpo = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        if not self._autorizado(): return
        sistema = cuerpo["messages"][0]["content"]
        texto = "Su hermana se llama Ana. Con gusto." if "Ana" in sistema else "No lo sé, señor. Pregunte otra cosa."
        self.send_response(200); self.send_header("Content-Type", "text/event-stream"); self.end_headers()
        for trozo in (texto[:12], texto[12:]):
            self.wfile.write(("data: " + json.dumps({"choices": [{"delta": {"content": trozo}}]}) + "\\n\\n").encode())
        self.wfile.write(b"data: [DONE]\\n\\n")

class S(socketserver.UnixStreamServer):
    def get_request(self):
        conexion, _ = super().get_request()
        return conexion, ("local", 0)

S(ruta, H).serve_forever()
"""


@pytest.fixture
def entorno(tmp_path):
    binario = tmp_path / "llama-server"
    binario.write_text(SERVIDOR_FALSO)
    binario.chmod(0o755)
    modelo = tmp_path / "modelo.gguf"
    modelo.write_bytes(b"pesos de mentira" * 100)
    return modelo, str(binario), sha256(modelo)


def local_falso(entorno):
    modelo, binario, sha = entorno
    return ModeloLocal(modelo, binario, sha)


def test_arranca_bajo_demanda_responde_por_frases_y_se_libera(entorno):
    local = local_falso(entorno)
    assert local.disponible() and not local.activo
    frases = list(local.frases([{"role": "user", "content": "¿cómo se llama mi hermana?"}], recuerdos=["mi hermana se llama Ana"]))
    assert frases[0] == config.LOCAL_AVISO  # avisa mientras carga
    assert "Ana" in " ".join(frases[1:])  # los recuerdos llegan al modelo, sin salir del equipo
    assert local.activo
    carpeta = local._carpeta
    assert stat.S_IMODE(carpeta.stat().st_mode) == 0o700
    assert stat.S_IMODE((carpeta / "clave").stat().st_mode) == 0o600
    assert (carpeta / "llm.sock").exists()
    # una segunda pregunta reutiliza el servidor, sin avisar de nuevo
    segunda = list(local.frases([{"role": "user", "content": "otra"}]))
    assert config.LOCAL_AVISO not in segunda and "No lo sé" in " ".join(segunda)
    proceso = local._proceso
    local.liberar()
    assert not local.activo and proceso.poll() is not None and not carpeta.exists()
    local.liberar()  # liberar dos veces no falla


def test_la_clave_es_obligatoria(entorno):
    local = local_falso(entorno)
    list(local.frases([{"role": "user", "content": "hola"}]))
    try:
        from asistente.local import _ConexionUnix

        conexion = _ConexionUnix(str(local._carpeta / "llm.sock"), 5.0)
        conexion.request("GET", "/health")
        assert conexion.getresponse().status == 401
    finally:
        local.liberar()


def test_un_modelo_alterado_no_se_carga(entorno):
    modelo, binario, sha = entorno
    modelo.write_bytes(modelo.read_bytes() + b"x")
    local = ModeloLocal(modelo, binario, sha)
    with pytest.raises(RuntimeError, match="hash"):
        list(local.frases([{"role": "user", "content": "hola"}]))
    assert not local.activo and local._carpeta is None


def test_si_el_servidor_se_cae_al_arrancar_se_avisa(entorno, monkeypatch):
    monkeypatch.setenv("FALSO_SALIR", "1")
    local = local_falso(entorno)
    with pytest.raises(RuntimeError, match="se cerró"):
        list(local.frases([{"role": "user", "content": "hola"}]))
    assert not local.activo and local._carpeta is None


def test_si_tarda_demasiado_en_arrancar_se_rinde(entorno, monkeypatch):
    monkeypatch.setattr(config, "LOCAL_ESPERA_ARRANQUE_S", 0.3)
    modelo, _, sha = entorno
    lento = modelo.parent / "dormilon"
    lento.write_text("#!/usr/bin/env python3\nimport time\ntime.sleep(30)\n")
    lento.chmod(0o755)
    local = ModeloLocal(modelo, str(lento), sha)
    with pytest.raises(RuntimeError, match="tardó demasiado"):
        list(local.frases([{"role": "user", "content": "hola"}]))
    assert not local.activo


def test_disponibilidad(entorno, monkeypatch, tmp_path):
    modelo, binario, sha = entorno
    assert ModeloLocal(modelo, binario, sha).disponible()
    assert not ModeloLocal(tmp_path / "no-existe.gguf", binario, sha).disponible()
    assert not ModeloLocal(modelo, str(tmp_path / "no-existe"), sha).disponible()
    monkeypatch.setattr(config, "LOCAL_ACTIVO", False)
    assert not ModeloLocal(modelo, binario, sha).disponible()


# --- guardián -------------------------------------------------------------------------------------


def test_el_guardian_cierra_el_servidor_si_el_padre_muere(tmp_path):
    carpeta = tmp_path / "jv"
    carpeta.mkdir()
    padre = subprocess.Popen([sys.executable, "-c", "pass"])
    padre.wait()  # un pid que ya no existe
    hijo = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])
    threading.Thread(target=hijo.wait, daemon=True).start()  # recoge al hijo como haría el sistema si el padre murió
    inicio = time.monotonic()
    vigilante.vigilar(padre.pid, hijo.pid, str(carpeta), pausa=0.05)
    hijo.wait(timeout=5)
    assert hijo.returncode != 0 and not carpeta.exists() and time.monotonic() - inicio < 5


def test_el_guardian_termina_si_el_servidor_ya_cerro(tmp_path):
    carpeta = tmp_path / "jv"
    carpeta.mkdir()
    hijo = subprocess.Popen([sys.executable, "-c", "pass"])
    hijo.wait()
    vigilante.vigilar(os.getpid(), hijo.pid, str(carpeta), pausa=0.05)
    assert not carpeta.exists()


# --- cerebro --------------------------------------------------------------------------------------


class LocalFalso:
    def __init__(self, disponible=True, respuesta=("Respuesta local.",), fallo=None):
        self._disponible, self.respuesta, self.fallo = disponible, respuesta, fallo
        self.mensajes: list[list[dict]] = []
        self.recuerdos: list[list[str]] = []
        self.liberado = 0

    def disponible(self):
        return self._disponible

    def frases(self, mensajes, usar_herramienta=None, recuerdos=(), web=False, marcar_externo=None):
        self.mensajes.append(list(mensajes))
        self.recuerdos.append(list(recuerdos))
        if self.fallo:
            raise self.fallo
        yield from self.respuesta

    def liberar(self):
        self.liberado += 1


def test_sin_clave_de_claude_conversa_con_el_modelo_local():
    local = LocalFalso()
    cerebro = Cerebro(None, Confirmador(), local=local)
    assert decir(cerebro.pensar("hola")) == "Respuesta local."


def test_decir_no_a_claude_se_resuelve_en_privado_sin_enviar_nada():
    nube, local, confirmar = NubeFalsa(), LocalFalso(), Confirmador(False)
    cerebro = Cerebro(nube, confirmar, local=local)
    assert decir(cerebro.pensar("cuéntame algo")) == "De acuerdo, lo resuelvo en privado, aquí en el equipo. Respuesta local."
    assert decir(cerebro.pensar("y más")) == "Respuesta local."
    assert nube.llamadas == [] and len(confirmar.preguntas) == 1  # no se vuelve a preguntar


def test_modo_privado_por_voz_y_su_historial_no_viaja_a_la_nube():
    nube, local, confirmar = NubeFalsa(), LocalFalso(), Confirmador(True)
    cerebro = Cerebro(nube, confirmar, local=local)
    assert "nada sale de este equipo" in cerebro.pensar("habla en privado").texto
    decir(cerebro.pensar("mi secreto es que me gustan los pulpos"))
    assert nube.llamadas == [] and confirmar.preguntas == []
    assert "vuelvo al modo normal" in cerebro.pensar("sal del modo privado").texto
    decir(cerebro.pensar("ahora en abierto"))
    assert nube.llamadas == [[{"role": "user", "content": "ahora en abierto"}]]  # nada de lo privado


def test_los_recuerdos_van_al_modelo_local_aunque_no_salgan_a_la_nube(monkeypatch, tmp_path):
    from cryptography.fernet import Fernet

    from asistente.memoria import Memoria

    monkeypatch.setattr(config, "MEMORIA_A_NUBE", False)
    memoria = Memoria(tmp_path / "m.enc", Fernet.generate_key())
    memoria.recordar("mi hermana se llama Ana")
    local = LocalFalso()
    cerebro = Cerebro(None, Confirmador(), memoria=memoria, local=local)
    decir(cerebro.pensar("hola"))
    assert local.recuerdos == [["mi hermana se llama Ana"]]


def test_modo_privado_sin_modelo_avisa_y_no_cambia_nada():
    cerebro = Cerebro(NubeFalsa(), Confirmador(), local=LocalFalso(disponible=False))
    assert "no está disponible" in cerebro.pensar("modo privado").texto
    assert decir(cerebro.pensar("hola")) == "Respuesta de Claude."


def test_si_el_modelo_local_falla_se_dice_y_no_se_guarda_en_el_historial():
    local = LocalFalso(fallo=RuntimeError("se cayó"))
    cerebro = Cerebro(None, Confirmador(), local=local)
    assert "no está disponible ahora mismo" in decir(cerebro.pensar("hola"))
    assert cerebro._historial_privado == []


def test_al_terminar_la_conversacion_se_libera_el_modelo_y_se_olvida_lo_privado():
    local = LocalFalso()
    cerebro = Cerebro(None, Confirmador(), local=local)
    decir(cerebro.pensar("hola"))
    assert len(cerebro._historial_privado) == 2
    cerebro.terminar_conversacion()
    assert local.liberado == 1
    cerebro.nueva_conversacion()
    assert cerebro._historial_privado == []
    Cerebro(None, Confirmador()).terminar_conversacion()  # sin modelo local no pasa nada


def test_el_aviso_de_carga_no_queda_en_el_historial():
    local = LocalFalso(respuesta=(config.LOCAL_AVISO, "Hola, señor."))
    cerebro = Cerebro(None, Confirmador(), local=local)
    decir(cerebro.pensar("hola"))
    assert cerebro._historial_privado[1]["content"] == "Hola, señor."


def test_el_modelo_real_no_se_toca_en_los_tests():
    assert Path(config.MODELO_LOCAL).name == "qwen2.5-1.5b-instruct-q4_k_m.gguf"
    assert len(config.SHA256_MODELO_LOCAL) == 64
