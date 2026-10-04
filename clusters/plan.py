"""Plan de produccion mensual.

Reparte el grafo en meses respetando el tope, y ordena por prioridad con una
regla editorial: el pilar se publica antes que sus satelites, porque los
satelites enlazan al pilar y un enlace a una pagina que no existe no vale nada.
"""

from __future__ import annotations

from textos import plural, porcentajes

from dataclasses import dataclass, field

from .graph import Graph, PageSpec
from .validate import MONTHLY_CAP


@dataclass
class PlannedPage:
    page: PageSpec
    month: int
    position: int

    @property
    def slug(self) -> str:
        return self.page.slug


@dataclass
class Plan:
    months: dict[int, list[PlannedPage]] = field(default_factory=dict)
    cap: int = MONTHLY_CAP

    @property
    def total(self) -> int:
        return sum(len(pages) for pages in self.months.values())

    @property
    def horizon(self) -> int:
        return len(self.months)

    def month(self, number: int) -> list[PlannedPage]:
        return self.months.get(number, [])

    def intent_mix(self, month: int | None = None) -> dict[str, float]:
        items = (
            self.month(month)
            if month is not None
            else [p for pages in self.months.values() for p in pages]
        )
        if not items:
            return {}
        counts: dict[str, int] = {}
        for item in items:
            label = item.page.intent
            counts[label] = counts.get(label, 0) + 1
        return porcentajes(counts)


def build(graph: Graph, cap: int = MONTHLY_CAP) -> Plan:
    """Ordena el grafo en meses. El pilar siempre antes que sus satelites."""
    ordered: list[PageSpec] = []
    for cluster in sorted(graph.clusters, key=lambda c: -c.priority):
        ordered.append(cluster.pillar)
        ordered.extend(sorted(cluster.satellites, key=lambda p: -p.priority))

    plan = Plan(cap=cap)
    for index, page in enumerate(ordered):
        month = index // cap + 1
        plan.months.setdefault(month, []).append(
            PlannedPage(page=page, month=month, position=index % cap + 1)
        )
    return plan


def to_markdown(graph: Graph, plan: Plan, validation=None) -> str:
    lines: list[str] = []
    add = lines.append

    add("# Plan de contenido — M2")
    add("")
    add(f"{len(graph.clusters)} clusters · {len(graph.pages)} paginas · "
        f"{graph.keyword_count} keywords cubiertas · {graph.merged} fusionadas "
        "para no fabricar canibalizacion")
    add("")
    mix = plan.intent_mix()
    if mix:
        add("Mezcla de intencion del plan: "
            + ", ".join(f"{k} {v}%" for k, v in mix.items()))
        add("")

    if validation is not None:
        add("## Validacion")
        add("")
        if validation.passed and not validation.findings:
            add("Solape cero verificado. Sin hallazgos.")
        else:
            if validation.passed:
                add("Solape cero verificado. Hallazgos no bloqueantes:")
            else:
                add("**BLOQUEADO**: hay que resolver lo marcado como bloqueante "
                    "antes de producir.")
            add("")
            for finding in sorted(validation.findings, key=lambda f: not f.blocking):
                mark = "**[BLOQUEANTE]**" if finding.blocking else "[aviso]"
                add(f"- {mark} `{finding.code}` — {finding.message}")
        add("")

    for month in sorted(plan.months):
        pages = plan.month(month)
        add(f"## Mes {month} — {plural(len(pages), 'pagina')}")
        add("")
        add("| # | Pagina | Rol | Cluster | Intencion | Min. palabras | Prioridad |")
        add("|---|---|---|---|---|---|---|")
        for item in pages:
            page = item.page
            add(f"| {item.position} | {page.primary.term} | {page.role} | "
                f"{page.cluster_id} | {page.intent} | {page.min_words} | "
                f"{page.priority:.0f} |")
        add("")

    add("## Enlazado interno")
    add("")
    links = graph.internal_links()
    add(f"{len(links)} enlaces pilar<->satelite. El pilar se publica antes que "
        "sus satelites: un enlace a una pagina que no existe no vale nada.")
    add("")
    return "\n".join(lines)
