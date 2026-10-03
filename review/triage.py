"""Triaje: quien se lleva los minutos del revisor.

Repartir la revision a ciegas es lo que hace que el coste humano crezca lineal
con el volumen. Aqui se reparte por riesgo.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from generator.pipeline import Production

if TYPE_CHECKING:  # solo para los tipos: evita el import circular en runtime
    from .log import RejectionLog

LEVEL_FULL = "completa"
LEVEL_SPOT = "muestreo"
LEVEL_AUTO = "automatica"

# Minutos estimados por nivel. Son la base del coste operativo y del precio.
MINUTES = {LEVEL_FULL: 25, LEVEL_SPOT: 8, LEVEL_AUTO: 0}

# Codigos que siempre exigen ojo humano, pasen o no las compuertas: tocan
# veracidad, no forma.
ALWAYS_HUMAN = {
    "afirmacion_sin_respaldo",
    "fuente_obligatoria_ausente",
    "dato_propio_ausente",
    "solape_con_publicado",
}


@dataclass
class Assignment:
    slug: str
    level: str
    minutes: int
    reasons: list[str] = field(default_factory=list)


@dataclass
class Queue:
    assignments: list[Assignment] = field(default_factory=list)

    @property
    def total_minutes(self) -> int:
        return sum(a.minutes for a in self.assignments)

    def by_level(self, level: str) -> list[Assignment]:
        return [a for a in self.assignments if a.level == level]

    def cost(self, hourly_rate: float) -> float:
        """Coste humano del lote. Es el numero que decide el precio de venta."""
        return round(self.total_minutes / 60 * hourly_rate, 2)

    def describe(self, hourly_rate: float = 20.0) -> str:
        return (
            f"{len(self.assignments)} paginas · "
            f"{len(self.by_level(LEVEL_FULL))} revision completa · "
            f"{len(self.by_level(LEVEL_SPOT))} muestreo · "
            f"{len(self.by_level(LEVEL_AUTO))} automatica · "
            f"{self.total_minutes} min · {self.cost(hourly_rate)} por lote"
        )


def assign(
    production: Production,
    history: "RejectionLog | None" = None,
) -> Assignment:
    """Decide el nivel de revision de una pagina."""
    slug = production.draft.slug if production.draft else "(sin borrador)"
    reasons: list[str] = []

    if production.aborted_reason:
        return Assignment(slug=slug, level=LEVEL_FULL, minutes=MINUTES[LEVEL_FULL],
                          reasons=["Brief incompleto: lo arregla una persona."])

    result = production.result
    assert result is not None  # hay borrador, luego hay resultado

    codes = {f.code for f in result.findings}

    if not result.passed:
        reasons.append(
            f"{len(result.blocking)} compuerta(s) bloqueante(s) sin resolver."
        )
        return Assignment(slug=slug, level=LEVEL_FULL, minutes=MINUTES[LEVEL_FULL],
                          reasons=reasons)

    # Paso las compuertas, pero hubo que repararlo: el modelo fallo primero y
    # eso correlaciona con fallos que las compuertas no ven.
    if production.repairs:
        reasons.append(f"Necesito {production.repairs} reparacion(es).")

    historical = codes & ALWAYS_HUMAN
    for attempt in production.attempts[:-1]:
        historical |= {f.code for f in attempt.result.findings} & ALWAYS_HUMAN
    if historical:
        reasons.append(
            "Toco veracidad en algun intento: " + ", ".join(sorted(historical))
        )

    # Lo que esta pagina ya ha fallado historicamente en este cliente.
    if history is not None:
        repeat = history.recurring_codes()
        if codes & repeat:
            reasons.append(
                "Repite un patron ya rechazado antes: "
                + ", ".join(sorted(codes & repeat))
            )

    if historical or (history is not None and codes & history.recurring_codes()):
        return Assignment(slug=slug, level=LEVEL_FULL, minutes=MINUTES[LEVEL_FULL],
                          reasons=reasons)

    # Las notas de cobertura no son defectos de la pagina: no gastan revisor.
    if production.repairs or result.warnings:
        if not reasons:
            reasons.append("Paso con avisos.")
        return Assignment(slug=slug, level=LEVEL_SPOT, minutes=MINUTES[LEVEL_SPOT],
                          reasons=reasons)

    return Assignment(slug=slug, level=LEVEL_AUTO, minutes=MINUTES[LEVEL_AUTO],
                      reasons=["Limpio a la primera."])


def build_queue(productions: list[Production], history: "RejectionLog | None" = None) -> Queue:
    queue = Queue()
    for production in productions:
        queue.assignments.append(assign(production, history))
    # Lo mas arriesgado primero: si el dia se corta, se corta por lo seguro.
    order = {LEVEL_FULL: 0, LEVEL_SPOT: 1, LEVEL_AUTO: 2}
    queue.assignments.sort(key=lambda a: order[a.level])
    return queue
