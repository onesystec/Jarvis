import anthropic

from . import config


class ClienteClaude:
    def __init__(self, clave: str) -> None:
        self._cliente = anthropic.Anthropic(api_key=clave, timeout=config.TIEMPO_MAX_CLAUDE_S, max_retries=1)

    def responder(self, mensajes: list[dict]) -> str:
        """Envía solo el texto de la conversación; nunca archivos ni datos del equipo."""
        respuesta = self._cliente.messages.create(
            model=config.MODELO_CLAUDE,
            max_tokens=config.MAX_TOKENS_CLAUDE,
            system=config.INSTRUCCIONES_CLAUDE,
            messages=mensajes,
        )
        return "".join(bloque.text for bloque in respuesta.content if bloque.type == "text").strip()
