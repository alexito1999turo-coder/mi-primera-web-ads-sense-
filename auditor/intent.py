"""Clasificacion de intencion y supervivencia al clic.

Por que esto esta en un auditor de SEO: las consultas informacionales tienen
99,9% de cobertura de AI Overviews y 74,3% de busquedas sin clic. Una pagina
informacional puede rankear perfecto y no recibir la visita. Medir la mezcla
de intencion de un sitio es medir cuanto de su trafico esta en riesgo.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# Senales ordenadas de mas a menos especifica. La primera que acierta manda.
SIGNALS: tuple[tuple[str, int, tuple[str, ...]], ...] = (
    (
        "transactional",
        90,
        (
            "near me", "cerca de mi", "buy", "comprar", "hire", "contratar",
            "quote", "presupuesto", "book", "reservar", "order", "pedir",
            "for sale", "en venta", "contractor", "installer", "instalador",
            "service near", "companies in", "empresas en",
        ),
    ),
    (
        "commercial",
        75,
        (
            " vs ", " vs. ", "versus", "best ", "mejor ", "mejores ",
            "top ", "review", "reseña", "resena", "comparison", "comparativa",
            "alternative", "alternativa", "cost", "coste", "costo", "precio",
            "price", "pricing", "cheap", "barato", "calculator", "calculadora",
            "how much", "cuanto cuesta", "cuánto cuesta", "worth it",
            "merece la pena", "brands", "marcas", "which ",
        ),
    ),
    (
        "informational",
        25,
        (
            "what is", "que es", "qué es", "how to", "como ", "cómo ",
            "why ", "por que", "por qué", "guide", "guia", "guía",
            "meaning", "significado", "definition", "definicion", "definición",
            "symptoms", "sintomas", "síntomas", "causes", "causas",
            "explained", "explicado", "tips", "consejos", "history", "historia",
            "examples", "ejemplos", "benefits", "beneficios", "types", "tipos",
        ),
    ),
)

SLUG_SPLIT = re.compile(r"[-_/]+")


@dataclass
class Intent:
    label: str
    click_survival: int  # 0-100: cuanto clic sobrevive a AI Overviews
    matched: str

    @property
    def at_risk(self) -> bool:
        """Informacional puro: el clic lo absorbe la respuesta generada."""
        return self.label == "informational"


def classify(url: str, title: str = "") -> Intent:
    """Clasifica por titulo y slug. Sin red: es analisis de texto."""
    slug = " ".join(SLUG_SPLIT.split(url.lower()))
    haystack = f" {title.lower()} {slug} "
    for label, survival, needles in SIGNALS:
        for needle in needles:
            if needle in haystack:
                return Intent(label=label, click_survival=survival, matched=needle.strip())
    # Sin senal clara: se trata como informacional debil, que es el caso por
    # defecto de un blog, pero se marca como no determinado.
    return Intent(label="undetermined", click_survival=45, matched="")


def distribution(items: list[Intent]) -> dict[str, float]:
    """Reparto porcentual por etiqueta. Es la cifra que se vende."""
    if not items:
        return {}
    total = len(items)
    counts: dict[str, int] = {}
    for item in items:
        counts[item.label] = counts.get(item.label, 0) + 1
    return {label: round(100 * count / total, 1) for label, count in sorted(counts.items())}
