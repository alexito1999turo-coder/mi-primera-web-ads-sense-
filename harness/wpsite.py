"""Servidor que imita un WordPress real: paginas, sitemaps y API REST.

Lo que se prueba aqui y no se podia probar con un doble en memoria:

- gzip y charset declarado en la cabecera
- redirect 301 de la URL sin barra a la canonica
- marcado de tema real: nav, header, footer, aside, comentarios de Yoast
- la API REST con sus codigos: 401 sin credenciales, 400 con cuerpo invalido,
  array vacio en la busqueda por slug, 201 al crear, 200 al actualizar
"""

from __future__ import annotations

import base64
import gzip
import json
import threading
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

# --- contenido del sitio simulado -----------------------------------------

AUTHOR_SLUG = "alexyter"

POSTS: dict[str, str] = {
    "coste-sistema-septico-aerobico": "Cuanto cuesta un sistema septico aerobico",
    "instalador-septico-cerca-de-mi": "Instalador septico cerca de mi",
    "alarma-septica-pitando": "Alarma septica pitando: que hacer",
    "alarma-septica-no-para": "La alarma septica no para de pitar",
    "bomba-de-aire-no-funciona": "La bomba de aire no funciona",
    "olores-del-sistema-septico": "Olores del sistema septico",
    "aspersor-atascado": "Aspersor atascado del sistema",
    "corte-de-luz-septico": "Corte de luz y sistema septico",
    "mantenimiento-anual-septico": "Mantenimiento anual del sistema septico",
    "requisitos-florida-septico": "Requisitos de Florida para septicos",
}

# Archivos: (slug, tipo, posts que listan, palabras de relleno, noindex)
ARCHIVES: list[tuple[str, str, list[str], int, bool]] = [
    (f"author/{AUTHOR_SLUG}", "author", list(POSTS)[:10], 820, False),
    ("category/alarmas", "category", ["alarma-septica-pitando"], 160, False),
    ("category/florida", "category", ["requisitos-florida-septico"], 150, False),
    ("category/costes", "category", ["coste-sistema-septico-aerobico",
                                      "instalador-septico-cerca-de-mi"], 240, False),
    ("category/mantenimiento", "category",
     ["mantenimiento-anual-septico", "olores-del-sistema-septico",
      "aspersor-atascado", "corte-de-luz-septico",
      "bomba-de-aire-no-funciona", "alarma-septica-no-para"], 780, False),
    ("tag/urgencias", "tag", ["alarma-septica-pitando"], 90, True),  # ya en noindex
]

ROBOTS = """User-agent: *
Disallow: /wp-admin/
Allow: /wp-admin/admin-ajax.php
Disallow: /?s=

Sitemap: {base}/sitemap_index.xml
"""


def _page(base: str, path: str, title: str, articles: list[str],
          filler_words: int, noindex: bool) -> str:
    """HTML con la forma de un tema real de WordPress."""
    items = "\n".join(
        f'      <article class="post type-post">\n'
        f'        <header class="entry-header"><h2 class="entry-title">'
        f'<a href="{base}/{slug}/" rel="bookmark">{POSTS[slug]}</a></h2></header>\n'
        f'        <div class="entry-summary"><p>Resumen breve de la entrada.</p></div>\n'
        f"      </article>"
        for slug in articles
    )
    filler = " ".join(["Texto de archivo generado por el tema."] * max(1, filler_words // 6))
    robots = "noindex, follow" if noindex else "index, follow"
    return f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title} - Sitio de prueba</title>
<!-- This site is optimized with the Yoast SEO plugin -->
<meta name="robots" content="{robots}">
<link rel="canonical" href="{base}/{path}/">
<script type="application/ld+json">{{"@context":"https://schema.org","@type":"CollectionPage"}}</script>
<link rel="stylesheet" href="{base}/wp-content/themes/demo/style.css">
</head>
<body class="archive">
<header id="masthead" class="site-header">
  <a class="site-logo" href="{base}/">Sitio de prueba</a>
  <nav id="site-navigation" class="main-navigation">
    <ul>
      <li><a href="{base}/">Inicio</a></li>
      <li><a href="{base}/category/costes/">Costes</a></li>
      <li><a href="{base}/category/mantenimiento/">Mantenimiento</a></li>
      <li><a href="{base}/contacto/">Contacto</a></li>
      <li><a href="{base}/politica-de-privacidad/">Privacidad</a></li>
    </ul>
  </nav>
</header>
<div id="content" class="site-content">
  <main id="primary" class="site-main">
    <header class="page-header"><h1 class="page-title">{title}</h1></header>
{items}
    <div class="archive-description"><p>{filler}</p></div>
    <nav class="pagination"><a href="{base}/{path}/page/2/">Siguiente</a></nav>
  </main>
  <aside id="secondary" class="widget-area">
    <section class="widget"><h2>Entradas recientes</h2><ul>
      <li><a href="{base}/coste-sistema-septico-aerobico/">Costes</a></li>
      <li><a href="{base}/alarma-septica-pitando/">Alarma</a></li>
    </ul></section>
  </aside>
</div>
<footer id="colophon" class="site-footer">
  <nav class="footer-navigation"><ul>
    <li><a href="{base}/aviso-legal/">Aviso legal</a></li>
    <li><a href="{base}/politica-de-cookies/">Cookies</a></li>
  </ul></nav>
  <p>Orgullosamente desarrollado con WordPress</p>
</footer>
<script src="{base}/wp-includes/js/jquery.min.js"></script>
</body>
</html>"""


def _urlset(urls: list[str]) -> str:
    entries = "".join(f"<url><loc>{u}</loc></url>" for u in urls)
    return ('<?xml version="1.0" encoding="UTF-8"?>'
            '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
            f"{entries}</urlset>")


def _index(urls: list[str]) -> str:
    entries = "".join(f"<sitemap><loc>{u}</loc></sitemap>" for u in urls)
    return ('<?xml version="1.0" encoding="UTF-8"?>'
            '<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
            f"{entries}</sitemapindex>")


@dataclass
class SiteState:
    """Estado mutable: los posts que crea la API REST."""

    user: str = "editor"
    password: str = "app-pass-1234"
    posts: dict[int, dict] = field(default_factory=dict)
    next_id: int = 100
    requests: list[tuple[str, str]] = field(default_factory=list)

    @property
    def auth_header(self) -> str:
        raw = f"{self.user}:{self.password}".encode()
        return "Basic " + base64.b64encode(raw).decode()


class _Handler(BaseHTTPRequestHandler):
    state: SiteState
    base: str

    def log_message(self, *args) -> None:  # silencio en las pruebas
        pass

    # -- utilidades -------------------------------------------------------
    def _send(self, status: int, body: bytes, content_type: str,
              extra: dict[str, str] | None = None, compress: bool = False) -> None:
        if compress:
            body = gzip.compress(body)
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        if compress:
            self.send_header("Content-Encoding", "gzip")
        for key, value in (extra or {}).items():
            self.send_header(key, value)
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def _json(self, status: int, payload) -> None:
        self._send(status, json.dumps(payload).encode(), "application/json; charset=UTF-8")

    def _authorized(self) -> bool:
        return self.headers.get("Authorization") == self.state.auth_header

    # -- GET --------------------------------------------------------------
    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        path = parsed.path
        self.state.requests.append(("GET", path))
        base = self.base

        if path == "/robots.txt":
            self._send(200, ROBOTS.format(base=base).encode(), "text/plain; charset=UTF-8")
            return

        if path == "/sitemap_index.xml":
            children = [
                f"{base}/post-sitemap.xml",
                f"{base}/category-sitemap.xml",
                f"{base}/post_tag-sitemap.xml",
                f"{base}/author-sitemap.xml",
            ]
            # gzip a proposito: el cliente tiene que saber descomprimir.
            self._send(200, _index(children).encode(), "application/xml; charset=UTF-8",
                       compress=True)
            return

        if path == "/post-sitemap.xml":
            self._send(200, _urlset([f"{base}/{s}/" for s in POSTS]).encode(),
                       "application/xml; charset=UTF-8")
            return
        if path == "/category-sitemap.xml":
            urls = [f"{base}/{slug}/" for slug, kind, *_ in ARCHIVES if kind == "category"]
            self._send(200, _urlset(urls).encode(), "application/xml; charset=UTF-8")
            return
        if path == "/post_tag-sitemap.xml":
            urls = [f"{base}/{slug}/" for slug, kind, *_ in ARCHIVES if kind == "tag"]
            self._send(200, _urlset(urls).encode(), "application/xml; charset=UTF-8")
            return
        if path == "/author-sitemap.xml":
            urls = [f"{base}/{slug}/" for slug, kind, *_ in ARCHIVES if kind == "author"]
            self._send(200, _urlset(urls).encode(), "application/xml; charset=UTF-8")
            return

        if path.startswith("/wp-json/wp/v2/posts"):
            if not self._authorized():
                self._json(401, {"code": "rest_not_logged_in",
                                 "message": "No estas conectado.", "data": {"status": 401}})
                return
            slug = parse_qs(parsed.query).get("slug", [""])[0]
            found = [p for p in self.state.posts.values() if p["slug"] == slug] if slug else []
            self._json(200, found)
            return

        # Paginas del sitio. WordPress redirige la URL sin barra final a la
        # canonica con barra. Hay que decidir por `path`, no por la version ya
        # despojada de barras: compararlas despues de quitarlas hacia que la
        # canonica se redirigiera a si misma, en bucle infinito.
        stripped = path.strip("/")
        canonical = path.endswith("/")

        known = {slug for slug, *_ in ARCHIVES} | set(POSTS)
        if stripped in known and not canonical:
            self._send(301, b"", "text/html", {"Location": f"{base}/{stripped}/"})
            return

        if canonical:
            for slug, kind, articles, words, noindex in ARCHIVES:
                if stripped == slug:
                    title = slug.rsplit("/", 1)[-1].capitalize()
                    html = _page(base, slug, title, articles, words, noindex)
                    self._send(200, html.encode("utf-8"), "text/html; charset=UTF-8",
                               compress=True)
                    return
            if stripped in POSTS:
                html = _page(base, stripped, POSTS[stripped], [], 1500, False)
                self._send(200, html.encode("utf-8"), "text/html; charset=UTF-8")
                return

        self._send(404, b"<html><body>No encontrado</body></html>",
                   "text/html; charset=UTF-8")

    # -- POST -------------------------------------------------------------
    def do_POST(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        path = parsed.path
        self.state.requests.append(("POST", path))

        if not path.startswith("/wp-json/wp/v2/posts"):
            self._json(404, {"code": "rest_no_route", "message": "Sin ruta",
                             "data": {"status": 404}})
            return
        if not self._authorized():
            self._json(401, {"code": "rest_cannot_create",
                             "message": "Credenciales no validas.",
                             "data": {"status": 401}})
            return

        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length) if length else b"{}"
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            self._json(400, {"code": "rest_invalid_json",
                             "message": "JSON invalido.", "data": {"status": 400}})
            return

        if not payload.get("title"):
            self._json(400, {"code": "rest_missing_callback_param",
                             "message": "Falta el parametro: title",
                             "data": {"status": 400}})
            return
        if payload.get("status") not in ("draft", "publish", "pending", "private", None):
            self._json(400, {"code": "rest_invalid_param",
                             "message": "status no es valido.",
                             "data": {"status": 400}})
            return

        remainder = path[len("/wp-json/wp/v2/posts"):].strip("/")
        if remainder.isdigit():  # actualizacion
            post_id = int(remainder)
            if post_id not in self.state.posts:
                self._json(404, {"code": "rest_post_invalid_id",
                                 "message": "ID no valido.", "data": {"status": 404}})
                return
            self.state.posts[post_id].update(payload)
            self._json(200, self.state.posts[post_id])
            return

        post_id = self.state.next_id
        self.state.next_id += 1
        record = {"id": post_id, "status": payload.get("status", "draft"),
                  "slug": payload.get("slug", ""), "title": payload.get("title", ""),
                  "content": payload.get("content", "")}
        self.state.posts[post_id] = record
        self._json(201, record)


class LocalWordPress:
    """Levanta el servidor en un puerto libre y lo apaga al salir."""

    def __init__(self) -> None:
        self.state = SiteState()
        handler = type("Bound", (_Handler,), {"state": self.state, "base": ""})
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        self.base = f"http://127.0.0.1:{self.server.server_address[1]}"
        handler.base = self.base
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)

    def __enter__(self) -> "LocalWordPress":
        self.thread.start()
        return self

    def __exit__(self, *exc) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)
