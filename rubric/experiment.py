"""El experimento: pasar los especimenes por las compuertas y medir.

La verdad de referencia esta anotada antes de ejecutar nada. Las compuertas no
saben que defectos lleva cada articulo. De ahi salen precision y cobertura por
compuerta sin que intervenga el criterio de nadie.
"""

from __future__ import annotations

from textos import plural

from dataclasses import dataclass, field

from generator.brief import Brief
from generator.gates import GateResult, check
from generator.gates import Draft

from .criteria import DEFECTS, Specimen


@dataclass
class Outcome:
    specimen: Specimen
    result: GateResult

    @property
    def fired(self) -> set[str]:
        return {f.code for f in self.result.findings}

    @property
    def fired_blocking(self) -> set[str]:
        return {f.code for f in self.result.blocking}

    @property
    def expected(self) -> set[str]:
        return self.specimen.expected_gates()

    @property
    def caught(self) -> set[str]:
        """Defectos anotados que alguna compuerta de su familia cazo."""
        return {
            defecto for defecto, familia in self.specimen.expected_families()
            if set(familia) & self.fired
        }

    @property
    def missed(self) -> set[str]:
        return set(self.specimen.injected) - self.caught

    @property
    def extra(self) -> set[str]:
        """Compuertas que saltaron sin defecto inyectado.

        No son necesariamente falsos positivos: un articulo puede tener un
        defecto que no se inyecto a proposito. Por eso se cuentan aparte y no
        se restan de la precision sin mirarlos.
        """
        return self.fired - self.expected

    @property
    def publishable_as_is(self) -> bool:
        return self.result.publishable_as_is


@dataclass
class GateScore:
    code: str
    caught: int = 0
    missed: int = 0
    fired_without_injection: int = 0

    @property
    def recall(self) -> float | None:
        total = self.caught + self.missed
        return self.caught / total if total else None

    def describe(self) -> str:
        if self.caught + self.missed == 0:
            return (
                f"{self.code}: no se inyecto ningun defecto de este tipo, "
                f"salto {self.fired_without_injection} vez/veces por su cuenta"
            )
        return (
            f"{self.code}: caza {self.caught} de {self.caught + self.missed} "
            f"defectos inyectados ({(self.recall or 0) * 100:.0f}%)"
            + (f", y salto {self.fired_without_injection} vez/veces sin defecto "
               "anotado" if self.fired_without_injection else "")
        )


@dataclass
class Experiment:
    outcomes: list[Outcome] = field(default_factory=list)
    gates: dict[str, GateScore] = field(default_factory=dict)

    @property
    def specimens(self) -> int:
        return len(self.outcomes)

    @property
    def clean(self) -> list[Outcome]:
        return [o for o in self.outcomes if o.specimen.clean]

    @property
    def dirty(self) -> list[Outcome]:
        return [o for o in self.outcomes if not o.specimen.clean]

    @property
    def injected_total(self) -> int:
        return sum(len(o.specimen.injected) for o in self.outcomes)

    @property
    def caught_total(self) -> int:
        return sum(len(o.caught) for o in self.outcomes)

    @property
    def detection_rate(self) -> float:
        return round(100 * self.caught_total / self.injected_total, 1) \
            if self.injected_total else 0.0

    @property
    def clean_pass_rate(self) -> float:
        """De los articulos SIN defecto inyectado, cuantos pasan limpios.

        Es la otra mitad del experimento: unas compuertas que bloquean todo
        tienen cobertura perfecta y son inutiles.
        """
        if not self.clean:
            return 0.0
        return round(100 * len([o for o in self.clean if o.result.passed]) / len(self.clean), 1)

    @property
    def publishable_rate(self) -> float:
        if not self.outcomes:
            return 0.0
        return round(
            100 * len([o for o in self.outcomes if o.publishable_as_is]) / len(self.outcomes), 1
        )

    def describe(self) -> str:
        return (
            f"{plural(self.specimens, 'articulo')} ({len(self.clean)} sin defectos, "
            f"{len(self.dirty)} con defectos anotados) · "
            f"{self.injected_total} defectos inyectados, "
            f"{self.caught_total} cazados ({self.detection_rate}%) · "
            f"{self.clean_pass_rate}% de los limpios pasan · "
            f"{self.publishable_rate}% publicables tal cual"
        )


def run(specimens: list[tuple[Specimen, Brief]],
        corpus: dict[str, set[str]] | None = None) -> Experiment:
    """Pasa cada especimen por las compuertas contra un corpus FIJO.

    El corpus no se acumula entre especimenes, y es un cambio importante: las
    variantes son alternativas del mismo articulo, no una secuencia de
    publicaciones. Al acumularlas, la compuerta de solape saltaba en todas
    contra la version limpia y ensuciaba cada medicion. Para probar el solape se
    pasa el corpus de entrada a proposito.
    """
    experiment = Experiment()
    running = dict(corpus or {})

    for specimen, brief in specimens:
        draft = Draft(
            slug=specimen.slug,
            title=specimen.body.splitlines()[0].lstrip("# ").strip(),
            body=specimen.body,
            declared_sources=[s.url for s in brief.required_sources],
        )
        result = check(draft, brief, corpus=running)
        experiment.outcomes.append(Outcome(specimen=specimen, result=result))

    for _codigo, (_texto, familia) in DEFECTS.items():
        for compuerta in familia:
            experiment.gates.setdefault(compuerta, GateScore(code=compuerta))

    for outcome in experiment.outcomes:
        for defecto, familia in outcome.specimen.expected_families():
            cazadoras = set(familia) & outcome.fired
            if cazadoras:
                for compuerta in cazadoras:
                    experiment.gates.setdefault(
                        compuerta, GateScore(code=compuerta)).caught += 1
            else:
                # Se le apunta a la primera de la familia, que es la canonica.
                experiment.gates.setdefault(
                    familia[0], GateScore(code=familia[0])).missed += 1
        for compuerta in outcome.extra:
            experiment.gates.setdefault(
                compuerta, GateScore(code=compuerta)).fired_without_injection += 1

    return experiment


def to_observations(experiment: Experiment):
    """Convierte el experimento en observaciones para el calibrador.

    Hasta ahora el calibrador solo tenia datos inventados. Esto le da verdad de
    referencia real: el veredicto no lo pone una persona, lo pone el registro de
    lo que se inyecto antes de ejecutar nada.
    """
    from calibration.calibrator import (
        VERDICT_APPROVED,
        VERDICT_REJECTED,
        Observation,
    )

    observaciones = []
    for outcome in experiment.outcomes:
        observaciones.append(
            Observation(
                slug=outcome.specimen.slug,
                fired=outcome.fired,
                verdict=VERDICT_REJECTED if outcome.specimen.injected
                        else VERDICT_APPROVED,
                reasons=sorted(outcome.expected),
                reviewed_despite_block=True,  # aqui se mira todo, no hay sombra
                minutes=25,
            )
        )
    return observaciones
