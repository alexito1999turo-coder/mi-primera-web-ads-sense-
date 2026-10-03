"""Keywords: modelo y carga desde exportaciones reales.

Acepta exportaciones de DataForSEO, Semrush, Ahrefs o un CSV a mano. Las
cabeceras cambian entre herramientas; el cargador las reconoce por contenido
en vez de exigir un formato.
"""

from __future__ import annotations

import csv
import re
from dataclasses import dataclass, field
from pathlib import Path

from auditor.intent import Intent, classify

TOKEN_RE = re.compile(r"[a-z0-9áéíóúüñ]+")

# Modificadores de intencion normalizados a un token canonico.
#
# "cuanto cuesta un sistema septico" y "precio sistema septico" son la misma
# busqueda y deben ser la misma pagina. Sin esta normalizacion caen en clusters
# distintos, porque al descartar los tokens genericos del nicho a las keywords
# cortas no les queda señal comun. Es un conjunto cerrado en la practica.
MODIFIER_SYNONYMS: tuple[tuple[str, str], ...] = (
    # Las frases van antes que las palabras: se reemplaza la mas larga primero.
    ("cuanto cuesta", "§precio"), ("cuánto cuesta", "§precio"),
    ("how much does", "§precio"), ("how much", "§precio"),
    ("donde comprar", "§comprar"), ("where to buy", "§comprar"),
    ("cerca de mi", "§cerca"), ("en mi zona", "§cerca"), ("near me", "§cerca"),
    ("que es", "§quees"), ("qué es", "§quees"), ("what is", "§quees"),
    ("how to", "§como"),
    ("precio", "§precio"), ("precios", "§precio"), ("coste", "§precio"),
    ("costo", "§precio"), ("costes", "§precio"), ("cost", "§precio"),
    ("price", "§precio"), ("pricing", "§precio"), ("tarifa", "§precio"),
    ("mejor", "§mejor"), ("mejores", "§mejor"), ("best", "§mejor"),
    ("top", "§mejor"),
    ("comparativa", "§vs"), ("comparison", "§vs"), ("versus", "§vs"),
    ("vs", "§vs"), ("compare", "§vs"),
    ("reseña", "§review"), ("resena", "§review"), ("opiniones", "§review"),
    ("review", "§review"), ("reviews", "§review"),
    ("comprar", "§comprar"), ("buy", "§comprar"),
    ("como", "§como"), ("cómo", "§como"),
)


def normalize_modifiers(term: str) -> str:
    """Sustituye sinonimos de intencion por su token canonico."""
    out = f" {term.lower()} "
    for phrase, canonical in MODIFIER_SYNONYMS:
        out = out.replace(f" {phrase} ", f" {canonical} ")
    return out.strip()
STOPWORDS = {
    "the", "and", "for", "with", "your", "you", "are", "how", "what", "why",
    "que", "los", "las", "del", "por", "con", "una", "uno", "para", "como",
    "mi", "de", "en", "el", "la", "un", "is", "to", "a", "of", "do", "does",
}


@dataclass
class Keyword:
    """Una keyword medida. `volume` y `difficulty` vienen de la exportacion."""

    term: str
    volume: int = 0
    difficulty: int = 0
    cpc: float = 0.0
    intent: Intent = field(default=None)  # type: ignore[assignment]

    def __post_init__(self) -> None:
        self.term = " ".join(self.term.lower().split())
        if self.intent is None:
            self.intent = classify(self.term.replace(" ", "-"), title=self.term)

    @property
    def tokens(self) -> set[str]:
        """Tokens con los modificadores de intencion ya normalizados."""
        normalized = normalize_modifiers(self.term)
        found = set()
        for raw in normalized.split():
            if raw.startswith("§"):
                found.add(raw)  # token canonico: se mantiene intacto
                continue
            for token in TOKEN_RE.findall(raw):
                if len(token) > 2 and token not in STOPWORDS:
                    found.add(token.rstrip("s") or token)
        return found

    @property
    def slug(self) -> str:
        return re.sub(r"[^a-z0-9]+", "-", self.term).strip("-")

    @property
    def priority(self) -> float:
        """Prioridad = volumen ponderado por supervivencia al clic.

        La supervivencia va al cuadrado a proposito. Con un factor lineal, una
        informacional de 10.000 busquedas seguia ganando a una comercial de
        2.000, que es justo la decision equivocada: la informacional la
        contesta AI Overviews (99,9% de cobertura, 74,3% sin clic) y no recibe
        la visita. Al cuadrado, la diferencia de intencion pesa mas que la
        diferencia de volumen, que es la realidad del SERP de 2026.
        """
        base = max(self.volume, 1)
        survival = (self.intent.click_survival / 100) ** 2
        cpc_boost = 1 + min(self.cpc, 20) / 20  # el CPC alto confirma intencion
        return round(base * survival * cpc_boost, 2)


def _pick(fields: list[str], names: tuple[str, ...]) -> str | None:
    lowered = {f.lower().strip(): f for f in fields}
    for name in names:
        if name in lowered:
            return lowered[name]
    for key, original in lowered.items():
        if any(name in key for name in names):
            return original
    return None


def _is_decimal_group(value: str, separator: str) -> bool:
    """Decide si el separador es decimal o de miles.

    Tres digitos detras (1.200) son un grupo de miles; cualquier otra longitud
    (8.50, 0.7) es un decimal. Es la heuristica estandar y acierta en los
    formatos que exportan Semrush, Ahrefs y DataForSEO.
    """
    tail = value.rsplit(separator, 1)[-1]
    return not (len(tail) == 3 and tail.isdigit())


def _number(raw: str | None) -> float:
    if not raw:
        return 0.0
    cleaned = raw.strip().replace("$", "").replace("€", "")
    cleaned = cleaned.replace(" ", "")
    # 1.234,56 (europeo) frente a 1,234.56 (anglosajon). El caso que mas duele
    # es el separador de miles suelto: "1.200" debe ser 1200, no 1.2.
    if "," in cleaned and "." in cleaned:
        if cleaned.rfind(",") > cleaned.rfind("."):
            cleaned = cleaned.replace(".", "").replace(",", ".")
        else:
            cleaned = cleaned.replace(",", "")
    elif cleaned.count(",") > 1:
        cleaned = cleaned.replace(",", "")
    elif "," in cleaned:
        cleaned = cleaned.replace(",", ".") if _is_decimal_group(cleaned, ",") else cleaned.replace(",", "")
    elif cleaned.count(".") > 1:
        cleaned = cleaned.replace(".", "")
    elif "." in cleaned and not _is_decimal_group(cleaned, "."):
        cleaned = cleaned.replace(".", "")
    try:
        return float(cleaned or 0)
    except ValueError:
        return 0.0


def load(path: str | Path) -> list[Keyword]:
    """Carga keywords de un CSV de cualquier herramienta habitual."""
    rows: list[Keyword] = []
    with open(path, newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames:
            return rows
        term_field = _pick(reader.fieldnames, ("keyword", "palabra", "query", "term", "consulta"))
        if not term_field:
            raise ValueError(
                "El CSV no tiene columna de keyword. Cabeceras encontradas: "
                + ", ".join(reader.fieldnames)
            )
        volume_field = _pick(reader.fieldnames, ("search volume", "volume", "volumen", "searches"))
        difficulty_field = _pick(reader.fieldnames, ("difficulty", "dificultad", "kd", "competition"))
        cpc_field = _pick(reader.fieldnames, ("cpc", "coste por clic", "cost per click"))

        seen: set[str] = set()
        for row in reader:
            term = (row.get(term_field) or "").strip()
            if not term:
                continue
            key = " ".join(term.lower().split())
            if key in seen:
                continue  # duplicado en origen: una keyword, una fila
            seen.add(key)
            rows.append(
                Keyword(
                    term=term,
                    volume=int(_number(row.get(volume_field) if volume_field else None)),
                    difficulty=int(_number(row.get(difficulty_field) if difficulty_field else None)),
                    cpc=_number(row.get(cpc_field) if cpc_field else None),
                )
            )
    return rows
