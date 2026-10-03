"""Descubrimiento y lectura de sitemaps.

El hallazgo que nadie mira: los sitemaps de autor y de categoria. Si existen,
el sitio esta declarando a Google que esos archivos son contenido indexable.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from urllib.parse import urljoin, urlparse
from xml.etree import ElementTree

from .http import Client

COMMON_PATHS = (
    "/sitemap_index.xml",
    "/sitemap.xml",
    "/wp-sitemap.xml",
    "/sitemap-index.xml",
)

# Tipo de archivo que representa cada sitemap hijo, por su nombre.
KIND_PATTERNS = (
    ("author", re.compile(r"author", re.I)),
    ("category", re.compile(r"categor", re.I)),
    ("tag", re.compile(r"(post_tag|/tag|tags)", re.I)),
    ("post", re.compile(r"(post|article|entr)", re.I)),
    ("page", re.compile(r"page", re.I)),
)


def classify(url: str) -> str:
    for kind, pattern in KIND_PATTERNS:
        if pattern.search(url):
            return kind
    return "other"


@dataclass
class Sitemap:
    url: str
    status: int = 0
    kind: str = "other"
    is_index: bool = False
    children: list[str] = field(default_factory=list)
    urls: list[str] = field(default_factory=list)
    verification: str = ""

    @property
    def exists(self) -> bool:
        return 200 <= self.status < 300


def _localname(tag: str) -> str:
    return tag.rsplit("}", 1)[-1].lower()


def _read(client: Client, url: str) -> Sitemap:
    response = client.get(url)
    sitemap = Sitemap(url=url, status=response.status, kind=classify(url))
    sitemap.verification = response.summary()
    if not response.ok or not response.body.strip():
        return sitemap
    try:
        root = ElementTree.fromstring(response.body.strip())
    except ElementTree.ParseError:
        return sitemap

    name = _localname(root.tag)
    sitemap.is_index = name == "sitemapindex"
    for element in root.iter():
        if _localname(element.tag) != "loc" or not (element.text or "").strip():
            continue
        location = element.text.strip()
        if sitemap.is_index:
            sitemap.children.append(location)
        else:
            sitemap.urls.append(location)
    return sitemap


def discover(client: Client, site_root: str, declared: list[str]) -> list[Sitemap]:
    """Lee los sitemaps declarados y, si no hay, prueba las rutas habituales.

    Devuelve el indice y sus hijos de primer nivel. No recorre los articulos:
    aqui solo interesa que archivos estan declarados como indexables.
    """
    candidates: list[str] = []
    for url in declared:
        if url not in candidates:
            candidates.append(url)
    if not candidates:
        candidates = [urljoin(site_root, path) for path in COMMON_PATHS]

    found: list[Sitemap] = []
    seen: set[str] = set()
    host = urlparse(site_root).netloc.lower()

    for url in candidates:
        if url in seen:
            continue
        seen.add(url)
        sitemap = _read(client, url)
        found.append(sitemap)
        if not sitemap.exists:
            continue
        for child in sitemap.children:
            if child in seen:
                continue
            if urlparse(child).netloc.lower() != host:
                continue
            seen.add(child)
            found.append(_read(client, child))
        # Con un indice valido ya tenemos el mapa: no seguimos probando rutas.
        if sitemap.is_index and sitemap.children:
            break
    return found
