"""Reasignacion del plan con dos periodos de datos reales.

Su plan se decide el dia uno y no se vuelve a mirar. Este compara el periodo
anterior con el actual y mueve el esfuerzo. Lo que no hace es confundir ruido
con tendencia: por debajo de un volumen minimo y de un cambio relativo minimo,
la respuesta es "todavia no se sabe", que es una respuesta.
"""

from __future__ import annotations

from textos import plural

from dataclasses import dataclass, field
from urllib.parse import urlparse

from clusters.graph import Graph

from .gsc import Report
from .opportunity import OpportunityReport

DECISION_INVEST = "invertir"
DECISION_HOLD = "mantener"
DECISION_RETIRE = "retirar"
DECISION_UNKNOWN = "sin datos"

# Umbrales anti-ruido. Una subida del 40% sobre 12 impresiones no es nada.
MIN_IMPRESSIONS_FOR_TREND = 100
MIN_RELATIVE_CHANGE = 0.20
# Tras este tiempo sin arrancar, el cluster deja de llevarse esfuerzo.
STALLED_PERIODS = 2


@dataclass
class ClusterSignal:
    cluster_id: str
    impressions_before: int = 0
    impressions_now: int = 0
    clicks_now: int = 0
    value_now: float = 0.0
    pages: int = 0

    @property
    def change(self) -> float | None:
        if self.impressions_before == 0:
            return None if self.impressions_now == 0 else 1.0
        return (self.impressions_now - self.impressions_before) / self.impressions_before

    @property
    def total_impressions(self) -> int:
        return self.impressions_before + self.impressions_now

    @property
    def enough_volume(self) -> bool:
        return self.total_impressions >= MIN_IMPRESSIONS_FOR_TREND


@dataclass
class Decision:
    cluster_id: str
    decision: str
    rationale: str
    signal: ClusterSignal

    def describe(self) -> str:
        change = self.signal.change
        trend = "sin base" if change is None else f"{change * 100:+.0f}%"
        return (
            f"{self.cluster_id}: **{self.decision}** · "
            f"{self.signal.impressions_before} -> {self.signal.impressions_now} "
            f"impresiones ({trend}) · valor {self.signal.value_now:.0f} — "
            f"{self.rationale}"
        )


def _slug_of(url: str) -> str:
    path = urlparse(url).path.strip("/")
    return path.rsplit("/", 1)[-1] if path else ""


def collect(
    graph: Graph,
    before: Report,
    now: Report,
    opportunities: OpportunityReport | None = None,
) -> dict[str, ClusterSignal]:
    """Agrupa las filas de Search Console por cluster del grafo."""
    signals: dict[str, ClusterSignal] = {}
    for cluster in graph.clusters:
        signals[cluster.id] = ClusterSignal(
            cluster_id=cluster.id, pages=cluster.size
        )

    slug_to_cluster = {
        page.slug: cluster.id
        for cluster in graph.clusters
        for page in cluster.pages
    }

    def attribute(report: Report, field_name: str) -> None:
        for row in report.rows:
            cluster_id = slug_to_cluster.get(_slug_of(row.page))
            if cluster_id is None:
                continue
            signal = signals[cluster_id]
            setattr(signal, field_name, getattr(signal, field_name) + row.impressions)
            if field_name == "impressions_now":
                signal.clicks_now += row.clicks

    attribute(before, "impressions_before")
    attribute(now, "impressions_now")

    if opportunities is not None:
        for opportunity in opportunities.measurable_items:
            cluster_id = slug_to_cluster.get(_slug_of(opportunity.row.page))
            if cluster_id is not None:
                signals[cluster_id].value_now += opportunity.value

    return signals


def decide(
    signals: dict[str, ClusterSignal],
    min_change: float = MIN_RELATIVE_CHANGE,
) -> list[Decision]:
    decisions: list[Decision] = []
    for cluster_id, signal in signals.items():
        if not signal.enough_volume:
            decisions.append(
                Decision(
                    cluster_id=cluster_id,
                    decision=DECISION_UNKNOWN,
                    rationale=(
                        f"Solo {signal.total_impressions} impresiones entre los dos "
                        f"periodos (hacen falta {MIN_IMPRESSIONS_FOR_TREND}). Todavia "
                        "no se sabe, y eso es una respuesta."
                    ),
                    signal=signal,
                )
            )
            continue

        change = signal.change
        if change is None:
            decisions.append(
                Decision(
                    cluster_id=cluster_id,
                    decision=DECISION_UNKNOWN,
                    rationale="Sin impresiones en ninguno de los dos periodos.",
                    signal=signal,
                )
            )
        elif change >= min_change:
            decisions.append(
                Decision(
                    cluster_id=cluster_id,
                    decision=DECISION_INVEST,
                    rationale=(
                        f"Subiendo {change * 100:.0f}% con valor {signal.value_now:.0f}. "
                        "Google ya le esta dando sitio: ampliar el cluster aqui "
                        "rinde mas que abrir uno nuevo."
                    ),
                    signal=signal,
                )
            )
        elif change <= -min_change:
            decisions.append(
                Decision(
                    cluster_id=cluster_id,
                    decision=DECISION_RETIRE,
                    rationale=(
                        f"Cayendo {change * 100:.0f}% con volumen suficiente para "
                        "saberlo. Dejar de alimentarlo y revisar si el problema es "
                        "la intencion o la competencia."
                    ),
                    signal=signal,
                )
            )
        else:
            decisions.append(
                Decision(
                    cluster_id=cluster_id,
                    decision=DECISION_HOLD,
                    rationale=(
                        f"Estable ({change * 100:+.0f}%, por debajo del "
                        f"{min_change * 100:.0f}% que se considera senal). Mantener "
                        "sin ampliar."
                    ),
                    signal=signal,
                )
            )

    order = {
        DECISION_INVEST: 0, DECISION_HOLD: 1,
        DECISION_RETIRE: 2, DECISION_UNKNOWN: 3,
    }
    decisions.sort(key=lambda d: (order[d.decision], -d.signal.value_now))
    return decisions


@dataclass
class Reallocation:
    decisions: list[Decision] = field(default_factory=list)

    def by_decision(self, decision: str) -> list[Decision]:
        return [d for d in self.decisions if d.decision == decision]

    def budget(self, pages: int) -> dict[str, int]:
        """Reparte las paginas del mes entre los clusters que lo merecen.

        Dos tercios a lo que sube, un tercio a lo estable. Lo que cae y lo que
        no se sabe no se lleva nada: es la decision que su plan fijo no puede
        tomar.
        """
        investing = self.by_decision(DECISION_INVEST)
        holding = self.by_decision(DECISION_HOLD)
        if not investing and not holding:
            return {}

        allocation: dict[str, int] = {}
        invest_share = pages * 2 // 3 if holding else pages
        hold_share = pages - invest_share

        def spread(group: list[Decision], amount: int) -> None:
            if not group or amount <= 0:
                return
            weights = [max(d.signal.value_now, 1.0) for d in group]
            total = sum(weights)
            assigned = 0
            for decision, weight in zip(group[:-1], weights[:-1]):
                share = int(amount * weight / total)
                allocation[decision.cluster_id] = share
                assigned += share
            allocation[group[-1].cluster_id] = amount - assigned

        spread(investing, invest_share if investing else 0)
        spread(holding, hold_share if holding else (0 if investing else pages))
        return {k: v for k, v in allocation.items() if v > 0}

    def describe(self, pages: int = 0) -> str:
        parts = [
            f"{len(self.by_decision(DECISION_INVEST))} cluster(s) para invertir · "
            f"{len(self.by_decision(DECISION_HOLD))} mantener · "
            f"{len(self.by_decision(DECISION_RETIRE))} retirar · "
            f"{len(self.by_decision(DECISION_UNKNOWN))} sin datos suficientes"
        ]
        if pages:
            allocation = self.budget(pages)
            if allocation:
                parts.append(
                    "Reparto de las "
                    + f"{plural(pages, 'pagina')}: "
                    + ", ".join(f"{k} {v}" for k, v in allocation.items())
                )
            else:
                parts.append(
                    f"Ningun cluster justifica las {pages} paginas todavia: hacen "
                    "falta mas datos antes de gastar."
                )
        return "\n".join(parts)


def reallocate(
    graph: Graph,
    before: Report,
    now: Report,
    opportunities: OpportunityReport | None = None,
) -> Reallocation:
    return Reallocation(decisions=decide(collect(graph, before, now, opportunities)))
