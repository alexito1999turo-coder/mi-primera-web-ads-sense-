"""Los cuatro servicios, envolviendo los modulos del motor.

Cada funcion recibe datos del formulario y devuelve algo serializable. Nada de
logica de negocio aqui: la logica esta en los modulos y probada aparte. Lo que
si hay aqui es la validacion de lo que llega de fuera, que es trabajo de la
frontera y no se delega.
"""

from __future__ import annotations

import csv
import io
import re
from dataclasses import asdict
from urllib.parse import urlparse

from auditor.audit import run as run_audit
from auditor.http import Client
from auditor.report import to_markdown as audit_markdown
from citability.score import analyse as analyse_citability
from clusters.graph import build as build_graph
from clusters.keywords import Keyword
from clusters.plan import build as build_plan
from clusters.validate import validate as validate_graph
from insight.gsc import Report, Row
from insight.opportunity import analyse as analyse_opportunity

from .jobs import Progress

MAX_UPLOAD = 4_000_000
MAX_TEXT = 400_000
MAX_KEYWORDS = 2000
MAX_GSC_ROWS = 20000

# Un servidor local no debe convertirse en un escaner de la red interna de quien
# lo levante. Se rechazan destinos que no son internet publico.
PRIVATE_HOSTS = re.compile(
    r"^(?:localhost|127\.|10\.|192\.168\.|169\.254\.|172\.(?:1[6-9]|2\d|3[01])\.|"
    r"0\.|\[?::1\]?|metadata\.)",
    re.I,
)


class BadRequest(ValueError):
    """Lo que llega de fuera esta mal. Se contesta con 400, no con una traza."""


def normalize_site(raw: str, allow_private: bool = False) -> str:
    site = (raw or "").strip()
    if not site:
        raise BadRequest("Falta el dominio.")
    if len(site) > 300:
        raise BadRequest("El dominio es absurdamente largo.")
    if "://" not in site:
        site = "https://" + site
    parsed = urlparse(site)
    if parsed.scheme not in ("http", "https"):
        raise BadRequest("Solo http y https.")
    if not parsed.netloc or "." not in parsed.netloc.split(":")[0]:
        raise BadRequest(f"«{raw}» no parece un dominio.")
    if not allow_private and PRIVATE_HOSTS.match(parsed.netloc):
        raise BadRequest(
            "Ese destino es una direccion interna. Esta herramienta audita sitios "
            "publicos; apuntarla a la red local la convertiria en un escaner."
        )
    return f"{parsed.scheme}://{parsed.netloc}"


# --- 1. Auditoria ----------------------------------------------------------

def audit(site: str, thin_words: int, interval: float, max_archives: int,
          allow_private: bool = False):
    root = normalize_site(site, allow_private=allow_private)
    thin_words = max(100, min(5000, int(thin_words)))
    interval = max(0.05, min(5.0, float(interval)))
    max_archives = max(1, min(200, int(max_archives)))

    def work(progress: Progress):
        progress.set_total(max_archives + 6)
        progress.step(f"Pidiendo robots.txt de {root}", advance=0)
        client = _ReportingClient(Client(min_interval=interval), progress)
        result = run_audit(root, client=client, thin_words=thin_words,
                           max_archives=max_archives)
        progress.step("Informe listo", advance=0)
        return {
            "site": result.site,
            "markdown": audit_markdown(result),
            "summary": {
                "archives": len(result.archives),
                "indexable": len([a for a in result.archives if a.indexable]),
                "actions": len(result.actionable),
                "posts": result.post_count,
                "requests": result.requests_made,
                "intent": result.intent_distribution,
            },
            "archives": [
                {
                    "url": a.url, "kind": a.kind, "status": a.status,
                    "indexable": a.indexable, "posts": a.posts, "words": a.words,
                    "verdict": a.verdict, "action": a.action, "reason": a.reason,
                    "candidates": a.recategorization_candidates[:10],
                    "verification": a.verification,
                }
                for a in sorted(result.archives, key=lambda x: (x.priority or 9, -x.words))
            ],
            "warnings": result.warnings,
            "notes": result.notes,
        }

    return work


class _ReportingClient:
    """Envuelve el cliente para contar el progreso sin tocar el auditor."""

    def __init__(self, client: Client, progress: Progress) -> None:
        self._client = client
        self._progress = progress

    def get(self, url: str):
        corto = urlparse(url).path or "/"
        self._progress.step(f"Midiendo {corto}")
        return self._client.get(url)

    @property
    def request_count(self) -> int:
        return self._client.request_count


# --- 2. Citabilidad --------------------------------------------------------

def citability(text: str) -> dict:
    if not (text or "").strip():
        raise BadRequest("Pega un texto para medirlo.")
    if len(text) > MAX_TEXT:
        raise BadRequest("El texto pasa del limite de 400.000 caracteres.")
    report = analyse_citability(text)
    return {
        "score": report.score,
        "question_headings": report.question_headings,
        "answer_first": report.answer_first_sections,
        "candidates": len(report.quotes),
        "liftable": [
            {"text": q.text, "total": q.total, "ext": q.extractability,
             "atr": q.attributability, "esc": q.scarcity, "ali": q.alignment}
            for q in report.liftable
        ],
        "worst": [
            {"text": q.text, "total": q.total, "ext": q.extractability,
             "atr": q.attributability, "esc": q.scarcity, "ali": q.alignment,
             "blockers": q.blockers}
            for q in sorted(report.quotes, key=lambda q: q.total)[:5]
            if not q.liftable
        ],
        "fixes": [{"fix": fix, "count": count} for fix, count in report.top_fixes(8)],
        "describe": report.describe(),
    }


# --- 3. Oportunidad --------------------------------------------------------

def opportunity(csv_text: str) -> dict:
    rows = _parse_gsc(csv_text)
    if not rows:
        raise BadRequest(
            "No se encontraron filas utilizables. Hace falta una columna de "
            "consulta o pagina y otra de impresiones."
        )
    report = analyse_opportunity(Report(rows=rows))
    if not report.ranked:
        raise BadRequest(
            "Ninguna fila tiene posicion y volumen suficientes para estimar "
            "oportunidad. Exporta con la columna de posicion."
        )

    def pack(items):
        return [
            {"subject": o.subject, "impressions": o.row.impressions,
             "position": round(o.row.position, 1), "intent": o.intent,
             "band": o.band, "raw": round(o.raw_gain), "adjusted": round(o.adjusted_gain),
             "value": round(o.value), "lost": round(o.lost_to_aio)}
            for o in items
        ]

    return {
        "describe": report.describe(),
        "by_value": pack(report.ranked[:40]),
        "by_clicks": pack(report.ranked_by_clicks[:40]),
        "demoted": [{"subject": s, "before": b, "after": a}
                    for s, b, a in report.demoted()],
        "promoted": [{"subject": s, "before": b, "after": a}
                     for s, b, a in report.promoted()],
        "totals": {"adjusted": report.total_adjusted,
                   "lost": report.total_lost_to_aio,
                   "skipped": report.skipped_low_volume,
                   "unmeasurable": report.unmeasurable},
    }


def _parse_gsc(csv_text: str) -> list[Row]:
    if not (csv_text or "").strip():
        raise BadRequest("Pega o sube la exportacion de Search Console.")
    if len(csv_text) > MAX_UPLOAD:
        raise BadRequest("El fichero es demasiado grande.")
    reader = csv.DictReader(io.StringIO(csv_text))
    if not reader.fieldnames:
        raise BadRequest("El CSV no tiene cabecera.")
    from insight.gsc import _number, _pick

    fields = list(reader.fieldnames)
    query_field = _pick(fields, ("query", "consulta", "consultas", "keyword"))
    page_field = _pick(fields, ("page", "pagina", "página", "url", "address"))
    clicks_field = _pick(fields, ("clicks", "clics"))
    impressions_field = _pick(fields, ("impressions", "impresiones"))
    position_field = _pick(fields, ("position", "posicion", "posición"))
    if not impressions_field:
        raise BadRequest("Falta la columna de impresiones.")
    if not (query_field or page_field):
        raise BadRequest("Falta la columna de consulta o de pagina.")

    rows: list[Row] = []
    for raw in reader:
        if len(rows) >= MAX_GSC_ROWS:
            break
        row = Row(
            query=(raw.get(query_field) or "").strip() if query_field else "",
            page=(raw.get(page_field) or "").strip() if page_field else "",
            clicks=int(_number(raw.get(clicks_field) if clicks_field else None)),
            impressions=int(_number(raw.get(impressions_field))),
            position=_number(raw.get(position_field) if position_field else None),
        )
        if row.impressions or row.clicks:
            rows.append(row)
    return rows


# --- 4. Clusters -----------------------------------------------------------

def clusters(csv_text: str, cap: int) -> dict:
    if not (csv_text or "").strip():
        raise BadRequest("Pega o sube el CSV de keywords.")
    if len(csv_text) > MAX_UPLOAD:
        raise BadRequest("El fichero es demasiado grande.")
    cap = max(1, min(120, int(cap)))

    from clusters.keywords import _number, _pick

    reader = csv.DictReader(io.StringIO(csv_text))
    if not reader.fieldnames:
        raise BadRequest("El CSV no tiene cabecera.")
    fields = list(reader.fieldnames)
    term_field = _pick(fields, ("keyword", "palabra", "query", "term", "consulta"))
    if not term_field:
        raise BadRequest(
            "No hay columna de keyword. Cabeceras encontradas: " + ", ".join(fields)
        )
    volume_field = _pick(fields, ("search volume", "volume", "volumen", "searches"))
    difficulty_field = _pick(fields, ("difficulty", "dificultad", "kd", "competition"))
    cpc_field = _pick(fields, ("cpc", "coste por clic"))

    keywords: list[Keyword] = []
    seen: set[str] = set()
    for raw in reader:
        if len(keywords) >= MAX_KEYWORDS:
            break
        term = (raw.get(term_field) or "").strip()
        if not term:
            continue
        key = " ".join(term.lower().split())
        if key in seen:
            continue
        seen.add(key)
        keywords.append(Keyword(
            term=term,
            volume=int(_number(raw.get(volume_field) if volume_field else None)),
            difficulty=int(_number(raw.get(difficulty_field) if difficulty_field else None)),
            cpc=_number(raw.get(cpc_field) if cpc_field else None),
        ))
    if not keywords:
        raise BadRequest("El CSV no contiene keywords.")

    graph = build_graph(keywords)
    validation = validate_graph(graph, monthly_cap=cap)
    plan = build_plan(graph, cap=cap)

    return {
        "summary": {
            "keywords": len(keywords), "clusters": len(graph.clusters),
            "pages": len(graph.pages), "merged": graph.merged,
            "covered": graph.keyword_count, "months": plan.horizon,
            "links": len(graph.internal_links()),
        },
        "intent_mix": plan.intent_mix(),
        "validation": {
            "passed": validation.passed,
            "findings": [
                {"code": f.code, "severity": f.severity, "message": f.message,
                 "blocking": f.blocking}
                for f in sorted(validation.findings, key=lambda f: not f.blocking)
            ],
        },
        "months": [
            {
                "month": month,
                "pages": [
                    {"term": item.page.primary.term, "role": item.page.role,
                     "cluster": item.page.cluster_id, "intent": item.page.intent,
                     "min_words": item.page.min_words,
                     "priority": round(item.page.priority),
                     "secondary": [k.term for k in item.page.secondary]}
                    for item in plan.month(month)
                ],
            }
            for month in sorted(plan.months)
        ],
    }
