"""Metricas por compuerta, con la honestidad estadistica por delante."""

from __future__ import annotations

import math
from dataclasses import dataclass, field

# Por debajo de esto no se recomienda nada: una proporcion sobre cinco casos no
# es una medicion, es una anecdota con decimales.
MIN_SAMPLE = 12
# Confianza del intervalo de Wilson (1,96 = 95%).
Z = 1.96

# Umbrales de decision, sobre el LIMITE INFERIOR del intervalo, no sobre la
# proporcion puntual: lo que importa es lo peor que la compuerta puede ser con
# los datos que hay, no su mejor cara.
PRECISION_DOWNGRADE = 0.50   # bloqueante que acierta menos de la mitad: es ruido
PRECISION_PROMOTE = 0.85     # aviso que casi siempre acierta: deberia bloquear
MISS_THRESHOLD = 3           # rechazos del revisor sin compuerta que los viera


def wilson_lower(successes: int, total: int, z: float = Z) -> float:
    """Limite inferior del intervalo de Wilson para una proporcion.

    Con 3 de 3 aciertos, la proporcion puntual es 1,0 y no dice nada; Wilson da
    0,44, que es lo honesto. Es la diferencia entre medir y presumir.
    """
    if total <= 0:
        return 0.0
    phat = successes / total
    denominator = 1 + z * z / total
    centre = phat + z * z / (2 * total)
    margin = z * math.sqrt(phat * (1 - phat) / total + z * z / (4 * total * total))
    return max(0.0, (centre - margin) / denominator)


@dataclass
class GateMetrics:
    """Lo que se sabe de una compuerta."""

    code: str
    severity: str = ""
    # Todas las paginas juzgadas, se activara o no esta compuerta. Es el
    # denominador honesto: los otros contadores solo cuentan las paginas donde
    # esta compuerta era concluyente, y usarlos como total enganaba.
    pages_seen: int = 0
    fired_and_rejected: int = 0   # acierto: marco algo que el revisor rechazo
    fired_and_approved: int = 0   # falso positivo: marco algo que estaba bien
    silent_and_rejected: int = 0  # no marco algo que el revisor rechazo por ESTE motivo
    silent_and_approved: int = 0

    @property
    def fired(self) -> int:
        return self.fired_and_rejected + self.fired_and_approved

    @property
    def conclusive(self) -> int:
        """Paginas donde esta compuerta era concluyente: acerto o fallo."""
        return self.fired + self.silent_and_rejected + self.silent_and_approved

    @property
    def precision(self) -> float | None:
        """De lo que marca, cuanto estaba de verdad mal. None si no marco nada."""
        return self.fired_and_rejected / self.fired if self.fired else None

    @property
    def precision_floor(self) -> float | None:
        if not self.fired:
            return None
        return wilson_lower(self.fired_and_rejected, self.fired)

    @property
    def recall(self) -> float | None:
        """De lo que estaba mal por este motivo, cuanto vio."""
        relevant = self.fired_and_rejected + self.silent_and_rejected
        return self.fired_and_rejected / relevant if relevant else None

    @property
    def enough_sample(self) -> bool:
        return self.fired >= MIN_SAMPLE

    @property
    def wasted_reviews(self) -> int:
        """Revisiones gastadas por esta compuerta sin encontrar nada."""
        return self.fired_and_approved

    def describe(self) -> str:
        if not self.fired:
            return (
                f"{self.code}: no se activo ni una vez en {self.pages_seen} "
                "pagina(s) juzgada(s). No se puede medir."
            )
        precision = self.precision or 0.0
        floor = self.precision_floor or 0.0
        sample = "" if self.enough_sample else "  (MUESTRA INSUFICIENTE)"
        recall = (
            f" · cobertura {self.recall * 100:.0f}%" if self.recall is not None else ""
        )
        return (
            f"{self.code} [{self.severity}]: se activo {self.fired} vez/veces, "
            f"precision {precision * 100:.0f}% (suelo Wilson {floor * 100:.0f}%)"
            f"{recall} · {self.wasted_reviews} revision(es) gastada(s){sample}"
        )


@dataclass
class MissedPattern:
    """Un motivo de rechazo que ninguna compuerta vio. Es una compuerta que falta."""

    reason: str
    count: int = 0
    examples: list[str] = field(default_factory=list)
