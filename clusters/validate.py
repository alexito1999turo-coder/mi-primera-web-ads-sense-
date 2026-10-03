"""Validaciones del grafo. Son compuertas, no sugerencias.

La promesa del modulo es solape cero. Una promesa sin comprobacion es
marketing, asi que aqui se comprueba y se bloquea.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .graph import Graph, jaccard

# Tope mensual por sitio. 24 paginas, no 120.
#
# Cuatro paginas al dia en un dominio sin revision es el patron que Google
# enforced en 2026 (scaled content abuse). El tope es una decision de producto
# y se vende como virtud.
MONTHLY_CAP = 24

# Minimo de intencion con clic superviviente. Las informacionales puras tienen
# 99,9% de cobertura de AI Overviews y 74,3% sin clic: un plan mayoritariamente
# informacional es un plan que rankea sin recibir visitas.
MIN_CLICK_SURVIVING_SHARE = 0.5

# Similitud entre primarias de paginas distintas a partir de la cual compiten.
CONFLICT_THRESHOLD = 0.75

SEVERITY_BLOCK = "bloqueante"
SEVERITY_WARN = "aviso"


@dataclass
class Finding:
    code: str
    severity: str
    message: str
    pages: list[str] = field(default_factory=list)

    @property
    def blocking(self) -> bool:
        return self.severity == SEVERITY_BLOCK


@dataclass
class Validation:
    findings: list[Finding] = field(default_factory=list)

    @property
    def blocking(self) -> list[Finding]:
        return [f for f in self.findings if f.blocking]

    @property
    def passed(self) -> bool:
        return not self.blocking

    def add(self, code: str, severity: str, message: str, pages: list[str] | None = None) -> None:
        self.findings.append(
            Finding(code=code, severity=severity, message=message, pages=pages or [])
        )


def validate(
    graph: Graph,
    monthly_cap: int = MONTHLY_CAP,
    min_survival_share: float = MIN_CLICK_SURVIVING_SHARE,
    conflict_threshold: float = CONFLICT_THRESHOLD,
) -> Validation:
    result = Validation()
    pages = graph.pages

    if not pages:
        result.add("vacio", SEVERITY_BLOCK, "El grafo no tiene paginas.")
        return result

    # 1. Solape cero: ninguna keyword primaria en dos paginas. Es la promesa
    #    del modulo y se comprueba, no se asume.
    primaries: dict[str, list[str]] = {}
    for page in pages:
        primaries.setdefault(page.primary.term, []).append(page.slug)
    for term, slugs in primaries.items():
        if len(slugs) > 1:
            result.add(
                "primaria_duplicada",
                SEVERITY_BLOCK,
                f"La keyword primaria '{term}' esta asignada a {len(slugs)} paginas. "
                "Es canibalizacion fabricada por el propio plan.",
                slugs,
            )

    # 2. Una keyword no puede ser primaria de una pagina y secundaria de otra.
    secondaries: dict[str, list[str]] = {}
    for page in pages:
        for keyword in page.secondary:
            secondaries.setdefault(keyword.term, []).append(page.slug)
    for term, slugs in secondaries.items():
        if term in primaries:
            result.add(
                "primaria_y_secundaria",
                SEVERITY_BLOCK,
                f"'{term}' es primaria en {primaries[term][0]} y secundaria en "
                f"{', '.join(slugs)}. Hay que decidir de quien es.",
                primaries[term] + slugs,
            )
        elif len(slugs) > 1:
            result.add(
                "secundaria_repartida",
                SEVERITY_WARN,
                f"'{term}' aparece como secundaria en {len(slugs)} paginas.",
                slugs,
            )

    # 3. Primarias distintas pero casi iguales.
    #
    #    Misma regla que usa el constructor al fusionar, para que el sistema no
    #    se contradiga: texto parecido Y misma intencion es canibalizacion
    #    fabricada y bloquea. Texto parecido con intencion distinta son dos
    #    paginas legitimas (la cabecera explica, la comercial vende) y solo
    #    merece una mirada humana.
    for index, page in enumerate(pages):
        for other in pages[index + 1 :]:
            score = jaccard(page.primary.tokens, other.primary.tokens)
            if score < conflict_threshold:
                continue
            same_intent = page.primary.intent.label == other.primary.intent.label
            if same_intent:
                result.add(
                    "primarias_en_conflicto",
                    SEVERITY_BLOCK,
                    f"'{page.primary.term}' y '{other.primary.term}' tienen "
                    f"similitud {score:.2f} y la misma intencion "
                    f"({page.primary.intent.label}): competiran entre si. Fusionar "
                    "en una pagina con la segunda como secundaria.",
                    [page.slug, other.slug],
                )
            else:
                result.add(
                    "primarias_parecidas_intencion_distinta",
                    SEVERITY_WARN,
                    f"'{page.primary.term}' ({page.primary.intent.label}) y "
                    f"'{other.primary.term}' ({other.primary.intent.label}) se "
                    f"parecen {score:.2f} pero buscan cosas distintas. Son dos "
                    "paginas legitimas; revisar que los titulos lo dejen claro.",
                    [page.slug, other.slug],
                )

    # 4. Slugs unicos: dos paginas con el mismo slug es una sobreescritura.
    slugs: dict[str, int] = {}
    for page in pages:
        slugs[page.slug] = slugs.get(page.slug, 0) + 1
    for slug, count in slugs.items():
        if count > 1:
            result.add(
                "slug_duplicado",
                SEVERITY_BLOCK,
                f"El slug '{slug}' se repite {count} veces: una pagina sobreescribe "
                "a la otra al publicar.",
                [slug],
            )

    # 5. Tope de volumen. El riesgo de politicas es el volumen, no el modelo.
    if len(pages) > monthly_cap:
        result.add(
            "tope_superado",
            SEVERITY_WARN,
            f"El grafo tiene {len(pages)} paginas y el tope mensual es "
            f"{monthly_cap}. El planificador las reparte en varios meses por "
            "prioridad; publicarlas de golpe es el patron de scaled content abuse.",
        )

    # 6. Mezcla de intencion.
    #
    #    Se mide por supervivencia al clic, no por etiqueta. Una keyword sin
    #    señal clara ("undetermined", 45/100) no cuenta como superviviente:
    #    contarla inflaba el porcentaje y dejaba pasar planes que en la
    #    practica son informacionales.
    surviving = [p for p in pages if p.primary.intent.click_survival >= 50]
    share = len(surviving) / len(pages)
    if share < min_survival_share:
        result.add(
            "mezcla_informacional",
            SEVERITY_WARN,
            f"Solo el {share * 100:.0f}% de las paginas tiene intencion con clic "
            f"superviviente (minimo recomendado {min_survival_share * 100:.0f}%). "
            "Las informacionales puras rankean sin recibir la visita: hacen falta "
            "mas comerciales, comparativas y transaccionales.",
        )

    # 7. Pilares que no sostienen su cluster.
    for cluster in graph.clusters:
        if cluster.satellites and cluster.pillar.priority < max(
            s.priority for s in cluster.satellites
        ):
            result.add(
                "pilar_mas_debil_que_satelite",
                SEVERITY_WARN,
                f"En el cluster '{cluster.id}' un satelite tiene mas prioridad que "
                "el pilar. Revisar quien debe ser la pagina central.",
                [cluster.pillar.slug],
            )

    return result
