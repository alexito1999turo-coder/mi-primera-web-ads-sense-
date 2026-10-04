"""Pipeline de produccion: brief -> borrador -> compuertas -> reparacion.

El bucle de reparacion es el mecanismo de calidad del producto. Las compuertas
no devuelven una nota, devuelven hallazgos con codigo y ejemplos; esos hallazgos
se convierten en la instruccion del siguiente intento. Es la diferencia entre
"el modelo escribe mejor" y un sistema que converge.

La linea base a batir es 52,4% de paginas publicables tal cual, que es lo que
un tercero midio en el producto de la competencia.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .brief import Brief
from .gates import Draft, GateResult, check
from .llm import DEFAULT_EFFORT, DEFAULT_MAX_TOKENS, LLM

# Reglas de la casa. Van en el system, se cachean y no cambian entre paginas.
HOUSE_RULES = """Eres redactor tecnico. Escribes paginas que un profesional del
sector firmaria y que un buscador puede citar.

Reglas que no se negocian:

1. No inventas fuentes. Solo enlazas las URL que te da el brief, con el texto de
   ancla que describa el destino. Si te falta una fuente para sostener algo, no
   lo afirmas.
2. Toda cifra, porcentaje, precio o superlativo va acompanado, en su frase o en
   la siguiente, de un enlace markdown a su fuente.
3. Los datos propios del brief aparecen literales en el cuerpo, con su metodo
   declarado al lado. Son lo que hace la pagina citable; no los parafraseas.
4. No repites la keyword primaria para rellenar. Si una frase solo existe para
   repetirla, la frase no existe.
5. Escribes en markdown: encabezados ##, parrafos, tablas cuando los datos son
   comparables, listas solo cuando los elementos son de verdad una lista.
6. Contestas las preguntas del brief de forma directa y en las primeras lineas
   de su seccion. Nada de preambulos.
7. No escribes conclusiones que resuman lo ya dicho. Cierras con lo que el
   lector tiene que hacer a continuacion.

## Como se escribe una frase que un buscador pueda citar

Un modelo no cita paginas: cita frases que puede levantar enteras, atribuir a
alguien, y que no encuentra en otras cincuenta fuentes. Asi que cada dato
importante va en una frase que cumple las cuatro cosas a la vez:

- **Se sostiene sola.** Nombra su sujeto. "Este cuesta 14.237 $" no se puede
  citar porque fuera del parrafo nadie sabe que es "este". Entre ocho y
  cuarenta y cinco palabras: menos no dice nada, mas no cabe en una respuesta.
- **Lleva quien, cuando y como.** Cifra, ano y metodo en la misma frase:
  "costo 14.237 $ de mediana en Texas en 2026, sobre una muestra de 40
  presupuestos".
- **Da la cifra exacta, no la redonda.** "Unos 14.000 $" ya lo sabe el modelo y
  no necesita citarte; "14.237 $" solo puede venir de quien lo midio. Y acota:
  donde, cuando, bajo que condicion.
- **Va primera.** Debajo de un encabezado en forma de pregunta, la respuesta en
  la primera frase de la seccion. Ahi es donde se busca."""


@dataclass
class Attempt:
    number: int
    draft: Draft
    result: GateResult

    @property
    def passed(self) -> bool:
        return self.result.passed


@dataclass
class Production:
    brief: Brief
    attempts: list[Attempt] = field(default_factory=list)
    aborted_reason: str = ""

    @property
    def draft(self) -> Draft | None:
        return self.attempts[-1].draft if self.attempts else None

    @property
    def result(self) -> GateResult | None:
        return self.attempts[-1].result if self.attempts else None

    @property
    def passed(self) -> bool:
        return bool(self.attempts) and self.attempts[-1].passed

    @property
    def publishable_as_is(self) -> bool:
        return bool(self.attempts) and self.attempts[-1].result.publishable_as_is

    @property
    def repairs(self) -> int:
        return max(0, len(self.attempts) - 1)

    def summary(self) -> str:
        if self.aborted_reason:
            return f"ABORTADO: {self.aborted_reason}"
        if not self.attempts:
            return "Sin intentos."
        state = "PASA" if self.passed else "BLOQUEADO"
        clean = " y publicable tal cual" if self.publishable_as_is else ""
        return (
            f"{state}{clean} tras {len(self.attempts)} intento(s) "
            f"({self.repairs} reparacion(es)), {self.draft.word_count} palabras."
        )


def _system(brief: Brief) -> str:
    blocks = [HOUSE_RULES]
    if brief.brand_voice:
        blocks.append(f"## Voz de marca\n\n{brief.brand_voice}")
    return "\n\n".join(blocks)


def repair_prompt(brief: Brief, draft: Draft, result: GateResult) -> str:
    """Convierte los hallazgos en instruccion. Concreto, no "mejoralo"."""
    lines = [
        "El borrador no ha pasado las compuertas de calidad. Corrige EXACTAMENTE",
        "lo que se enumera y devuelve el articulo completo en markdown, sin",
        "comentarios ni explicaciones sobre los cambios.",
        "",
        "## Lo que falla",
        "",
    ]
    for finding in result.findings:
        mark = "OBLIGATORIO" if finding.blocking else "recomendado"
        lines.append(f"- [{mark}] {finding.message}")
        for sample in finding.samples[:5]:
            lines.append(f"    · {sample}")
    lines += [
        "",
        "## Recordatorio del brief",
        "",
        brief.to_prompt(),
        "",
        "## Borrador a corregir",
        "",
        draft.body,
    ]
    return "\n".join(lines)


def draft_prompt(brief: Brief) -> str:
    return (
        brief.to_prompt()
        + "\n\nEscribe la pagina completa en markdown. Empieza por el titulo con "
        "un solo #, y despues el cuerpo."
    )


def _title_of(body: str, fallback: str) -> str:
    for line in body.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return fallback


def produce(
    brief: Brief,
    llm: LLM,
    corpus: dict[str, set[str]] | None = None,
    published: dict | None = None,
    max_repairs: int = 2,
    effort: str = DEFAULT_EFFORT,
    max_tokens: int = DEFAULT_MAX_TOKENS,
) -> Production:
    """Produce una pagina y la hace pasar por las compuertas.

    Un brief incompleto no llega al modelo: generar con un brief sin dato propio
    es pagar por una reescritura del top 10.

    `published` son las firmas del almacen, para que el solape se compruebe
    contra lo que ya esta publicado en el sitio y no solo contra el lote.
    """
    production = Production(brief=brief)

    gaps = brief.missing()
    if gaps:
        production.aborted_reason = (
            "Brief incompleto, no se gasta en generar: " + " ".join(gaps)
        )
        return production

    system = _system(brief)
    prompt = draft_prompt(brief)

    for attempt_number in range(1, max_repairs + 2):
        body = llm.complete(
            system=system, prompt=prompt, max_tokens=max_tokens, effort=effort
        )
        draft = Draft(
            slug=brief.page.slug,
            title=_title_of(body, brief.primary_term),
            body=body,
            declared_sources=[s.url for s in brief.required_sources],
        )
        result = check(draft, brief, corpus=corpus, published=published)
        production.attempts.append(
            Attempt(number=attempt_number, draft=draft, result=result)
        )
        if result.passed:
            break
        prompt = repair_prompt(brief, draft, result)

    return production


@dataclass
class BatchStats:
    """Lo que se mide de un lote. Es la cifra con la que se vende."""

    total: int = 0
    passed: int = 0
    publishable_as_is: int = 0
    aborted: int = 0
    repairs: int = 0

    @property
    def publishable_rate(self) -> float:
        return round(100 * self.publishable_as_is / self.total, 1) if self.total else 0.0

    @property
    def pass_rate(self) -> float:
        return round(100 * self.passed / self.total, 1) if self.total else 0.0

    def describe(self) -> str:
        return (
            f"{self.total} paginas · {self.pass_rate}% pasan las compuertas · "
            f"{self.publishable_rate}% publicables tal cual · "
            f"{self.repairs} reparacion(es) · {self.aborted} abortada(s) por brief "
            "incompleto. Linea base del competidor: 52,4% publicables tal cual."
        )


def produce_many(
    briefs: list[Brief],
    llm: LLM,
    corpus: dict[str, set[str]] | None = None,
    store=None,
    max_repairs: int = 2,
) -> tuple[list[Production], BatchStats]:
    """Produce un lote y acumula el corpus en marcha.

    Cada pagina que pasa entra en el corpus, asi la siguiente se compara tambien
    contra ella: el lote no puede canibalizarse a si mismo.

    Con `store` (un `ProjectStore`) el lote se compara ademas contra todo lo ya
    publicado del sitio, y cada pagina que pasa queda guardada. Es la
    diferencia entre un lote que no se repite a si mismo y un sitio que no se
    repite nunca: sin almacen, la pagina numero 201 podia ser la numero 12
    reescrita y ninguna compuerta lo veia.
    """
    running = dict(corpus or {})
    firmas = dict(store.corpus()) if store is not None else None
    productions: list[Production] = []
    stats = BatchStats(total=len(briefs))

    for brief in briefs:
        production = produce(brief, llm, corpus=running,
                             published=firmas, max_repairs=max_repairs)
        productions.append(production)
        if production.aborted_reason:
            stats.aborted += 1
            continue
        stats.repairs += production.repairs
        if production.passed:
            stats.passed += 1
            running[production.draft.slug] = production.draft.shingles()
            if store is not None:
                pagina = store.record_page(
                    production.draft.slug, production.draft.body,
                    words=production.draft.word_count,
                    role=brief.page.role,
                )
                firmas[pagina.slug] = pagina.sketch
        if production.publishable_as_is:
            stats.publishable_as_is += 1

    return productions, stats
