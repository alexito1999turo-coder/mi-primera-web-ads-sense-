"""El brief: el contrato de lo que la pagina debe aportar.

Un brief sin la respuesta a "que aporta esto que no este ya en el top 10" es
una invitacion a reescribir el top 10, que es exactamente el patron que Google
clasifica como material no original de poco valor.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from clusters.graph import PageSpec


@dataclass
class Source:
    """Una fuente citable. Sin URL y sin fecha de consulta no es una fuente."""

    url: str
    title: str = ""
    consulted_at: str = ""
    note: str = ""

    @property
    def verifiable(self) -> bool:
        return bool(self.url) and "://" in self.url and bool(self.consulted_at)


@dataclass
class OwnData:
    """El dato propio. Es lo que hace la pagina citable por un LLM.

    Los modelos citan cifras atribuibles, procedimientos concretos y tablas con
    origen. No citan prosa. Sin dato propio la pagina puede estar bien escrita
    y no ser citada nunca.
    """

    label: str
    value: str
    method: str = ""          # como se obtuvo: medicion, encuesta, registro
    marker: str = ""          # cadena que debe aparecer literal en el cuerpo

    def __post_init__(self) -> None:
        if not self.marker:
            self.marker = self.value

    @property
    def usable(self) -> bool:
        return bool(self.label and self.value and self.method)


@dataclass
class Brief:
    page: PageSpec
    audience: str = ""
    angle: str = ""
    # La pregunta que separa una pagina util de una reescritura del top 10.
    what_it_adds: str = ""
    entities: list[str] = field(default_factory=list)
    questions: list[str] = field(default_factory=list)
    required_sources: list[Source] = field(default_factory=list)
    own_data: list[OwnData] = field(default_factory=list)
    brand_voice: str = ""
    # Secciones obligatorias; el generador no puede omitirlas.
    outline: list[str] = field(default_factory=list)

    @property
    def primary_term(self) -> str:
        return self.page.primary.term

    @property
    def min_words(self) -> int:
        return self.page.min_words

    @property
    def complete(self) -> bool:
        """Un brief incompleto no debe llegar al generador."""
        return bool(
            self.what_it_adds
            and self.questions
            and any(s.verifiable for s in self.required_sources)
            and any(d.usable for d in self.own_data)
        )

    def missing(self) -> list[str]:
        gaps: list[str] = []
        if not self.what_it_adds:
            gaps.append(
                "Falta 'que aporta': sin esto la pagina sera una reescritura del top 10."
            )
        if not self.questions:
            gaps.append("Faltan las preguntas reales que la pagina debe contestar.")
        if not any(s.verifiable for s in self.required_sources):
            gaps.append(
                "Ninguna fuente es verificable (hace falta URL y fecha de consulta)."
            )
        if not any(d.usable for d in self.own_data):
            gaps.append(
                "Falta dato propio con metodo. Sin el, la pagina no sera citable por un LLM."
            )
        return gaps

    def to_prompt(self) -> str:
        """El brief como instruccion. Explicito a proposito: lo que no se pide
        no aparece, y lo que se pide vagamente aparece vago."""
        lines = [
            f"# Pagina a escribir: {self.primary_term}",
            "",
            f"Rol en el cluster: {self.page.role} ({self.page.cluster_id})",
            f"Intencion de busqueda: {self.page.intent}",
            f"Longitud minima: {self.min_words} palabras",
            "",
        ]
        if self.audience:
            lines += [f"Audiencia: {self.audience}", ""]
        if self.angle:
            lines += [f"Angulo: {self.angle}", ""]

        lines += [
            "## Que aporta esta pagina que no este ya en el top 10",
            "",
            self.what_it_adds,
            "",
        ]

        if self.page.secondary:
            lines += [
                "## Keywords secundarias (cubrir, sin repetir en exceso)",
                "",
                *[f"- {k.term}" for k in self.page.secondary],
                "",
            ]

        lines += ["## Preguntas que la pagina debe contestar", ""]
        lines += [f"{i}. {q}" for i, q in enumerate(self.questions, 1)]
        lines.append("")

        if self.entities:
            lines += ["## Entidades a nombrar", "", ", ".join(self.entities), ""]

        lines += ["## Datos propios de obligada aparicion", ""]
        for data in self.own_data:
            lines.append(f"- **{data.label}**: {data.value} (metodo: {data.method})")
        lines += [
            "",
            "Cada dato propio debe aparecer literal en el cuerpo y con su metodo "
            "declarado. Es lo que hace la pagina citable.",
            "",
        ]

        lines += ["## Fuentes obligatorias", ""]
        for source in self.required_sources:
            label = source.title or source.url
            lines.append(f"- [{label}]({source.url}) — consultada {source.consulted_at}")
        lines += [
            "",
            "Toda afirmacion con cifra o superlativo va acompanada de enlace a su "
            "fuente. Una afirmacion sin respaldo no pasa la compuerta.",
            "",
        ]

        if self.outline:
            lines += ["## Estructura obligatoria", ""]
            lines += [f"- {section}" for section in self.outline]
            lines.append("")

        if self.brand_voice:
            lines += ["## Voz de marca", "", self.brand_voice, ""]

        return "\n".join(lines)


def from_page(
    page: PageSpec,
    what_it_adds: str,
    questions: list[str],
    sources: list[Source],
    own_data: list[OwnData],
    **extra,
) -> Brief:
    """Atajo para construir un brief completo de una pagina del grafo."""
    return Brief(
        page=page,
        what_it_adds=what_it_adds,
        questions=questions,
        required_sources=sources,
        own_data=own_data,
        **extra,
    )
