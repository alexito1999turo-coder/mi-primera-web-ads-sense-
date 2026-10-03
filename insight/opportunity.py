"""Oportunidad real, no oportunidad aparente.

La diferencia entre las dos es el descuento por AI Overviews. Una consulta
informacional en posicion 12 con 10.000 impresiones parece la mayor oportunidad
del informe y suele ser la peor inversion del mes.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .curves import click_retention, click_value, ctr_at
from .gsc import Report, Row

BAND_TOP = "ya arriba"
BAND_NEAR = "a tiro"
BAND_STRIKING = "distancia de golpeo"
BAND_FAR = "lejos"
BAND_UNKNOWN = "sin posicion"

# Objetivo realista por banda. Prometer la posicion 1 desde la 25 es vender
# humo; desde la 12 al 7 es un mes de trabajo creible.
TARGETS = {BAND_TOP: 1.0, BAND_NEAR: 3.0, BAND_STRIKING: 7.0, BAND_FAR: 15.0}

# Por debajo de esto, la fila es ruido estadistico y no se prioriza.
MIN_IMPRESSIONS = 30


def band_of(position: float) -> str:
    if position <= 0:
        return BAND_UNKNOWN
    if position <= 3:
        return BAND_TOP
    if position <= 10:
        return BAND_NEAR
    if position <= 30:
        return BAND_STRIKING
    return BAND_FAR


@dataclass
class Opportunity:
    row: Row
    band: str
    target: float
    raw_gain: float = 0.0        # clics que daria la curva sin descontar nada
    adjusted_gain: float = 0.0   # lo que queda tras la AI Overview
    measurable: bool = True

    @property
    def intent(self) -> str:
        return self.row.intent

    @property
    def retention(self) -> float:
        return click_retention(self.intent)

    @property
    def lost_to_aio(self) -> float:
        return round(self.raw_gain - self.adjusted_gain, 1)

    @property
    def value(self) -> float:
        """Valor esperado, no clics esperados.

        Es lo que de verdad reordena la lista. El objetivo no son visitas.
        """
        return round(self.adjusted_gain * click_value(self.intent), 2)

    @property
    def subject(self) -> str:
        return self.row.query or self.row.page

    def describe(self) -> str:
        if not self.measurable:
            return f"{self.subject}: sin posicion, oportunidad no medible."
        return (
            f"{self.subject} · pos {self.row.position:.1f} ({self.band}) · "
            f"{self.row.impressions} impresiones · {self.intent} · "
            f"+{self.adjusted_gain:.0f} clics/mes · valor {self.value:.0f} "
            f"(bruto +{self.raw_gain:.0f} clics, {self.lost_to_aio:.0f} se los "
            f"queda la respuesta generada)"
        )


def evaluate(row: Row) -> Opportunity:
    band = band_of(row.position)
    if band == BAND_UNKNOWN:
        return Opportunity(row=row, band=band, target=0.0, measurable=False)

    target = TARGETS[band]
    delta = max(0.0, ctr_at(target) - ctr_at(row.position))
    raw = row.impressions * delta
    adjusted = raw * click_retention(row.intent)
    return Opportunity(
        row=row, band=band, target=target,
        raw_gain=round(raw, 2), adjusted_gain=round(adjusted, 2),
    )


@dataclass
class OpportunityReport:
    opportunities: list[Opportunity] = field(default_factory=list)
    skipped_low_volume: int = 0
    unmeasurable: int = 0

    @property
    def measurable_items(self) -> list[Opportunity]:
        return [o for o in self.opportunities if o.measurable]

    @property
    def ranked(self) -> list[Opportunity]:
        """Por VALOR esperado. Es el orden en el que hay que trabajar."""
        return sorted(self.measurable_items, key=lambda o: -o.value)

    @property
    def ranked_by_clicks(self) -> list[Opportunity]:
        """Por clics brutos: el orden que daria el SEO clasico."""
        return sorted(self.measurable_items, key=lambda o: -o.raw_gain)

    @property
    def total_adjusted(self) -> float:
        return round(sum(o.adjusted_gain for o in self.opportunities), 1)

    @property
    def total_lost_to_aio(self) -> float:
        return round(sum(o.lost_to_aio for o in self.opportunities), 1)

    def demoted(self, min_drop: int = 2) -> list[tuple[str, int, int]]:
        """Filas que el SEO clasico pondria arriba y que aqui bajan.

        Es la salida que justifica el modulo. Compara el orden por clics brutos
        contra el orden por valor: el descuento por AI Overviews solo casi nunca
        da la vuelta a nada, pero el descuento MAS el valor del clic si.
        """
        by_clicks = self.ranked_by_clicks
        by_value = self.ranked
        moves: list[tuple[str, int, int]] = []
        for click_position, opportunity in enumerate(by_clicks, start=1):
            value_position = by_value.index(opportunity) + 1
            if value_position - click_position >= min_drop:
                moves.append((opportunity.subject, click_position, value_position))
        return moves

    def promoted(self, min_rise: int = 2) -> list[tuple[str, int, int]]:
        """Y las que suben: donde esta el dinero que el volumen escondia."""
        by_clicks = self.ranked_by_clicks
        by_value = self.ranked
        moves: list[tuple[str, int, int]] = []
        for value_position, opportunity in enumerate(by_value, start=1):
            click_position = by_clicks.index(opportunity) + 1
            if click_position - value_position >= min_rise:
                moves.append((opportunity.subject, click_position, value_position))
        return moves

    def describe(self) -> str:
        return (
            f"{len(self.ranked)} oportunidad(es) medible(s) · "
            f"+{self.total_adjusted:.0f} clics/mes estimados · "
            f"{self.total_lost_to_aio:.0f} clics se los queda la respuesta "
            f"generada · {self.skipped_low_volume} fila(s) descartada(s) por "
            f"volumen bajo · {self.unmeasurable} sin posicion. "
            "Curva de CTR, exposicion a AIO y valor del clic son priores de "
            "mercado, no mediciones de este sitio."
        )


def analyse(report: Report, min_impressions: int = MIN_IMPRESSIONS) -> OpportunityReport:
    result = OpportunityReport()
    for row in report.rows:
        if row.impressions < min_impressions:
            result.skipped_low_volume += 1
            continue
        opportunity = evaluate(row)
        if not opportunity.measurable:
            result.unmeasurable += 1
            continue
        result.opportunities.append(opportunity)
    return result
