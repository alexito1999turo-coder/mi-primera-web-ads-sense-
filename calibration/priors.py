"""Priores que se apagan solos conforme llegan datos.

El problema de un prior declarado: se queda ahi para siempre si nadie lo
sustituye, y «lo sustituiremos cuando haya datos» es una promesa que no obliga a
nada. La alternativa no es esperar, es construir la maquina que lo apaga.

La idea es vieja y buena: **un prior vale lo que valen N observaciones
imaginarias.** Si el prior pesa 20 y llegan 5 datos reales, el resultado es
cuatro quintas partes prior. Con 200 datos reales el prior ya no se nota. Nadie
tiene que acordarse de borrarlo: se diluye.

Y lo que hace util el metodo aqui es que el sistema puede DECIR cuanto de cada
cifra sigue siendo suposicion. Un informe que dice «esta curva es 78% prior
todavia» es honesto; uno que la presenta como medicion, no.
"""

from __future__ import annotations

from dataclasses import dataclass, field

# Un prior fuerte tarda mas en apagarse. Se elige segun lo que costaria
# equivocarse: la curva de CTR es de mercado y bien conocida, asi que pesa; el
# valor del clic depende del negocio y debe ceder antes.
PESO_FUERTE = 40
PESO_MEDIO = 20
PESO_DEBIL = 8


@dataclass
class Prior:
    """Un valor supuesto, con el peso de las observaciones que simula."""

    name: str
    value: float
    weight: int = PESO_MEDIO
    source: str = ""

    def posterior(self, observations: list[float]) -> "Posterior":
        n = len(observations)
        if not n:
            return Posterior(prior=self, value=self.value, n=0, shrinkage=1.0)
        media = sum(observations) / n
        total = self.weight + n
        mezcla = (self.value * self.weight + media * n) / total
        return Posterior(prior=self, value=round(mezcla, 4), n=n,
                         shrinkage=round(self.weight / total, 4),
                         observed_mean=round(media, 4))


@dataclass
class Posterior:
    prior: Prior
    value: float
    n: int
    shrinkage: float          # 1.0 = todo prior · 0.0 = todo dato
    observed_mean: float | None = None

    @property
    def prior_share(self) -> int:
        return round(self.shrinkage * 100)

    @property
    def trustworthy(self) -> bool:
        """Por debajo de un tercio de prior, la cifra ya es una medicion."""
        return self.shrinkage < 0.34

    def describe(self) -> str:
        if not self.n:
            return (
                f"{self.prior.name}: {self.value} — 100% prior, sin una sola "
                f"observacion. Origen: {self.prior.source or 'sin declarar'}."
            )
        estado = "medido" if self.trustworthy else "todavia suposicion"
        return (
            f"{self.prior.name}: {self.value} ({estado}) — {self.prior_share}% "
            f"prior sobre {self.n} observacion(es); los datos solos darian "
            f"{self.observed_mean}."
        )


@dataclass
class PriorSet:
    """El conjunto de priores de un modulo, con su estado de calibracion."""

    label: str
    priors: dict[str, Prior] = field(default_factory=dict)
    observations: dict[str, list[float]] = field(default_factory=dict)

    def declare(self, name: str, value: float, weight: int = PESO_MEDIO,
                source: str = "") -> Prior:
        prior = Prior(name=name, value=value, weight=weight, source=source)
        self.priors[name] = prior
        self.observations.setdefault(name, [])
        return prior

    def observe(self, name: str, value: float) -> None:
        if name not in self.priors:
            raise KeyError(f"No hay prior declarado para {name!r}.")
        self.observations[name].append(value)

    def value(self, name: str) -> float:
        return self.posterior(name).value

    def posterior(self, name: str) -> Posterior:
        return self.priors[name].posterior(self.observations.get(name, []))

    def report(self) -> list[Posterior]:
        return [self.posterior(n) for n in sorted(self.priors)]

    def calibration(self) -> float:
        """Cuanto del conjunto sigue siendo suposicion, de 0 a 1."""
        posteriores = self.report()
        if not posteriores:
            return 1.0
        return round(sum(p.shrinkage for p in posteriores) / len(posteriores), 4)

    def describe(self) -> str:
        medidos = len([p for p in self.report() if p.trustworthy])
        total = len(self.priors)
        return (
            f"{self.label}: {medidos} de {total} cifras ya son medicion; "
            f"el conjunto es {round(self.calibration() * 100)}% prior todavia."
        )


def weights_from_separation(
    cited: list[dict[str, float]],
    not_cited: list[dict[str, float]],
    prior_weights: dict[str, float],
    prior_strength: int = PESO_MEDIO,
) -> dict[str, float]:
    """Recalcula los pesos de un scorer por su poder discriminante.

    El metodo: un factor merece peso en la medida en que separa lo citado de lo
    no citado. Se mide la diferencia de medias por factor, se normaliza, y se
    mezcla con los pesos previos segun cuantos ejemplos haya. Con pocos
    ejemplos los pesos apenas se mueven; con muchos, mandan los datos.

    No es un ajuste sofisticado y no pretende serlo: es el metodo mas simple que
    usa la evidencia sin dejar que tres ejemplos reescriban el scorer.
    """
    if not cited or not not_cited:
        return dict(prior_weights)

    n = min(len(cited), len(not_cited))
    separacion: dict[str, float] = {}
    varianza: dict[str, float] = {}
    for factor in prior_weights:
        valores_si = [x.get(factor, 0.0) for x in cited]
        valores_no = [x.get(factor, 0.0) for x in not_cited]
        media_si = sum(valores_si) / len(valores_si)
        media_no = sum(valores_no) / len(valores_no)
        separacion[factor] = max(0.0, media_si - media_no)
        todos = valores_si + valores_no
        varianza[factor] = max(todos) - min(todos)

    # SEGURO contra calibrar con ruido.
    #
    # Un factor que no varia en la muestra no aporta evidencia: no es que no
    # importe, es que el experimento no lo midio. Lo descubri en la primera
    # prueba real: el banco envolvia cada frase en el mismo encabezado, asi que
    # la alineacion salia identica en todas y el ajuste le bajaba el peso por un
    # artefacto del diseno. Un factor sin varianza conserva su peso previo y se
    # declara como no medido.
    sin_evidencia = {k for k, v in varianza.items() if v < 1e-9}
    con_evidencia = {k: v for k, v in separacion.items() if k not in sin_evidencia}

    suma = sum(con_evidencia.values())
    if suma <= 0 or not con_evidencia:
        return dict(prior_weights)

    # El reajuste reparte SOLO la masa de los factores medidos; los no medidos
    # conservan su peso intacto.
    masa_medida = sum(prior_weights[k] for k in con_evidencia)
    empirico = {k: v / suma * masa_medida for k, v in con_evidencia.items()}

    total = prior_strength + n
    salida = dict(prior_weights)
    for k in con_evidencia:
        salida[k] = round(
            (prior_weights[k] * prior_strength + empirico[k] * n) / total, 4
        )
    return salida


def unmeasured_factors(
    cited: list[dict[str, float]], not_cited: list[dict[str, float]],
    factors: list[str],
) -> list[str]:
    """Factores que el experimento no pudo medir por falta de varianza."""
    sin: list[str] = []
    for factor in factors:
        todos = [x.get(factor, 0.0) for x in cited + not_cited]
        if todos and max(todos) - min(todos) < 1e-9:
            sin.append(factor)
    return sin
