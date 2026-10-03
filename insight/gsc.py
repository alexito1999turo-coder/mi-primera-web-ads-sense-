"""Carga de exportaciones de Search Console.

Acepta la exportacion por consultas, por paginas o la combinada, en ingles o
espanol. Lo que no trae el fichero no se inventa: se marca como ausente.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass, field
from pathlib import Path

from auditor.intent import classify


def _pick(fields: list[str], names: tuple[str, ...]) -> str | None:
    lowered = {f.lower().strip(): f for f in fields}
    for name in names:
        if name in lowered:
            return lowered[name]
    for key, original in lowered.items():
        if any(name in key for name in names):
            return original
    return None


def _number(raw: str | None) -> float:
    if not raw:
        return 0.0
    cleaned = raw.strip().replace("%", "").replace(" ", "")
    if "," in cleaned and "." in cleaned:
        if cleaned.rfind(",") > cleaned.rfind("."):
            cleaned = cleaned.replace(".", "").replace(",", ".")
        else:
            cleaned = cleaned.replace(",", "")
    elif "," in cleaned:
        tail = cleaned.rsplit(",", 1)[-1]
        cleaned = cleaned.replace(",", "") if len(tail) == 3 and tail.isdigit() \
            else cleaned.replace(",", ".")
    try:
        return float(cleaned or 0)
    except ValueError:
        return 0.0


@dataclass
class Row:
    """Una fila de Search Console, con su intencion deducida."""

    query: str = ""
    page: str = ""
    clicks: int = 0
    impressions: int = 0
    position: float = 0.0

    @property
    def intent(self) -> str:
        subject = self.query or self.page
        return classify(subject.replace(" ", "-"), title=self.query).label

    @property
    def ctr(self) -> float:
        return self.clicks / self.impressions if self.impressions else 0.0


@dataclass
class Report:
    rows: list[Row] = field(default_factory=list)
    has_queries: bool = False
    has_pages: bool = False
    has_positions: bool = False
    notes: list[str] = field(default_factory=list)

    @property
    def impressions(self) -> int:
        return sum(row.impressions for row in self.rows)

    @property
    def clicks(self) -> int:
        return sum(row.clicks for row in self.rows)


def load(path: str | Path) -> Report:
    report = Report()
    with open(path, newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames:
            report.notes.append("El fichero no tiene cabecera.")
            return report

        fields = list(reader.fieldnames)
        query_field = _pick(fields, ("query", "consulta", "consultas", "keyword"))
        page_field = _pick(fields, ("page", "pagina", "página", "url", "address"))
        clicks_field = _pick(fields, ("clicks", "clics", "clicks totales"))
        impressions_field = _pick(fields, ("impressions", "impresiones"))
        position_field = _pick(fields, ("position", "posicion", "posición"))

        report.has_queries = bool(query_field)
        report.has_pages = bool(page_field)
        report.has_positions = bool(position_field)

        if not impressions_field:
            report.notes.append(
                "Sin columna de impresiones: no se puede estimar oportunidad."
            )
            return report
        if not position_field:
            report.notes.append(
                "Sin columna de posicion: la distancia al objetivo no se mide, "
                "asi que no se afirma."
            )

        for raw in reader:
            row = Row(
                query=(raw.get(query_field) or "").strip() if query_field else "",
                page=(raw.get(page_field) or "").strip() if page_field else "",
                clicks=int(_number(raw.get(clicks_field) if clicks_field else None)),
                impressions=int(_number(raw.get(impressions_field))),
                position=_number(raw.get(position_field) if position_field else None),
            )
            if row.impressions or row.clicks:
                report.rows.append(row)
    return report
