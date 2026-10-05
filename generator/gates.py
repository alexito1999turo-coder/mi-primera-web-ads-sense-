"""Compuertas de calidad. Bloquean publicacion, no sugieren.

Su contenido mide 2,1/5 porque nadie le pone una compuerta. Esta es la
diferencia de producto, asi que estas reglas devuelven BLOQUEANTE y el
publicador se niega a publicar lo que no pasa.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from citability.score import analyse as analyse_citability
from store.sketch import Sketch, similarity

from .brief import Brief

SEVERITY_BLOCK = "bloqueante"
SEVERITY_WARN = "aviso"
# Nota informativa sobre lo que el sistema NO ha podido medir. No es un defecto
# de la pagina y no debe contar contra ella: sin esta distincion, la primera
# pagina de cualquier lote nunca podria ser "publicable tal cual", porque
# arrastra el aviso de que aun no hay corpus con el que comparar. La metrica que
# se vende tiene que medir la pagina, no la cobertura del sistema.
SEVERITY_NOTE = "nota"

# Densidad maxima de la keyword primaria. Por encima es relleno y lo detecta
# cualquier revisor, humano o algoritmico.
MAX_DENSITY = 0.025
# Similitud de shingles con una pagina existente a partir de la cual es un
# duplicado interno: canibalizacion, esta vez fabricada por el generador.
MAX_OVERLAP = 0.30
SHINGLE_SIZE = 5

MARKDOWN_LINK = re.compile(r"\[[^\]]+\]\((https?://[^)]+)\)")
SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")
WORD_RE = re.compile(r"[0-9A-Za-zÁÉÍÓÚÜÑáéíóúüñ][0-9A-Za-zÁÉÍÓÚÜÑáéíóúüñ'’\-]*")

# Marcas de afirmacion que exige respaldo: cifras con unidad, porcentajes,
# superlativos y absolutos. Son las frases por las que un revisor te devuelve
# el articulo, y las que un lector usa para decidir si te cree.
CLAIM_PATTERNS = (
    re.compile(r"\b\d[\d.,]*\s?%"),
    re.compile(r"\b\d[\d.,]*\s?(?:\$|€|usd|eur|dolares|dólares|euros)", re.I),
    re.compile(r"(?:\$|€)\s?\d[\d.,]*"),
    re.compile(r"\b\d[\d.,]*\s?(?:años|anos|meses|dias|días|horas|litros|galones|"
               r"metros|pies|kg|libras|grados)\b", re.I),
    re.compile(r"\b(?:el|la|los|las)\s+(?:mejor|peor|mayor|menor|unico|única|único)\b", re.I),
    re.compile(r"\b(?:siempre|nunca|todos los|ninguna? )\b", re.I),
    re.compile(r"\b(?:estudios|investigaciones|expertos|segun datos|según datos)\b", re.I),
)


@dataclass
class Draft:
    """Lo que produce el generador, antes de pasar por nadie."""

    slug: str
    title: str
    body: str
    declared_sources: list[str] = field(default_factory=list)

    @property
    def words(self) -> list[str]:
        # El cuerpo sin marcado de enlace, para no contar URLs como palabras.
        clean = MARKDOWN_LINK.sub(lambda m: m.group(0).split("](")[0][1:], self.body)
        return WORD_RE.findall(clean)

    @property
    def word_count(self) -> int:
        return len(self.words)

    @property
    def links(self) -> list[str]:
        return MARKDOWN_LINK.findall(self.body)

    def sentences(self) -> list[str]:
        text = " ".join(self.body.split())
        return [s for s in SENTENCE_SPLIT.split(text) if s.strip()]

    def shingles(self, size: int = SHINGLE_SIZE) -> set[str]:
        words = [w.lower() for w in self.words]
        if len(words) < size:
            return {" ".join(words)} if words else set()
        return {" ".join(words[i : i + size]) for i in range(len(words) - size + 1)}


@dataclass
class GateFinding:
    code: str
    severity: str
    message: str
    samples: list[str] = field(default_factory=list)

    @property
    def blocking(self) -> bool:
        return self.severity == SEVERITY_BLOCK


@dataclass
class GateResult:
    findings: list[GateFinding] = field(default_factory=list)

    @property
    def blocking(self) -> list[GateFinding]:
        return [f for f in self.findings if f.blocking]

    @property
    def passed(self) -> bool:
        return not self.blocking

    @property
    def notes(self) -> list[GateFinding]:
        return [f for f in self.findings if f.severity == SEVERITY_NOTE]

    @property
    def warnings(self) -> list[GateFinding]:
        return [f for f in self.findings if f.severity == SEVERITY_WARN]

    @property
    def publishable_as_is(self) -> bool:
        """Sin bloqueantes y sin avisos. Las notas no cuentan.

        La linea base del competidor, medida por un tercero, es 52,4% de
        articulos publicables tal cual. Esta propiedad es como se cuenta la
        nuestra, y hay que medirla a ciegas para que valga algo.
        """
        return not self.blocking and not self.warnings

    def add(self, code: str, severity: str, message: str,
            samples: list[str] | None = None) -> None:
        self.findings.append(
            GateFinding(code=code, severity=severity, message=message,
                        samples=samples or [])
        )


# Una afirmacion tambien esta respaldada cuando declara SU PROPIO metodo.
#
# Lo descubrio un experimento con un articulo real: la compuerta marcaba trece
# frases, y la mayoria eran mediciones propias con su metodo en la misma frase
# ("sobre una muestra propia de 30 presupuestos"). Exigirles un enlace externo
# penalizaba exactamente el contenido que este sistema existe para producir, y
# confundia dos cosas distintas: tener fuente y tener enlace. El dato propio es
# su propia fuente, siempre que diga como se obtuvo.
OWN_METHOD = re.compile(
    r"\b(?:muestra propia|de nuestra|de nuestro|segun nuestr[oa]s?|según nuestr[oa]s?|"
    r"nuestra muestra|nuestro registro|medimos|recogimos|entrevistamos|"
    r"analizamos|pedimos presupuesto|mediana de \d|media de \d|promedio de \d|"
    r"sobre \d[\d.,]* (?:presupuestos|casos|observaciones|respuestas|muestras))\b",
    re.I,
)


def unsupported_claims(draft: Draft) -> list[str]:
    """Frases con cifra o superlativo que nada respalda.

    Una afirmacion esta respaldada cuando su PARRAFO contiene un enlace a una
    fuente, o cuando la propia frase declara el metodo con el que se obtuvo el
    dato.

    Dos decisiones, las dos salidas de medir la regla contra un articulo real:

    - La ventana es el parrafo, no la frase y la siguiente. La gente escribe el
      dato en una frase y la fuente dos frases despues; exigir adyacencia
      marcaba prosa correcta.
    - El metodo propio cuenta como respaldo. Un dato medido por uno mismo, con
      el metodo dicho, no necesita enlazar a nadie: enlazar a otro seria
      atribuirle un dato que no es suyo.
    """
    offenders: list[str] = []
    for paragraph in draft.body.split("\n\n"):
        if not paragraph.strip():
            continue
        tiene_enlace = bool(MARKDOWN_LINK.search(paragraph))
        texto = " ".join(paragraph.split())
        for sentence in SENTENCE_SPLIT.split(texto):
            sentence = sentence.strip()
            if not sentence or sentence.startswith("#"):
                continue
            if not any(pattern.search(sentence) for pattern in CLAIM_PATTERNS):
                continue
            if tiene_enlace or OWN_METHOD.search(sentence):
                continue
            offenders.append(sentence[:180])
    return offenders


def check(
    draft: Draft,
    brief: Brief,
    corpus: dict[str, set[str]] | None = None,
    published: "dict[str, Sketch] | None" = None,
    max_density: float = MAX_DENSITY,
    max_overlap: float = MAX_OVERLAP,
) -> GateResult:
    """Pasa el borrador por todas las compuertas.

    Hay dos formas de darle lo ya publicado, y la diferencia importa:

      - `corpus`: los shingles enteros por slug. Exacto, y solo viable dentro
        de un lote que ya esta en memoria.
      - `published`: las firmas MinHash del almacen. Estimado con ~6% de error
        y de tamano fijo, asi que funciona con mil paginas en disco.

    Sin ninguno de los dos el solape no se comprueba y el informe lo dice, en
    vez de dejar pasar la pagina como si estuviera comprobada.
    """
    result = GateResult()

    # 1. Longitud. Un pilar corto no sostiene su cluster.
    if draft.word_count < brief.min_words:
        result.add(
            "longitud_insuficiente",
            SEVERITY_BLOCK,
            f"{draft.word_count} palabras frente a las {brief.min_words} que pide "
            f"el rol {brief.page.role}.",
        )

    # 2. Fuentes verificables citadas EN EL CUERPO, no solo declaradas.
    required = [s.url for s in brief.required_sources if s.verifiable]
    linked = set(draft.links)
    if not linked:
        result.add(
            "sin_fuentes_enlazadas",
            SEVERITY_BLOCK,
            "El cuerpo no enlaza ninguna fuente. Declarar fuentes y no citarlas "
            "es lo mismo que no tenerlas.",
        )
    else:
        faltan = [url for url in required if url not in linked]
        if faltan:
            result.add(
                "fuente_obligatoria_ausente",
                SEVERITY_BLOCK,
                f"{len(faltan)} fuente(s) obligatoria(s) del brief no aparecen "
                "enlazadas en el cuerpo.",
                faltan,
            )

    # 3. Dato propio presente de verdad. Es lo que hace la pagina citable.
    usable = [d for d in brief.own_data if d.usable]
    if not usable:
        result.add(
            "brief_sin_dato_propio",
            SEVERITY_BLOCK,
            "El brief no trae dato propio con metodo: la pagina no sera citable "
            "por un LLM y es una reescritura del top 10.",
        )
    else:
        ausentes = [d.label for d in usable if d.marker not in draft.body]
        if ausentes:
            result.add(
                "dato_propio_ausente",
                SEVERITY_BLOCK,
                f"{len(ausentes)} dato(s) propio(s) del brief no aparecen en el "
                "cuerpo. El generador los ha ignorado.",
                ausentes,
            )

    # 4. Afirmaciones sin respaldo.
    offenders = unsupported_claims(draft)
    if offenders:
        result.add(
            "afirmacion_sin_respaldo",
            SEVERITY_BLOCK,
            f"{len(offenders)} afirmacion(es) con cifra o superlativo sin fuente "
            "enlazada cerca.",
            offenders[:5],
        )

    # 5. Densidad de la primaria.
    words = [w.lower() for w in draft.words]
    if words:
        term_words = brief.primary_term.lower().split()
        size = len(term_words)
        hits = sum(
            1 for i in range(len(words) - size + 1) if words[i : i + size] == term_words
        )
        density = hits * size / len(words)
        if density > max_density:
            result.add(
                "densidad_anomala",
                SEVERITY_BLOCK,
                f"La primaria aparece {hits} veces ({density * 100:.1f}% del texto, "
                f"maximo {max_density * 100:.1f}%). Es relleno y se nota.",
            )

    # 6. Solape con lo ya publicado.
    #
    # Las dos fuentes se comprueban, no una o la otra. En un lote con almacen
    # el corpus en memoria se llena con la primera pagina, y con un `elif` el
    # resto del lote dejaba de compararse contra el sitio publicado: la pagina
    # 2 del lote podia ser la 12 del sitio y nadie lo veia. Lo marcaba un
    # `elif` que escribi hace diez minutos y que los 347 tests no cazaron,
    # porque ninguno pasaba las dos fuentes a la vez.
    comprobado = False
    if corpus:
        comprobado = True
        mine = draft.shingles()
        for slug, other in corpus.items():
            if slug == draft.slug or not other or not mine:
                continue
            overlap = len(mine & other) / min(len(mine), len(other))
            if overlap > max_overlap:
                result.add(
                    "solape_con_publicado",
                    SEVERITY_BLOCK,
                    f"Comparte el {overlap * 100:.0f}% de sus frases con '{slug}'. "
                    "Es canibalizacion fabricada por el generador.",
                    [slug],
                )
    if published:
        comprobado = True
        mia = Sketch.of(draft.body)
        exactos = set(corpus or {})
        for slug, firma in published.items():
            # Si el slug ya se comparo con los shingles enteros, no se repite
            # el hallazgo con la version estimada.
            if slug == draft.slug or slug in exactos or not firma.hashes:
                continue
            overlap = similarity(mia, firma)
            if overlap > max_overlap:
                exacto = mia.exact and firma.exact
                result.add(
                    "solape_con_publicado",
                    SEVERITY_BLOCK,
                    f"Comparte el {overlap * 100:.0f}% de sus frases con '{slug}' "
                    f"({'medido sobre la firma completa' if exacto else 'estimado desde la firma, ~6% de error'}). "
                    "Es canibalizacion fabricada por el generador.",
                    [slug],
                )
    if not comprobado:
        result.add(
            "solape_no_comprobado",
            SEVERITY_NOTE,
            "Sin corpus de paginas publicadas: el solape interno no se ha "
            "comprobado. No se afirma lo que no se mide.",
        )

    # 7. Citabilidad: el dato esta, pero esta redactado de forma que un modelo
    #    no lo puede levantar.
    #
    #    Bloquea solo cuando el brief SI trae dato propio y la pagina no tiene
    #    ni una frase citable: eso no es una preferencia de estilo, es que se
    #    pago por un dato exclusivo y se escribio de forma que no se puede
    #    atribuir. Si no hay dato propio ya hay un bloqueante por eso.
    #
    #    Lo demas es aviso, porque los pesos del scorer son priores sin
    #    calibrar y bloquear sobre una heuristica no medida seria deshonesto.
    citability = analyse_citability(draft.body)
    if usable and not citability.liftable:
        fixes = [fix for fix, _count in citability.top_fixes(3)]
        result.add(
            "sin_frase_citable",
            SEVERITY_BLOCK,
            f"Ninguna frase es citable (citabilidad {citability.score}/100). El "
            "dato propio esta en la pagina pero redactado de forma que un modelo "
            "no lo puede levantar ni atribuir.",
            fixes,
        )
    elif len(citability.liftable) < 2:
        result.add(
            "citabilidad_pobre",
            SEVERITY_WARN,
            f"Solo {len(citability.liftable)} frase(s) citable(s) "
            f"(citabilidad {citability.score}/100). Cuantas mas frases "
            "atribuibles, mas superficie para ser citado.",
            [fix for fix, _count in citability.top_fixes(3)],
        )

    # 8. Preguntas del brief sin contestar (aviso: lo juzga el revisor).
    body_lower = draft.body.lower()
    sin_contestar = [
        q for q in brief.questions
        if not _covered(q, body_lower)
    ]
    if sin_contestar:
        result.add(
            "pregunta_sin_contestar",
            SEVERITY_WARN,
            f"{len(sin_contestar)} pregunta(s) del brief no parecen contestadas.",
            sin_contestar[:5],
        )

    # 9. Secundarias ausentes.
    ausentes = [
        k.term for k in brief.page.secondary if k.term.lower() not in body_lower
    ]
    if ausentes:
        result.add(
            "secundaria_ausente",
            SEVERITY_WARN,
            f"{len(ausentes)} keyword(s) secundaria(s) no aparecen en el cuerpo.",
            ausentes[:5],
        )

    return result


def _covered(question: str, body_lower: str) -> bool:
    """Una pregunta se considera tratada si sus terminos sustantivos aparecen."""
    tokens = [
        w.lower() for w in WORD_RE.findall(question)
        if len(w) > 4
    ]
    if not tokens:
        return True
    hits = sum(1 for token in tokens if token.lower() in body_lower)
    return hits >= max(1, len(tokens) // 2)
