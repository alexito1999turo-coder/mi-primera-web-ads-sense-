"""Orquestacion del M1.

Secuencia: robots.txt -> sitemaps -> archivos indexables -> veredicto.
Todo con peticiones espaciadas y con la hora de consulta registrada.
"""

from __future__ import annotations

import csv
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

from . import intent as intent_mod
from . import page as page_mod
from . import robots as robots_mod
from . import rules as rules_mod
from .http import Client
from .sitemaps import Sitemap, discover

ARCHIVE_KINDS = ("author", "category", "tag")
STOPWORDS = {
    "the", "and", "for", "with", "your", "you", "are", "que", "los", "las",
    "del", "por", "con", "una", "uno", "sitemap", "xml", "www", "com", "http",
    "https", "category", "categoria", "tag", "etiqueta", "author", "autor",
}
TOKEN_RE = re.compile(r"[a-z0-9áéíóúüñ]+")


@dataclass
class Audit:
    site: str
    started_at: str = ""
    finished_at: str = ""
    requests_made: int = 0

    robots: robots_mod.Robots | None = None
    sitemaps: list[Sitemap] = field(default_factory=list)
    archives: list[rules_mod.Archive] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    cannibalization: list[rules_mod.Cannibalization] = field(default_factory=list)
    intent_distribution: dict[str, float] = field(default_factory=dict)
    intent_at_risk_urls: list[str] = field(default_factory=list)
    post_count: int = 0
    impressions_loaded: int = 0
    notes: list[str] = field(default_factory=list)

    @property
    def actionable(self) -> list[rules_mod.Archive]:
        items = [a for a in self.archives if a.action != rules_mod.ACTION_NONE]
        return sorted(items, key=lambda a: (a.priority, -a.words))


def _tokens(text: str) -> set[str]:
    out = set()
    for token in TOKEN_RE.findall(text.lower()):
        if len(token) < 4 or token in STOPWORDS:
            continue
        out.add(token.rstrip("s") or token)
    return out


def load_impressions(path: str | Path) -> dict[str, int]:
    """Carga impresiones de una exportacion de Search Console.

    Acepta cualquier CSV con una columna de URL y una de impresiones, en
    ingles o espanol. Sin este fichero no se afirma nada sobre canibalizacion.
    """
    data: dict[str, int] = {}
    with open(path, newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames:
            return data
        url_field = _pick(reader.fieldnames, ("page", "pagina", "página", "url", "address"))
        imp_field = _pick(reader.fieldnames, ("impressions", "impresiones"))
        if not url_field or not imp_field:
            return data
        for row in reader:
            url = (row.get(url_field) or "").strip()
            if not url:
                continue
            raw = (row.get(imp_field) or "0").strip().replace(".", "").replace(",", "")
            try:
                data[rules_mod._key(url)] = int(float(raw or 0))
            except ValueError:
                continue
    return data


def _pick(fields: list[str], names: tuple[str, ...]) -> str | None:
    lowered = {f.lower().strip(): f for f in fields}
    for name in names:
        if name in lowered:
            return lowered[name]
    for key, original in lowered.items():
        if any(name in key for name in names):
            return original
    return None


def run(
    site: str,
    client: Client | None = None,
    thin_words: int = rules_mod.THIN_WORDS,
    impressions_csv: str | Path | None = None,
    max_archives: int = 60,
) -> Audit:
    site = site if site.startswith("http") else f"https://{site}"
    root = f"{urlparse(site).scheme}://{urlparse(site).netloc}"
    client = client or Client()
    audit = Audit(site=root, started_at=_now())

    impressions: dict[str, int] = {}
    if impressions_csv:
        impressions = load_impressions(impressions_csv)
        audit.impressions_loaded = len(impressions)
    if not impressions:
        audit.notes.append(
            "Sin exportacion de Search Console: la canibalizacion no se mide. "
            "No se afirma lo que no se ha medido."
        )

    # 1. robots.txt: declaracion de sitemap y reglas a respetar.
    audit.robots = robots_mod.fetch(client, root)
    if audit.robots.present and not audit.robots.declares_sitemap:
        audit.warnings.append(
            "robots.txt no declara el sitemap. Anadir una linea 'Sitemap:' con "
            "la URL absoluta."
        )

    # 2. Sitemaps. Los de autor, categoria y etiqueta son el hallazgo.
    audit.sitemaps = discover(client, root, audit.robots.sitemaps if audit.robots else [])

    archive_urls: list[tuple[str, str]] = []
    post_urls: list[str] = []
    for sitemap in audit.sitemaps:
        if not sitemap.exists:
            continue
        if sitemap.kind in ARCHIVE_KINDS:
            for url in sitemap.urls:
                archive_urls.append((url, sitemap.kind))
        elif sitemap.kind in ("post", "page"):
            post_urls.extend(sitemap.urls)

    audit.post_count = len(post_urls)
    for kind in ARCHIVE_KINDS:
        if any(s.kind == kind and s.exists for s in audit.sitemaps):
            audit.warnings.append(
                f"Existe sitemap de {kind}: el sitio declara esos archivos a Google "
                "como contenido indexable."
            )

    # 3. Distribucion de intencion sobre los articulos declarados.
    if post_urls:
        intents = [intent_mod.classify(url) for url in post_urls]
        audit.intent_distribution = intent_mod.distribution(intents)
        audit.intent_at_risk_urls = [
            url for url, item in zip(post_urls, intents) if item.at_risk
        ]

    # 4. Medir cada archivo contra el HTML servido.
    post_tokens = {url: _tokens(url) for url in post_urls}
    for url, kind in archive_urls[:max_archives]:
        if audit.robots and not audit.robots.allows(url):
            audit.notes.append(f"robots.txt prohibe {url}: no se pide.")
            continue
        response = client.get(url)
        parsed = page_mod.parse(response.body, url) if response.body else page_mod.Page(url=url)
        listed = [link.href for link in parsed.internal_article_links()]
        posts = max(parsed.article_elements, len(listed))

        archive = rules_mod.Archive(
            url=url,
            kind=kind,
            title=parsed.title,
            status=response.status,
            words=parsed.word_count,
            posts=posts,
            indexable=parsed.indexable and response.ok,
            self_canonical=parsed.self_canonical,
            in_sitemap=True,
            verification=response.summary(),
        )
        archive.recategorization_candidates = _candidates(
            url, listed, post_tokens
        )
        rules_mod.judge(archive, thin_words=thin_words)
        audit.archives.append(archive)

        audit.cannibalization.extend(
            rules_mod.find_cannibalization(archive, listed, impressions)
        )

    if len(archive_urls) > max_archives:
        audit.notes.append(
            f"Se midieron {max_archives} de {len(archive_urls)} archivos "
            "(limite por cortesia con el servidor)."
        )

    audit.warnings.extend(rules_mod.network_guard(audit.archives))
    audit.requests_made = client.request_count
    audit.finished_at = _now()
    return audit


def _candidates(
    archive_url: str,
    already_listed: list[str],
    post_tokens: dict[str, set[str]],
) -> list[str]:
    """Articulos reasignables a este archivo, por solape de terminos.

    Si el archivo trata de 'alarms' y hay articulos con 'alarm' en la URL que
    no estan listados aqui, son candidatos a recategorizacion. Esto convierte
    el hallazgo en una accion concreta en vez de un noindex.
    """
    topic = _tokens(urlparse(archive_url).path)
    if not topic:
        return []
    listed = {rules_mod._key(u) for u in already_listed}
    found: list[str] = []
    for url, tokens in post_tokens.items():
        if rules_mod._key(url) in listed:
            continue
        if topic & tokens:
            found.append(url)
    return found


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")
