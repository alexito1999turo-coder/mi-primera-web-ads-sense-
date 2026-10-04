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
class Usage:
    """Lo que una llamada gasto de verdad.

    Sin esto, el coste por pagina de la propuesta comercial es una suposicion
    con dos decimales, que es la peor clase de suposicion: parece medida. Los
    tokens de cache van aparte porque se facturan distinto, y porque el ahorro
    del cache es justo lo que hay que poder demostrar.
    """

    input_tokens: int = 0
    output_tokens: int = 0
    cache_write_tokens: int = 0
    cache_read_tokens: int = 0
    calls: int = 0

    def add(self, otra: "Usage") -> None:
        self.input_tokens += otra.input_tokens
        self.output_tokens += otra.output_tokens
        self.cache_write_tokens += otra.cache_write_tokens
        self.cache_read_tokens += otra.cache_read_tokens
        self.calls += otra.calls

    @classmethod
    def from_message(cls, message) -> "Usage":
        """Lee el uso de una respuesta del SDK, sin romperse si falta un campo.

        Los nombres de los campos de cache han cambiado entre versiones del
        SDK. Un `getattr` con defecto aqui vale mas que una version fijada:
        el peor fallo posible en este modulo es que una actualizacion del SDK
        tumbe la generacion por un contador.
        """
        uso = getattr(message, "usage", None)
        if uso is None:
            return cls(calls=1)
        return cls(
            input_tokens=int(getattr(uso, "input_tokens", 0) or 0),
            output_tokens=int(getattr(uso, "output_tokens", 0) or 0),
            cache_write_tokens=int(
                getattr(uso, "cache_creation_input_tokens", 0) or 0),
            cache_read_tokens=int(
                getattr(uso, "cache_read_input_tokens", 0) or 0),
            calls=1,
        )

    @property
    def total_input(self) -> int:
        return self.input_tokens + self.cache_write_tokens + self.cache_read_tokens

    def describe(self) -> str:
        if not self.calls:
            return "Sin llamadas registradas."
        ahorro = ""
        if self.cache_read_tokens:
            leidos = self.cache_read_tokens
            ahorro = (f"; {leidos:,} token(s) servidos de cache"
                      .replace(",", "."))
        return (f"{self.calls} llamada(s): {self.total_input:,} de entrada y "
                f"{self.output_tokens:,} de salida{ahorro}.").replace(",", ".")


@dataclass
class ScriptedLLM:
    """Modelo falso. Con esto el pipeline se verifica sin clave y sin gastar.

    Tres modos, por precedencia:

    - `routes`: la clave que aparezca en el prompt decide la respuesta. Es el
      modo correcto para un lote, porque el orden global de llamadas se
      desalinea en cuanto una pagina necesita reparacion.
    - `responses`: por orden de llamada. Vale para una sola pagina.
    - `fallback`: lo demas.
    """

    responses: list[str] = field(default_factory=list)
    routes: dict[str, str] = field(default_factory=dict)
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
        # La clave mas larga primero: una clave corta puede estar contenida en
        # otra mas especifica y robarle la respuesta.
        for key in sorted(self.routes, key=len, reverse=True):
            if key in prompt:
                return self.routes[key]
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
        # Se acumula por instancia: un lote entero da el coste del lote sin
        # tener que instrumentar el pipeline por fuera.
        self.usage = Usage()

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

        self.usage.add(Usage.from_message(message))

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
