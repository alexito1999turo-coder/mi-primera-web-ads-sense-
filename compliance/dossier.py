"""Dossier mensual de cumplimiento.

Documento por cliente que mapea lo producido contra la politica de spam de
Google (revisada el 28-08-2026) y la site reputation policy. No es una promesa:
cada fila se rellena con lo que el sistema registro, y si un dato no se midio,
la fila lo dice en vez de afirmarlo.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

from .fingerprint import PortfolioAudit

# Los cinco patrones, con la letra de la politica y la evidencia que les
# corresponde en este sistema.
PATTERNS: tuple[tuple[str, str, str], ...] = (
    (
        "A",
        "Usar IA generativa para producir muchas paginas sin anadir valor",
        "Cada pagina pasa una compuerta que exige dato propio con metodo y "
        "fuente verificable enlazada en el cuerpo. Tope mensual por sitio.",
    ),
    (
        "B",
        "Scraping, incluido el sinonimizado o la traduccion automatizados",
        "Las fuentes se citan con enlace y fecha de consulta, no se copian. "
        "Ningun idioma se publica por traduccion automatica sin revision nativa.",
    ),
    (
        "C",
        "Unir contenido de varias paginas",
        "Compuerta de solape de frases contra el corpus ya publicado del propio "
        "sitio; el lote tambien se compara contra si mismo mientras se produce.",
    ),
    (
        "D",
        "Repartir la salida entre varios sitios para ocultar su escala",
        "Auditoria de huella cruzada de toda la cartera: frases y esqueletos de "
        "encabezados entre sitios distintos, con umbral que bloquea publicacion.",
    ),
    (
        "E",
        "Paginas cargadas de keywords que apenas tienen sentido para un lector",
        "Compuerta de densidad de la keyword primaria, con maximo declarado.",
    ),
)


@dataclass
class MonthRecord:
    """Lo que de verdad paso este mes. Lo rellena el sistema, no el comercial."""

    client: str
    site: str
    period: str                       # p. ej. "2026-10"
    pages_published: int = 0
    pages_blocked: int = 0
    monthly_cap: int = 24
    publishable_as_is: int = 0
    repairs: int = 0
    review_minutes: int = 0
    pages_with_own_data: int = 0
    pages_with_sources: int = 0
    sources_cited: list[str] = field(default_factory=list)
    languages: list[str] = field(default_factory=list)
    languages_human_reviewed: list[str] = field(default_factory=list)
    max_internal_overlap: float | None = None
    max_density: float | None = None
    portfolio: PortfolioAudit | None = None
    # Declaraciones que el sistema puede sostener porque no tiene esas piezas.
    hosts_third_party_content: bool = False
    reciprocal_link_exchange: bool = False
    automated_social_comments: bool = False
    notes: list[str] = field(default_factory=list)

    @property
    def publishable_rate(self) -> float:
        total = self.pages_published + self.pages_blocked
        return round(100 * self.publishable_as_is / total, 1) if total else 0.0

    @property
    def cap_respected(self) -> bool:
        return self.pages_published <= self.monthly_cap


def _status(ok: bool | None) -> str:
    if ok is None:
        return "NO MEDIDO"
    return "cumple" if ok else "INCUMPLE"


def _evaluate(record: MonthRecord) -> list[tuple[str, str, str, str, str]]:
    """Por patron: letra, texto, evidencia, estado y el dato concreto."""
    rows: list[tuple[str, str, str, str, str]] = []

    total = record.pages_published
    for letter, text, evidence in PATTERNS:
        if letter == "A":
            ok = (
                record.cap_respected
                and total > 0
                and record.pages_with_own_data == total
                and record.pages_with_sources == total
            )
            detail = (
                f"{record.pages_with_own_data}/{total} paginas con dato propio, "
                f"{record.pages_with_sources}/{total} con fuente enlazada, "
                f"{total}/{record.monthly_cap} del tope mensual"
            )
            if total == 0:
                ok, detail = None, "no se publico nada este periodo"
        elif letter == "B":
            pendientes = [
                lang for lang in record.languages
                if lang not in record.languages_human_reviewed
            ]
            ok = not pendientes
            detail = (
                f"{len(record.sources_cited)} fuentes citadas con enlace; "
                f"idiomas {', '.join(record.languages) or 'solo el original'}; "
                + ("todos con revision nativa" if ok
                   else f"SIN revision nativa: {', '.join(pendientes)}")
            )
        elif letter == "C":
            if record.max_internal_overlap is None:
                ok, detail = None, "el solape interno no se comprobo este periodo"
            else:
                ok = record.max_internal_overlap <= 0.30
                detail = f"solape maximo medido {record.max_internal_overlap * 100:.0f}% (max 30%)"
        elif letter == "D":
            if record.portfolio is None:
                ok, detail = None, "sin auditoria de cartera este periodo"
            else:
                ok = record.portfolio.passed
                detail = record.portfolio.describe()
        else:  # E
            if record.max_density is None:
                ok, detail = None, "la densidad no se midio"
            else:
                ok = record.max_density <= 0.025
                detail = f"densidad maxima {record.max_density * 100:.1f}% (max 2,5%)"
        rows.append((letter, text, evidence, _status(ok), detail))
    return rows


def to_markdown(record: MonthRecord) -> str:
    lines: list[str] = []
    add = lines.append
    generated = datetime.now(timezone.utc).isoformat(timespec="seconds")

    add(f"# Dossier de cumplimiento — {record.client}")
    add("")
    add(f"Sitio: {record.site} · Periodo: {record.period} · Generado: {generated}")
    add("")
    add("Este documento mapea lo producido contra la politica de spam de Google "
        "revisada el 28 de agosto de 2026 y la site reputation policy. Cada fila "
        "se rellena con registros del sistema. Lo que no se midio aparece como "
        "NO MEDIDO, no como cumple.")
    add("")

    # --- Produccion ------------------------------------------------------
    add("## Produccion del periodo")
    add("")
    add(f"- Paginas publicadas: **{record.pages_published}** de un tope de "
        f"{record.monthly_cap}" + ("" if record.cap_respected else "  ← **TOPE SUPERADO**"))
    add(f"- Paginas bloqueadas por las compuertas: **{record.pages_blocked}**")
    add(f"- Publicables tal cual: **{record.publishable_rate}%** "
        "(linea base del competidor medida por un tercero: 52,4%)")
    add(f"- Reparaciones automaticas: {record.repairs}")
    add(f"- Minutos de revision humana: {record.review_minutes}")
    add("")

    # --- Patrones --------------------------------------------------------
    add("## Mapeo contra los cinco patrones de scaled content abuse")
    add("")
    add("| | Patron | Estado | Dato medido |")
    add("|---|---|---|---|")
    for letter, text, _evidence, status, detail in _evaluate(record):
        mark = {"cumple": "cumple", "INCUMPLE": "**INCUMPLE**",
                "NO MEDIDO": "_no medido_"}[status]
        add(f"| {letter} | {text} | {mark} | {detail} |")
    add("")
    add("### Como se evita cada uno")
    add("")
    for letter, _text, evidence, _status, _detail in _evaluate(record):
        add(f"- **{letter}**: {evidence}")
    add("")

    # --- Declaraciones ---------------------------------------------------
    add("## Declaraciones")
    add("")
    add("Son las piezas que este sistema no tiene, y por eso se pueden afirmar:")
    add("")
    add(f"- Contenido de terceros alojado en el dominio: "
        f"**{'SI — revisar' if record.hosts_third_party_content else 'no'}**. "
        "Alojar contenido ajeno para que tome prestadas las senales del dominio "
        "es site reputation abuse, con aplicacion distinta en el EEE desde el "
        "30-08-2026.")
    add(f"- Intercambio reciproco de enlaces: "
        f"**{'SI — revisar' if record.reciprocal_link_exchange else 'no'}**. "
        "Una red reciproca es un esquema de enlaces por la letra de la politica.")
    add(f"- Comentarios automaticos con marca en redes: "
        f"**{'SI — revisar' if record.automated_social_comments else 'no'}**. "
        "Automatizarlos va contra el acuerdo de usuario de las plataformas y "
        "puede provocar el baneo de la marca.")
    add("")

    # --- Fuentes ---------------------------------------------------------
    if record.sources_cited:
        add("## Fuentes citadas en el periodo")
        add("")
        for source in sorted(set(record.sources_cited)):
            add(f"- {source}")
        add("")

    if record.notes:
        add("## Notas")
        add("")
        for note in record.notes:
            add(f"- {note}")
        add("")

    return "\n".join(lines)


def unresolved(record: MonthRecord) -> list[str]:
    """Lo que impide firmar el dossier. Vacio = se puede entregar."""
    problems: list[str] = []
    for letter, text, _evidence, status, detail in _evaluate(record):
        if status == "INCUMPLE":
            problems.append(f"Patron {letter} ({text}): {detail}")
    if record.hosts_third_party_content:
        problems.append("Se aloja contenido de terceros en el dominio.")
    if record.reciprocal_link_exchange:
        problems.append("Hay intercambio reciproco de enlaces.")
    if record.automated_social_comments:
        problems.append("Hay comentarios automaticos con marca.")
    return problems
