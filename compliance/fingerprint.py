"""Huella de similitud entre sitios de la cartera.

Es la guarda contra el quinto patron de scaled content abuse: "repartir la
salida entre varios sitios para ocultar su escala".

Nadie habla de este riesgo y es el que mata el negocio entero de golpe en vez
de cliente a cliente. Un sitio puede parecer limpio por separado; veinte sitios
con el mismo esqueleto de parrafos son una granja de contenido en agregado.
"""

from __future__ import annotations

from textos import plural

import re
from dataclasses import dataclass, field

WORD_RE = re.compile(r"[0-9A-Za-zÁÉÍÓÚÜÑáéíóúüñ]+")
HEADING_RE = re.compile(r"^#{2,3}\s+(.+)$", re.M)
SHINGLE_SIZE = 6

# Umbrales de cartera. Mas estrictos que los de una pagina suelta: entre sitios
# de clientes distintos la similitud legitima es casi nula.
MAX_PHRASE_SIMILARITY = 0.08
MAX_OUTLINE_SIMILARITY = 0.50


def shingles(text: str, size: int = SHINGLE_SIZE) -> set[str]:
    words = [w.lower() for w in WORD_RE.findall(text)]
    if len(words) < size:
        return {" ".join(words)} if words else set()
    return {" ".join(words[i : i + size]) for i in range(len(words) - size + 1)}


def outline(text: str) -> list[str]:
    """Esqueleto de encabezados, normalizado.

    Dos sitios con el mismo esqueleto delatan la plantilla aunque las palabras
    cambien. Es la senal mas facil de ver desde fuera.
    """
    return [" ".join(WORD_RE.findall(h.lower())) for h in HEADING_RE.findall(text)]


def _similarity(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / min(len(a), len(b))


def _sequence_similarity(a: list[str], b: list[str]) -> float:
    """Similitud de esqueletos por solape de encabezados normalizados."""
    if not a or not b:
        return 0.0
    set_a, set_b = set(a), set(b)
    return len(set_a & set_b) / min(len(set_a), len(set_b))


@dataclass
class SitePrint:
    """La huella de un sitio: frases y esqueletos de todas sus paginas."""

    site: str
    phrases: set[str] = field(default_factory=set)
    outlines: list[str] = field(default_factory=list)
    pages: int = 0

    def add_page(self, body: str) -> None:
        self.phrases |= shingles(body)
        self.outlines.extend(outline(body))
        self.pages += 1


@dataclass
class Collision:
    site_a: str
    site_b: str
    phrase_similarity: float
    outline_similarity: float

    @property
    def blocking(self) -> bool:
        return (
            self.phrase_similarity > MAX_PHRASE_SIMILARITY
            or self.outline_similarity > MAX_OUTLINE_SIMILARITY
        )

    def describe(self) -> str:
        verdict = "BLOQUEA" if self.blocking else "ok"
        return (
            f"[{verdict}] {self.site_a} vs {self.site_b}: "
            f"frases {self.phrase_similarity * 100:.1f}% "
            f"(max {MAX_PHRASE_SIMILARITY * 100:.0f}%), "
            f"esqueleto {self.outline_similarity * 100:.0f}% "
            f"(max {MAX_OUTLINE_SIMILARITY * 100:.0f}%)"
        )


@dataclass
class PortfolioAudit:
    collisions: list[Collision] = field(default_factory=list)
    sites: int = 0

    @property
    def blocking(self) -> list[Collision]:
        return [c for c in self.collisions if c.blocking]

    @property
    def passed(self) -> bool:
        return not self.blocking

    def describe(self) -> str:
        if self.sites < 2:
            return (
                f"{self.sites} sitio(s) en cartera: no hay huella cruzada que medir."
            )
        if self.passed:
            return (
                f"{plural(self.sites, 'sitio')}, "
                f"{plural(len(self.collisions), 'par', 'pares')} comparados, "
                "ninguna colision. Cada sitio es independiente en agregado."
            )
        return (
            f"{len(self.blocking)} par(es) de sitios comparten plantilla. En "
            "agregado la cartera es una granja de contenido, aunque cada sitio "
            "parezca limpio por separado. BLOQUEA publicacion."
        )


def audit(prints: list[SitePrint]) -> PortfolioAudit:
    result = PortfolioAudit(sites=len(prints))
    for index, first in enumerate(prints):
        for second in prints[index + 1 :]:
            result.collisions.append(
                Collision(
                    site_a=first.site,
                    site_b=second.site,
                    phrase_similarity=_similarity(first.phrases, second.phrases),
                    outline_similarity=_sequence_similarity(
                        first.outlines, second.outlines
                    ),
                )
            )
    return result
