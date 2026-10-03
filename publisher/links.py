"""Enlazado interno pilar<->satelite.

Regla editorial: un enlace se inserta donde el texto ya nombra el destino, y
una sola vez por destino. Insertar enlaces en frases que no los piden es lo que
convierte un articulo en un directorio.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from clusters.graph import Cluster, Graph


@dataclass
class LinkTarget:
    slug: str
    anchor: str
    url: str


def targets_for(graph: Graph, slug: str, site_url: str) -> list[LinkTarget]:
    """Destinos legitimos de esta pagina: su pilar y sus hermanos de cluster."""
    cluster: Cluster | None = graph.cluster_of(slug)
    if cluster is None:
        return []
    base = site_url.rstrip("/")
    out: list[LinkTarget] = []
    for page in cluster.pages:
        if page.slug == slug:
            continue
        out.append(
            LinkTarget(
                slug=page.slug,
                anchor=page.primary.term,
                url=f"{base}/{page.slug}/",
            )
        )
    return out


def inject(body: str, targets: list[LinkTarget], max_links: int = 6) -> tuple[str, list[str]]:
    """Enlaza la primera mencion de cada destino. Devuelve el cuerpo y los
    destinos que no se pudieron enlazar porque el texto no los nombra.
    """
    out = body
    missed: list[str] = []
    inserted = 0

    for target in targets:
        if inserted >= max_links:
            missed.append(target.slug)
            continue
        if f"]({target.url})" in out:
            continue  # ya enlazado por el redactor
        pattern = re.compile(re.escape(target.anchor), re.I)
        match = _first_linkable(out, pattern)
        if match is None:
            missed.append(target.slug)
            continue
        start, end = match
        out = f"{out[:start]}[{out[start:end]}]({target.url}){out[end:]}"
        inserted += 1

    return out, missed


def _first_linkable(text: str, pattern: re.Pattern) -> tuple[int, int] | None:
    """Primera aparicion que no este ya dentro de un enlace ni en un titulo."""
    for match in pattern.finditer(text):
        start, end = match.start(), match.end()
        line_start = text.rfind("\n", 0, start) + 1
        line = text[line_start : text.find("\n", start) if text.find("\n", start) > 0 else len(text)]
        if line.lstrip().startswith("#"):
            continue  # un encabezado no se enlaza
        before = text[max(0, start - 200) : start]
        # Dentro de un ancla o de una URL: no tocar.
        if before.count("[") > before.count("]") or before.count("(") > before.count(")"):
            continue
        return start, end
    return None
