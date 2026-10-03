"""Construccion del grafo: clusters, pilares y satelites.

Garantia estructural: ninguna keyword es primaria de dos paginas. No es una
comprobacion posterior, es como se construye. Y las casi-duplicadas se fusionan
en una pagina con keywords secundarias, en vez de generar dos paginas que
compiten entre si, que es la canibalizacion que se autoinfligen las
herramientas que generan una pagina por keyword.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from .keywords import Keyword

ROLE_PILLAR = "pillar"
ROLE_SATELLITE = "satellite"

# Solape de tokens topicos para entrar en el mismo cluster.
CLUSTER_MIN_OVERLAP = 1
# Un token presente en mas de esta fraccion de las keywords es el nombre del
# nicho, no un tema. "septico" en un sitio de septicos agrupa todo con todo.
GENERIC_TOKEN_RATIO = 0.4
# Similitud a partir de la cual dos keywords son la misma pagina.
MERGE_THRESHOLD = 0.6
# Palabras minimas por rol: un pilar con menos no sostiene el cluster.
WORDS_PILLAR = 1800
WORDS_SATELLITE = 1200


def generic_tokens(keywords: list[Keyword], ratio: float = GENERIC_TOKEN_RATIO) -> set[str]:
    """Tokens demasiado frecuentes para ser topicos.

    Sin esto, un solape de un solo token mete "alarma septica pitando" en el
    cluster de "mejor bomba de aire septica" porque comparten "septica". El
    nombre del nicho esta en todas las keywords y no distingue temas.
    """
    if len(keywords) < 5:
        return set()
    counts: dict[str, int] = {}
    for keyword in keywords:
        for token in keyword.tokens:
            counts[token] = counts.get(token, 0) + 1
    limit = max(2, int(len(keywords) * ratio))
    return {token for token, count in counts.items() if count >= limit}


def jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


@dataclass
class PageSpec:
    """Una pagina a producir. `primary` no se repite en todo el grafo."""

    primary: Keyword
    role: str
    cluster_id: str
    secondary: list[Keyword] = field(default_factory=list)

    @property
    def slug(self) -> str:
        return self.primary.slug

    @property
    def min_words(self) -> int:
        return WORDS_PILLAR if self.role == ROLE_PILLAR else WORDS_SATELLITE

    @property
    def priority(self) -> float:
        """La pagina hereda la prioridad de su primaria mas la cola larga."""
        return self.primary.priority + sum(k.priority for k in self.secondary) * 0.25

    @property
    def intent(self) -> str:
        return self.primary.intent.label

    @property
    def all_terms(self) -> list[str]:
        return [self.primary.term] + [k.term for k in self.secondary]


@dataclass
class Cluster:
    """Un pilar y sus satelites. El enlazado interno sigue esta forma."""

    id: str
    topic: str
    pillar: PageSpec
    satellites: list[PageSpec] = field(default_factory=list)

    @property
    def pages(self) -> list[PageSpec]:
        return [self.pillar] + self.satellites

    @property
    def size(self) -> int:
        return len(self.pages)

    @property
    def priority(self) -> float:
        return sum(page.priority for page in self.pages)


@dataclass
class Graph:
    clusters: list[Cluster] = field(default_factory=list)
    merged: int = 0  # keywords absorbidas como secundarias

    @property
    def pages(self) -> list[PageSpec]:
        return [page for cluster in self.clusters for page in cluster.pages]

    @property
    def keyword_count(self) -> int:
        return sum(len(page.all_terms) for page in self.pages)

    def cluster_of(self, slug: str) -> Cluster | None:
        for cluster in self.clusters:
            if any(page.slug == slug for page in cluster.pages):
                return cluster
        return None

    def internal_links(self) -> list[tuple[str, str]]:
        """Enlaces pilar<->satelite. Es el mapa que consume el publicador."""
        links: list[tuple[str, str]] = []
        for cluster in self.clusters:
            for satellite in cluster.satellites:
                links.append((cluster.pillar.slug, satellite.slug))
                links.append((satellite.slug, cluster.pillar.slug))
        return links


def _topic(keyword: Keyword) -> str:
    tokens = sorted(keyword.tokens)[:3]
    return " ".join(tokens) if tokens else keyword.term


def _slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-") or "cluster"


def build(
    keywords: list[Keyword],
    min_overlap: int = CLUSTER_MIN_OVERLAP,
    merge_threshold: float = MERGE_THRESHOLD,
    serp_overlap: dict[tuple[str, str], float] | None = None,
) -> Graph:
    """Agrupa por solape de tokens; si hay datos de SERP, manda el SERP.

    `serp_overlap` permite inyectar solape real de resultados cuando se tiene
    (DataForSEO u otra fuente). Sin ese dato se usa el solape de tokens, que es
    la aproximacion offline y asi queda documentado en el informe.
    """
    graph = Graph()
    if not keywords:
        return graph

    ubiquitous = generic_tokens(keywords)
    topical = {k.term: (k.tokens - ubiquitous) or k.tokens for k in keywords}

    pending = sorted(keywords, key=lambda k: (-k.priority, k.term))
    assigned: set[str] = set()

    for seed in pending:
        if seed.term in assigned:
            continue

        members = [seed]
        assigned.add(seed.term)
        for candidate in pending:
            if candidate.term in assigned:
                continue
            if _related(seed, candidate, min_overlap, serp_overlap, topical):
                members.append(candidate)
                assigned.add(candidate.term)

        pages = _pages_from(members, seed, merge_threshold)
        graph.merged += len(members) - len(pages)

        cluster_id = _slugify(_topic(seed))
        # Un cluster por tema: si el slug ya existe, se desambigua.
        existing = {cluster.id for cluster in graph.clusters}
        if cluster_id in existing:
            cluster_id = f"{cluster_id}-{len(graph.clusters) + 1}"

        pillar = pages[0]
        pillar.role = ROLE_PILLAR
        pillar.cluster_id = cluster_id
        satellites = []
        for page in pages[1:]:
            page.role = ROLE_SATELLITE
            page.cluster_id = cluster_id
            satellites.append(page)

        graph.clusters.append(
            Cluster(id=cluster_id, topic=_topic(seed), pillar=pillar, satellites=satellites)
        )

    graph.clusters.sort(key=lambda c: -c.priority)
    return graph


def _related(
    seed: Keyword,
    candidate: Keyword,
    min_overlap: int,
    serp_overlap: dict[tuple[str, str], float] | None,
    topical: dict[str, set[str]],
) -> bool:
    if serp_overlap:
        key = (seed.term, candidate.term)
        reverse = (candidate.term, seed.term)
        score = serp_overlap.get(key, serp_overlap.get(reverse))
        if score is not None:
            return score >= 0.3
    shared = topical.get(seed.term, seed.tokens) & topical.get(candidate.term, candidate.tokens)
    if len(shared) >= min_overlap:
        return True
    # Red de seguridad para keywords cortas: si al descartar los tokens del
    # nicho no queda nada en comun, vale una similitud textual alta sobre los
    # tokens completos.
    return jaccard(seed.tokens, candidate.tokens) >= 0.5


def _pages_from(
    members: list[Keyword], seed: Keyword, merge_threshold: float
) -> list[PageSpec]:
    """Convierte keywords en paginas, fusionando las casi iguales.

    Dos keywords con similitud alta son la misma intencion de busqueda. Darles
    paginas separadas es fabricar canibalizacion.
    """
    ordered = sorted(members, key=lambda k: (-k.priority, k.term))
    pages: list[PageSpec] = []
    for keyword in ordered:
        for page in pages:
            # Misma intencion ademas de texto parecido. "sistema septico
            # aerobico" y "cuanto cuesta un sistema septico aerobico" se
            # parecen mucho y son dos paginas distintas: una explica, la otra
            # vende. Fusionarlas pierde la comercial o desenfoca la cabecera.
            if page.primary.intent.label != keyword.intent.label:
                continue
            if jaccard(page.primary.tokens, keyword.tokens) >= merge_threshold:
                page.secondary.append(keyword)
                break
        else:
            pages.append(
                PageSpec(primary=keyword, role=ROLE_SATELLITE, cluster_id="")
            )
    # El pilar es la pagina de la semilla.
    for index, page in enumerate(pages):
        if page.primary.term == seed.term and index != 0:
            pages.insert(0, pages.pop(index))
            break
    return pages
