"""Acceso al modelo. Inyectable, para que el pipeline se pruebe sin gastar.

Decisiones de coste, que son las que mandan en este modulo:

- Modelo por defecto claude-opus-5-5 y esfuerzo alto. Generar cuesta $0.30-0.60
  por pagina; revisar a mano cuesta $6-15. Ahorrar en el modelo es ahorrar en
  lo barato para pagar mas de lo caro.
- Cache de prompt para el contexto estable (voz de marca, contexto del sitio):
  se envia una vez y se reutiliza en todas las paginas del lote.
- API de lotes cuando el trabajo no es interactivo: 50% de descuento, y generar
  contenido nunca es sensible a latencia.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

DEFAULT_MODEL = "claude-opus-5-5"
DEFAULT_EFFORT = "high"
DEFAULT_MAX_TOKENS = 64000  # con streaming, para que quepa una pagina larga


class LLM(Protocol):
    """Lo minimo que el pipeline necesita de un modelo."""

    def complete(
        self,
        system: str,
        prompt: str,
        max_tokens: int = DEFAULT_MAX_TOKENS,
        effort: str = DEFAULT_EFFORT,
    ) -> str: ...


@dataclass
class Call:
    """Una llamada registrada. Sirve para auditar coste y para las pruebas."""

    system: str
    prompt: str
    effort: str
    max_tokens: int


@dataclass
class ScriptedLLM:
    """Modelo falso que devuelve respuestas preparadas, en orden.

    Con esto el pipeline entero se verifica sin clave y sin gastar.
    """

    responses: list[str] = field(default_factory=list)
    calls: list[Call] = field(default_factory=list)
    fallback: str = ""

    def complete(
        self,
        system: str,
        prompt: str,
        max_tokens: int = DEFAULT_MAX_TOKENS,
        effort: str = DEFAULT_EFFORT,
    ) -> str:
        self.calls.append(
            Call(system=system, prompt=prompt, effort=effort, max_tokens=max_tokens)
        )
        index = len(self.calls) - 1
        if index < len(self.responses):
            return self.responses[index]
        return self.fallback


class AnthropicLLM:
    """Cliente real. El SDK se importa al usarlo, no al importar el modulo.

    Asi el paquete funciona, y se prueba, en una maquina sin `anthropic`
    instalado ni clave configurada.
    """

    def __init__(
        self,
        model: str = DEFAULT_MODEL,
        client=None,
        cache_system: bool = True,
    ) -> None:
        self.model = model
        self.cache_system = cache_system
        self._client = client

    @property
    def client(self):
        if self._client is None:
            try:
                import anthropic
            except ImportError as exc:  # pragma: no cover - depende del entorno
                raise RuntimeError(
                    "Falta el SDK: pip install anthropic. Para probar el pipeline "
                    "sin gastar, usa ScriptedLLM."
                ) from exc
            # Sin api_key: el SDK resuelve ANTHROPIC_API_KEY, ANTHROPIC_AUTH_TOKEN
            # o el perfil de `ant auth login`. Nunca una clave en el codigo.
            self._client = anthropic.Anthropic()
        return self._client

    def _system_blocks(self, system: str) -> list[dict]:
        block: dict = {"type": "text", "text": system}
        if self.cache_system:
            # El contexto estable se cachea: se paga una vez por lote en vez de
            # una vez por pagina.
            block["cache_control"] = {"type": "ephemeral"}
        return [block]

    def complete(
        self,
        system: str,
        prompt: str,
        max_tokens: int = DEFAULT_MAX_TOKENS,
        effort: str = DEFAULT_EFFORT,
    ) -> str:
        # Streaming porque max_tokens es alto: sin el, la peticion se va por
        # timeout HTTP antes de terminar una pagina larga.
        with self.client.messages.stream(
            model=self.model,
            max_tokens=max_tokens,
            system=self._system_blocks(system),
            thinking={"type": "adaptive"},
            output_config={"effort": effort},
            messages=[{"role": "user", "content": prompt}],
        ) as stream:
            message = stream.get_final_message()

        if getattr(message, "stop_reason", None) == "refusal":
            details = getattr(message, "stop_details", None)
            category = getattr(details, "category", "sin categoria")
            raise RuntimeError(f"El modelo declino la peticion ({category}).")

        return "".join(
            block.text for block in message.content if block.type == "text"
        )


def batch_requests(
    jobs: list[tuple[str, str, str]],
    model: str = DEFAULT_MODEL,
    max_tokens: int = 16000,
    effort: str = DEFAULT_EFFORT,
) -> list[dict]:
    """Construye peticiones para la API de lotes (50% de descuento).

    `jobs` son tripletes (custom_id, system, prompt). Se devuelven diccionarios
    en el formato que espera `client.messages.batches.create`, sin importar el
    SDK: asi esta funcion se prueba igual que el resto.

    Los resultados de un lote llegan en cualquier orden: hay que indexarlos por
    `custom_id`, nunca por posicion.
    """
    return [
        {
            "custom_id": custom_id,
            "params": {
                "model": model,
                "max_tokens": max_tokens,
                "system": [
                    {
                        "type": "text",
                        "text": system,
                        "cache_control": {"type": "ephemeral"},
                    }
                ],
                "thinking": {"type": "adaptive"},
                "output_config": {"effort": effort},
                "messages": [{"role": "user", "content": prompt}],
            },
        }
        for custom_id, system, prompt in jobs
    ]
