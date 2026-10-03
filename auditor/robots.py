"""robots.txt: declaracion de sitemap y reglas que el auditor respeta.

Dos trabajos. Uno: comprobar que el sitemap esta declarado, que es uno de los
puntos de la auditoria. Dos: no pedir rutas que el sitio prohibe.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from urllib.parse import urljoin, urlparse

from .http import Client, Response


@dataclass
class Robots:
    url: str
    status: int = 0
    present: bool = False
    sitemaps: list[str] = field(default_factory=list)
    disallow: list[str] = field(default_factory=list)
    allow: list[str] = field(default_factory=list)
    raw: str = ""
    verification: str = ""

    @property
    def declares_sitemap(self) -> bool:
        return bool(self.sitemaps)

    def allows(self, url: str) -> bool:
        """Coincidencia de prefijo con precedencia de la regla mas larga."""
        path = urlparse(url).path or "/"
        best_block = max(
            (rule for rule in self.disallow if rule and path.startswith(rule)),
            key=len,
            default="",
        )
        if not best_block:
            return True
        best_allow = max(
            (rule for rule in self.allow if rule and path.startswith(rule)),
            key=len,
            default="",
        )
        return len(best_allow) >= len(best_block)


def fetch(client: Client, site_root: str) -> Robots:
    url = urljoin(site_root, "/robots.txt")
    response: Response = client.get(url)
    robots = Robots(url=url, status=response.status, raw=response.body)
    robots.verification = response.summary()
    if not response.ok:
        return robots
    robots.present = True

    # Solo aplicamos las reglas de los grupos que nos afectan: '*' y el
    # nuestro. Un bloque para Googlebot no limita a este auditor.
    applies = False
    for line in response.body.splitlines():
        line = line.split("#", 1)[0].strip()
        if not line or ":" not in line:
            continue
        field_name, _, value = line.partition(":")
        key = field_name.strip().lower()
        value = value.strip()
        if key == "user-agent":
            applies = value == "*" or "m1auditor" in value.lower()
        elif key == "sitemap" and value:
            robots.sitemaps.append(value)
        elif key == "disallow" and applies and value:
            robots.disallow.append(value)
        elif key == "allow" and applies and value:
            robots.allow.append(value)
    return robots
