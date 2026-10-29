from collections.abc import Callable, Iterator

import anthropic

from . import config
from .frases import Diferida, dividir_en_frases

HERRAMIENTAS_CLAUDE = [
    {
        "name": "abrir_app",
        "description": "Abre una aplicación del Mac por su nombre.",
        "input_schema": {
            "type": "object",
            "properties": {"nombre": {"type": "string", "description": "Nombre de la aplicación, por ejemplo Safari o Calendario"}},
            "required": ["nombre"],
        },
    },
    {
        "name": "cerrar_app",
        "description": "Cierra una aplicación del Mac. El sistema pide confirmación al usuario antes de hacerlo.",
        "input_schema": {
            "type": "object",
            "properties": {"nombre": {"type": "string", "description": "Nombre de la aplicación"}},
            "required": ["nombre"],
        },
    },
    {
        "name": "volumen",
        "description": "Ajusta el volumen del Mac: sube o baja un paso, lo silencia o lo fija en un nivel.",
        "input_schema": {
            "type": "object",
            "properties": {
                "accion": {"type": "string", "enum": ["subir", "bajar", "silenciar", "fijar"]},
                "nivel": {"type": "integer", "minimum": 0, "maximum": 100, "description": "Solo con la acción fijar"},
            },
            "required": ["accion"],
        },
    },
]


class ClienteClaude:
    def __init__(self, clave: str) -> None:
        self._cliente = anthropic.Anthropic(api_key=clave, timeout=config.TIEMPO_MAX_CLAUDE_S, max_retries=1)

    def frases(self, mensajes: list[dict], usar_herramienta: Callable[[str, dict], str]) -> Iterator[str | Diferida]:
        """Responde por frases, a medida que Claude las escribe.

        Solo viaja el texto de la conversación; nunca archivos ni datos del equipo. Si Claude pide una
        herramienta, `usar_herramienta` la ejecuta (con sus permisos) y Claude continúa con el resultado.
        """
        mensajes = list(mensajes)
        for _ in range(config.RONDAS_HERRAMIENTAS_MAX):
            with self._cliente.messages.stream(
                model=config.MODELO_CLAUDE,
                max_tokens=config.MAX_TOKENS_CLAUDE,
                system=config.INSTRUCCIONES_CLAUDE,
                messages=mensajes,
                tools=HERRAMIENTAS_CLAUDE,
            ) as flujo:
                yield from dividir_en_frases(flujo.text_stream)
                final = flujo.get_final_message()
            usos = [bloque for bloque in final.content if bloque.type == "tool_use"]
            if not usos:
                return
            resultados = []
            for uso in usos:
                # La herramienta puede hablar y escuchar: se ejecuta en el hilo principal, tras la voz pendiente.
                accion = Diferida(lambda uso=uso: usar_herramienta(uso.name, uso.input))
                yield accion
                resultado = accion.esperar()
                if resultado is None:
                    return
                resultados.append({"type": "tool_result", "tool_use_id": uso.id, "content": resultado})
            mensajes.append({"role": "assistant", "content": final.content})
            mensajes.append({"role": "user", "content": resultados})
