"""Cliente falso: la auditoria completa se verifica sin tocar la red."""

from __future__ import annotations

from datetime import datetime, timezone

from auditor.http import Response


class FakeClient:
    """Sirve respuestas de un diccionario. Cuenta peticiones como el real."""

    def __init__(self, routes: dict[str, tuple[int, str, str]]) -> None:
        # routes: url -> (status, content_type, body)
        self.routes = routes
        self.request_count = 0
        self.requested: list[str] = []

    def get(self, url: str) -> Response:
        self.request_count += 1
        self.requested.append(url)
        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        if url not in self.routes:
            return Response(
                url=url, final_url=url, status=404, headers={"content-type": "text/html"},
                body="", elapsed_ms=1, consulted_at=now,
            )
        status, content_type, body = self.routes[url]
        return Response(
            url=url, final_url=url, status=status,
            headers={"content-type": content_type}, body=body,
            elapsed_ms=1, consulted_at=now,
        )


SITE = "https://ejemplo.test"

ROBOTS = """User-agent: *
Disallow: /wp-admin/
Allow: /wp-admin/admin-ajax.php

Sitemap: https://ejemplo.test/sitemap_index.xml
"""

ROBOTS_SIN_SITEMAP = """User-agent: *
Disallow: /wp-admin/
"""


def _urlset(urls: list[str]) -> str:
    entries = "".join(f"<url><loc>{u}</loc></url>" for u in urls)
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
        f"{entries}</urlset>"
    )


def _index(urls: list[str]) -> str:
    entries = "".join(f"<sitemap><loc>{u}</loc></sitemap>" for u in urls)
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
        f"{entries}</sitemapindex>"
    )


def _archive_html(url: str, title: str, articles: list[str], filler_words: int,
                  robots_meta: str = "index, follow") -> str:
    items = "".join(
        f'<article><h2><a href="{a}">{a.rstrip("/").rsplit("/", 1)[-1]}</a></h2></article>'
        for a in articles
    )
    filler = " ".join(["palabra"] * filler_words)
    return (
        f"<html><head><title>{title}</title>"
        f'<meta name="robots" content="{robots_meta}">'
        f'<link rel="canonical" href="{url}">'
        "</head><body>"
        '<nav><a href="/">Inicio</a><a href="/contacto/">Contacto</a></nav>'
        f"<main><h1>{title}</h1>{items}<p>{filler}</p></main>"
        '<footer><a href="/aviso-legal/">Aviso legal</a></footer>'
        "</body></html>"
    )


# Escenario completo: un autor duplicado, una categoria fina con candidatos,
# una categoria fina sin salida, y un hub legitimo que no se debe tocar.
POSTS = [
    f"{SITE}/alarma-septica-pitando/",
    f"{SITE}/bomba-de-aire-no-funciona/",
    f"{SITE}/aspersor-atascado-alarma/",
    f"{SITE}/mejor-equipo-septico-comparativa/",
    f"{SITE}/cuanto-cuesta-instalar-septico/",
    f"{SITE}/que-es-un-sistema-aerobico/",
    f"{SITE}/como-mantener-el-sistema/",
    f"{SITE}/guia-de-inspeccion/",
    f"{SITE}/tipos-de-filtros/",
    f"{SITE}/instalador-cerca-de-mi/",
]

AUTHOR_URL = f"{SITE}/author/alex/"
CAT_ALARMAS = f"{SITE}/category/alarma/"
CAT_FLORIDA = f"{SITE}/category/florida/"
CAT_HUB = f"{SITE}/category/mantenimiento/"


def routes(robots_body: str = ROBOTS) -> dict[str, tuple[int, str, str]]:
    xml = "application/xml"
    html = "text/html; charset=UTF-8"
    return {
        f"{SITE}/robots.txt": (200, "text/plain", robots_body),
        f"{SITE}/sitemap_index.xml": (200, xml, _index([
            f"{SITE}/post-sitemap.xml",
            f"{SITE}/category-sitemap.xml",
            f"{SITE}/author-sitemap.xml",
        ])),
        f"{SITE}/post-sitemap.xml": (200, xml, _urlset(POSTS)),
        f"{SITE}/category-sitemap.xml": (200, xml, _urlset(
            [CAT_ALARMAS, CAT_FLORIDA, CAT_HUB]
        )),
        f"{SITE}/author-sitemap.xml": (200, xml, _urlset([AUTHOR_URL])),
        AUTHOR_URL: (200, html, _archive_html(
            AUTHOR_URL, "Archivo de Alex", POSTS, 900
        )),
        CAT_ALARMAS: (200, html, _archive_html(
            CAT_ALARMAS, "Alarma", [POSTS[0]], 300
        )),
        CAT_FLORIDA: (200, html, _archive_html(
            CAT_FLORIDA, "Florida", [f"{SITE}/requisitos-florida/"], 290
        )),
        CAT_HUB: (200, html, _archive_html(
            CAT_HUB, "Mantenimiento", POSTS[5:10], 900
        )),
    }
