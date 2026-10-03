"""Reglas de decision sobre archivos.

El criterio, que es lo que separa esto de un noindex masivo:

  Un archivo con diez articulos es un hub legitimo y Google premia la
  estructura. Un archivo con un articulo y 400 palabras es una version peor
  de ese articulo.

Y la preferencia que casi nadie aplica: si existen articulos huerfanos que
convertirian el archivo fino en un hub real, la recomendacion es RECATEGORIZAR,
no ocultar. Arreglar la causa en vez del sintoma.
"""

from __future__ import annotations

from dataclasses import dataclass, field

THIN_WORDS = 600
THIN_POSTS = 3
HUB_POSTS = 6

VERDICT_HUB = "hub"
VERDICT_THIN = "thin"
VERDICT_BORDERLINE = "borderline"
VERDICT_DUPLICATE = "duplicado"

ACTION_NONE = "ninguna"
ACTION_RECATEGORIZE = "recategorizar"
ACTION_NOINDEX = "noindex"
ACTION_DISABLE = "desactivar_archivo"


@dataclass
class Archive:
    """Un archivo medido: autor, categoria o etiqueta."""

    url: str
    kind: str
    title: str = ""
    status: int = 0
    words: int = 0
    posts: int = 0
    indexable: bool = True
    self_canonical: bool = False
    in_sitemap: bool = False
    verification: str = ""
    # Articulos que podrian reasignarse aqui para convertirlo en hub.
    recategorization_candidates: list[str] = field(default_factory=list)

    verdict: str = ""
    action: str = ""
    reason: str = ""
    priority: int = 0  # 1 = primero


def _plural(count: int, singular: str) -> str:
    """Evita el '1 articulos' que delata una plantilla sin cuidado."""
    return f"{count} {singular}" if count == 1 else f"{count} {singular}s"


def judge(archive: Archive, thin_words: int = THIN_WORDS) -> Archive:
    """Asigna veredicto, accion y prioridad. No toca la red."""

    # Un archivo ya en noindex no es un problema abierto.
    if not archive.indexable:
        archive.verdict = VERDICT_THIN if archive.words < thin_words else VERDICT_HUB
        archive.action = ACTION_NONE
        archive.reason = "Ya esta en noindex: no es indexable, no compite."
        archive.priority = 0
        return archive

    if not (200 <= archive.status < 300):
        archive.verdict = VERDICT_THIN
        archive.action = ACTION_NONE
        archive.reason = f"No se sirve (HTTP {archive.status}): nada que arreglar."
        archive.priority = 0
        return archive

    # Archivo de autor en sitio de un solo autor: duplicado de la portada.
    # Yoast lo dice en su propia documentacion. El arreglo fuerte es
    # desactivar el archivo entero, no ponerle noindex.
    if archive.kind == "author":
        archive.verdict = VERDICT_DUPLICATE
        archive.action = ACTION_DISABLE
        archive.reason = (
            "Archivo de autor indexable. En un sitio de un solo autor es un "
            "duplicado de la portada. Desactivar el archivo completo."
        )
        archive.priority = 1
        return archive

    is_thin = archive.words < thin_words or archive.posts <= THIN_POSTS

    if not is_thin:
        archive.verdict = VERDICT_HUB
        archive.action = ACTION_NONE
        archive.reason = (
            f"Hub legitimo: {_plural(archive.posts, 'articulo')} y "
            f"{archive.words} palabras. Google premia esta estructura. No tocar."
        )
        archive.priority = 0
        return archive

    # Fino. La pregunta no es si ocultarlo, es si puede dejar de ser fino.
    if archive.recategorization_candidates:
        available = len(archive.recategorization_candidates)
        needed = max(0, HUB_POSTS - archive.posts)
        archive.verdict = VERDICT_BORDERLINE
        archive.action = ACTION_RECATEGORIZE
        head = (
            f"Fino hoy ({_plural(archive.posts, 'articulo')}, "
            f"{archive.words} palabras)."
        )
        if available >= needed:
            tail = (
                f"Reasignando {_plural(needed, 'articulo')} de "
                f"{_plural(available, 'candidato')} deja de ser archivo fino y "
                "pasa a hub real."
            )
        else:
            # Honestidad en la cifra: los candidatos no bastan por si solos.
            gap = needed - available
            tail = (
                f"Hay {_plural(available, 'candidato')} "
                f"{'reasignable' if available == 1 else 'reasignables'}, pero el umbral "
                f"de hub pide {needed}: reasignarlos deja el archivo a "
                f"{_plural(gap, 'articulo')} de ser un hub real. Mientras tanto "
                "sigue siendo fino."
            )
        archive.reason = f"{head} {tail} Arreglar la causa, no ocultar el sintoma."
        archive.priority = 1
        return archive

    archive.verdict = VERDICT_THIN
    archive.action = ACTION_NOINDEX
    archive.reason = (
        f"Fino sin salida: {_plural(archive.posts, 'articulo')}, {archive.words} "
        "palabras, y no hay articulos reasignables. Es una version peor del "
        "articulo que lista."
    )
    archive.priority = 2
    return archive


def network_guard(archives: list[Archive]) -> list[str]:
    """Avisos que evitan el error de bulto.

    El fallo clasico es noindexar las siete categorias de golpe: pierdes los
    hubs legitimos y la estructura que Google premia.
    """
    warnings: list[str] = []
    categories = [a for a in archives if a.kind == "category"]
    if categories:
        to_hide = [a for a in categories if a.action == ACTION_NOINDEX]
        if len(to_hide) == len(categories) and len(categories) > 2:
            warnings.append(
                f"AVISO: la regla propone noindex en las {len(categories)} categorias. "
                "Revisar a mano antes de aplicar: ocultarlas todas destruye la "
                "estructura de silos. Preferir recategorizacion donde sea posible."
            )
    hubs = [a for a in archives if a.verdict == VERDICT_HUB]
    if hubs:
        warnings.append(
            f"{len(hubs)} archivo(s) son hubs legitimos y quedan intactos: "
            + ", ".join(a.url for a in hubs)
        )
    return warnings


@dataclass
class Cannibalization:
    """Canibalizacion archivo-vs-articulo, con cifras de Search Console."""

    archive_url: str
    archive_impressions: int
    article_url: str
    article_impressions: int

    @property
    def confirmed(self) -> bool:
        return self.archive_impressions > self.article_impressions

    def describe(self) -> str:
        verdict = "CONFIRMADA" if self.confirmed else "no confirmada"
        return (
            f"{verdict}: archivo {self.archive_url} con {self.archive_impressions} "
            f"impresiones frente a {self.article_url} con {self.article_impressions}."
        )


def find_cannibalization(
    archive: Archive,
    listed_articles: list[str],
    impressions: dict[str, int],
) -> list[Cannibalization]:
    """Compara el archivo contra cada articulo que lista.

    `impressions` viene de una exportacion de Search Console. Sin ese dato no
    se inventa nada: se devuelve lista vacia y el informe lo dice.
    """
    archive_impressions = impressions.get(_key(archive.url))
    if archive_impressions is None:
        return []
    results: list[Cannibalization] = []
    for article in listed_articles:
        article_impressions = impressions.get(_key(article))
        if article_impressions is None:
            continue
        results.append(
            Cannibalization(
                archive_url=archive.url,
                archive_impressions=archive_impressions,
                article_url=article,
                article_impressions=article_impressions,
            )
        )
    return results


def _key(url: str) -> str:
    from urllib.parse import urlparse

    parsed = urlparse(url)
    path = (parsed.path or "/").rstrip("/") or "/"
    return f"{parsed.netloc.lower()}{path}"
