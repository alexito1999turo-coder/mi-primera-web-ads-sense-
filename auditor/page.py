"""Analisis del HTML SERVIDO.

La casilla marcada en el panel de Yoast no es una verificacion. Lo unico que
cuenta es la etiqueta meta robots que el servidor entrega de verdad.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from html.parser import HTMLParser
from urllib.parse import urljoin, urlparse

# Bloques que no son contenido: no deben contar palabras ni enlaces de articulo.
CHROME_TAGS = {
    "script", "style", "noscript", "nav", "header", "footer",
    "aside", "form", "template", "svg", "button", "select",
}

CONTENT_TAGS = ("main", "article")

ARCHIVE_PATH_HINTS = (
    "/category/", "/categoria/", "/tag/", "/etiqueta/", "/author/", "/autor/",
    "/page/", "/pagina/", "/feed", "/wp-json", "/wp-admin", "/wp-content/",
    "/search", "/buscar", "/comment", "?replytocom", "/amp/",
)

WORD_RE = re.compile(r"[0-9A-Za-zÁÉÍÓÚÜÑáéíóúüñ][0-9A-Za-zÁÉÍÓÚÜÑáéíóúüñ'’\-]*")


@dataclass
class Link:
    href: str
    text: str


@dataclass
class Page:
    """Lo que el servidor entrego, interpretado."""

    url: str = ""
    title: str = ""
    meta_robots: str = ""
    canonical: str = ""
    h1: str = ""
    word_count: int = 0
    content_source: str = ""  # main | article | body
    links: list[Link] = field(default_factory=list)
    article_elements: int = 0

    @property
    def noindex(self) -> bool:
        return "noindex" in self.meta_robots.lower()

    @property
    def indexable(self) -> bool:
        return not self.noindex

    @property
    def self_canonical(self) -> bool:
        if not self.canonical:
            return False
        return _normalize(self.canonical) == _normalize(self.url)

    def internal_article_links(self) -> list[Link]:
        """Enlaces que parecen articulos, no navegacion ni paginacion.

        Es la base del recuento de posts de un archivo: un archivo con un
        enlace de articulo es un archivo fino aunque liste diez categorias.
        """
        host = urlparse(self.url).netloc.lower()
        own = _normalize(self.url)
        seen: set[str] = set()
        result: list[Link] = []
        for link in self.links:
            parsed = urlparse(link.href)
            if parsed.scheme and parsed.scheme not in ("http", "https"):
                continue
            if parsed.netloc and parsed.netloc.lower() != host:
                continue
            path = (parsed.path or "/").lower()
            if path in ("", "/"):
                continue
            if any(hint in link.href.lower() for hint in ARCHIVE_PATH_HINTS):
                continue
            key = _normalize(link.href)
            if key == own or key in seen:
                continue
            seen.add(key)
            result.append(link)
        return result


def _normalize(url: str) -> str:
    parsed = urlparse(url.strip())
    path = (parsed.path or "/").rstrip("/") or "/"
    return f"{parsed.netloc.lower()}{path}"


class _Parser(HTMLParser):
    def __init__(self, base_url: str) -> None:
        super().__init__(convert_charrefs=True)
        self.base_url = base_url
        self.page = Page(url=base_url)
        self._chrome_depth = 0
        self._content_depth = 0
        self._content_tag = ""
        self._in_title = False
        self._in_h1 = False
        self._anchor: Link | None = None
        self._body_words: list[str] = []
        self._content_words: list[str] = []

    # -- apertura ---------------------------------------------------------
    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = {k.lower(): (v or "") for k, v in attrs}

        if tag in CHROME_TAGS:
            self._chrome_depth += 1
            return

        if tag == "title":
            self._in_title = True
        elif tag == "h1":
            self._in_h1 = True
        elif tag == "meta":
            name = attributes.get("name", "").lower()
            if name == "robots":
                self.page.meta_robots = attributes.get("content", "")
        elif tag == "link":
            rel = attributes.get("rel", "").lower()
            if "canonical" in rel:
                self.page.canonical = urljoin(self.base_url, attributes.get("href", ""))
        elif tag == "a":
            # Un enlace dentro de nav, header, footer o aside es navegacion,
            # nunca un articulo listado por el archivo.
            href = attributes.get("href", "").strip()
            if (
                not self._chrome_depth
                and href
                and not href.startswith(("#", "javascript:", "mailto:", "tel:"))
            ):
                self._anchor = Link(href=urljoin(self.base_url, href), text="")
        elif tag == "article":
            self.page.article_elements += 1

        if tag in CONTENT_TAGS:
            # El primer contenedor de contenido que aparece manda.
            if self._content_depth == 0:
                self._content_tag = tag
                self._content_words = []
            if tag == self._content_tag:
                self._content_depth += 1

    # -- cierre -----------------------------------------------------------
    def handle_endtag(self, tag: str) -> None:
        if tag in CHROME_TAGS:
            self._chrome_depth = max(0, self._chrome_depth - 1)
            return
        if tag == "title":
            self._in_title = False
        elif tag == "h1":
            self._in_h1 = False
        elif tag == "a" and self._anchor is not None:
            self._anchor.text = self._anchor.text.strip()
            self.page.links.append(self._anchor)
            self._anchor = None
        elif tag == self._content_tag and self._content_depth > 0:
            self._content_depth -= 1

    # -- texto ------------------------------------------------------------
    def handle_data(self, data: str) -> None:
        if self._in_title:
            self.page.title += data.strip() + " "
            return
        if self._chrome_depth:
            return
        if self._in_h1 and not self.page.h1:
            self.page.h1 = data.strip()
        if self._anchor is not None:
            self._anchor.text += data
        words = WORD_RE.findall(data)
        if not words:
            return
        self._body_words.extend(words)
        if self._content_depth:
            self._content_words.extend(words)

    # -- resultado --------------------------------------------------------
    def finish(self) -> Page:
        # Preferir el contenedor de contenido; caer al body solo si no hay o
        # si lo que trae es tan corto que claramente no es el contenido.
        if self._content_words and len(self._content_words) >= 25:
            self.page.word_count = len(self._content_words)
            self.page.content_source = self._content_tag
        else:
            self.page.word_count = len(self._body_words)
            self.page.content_source = "body"
        self.page.title = self.page.title.strip()
        return self.page


def parse(html: str, url: str) -> Page:
    """Interpreta el HTML servido. No descarga nada."""
    parser = _Parser(url)
    try:
        parser.feed(html)
        # close() vacia el buffer: sin esto, el HTML truncado pierde el ultimo
        # fragmento (un <title> sin cerrar se quedaba vacio).
        parser.close()
    except Exception:  # noqa: BLE001 - HTML roto no debe tumbar la auditoria
        pass
    return parser.finish()
