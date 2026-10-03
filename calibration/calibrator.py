"""Motor de calibracion: observaciones -> metricas -> recomendaciones.

El problema metodologico que hay que decir en voz alta: una compuerta
BLOQUEANTE impide que la pagina llegue al revisor, asi que su precision es
inmedible salvo que se revise a proposito una muestra de lo que bloqueo.

Sin ese muestreo en la sombra no se sabe si la compuerta protege o estorba, y
este modulo lo declara en vez de rellenar el hueco con un numero bonito.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field

from .metrics import (
    MIN_SAMPLE,
    MISS_THRESHOLD,
    PRECISION_DOWNGRADE,
    PRECISION_PROMOTE,
    GateMetrics,
    MissedPattern,
)

VERDICT_APPROVED = "aprobada"
VERDICT_REJECTED = "rechazada"

ACTION_KEEP = "mantener"
ACTION_DOWNGRADE = "bajar_a_aviso"
ACTION_PROMOTE = "subir_a_bloqueante"
ACTION_RETIRE = "retirar"
ACTION_CREATE = "crear_compuerta"
ACTION_SHADOW = "muestrear_en_sombra"


@dataclass
class Observation:
    """Una pagina juzgada por una persona.

    `fired` son los codigos que se activaron. `reasons` son los motivos por los
    que el revisor la rechazo, con el vocabulario de los codigos cuando
    coincide: asi se puede cruzar lo que vio la maquina con lo que vio la
    persona.

    `reviewed_despite_block` marca las paginas que un humano miro aunque una
    compuerta bloqueante las hubiera parado. Son las unicas con las que se
    puede medir si ese bloqueo estaba justificado.
    """

    slug: str
    fired: set[str] = field(default_factory=set)
    verdict: str = VERDICT_APPROVED
    reasons: list[str] = field(default_factory=list)
    reviewed_despite_block: bool = False
    minutes: int = 0

    @property
    def rejected(self) -> bool:
        return self.verdict == VERDICT_REJECTED


@dataclass
class Recommendation:
    code: str
    action: str
    rationale: str
    evidence: str = ""

    @property
    def actionable(self) -> bool:
        return self.action != ACTION_KEEP


@dataclass
class Calibration:
    observations: int = 0
    metrics: dict[str, GateMetrics] = field(default_factory=dict)
    missed: list[MissedPattern] = field(default_factory=list)
    recommendations: list[Recommendation] = field(default_factory=list)
    unmeasurable: list[str] = field(default_factory=list)
    wasted_minutes: int = 0

    @property
    def actionable(self) -> list[Recommendation]:
        return [r for r in self.recommendations if r.actionable]

    def describe(self) -> str:
        lines = [
            f"{self.observations} pagina(s) con veredicto humano · "
            f"{len(self.metrics)} compuerta(s) observada(s) · "
            f"{len(self.actionable)} recomendacion(es)"
        ]
        if self.wasted_minutes:
            lines.append(
                f"{self.wasted_minutes} minuto(s) de revision gastados en "
                "compuertas que marcaron paginas correctas."
            )
        if self.unmeasurable:
            lines.append(
                f"{len(self.unmeasurable)} compuerta(s) bloqueante(s) sin muestreo "
                "en sombra: su precision es INMEDIBLE, no buena ni mala."
            )
        return "\n".join(lines)


def calibrate(
    observations: list[Observation],
    severities: dict[str, str],
    min_sample: int = MIN_SAMPLE,
) -> Calibration:
    """Mide cada compuerta contra el criterio humano y recomienda.

    `severities` es la severidad actual de cada codigo, para saber si una
    recomendacion es subir o bajar.
    """
    result = Calibration(observations=len(observations))
    if not observations:
        return result

    all_codes = set(severities) | {c for o in observations for c in o.fired}
    for code in sorted(all_codes):
        result.metrics[code] = GateMetrics(code=code, severity=severities.get(code, "?"))

    # --- acumular ------------------------------------------------------
    for observation in observations:
        for code in all_codes:
            metrics = result.metrics[code]
            metrics.pages_seen += 1
            fired = code in observation.fired
            # Un rechazo cuenta contra una compuerta solo si el revisor dio ESE
            # motivo. Si rechazo por otra cosa, esta compuerta no fallo.
            blamed = code in observation.reasons
            if fired:
                if observation.rejected and blamed:
                    metrics.fired_and_rejected += 1
                elif observation.rejected:
                    # Rechazada por otro motivo: para esta compuerta no es ni
                    # acierto ni fallo, asi que no se cuenta.
                    pass
                else:
                    metrics.fired_and_approved += 1
                    result.wasted_minutes += observation.minutes
            else:
                if observation.rejected and blamed:
                    metrics.silent_and_rejected += 1
                elif not observation.rejected:
                    metrics.silent_and_approved += 1

    # --- motivos del revisor que ninguna compuerta vio -----------------
    unseen: Counter[str] = Counter()
    examples: dict[str, list[str]] = {}
    for observation in observations:
        if not observation.rejected:
            continue
        for reason in observation.reasons:
            if reason in observation.fired:
                continue
            if reason in severities:
                continue  # la compuerta existe, simplemente no se activo
            unseen[reason] += 1
            examples.setdefault(reason, []).append(observation.slug)
    for reason, count in unseen.most_common():
        result.missed.append(
            MissedPattern(reason=reason, count=count, examples=examples[reason][:5])
        )

    # --- recomendaciones ------------------------------------------------
    blocking_sampled = {
        code
        for observation in observations
        if observation.reviewed_despite_block
        for code in observation.fired
    }

    for code, metrics in result.metrics.items():
        severity = metrics.severity
        floor = metrics.precision_floor

        if not metrics.fired:
            if metrics.pages_seen >= min_sample * 2:
                result.recommendations.append(
                    Recommendation(
                        code=code,
                        action=ACTION_RETIRE,
                        rationale=(
                            "No se ha activado nunca en una muestra ya grande. O el "
                            "problema no existe en este nicho, o la regla no lo "
                            "detecta. En ambos casos es peso muerto."
                        ),
                        evidence=f"0 activaciones en {metrics.pages_seen} paginas",
                    )
                )
            continue

        # Una bloqueante sin muestreo en sombra no se puede juzgar.
        if severity == "bloqueante" and code not in blocking_sampled:
            result.unmeasurable.append(code)
            result.recommendations.append(
                Recommendation(
                    code=code,
                    action=ACTION_SHADOW,
                    rationale=(
                        "Es bloqueante, asi que las paginas que marca no llegan al "
                        "revisor y su precision es inmedible. Hay que revisar a "
                        "proposito una muestra de lo que bloquea para saber si "
                        "protege o estorba."
                    ),
                    evidence=f"{metrics.fired} bloqueo(s), 0 revisados en sombra",
                )
            )
            continue

        if not metrics.enough_sample:
            result.recommendations.append(
                Recommendation(
                    code=code,
                    action=ACTION_KEEP,
                    rationale=(
                        f"Muestra insuficiente: {metrics.fired} activacion(es), hacen "
                        f"falta {min_sample}. No se toca lo que no se puede medir."
                    ),
                    evidence=metrics.describe(),
                )
            )
            continue

        assert floor is not None
        if severity == "bloqueante" and floor < PRECISION_DOWNGRADE:
            result.recommendations.append(
                Recommendation(
                    code=code,
                    action=ACTION_DOWNGRADE,
                    rationale=(
                        f"Bloquea con una precision de suelo {floor * 100:.0f}%: mas "
                        "de la mitad de lo que para estaba bien. Cuesta revisiones y "
                        "ensena al revisor a ignorarla. Bajar a aviso y reescribir la "
                        "regla."
                    ),
                    evidence=metrics.describe(),
                )
            )
        elif severity == "aviso" and floor >= PRECISION_PROMOTE:
            result.recommendations.append(
                Recommendation(
                    code=code,
                    action=ACTION_PROMOTE,
                    rationale=(
                        f"Avisa con una precision de suelo {floor * 100:.0f}%: cuando "
                        "habla, acierta. Subirla a bloqueante quita trabajo al revisor "
                        "sin perder calidad."
                    ),
                    evidence=metrics.describe(),
                )
            )
        else:
            result.recommendations.append(
                Recommendation(
                    code=code,
                    action=ACTION_KEEP,
                    rationale="Precision dentro de lo esperado para su severidad.",
                    evidence=metrics.describe(),
                )
            )

    for pattern in result.missed:
        if pattern.count >= MISS_THRESHOLD:
            result.recommendations.append(
                Recommendation(
                    code=pattern.reason,
                    action=ACTION_CREATE,
                    rationale=(
                        f"El revisor ha rechazado {pattern.count} pagina(s) por este "
                        "motivo y ninguna compuerta lo detecta. Es trabajo humano "
                        "repetido que deberia hacer una regla."
                    ),
                    evidence="ejemplos: " + ", ".join(pattern.examples),
                )
            )

    return result


def to_markdown(calibration: Calibration) -> str:
    lines = ["# Calibracion de compuertas", "", calibration.describe(), ""]
    add = lines.append

    add("## Recomendaciones")
    add("")
    if not calibration.actionable:
        add("Ninguna. Las compuertas estan donde deben con los datos de hoy.")
        add("")
    else:
        for rec in sorted(calibration.actionable, key=lambda r: r.action):
            add(f"### `{rec.code}` -> **{rec.action}**")
            add("")
            add(rec.rationale)
            add("")
            if rec.evidence:
                add(f"Evidencia: {rec.evidence}")
                add("")

    add("## Medicion por compuerta")
    add("")
    for code in sorted(calibration.metrics):
        add(f"- {calibration.metrics[code].describe()}")
    add("")

    if calibration.missed:
        add("## Motivos de rechazo sin compuerta")
        add("")
        for pattern in calibration.missed:
            add(f"- **{pattern.reason}** x{pattern.count} "
                f"({', '.join(pattern.examples)})")
        add("")

    return "\n".join(lines)
