"""Puntuacion de citabilidad y, lo que de verdad sirve, las frases citables.

El resultado principal de este modulo no es un numero del 0 al 100. Es la lista
de frases que un modelo levantaria de la pagina, y la lista de las que estan a
un arreglo concreto de serlo. A un cliente se le puede ensenar eso; una nota
global no le dice que cambiar.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .signals import (
    ANAPHORA_START,
    DATE,
    FIGURE,
    HEADING,
    LIFTABLE_MAX_WORDS,
    LIFTABLE_MIN_WORDS,
    MARKDOWN_LINK,
    METHOD,
    NAMED_SOURCE,
    QUALIFIER,
    QUESTION_HEADING,
    WORD,
    is_precise,
    sentences_of,
    strip_links,
)

# La extraibilidad NO es un factor ponderado: es una PRECONDICION, y por eso
# multiplica en vez de sumar.
#
# Lo tenia mal al principio: con la extraibilidad como un sumando mas, una frase
# imposible de levantar (extraibilidad 0) pero perfectamente atribuida y
# exclusiva salia citable. Es absurdo — si fuera del parrafo nadie sabe de que
# habla, no hay cita posible por buenos que sean los demas factores. Una
# condicion necesaria no se promedia con las deseables.
#
# Los tres pesos de abajo son PRIORES, no verdad medida: salen de como funciona
# la generacion con recuperacion, no de un experimento. Cuando haya citaciones
# reales medidas hay que recalibrarlos, y el informe lo dice en vez de
# disimularlo.
WEIGHTS = {
    "attributability": 0.385,
    "scarcity": 0.385,
    "alignment": 0.230,
}

LIFTABLE_THRESHOLD = 65
# Umbral bajo a proposito. Una pagina mala tiene frases que necesitan tres
# arreglos, no uno, y es justo donde la lista de arreglos hace falta: dejarla
# vacia porque "estan muy lejos" es inutil para el que tiene que arreglarla.
IMPROVABLE_THRESHOLD = 22


@dataclass
class Quote:
    """Una frase candidata, con su puntuacion y lo que le falta."""

    text: str
    extractability: int = 0
    attributability: int = 0
    scarcity: int = 0
    alignment: int = 0
    blockers: list[str] = field(default_factory=list)

    @property
    def total(self) -> int:
        """Los tres factores ponderados, escalados por la extraibilidad.

        Multiplicativo a proposito: la extraibilidad es la condicion necesaria.
        """
        base = (
            self.attributability * WEIGHTS["attributability"]
            + self.scarcity * WEIGHTS["scarcity"]
            + self.alignment * WEIGHTS["alignment"]
        )
        return round(base * self.extractability / 100)

    @property
    def liftable(self) -> bool:
        return self.total >= LIFTABLE_THRESHOLD

    @property
    def improvable(self) -> bool:
        return IMPROVABLE_THRESHOLD <= self.total < LIFTABLE_THRESHOLD

    def describe(self) -> str:
        return (
            f"[{self.total}] ext {self.extractability} · atr {self.attributability} "
            f"· esc {self.scarcity} · ali {self.alignment}"
        )


def _extractability(sentence: str) -> tuple[int, list[str]]:
    """Se sostiene la frase fuera de su parrafo?"""
    score, blockers = 100, []
    words = WORD.findall(sentence)

    if ANAPHORA_START.match(sentence):
        score -= 55
        blockers.append(
            "Empieza por un pronombre o conector: fuera del parrafo no se sabe "
            "de que habla. Nombrar el sujeto."
        )
    if len(words) < LIFTABLE_MIN_WORDS:
        score -= 30
        blockers.append(
            f"Demasiado corta ({len(words)} palabras): no dice lo suficiente "
            "para ser una respuesta."
        )
    elif len(words) > LIFTABLE_MAX_WORDS:
        score -= 35
        blockers.append(
            f"Demasiado larga ({len(words)} palabras): no cabe en una respuesta "
            "generada. Partirla."
        )
    # Una frase que se apoya en la anterior para el dato tampoco se levanta.
    if sentence.lstrip().startswith(("Y ", "Pero ", "Aunque ", "Mientras ")):
        score -= 20
        blockers.append("Arranca subordinada a la frase anterior.")
    return max(0, score), blockers


def _attributability(sentence: str) -> tuple[int, list[str]]:
    """Lleva quien, cuando y como?"""
    score, blockers = 0, []
    has_date = bool(DATE.search(sentence))
    has_method = bool(METHOD.search(sentence))
    has_link = bool(MARKDOWN_LINK.search(sentence))
    has_named = bool(NAMED_SOURCE.search(strip_links(sentence)))

    score += 35 if has_method else 0
    score += 30 if has_date else 0
    score += 25 if has_link else 0
    score += 10 if has_named else 0

    if not has_method:
        blockers.append(
            "Sin metodo: anadir de donde sale el dato (media de N casos, "
            "muestra, registro)."
        )
    if not has_date:
        blockers.append("Sin fecha: un dato sin ano no se puede citar con confianza.")
    if not (has_link or has_named):
        blockers.append("Sin fuente nombrada ni enlazada en la propia frase.")
    return min(100, score), blockers


def _scarcity(sentence: str) -> tuple[int, list[str]]:
    """Hay que venir a esta pagina a por el dato, o esta en el consenso?"""
    score, blockers = 0, []

    if is_precise(sentence):
        # La senal mas discriminante: un numero preciso solo puede venir de
        # alguien que lo midio.
        score += 50
    elif FIGURE.search(sentence):
        score += 10
        blockers.append(
            "Cifra redonda o aproximada: eso lo tiene el modelo en su propio "
            "peso y no necesita citarte. Dar la cifra exacta medida."
        )
    else:
        blockers.append("Sin cifra: no hay nada atribuible que levantar.")

    qualifiers = QUALIFIER.findall(sentence)
    score += min(35, len(qualifiers) * 15)
    if len(qualifiers) < 2:
        blockers.append(
            "Poco acotada: anadir donde, cuando o bajo que condicion. Un dato "
            "sin contexto es intercambiable por el de cualquier otro."
        )
    if METHOD.search(sentence):
        score += 15
    return min(100, score), blockers


def _alignment(sentence: str, answers_question: bool, position: int) -> tuple[int, list[str]]:
    """Esta redactada como se pregunta, y donde se busca la respuesta?"""
    score, blockers = 40, []
    if answers_question:
        score += 40
    else:
        blockers.append(
            "No esta debajo de un encabezado en forma de pregunta: el modelo "
            "empareja pregunta con respuesta."
        )
    if position == 0:
        score += 20  # primera frase de su seccion: es donde se busca
    elif position > 2:
        score -= 10
        blockers.append(
            "Enterrada en la seccion: la respuesta va en la primera frase."
        )
    return max(0, min(100, score)), blockers


@dataclass
class CitabilityReport:
    quotes: list[Quote] = field(default_factory=list)
    question_headings: int = 0
    answer_first_sections: int = 0

    @property
    def liftable(self) -> list[Quote]:
        return sorted(
            [q for q in self.quotes if q.liftable], key=lambda q: -q.total
        )

    @property
    def improvable(self) -> list[Quote]:
        return sorted(
            [q for q in self.quotes if q.improvable], key=lambda q: -q.total
        )

    @property
    def score(self) -> int:
        """Nota de la pagina: cuanto material citable ofrece.

        No es la media de las frases. Una pagina con tres frases excelentes es
        mas citable que una con treinta mediocres, porque al modelo le basta
        una. Asi que pesa el techo, no el promedio.
        """
        if not self.quotes:
            return 0
        best = sorted((q.total for q in self.quotes), reverse=True)[:5]
        ceiling = sum(best) / len(best)
        breadth = min(1.0, len(self.liftable) / 5)
        return round(ceiling * (0.7 + 0.3 * breadth))

    def top_fixes(self, limit: int = 5) -> list[tuple[str, int]]:
        """Los arreglos que afectan a mas frases no citables.

        Arreglar el bloqueo que repiten veinte frases vale mas que pulir una.

        Mira TODAS las frases que no son citables, no solo las de la banda
        "mejorable". Atarlo a esa banda era un error: con la extraibilidad
        multiplicando, una frase mal escrita se va al suelo y queda fuera de la
        banda, y entonces la lista de arreglos salia vacia precisamente en la
        pagina que mas la necesitaba.
        """
        counts: dict[str, int] = {}
        for quote in self.quotes:
            if quote.liftable:
                continue
            for blocker in quote.blockers:
                counts[blocker] = counts.get(blocker, 0) + 1
        return sorted(counts.items(), key=lambda item: -item[1])[:limit]

    def describe(self) -> str:
        return (
            f"Citabilidad {self.score}/100 · {len(self.liftable)} frase(s) "
            f"citable(s) · {len(self.improvable)} a un arreglo de serlo · "
            f"{self.question_headings} encabezado(s) en forma de pregunta, "
            f"{self.answer_first_sections} con la respuesta en la primera frase. "
            "Pesos sin calibrar: son priores hasta que haya citaciones medidas."
        )


def analyse(body: str) -> CitabilityReport:
    """Puntua la pagina. Sin red: es analisis de texto."""
    report = CitabilityReport()

    questions = QUESTION_HEADING.findall(body)
    report.question_headings = len(questions)

    # Recorrido por secciones para saber si una frase contesta una pregunta y
    # en que posicion de su seccion esta.
    current_is_question = False
    position = 0
    for sentence in sentences_of(body):
        if sentence.startswith("#"):
            heading = HEADING.match(sentence)
            text = heading.group(1) if heading else sentence
            current_is_question = text.strip().endswith("?")
            position = 0
            continue

        # Solo las frases con cifra son candidatas: un modelo no cita opiniones.
        if not FIGURE.search(sentence):
            position += 1
            continue

        extractability, ext_blockers = _extractability(sentence)
        attributability, atr_blockers = _attributability(sentence)
        scarcity, sca_blockers = _scarcity(sentence)
        alignment, ali_blockers = _alignment(sentence, current_is_question, position)

        quote = Quote(
            text=sentence[:300],
            extractability=extractability,
            attributability=attributability,
            scarcity=scarcity,
            alignment=alignment,
            blockers=ext_blockers + atr_blockers + sca_blockers + ali_blockers,
        )
        report.quotes.append(quote)

        if current_is_question and position == 0 and quote.liftable:
            report.answer_first_sections += 1
        position += 1

    return report
