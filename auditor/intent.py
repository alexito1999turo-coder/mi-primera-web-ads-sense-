"""Clasificacion de intencion y supervivencia al clic.

Por que esto esta en un auditor de SEO: las consultas informacionales tienen
99,9% de cobertura de AI Overviews y 74,3% de busquedas sin clic. Una pagina
informacional puede rankear perfecto y no recibir la visita. Medir la mezcla
de intencion de un sitio es medir cuanto de su trafico esta en riesgo.
"""

from __future__ import annotations

from textos import porcentajes

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
            # Quien busca un contrato o una garantia esta comparando
            # proveedores de un servicio, no leyendo sobre el.
            "contract", "contrato", "agreement", "acuerdo",
            "service plan", "plan de servicio", "warranty", "garantia",
            "garantía", "subscription", "suscripcion", "suscripción",
        ),
    ),
    (
        # Problema: el sistema del que busca esta roto AHORA.
        #
        # Esta clase faltaba, y la encontre mirando datos reales de un nicho de
        # servicios para el hogar: «aerobic septic alarm going off» salia como
        # «sin determinar», que es tanto como no clasificarla. Es justo la
        # consulta mas valiosa del nicho — quien tiene la alarma sonando no
        # esta leyendo, esta buscando a quien llamar o que pieza comprar.
        #
        # Va DESPUES de comercial y transaccional a proposito: quien busca
        # «mejor bomba de repuesto para septico averiado» ya esta comprando, y
        # esa senal manda sobre la de averia. Y va ANTES de informacional
        # porque «como arreglar X» con una averia detras no es curiosidad.
        #
        # El 55 de supervivencia es un PRIOR declarado, no una medicion: la
        # respuesta generada cubre estas consultas, pero el clic sobrevive
        # mejor que en lo informacional puro porque la respuesta generica no
        # sirve para un modelo concreto averiado. Se puede medir con los datos
        # de Search Console del propio sitio, y entonces este numero sobra.
        "problem",
        55,
        (
            "not working", "no funciona", "stopped working", "dejo de funcionar",
            "dejó de funcionar", "going off", "keeps going off", "wont stop",
            "won't stop", "no para", "not draining", "no drena", "backing up",
            "overflow", "desborda", "clogged", "atascado", "atascada",
            "leaking", "gotea", "fuga", "smell", "smells", "odor", "odour",
            "olor", "huele", "broken", "roto", "rota", "averiado", "averiada",
            "failure", "fallo", "failing", "error code", "codigo de error",
            "código de error", "beeping", "pitando", "pita", "alarm", "alarma",
            "troubleshoot", "problema", "problems", "problemas", "fix ",
            # Vistos en datos reales: la luz de aviso y el corte de luz son
            # averias de libro y se nos escapaban enteras.
            "red light", "luz roja", "warning light", "luz de aviso",
            "power outage", "corte de luz", "apagon", "apagón", "reset",
            "no arranca", "wont drain", "won't drain",
            "repair", "reparar", "arreglar", "won't turn on", "no enciende",
            "replace", "reemplazar", "sustituir",
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
            # Material de referencia: quien pide un diagrama, una plantilla o
            # una lista quiere el documento, no el servicio. Lo generaliza
            # cualquier nicho: todos tienen su «X diagram» y su «X template».
            "diagram", "diagrama", "schematic", "esquema", "layout",
            "look like", "como es", "cómo es", "checklist", "lista de",
            "template", "plantilla", "parts of", "partes de",
            "where to", "donde se", "dónde se",
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
    return porcentajes(counts)
