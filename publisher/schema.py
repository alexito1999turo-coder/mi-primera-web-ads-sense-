"""JSON-LD. No es decoracion: es como se le dice a un buscador que la cifra
que aparece en la pagina tiene un autor y una fecha.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field

HEADING = re.compile(r"^##\s+(.+)$", re.M)
QUESTION = re.compile(r"^###?\s+(.*\?)\s*$", re.M)
STEP = re.compile(r"^(?:\d+\.|-)\s+(.+)$", re.M)


@dataclass
class Publisher:
    name: str
    url: str = ""
    logo: str = ""


@dataclass
class SchemaContext:
    site_url: str
    author_name: str
    publisher: Publisher
    language: str = "es"


def _answer_after(body: str, question: str) -> str:
    """El parrafo que sigue a la pregunta. Si no hay, no se inventa."""
    index = body.find(question)
    if index < 0:
        return ""
    rest = body[index + len(question):].strip()
    for block in rest.split("\n\n"):
        text = block.strip()
        if text and not text.startswith("#"):
            return " ".join(text.split())
    return ""


def article(
    title: str,
    body: str,
    slug: str,
    context: SchemaContext,
    description: str = "",
    published_at: str = "",
    modified_at: str = "",
    sources: list[str] | None = None,
) -> dict:
    data: dict = {
        "@context": "https://schema.org",
        "@type": "Article",
        "headline": title[:110],
        "inLanguage": context.language,
        "mainEntityOfPage": {
            "@type": "WebPage",
            "@id": f"{context.site_url.rstrip('/')}/{slug}/",
        },
        "author": {"@type": "Person", "name": context.author_name},
        "publisher": {
            "@type": "Organization",
            "name": context.publisher.name,
            **({"url": context.publisher.url} if context.publisher.url else {}),
            **(
                {"logo": {"@type": "ImageObject", "url": context.publisher.logo}}
                if context.publisher.logo
                else {}
            ),
        },
    }
    if description:
        data["description"] = description
    if published_at:
        data["datePublished"] = published_at
    if modified_at:
        data["dateModified"] = modified_at
    # Las fuentes citadas van en citation: es la declaracion de que la pagina
    # se apoya en algo verificable.
    if sources:
        data["citation"] = [{"@type": "CreativeWork", "url": url} for url in sources]
    return data


def faq_page(body: str) -> dict | None:
    """FAQPage solo si hay preguntas CON respuesta. Nunca el esqueleto vacio."""
    pairs: list[tuple[str, str]] = []
    for question in QUESTION.findall(body):
        answer = _answer_after(body, question)
        if answer:
            pairs.append((question.strip(), answer))
    if not pairs:
        return None
    return {
        "@context": "https://schema.org",
        "@type": "FAQPage",
        "mainEntity": [
            {
                "@type": "Question",
                "name": question,
                "acceptedAnswer": {"@type": "Answer", "text": answer[:1200]},
            }
            for question, answer in pairs
        ],
    }


def how_to(title: str, body: str, min_steps: int = 3) -> dict | None:
    """HowTo solo si de verdad hay una secuencia de pasos."""
    steps = [s.strip() for s in STEP.findall(body) if len(s.strip()) > 15]
    if len(steps) < min_steps:
        return None
    return {
        "@context": "https://schema.org",
        "@type": "HowTo",
        "name": title[:110],
        "step": [
            {"@type": "HowToStep", "position": i, "text": text[:500]}
            for i, text in enumerate(steps, 1)
        ],
    }


def build(
    title: str,
    body: str,
    slug: str,
    context: SchemaContext,
    intent: str = "",
    sources: list[str] | None = None,
    **kwargs,
) -> list[dict]:
    """Los bloques que corresponden a esta pagina, y solo esos.

    Marcar HowTo en una pagina que no tiene pasos, o FAQPage sin respuestas,
    es datos estructurados falsos. Google lo trata como lo que es.
    """
    blocks = [article(title, body, slug, context, sources=sources, **kwargs)]
    faq = faq_page(body)
    if faq:
        blocks.append(faq)
    # El HowTo solo tiene sentido en contenido de procedimiento.
    if intent in ("", "informational", "undetermined"):
        guide = how_to(title, body)
        if guide:
            blocks.append(guide)
    return blocks


def to_script(blocks: list[dict]) -> str:
    """Los bloques como etiqueta lista para insertar en el HTML."""
    return "\n".join(
        '<script type="application/ld+json">'
        + json.dumps(block, ensure_ascii=False, separators=(",", ":"))
        + "</script>"
        for block in blocks
    )
