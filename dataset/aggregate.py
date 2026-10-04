"""Agregacion: donde nace el dato propio.

La agregacion crea originalidad. Cuarenta presupuestos pueden ser publicos uno
a uno; su mediana por condado no existe en ningun otro sitio.

Dos reglas de honestidad, las dos con la misma logica que el limite de Wilson
en la calibracion:

  - por debajo de un minimo de observaciones, una agregacion no es una medicion
    y se marca NO publicable, en vez de redondearla a algo que suene bien;
  - un percentil necesita mas muestra que una mediana, y una mediana mas que un
    recuento, porque no todos los estadisticos aguantan igual.
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass, field

from .records import Dataset, Record

# Muestra minima por estadistico. Una mediana de tres casos es una anecdota con
# decimales.
MIN_N = {"recuento": 3, "mediana": 8, "media": 8, "p25": 20, "p75": 20, "rango": 8}
DEFAULT_MIN_N = 8

MESES = ("enero", "febrero", "marzo", "abril", "mayo", "junio", "julio",
         "agosto", "septiembre", "octubre", "noviembre", "diciembre")


@dataclass
class Figure:
    """Una cifra agregada, con todo lo que hace falta para defenderla."""

    label: str
    statistic: str
    value: float
    unit: str
    n: int
    dims: dict[str, str] = field(default_factory=dict)
    period: str = ""
    sources: list[str] = field(default_factory=list)
    collection_method: str = ""

    @property
    def min_n(self) -> int:
        return MIN_N.get(self.statistic, DEFAULT_MIN_N)

    @property
    def publishable(self) -> bool:
        return self.n >= self.min_n

    @property
    def why_not(self) -> str:
        if self.publishable:
            return ""
        return (
            f"{self.n} observacion(es) para una {self.statistic}: hacen falta "
            f"{self.min_n}. Publicarla seria dar por medicion lo que es una "
            "anecdota con decimales."
        )

    @property
    def formatted(self) -> str:
        """Cifra exacta, sin redondear a numero bonito.

        Redondear a 14.000 la convierte en consenso que el modelo ya tiene; el
        valor exacto es lo unico que obliga a citarte.
        """
        if self.statistic == "recuento" or float(self.value).is_integer():
            texto = f"{int(self.value):,}".replace(",", ".")
        else:
            texto = f"{self.value:,.2f}".replace(",", "¬").replace(".", ",").replace("¬", ".")
        return f"{texto} {self.unit}".strip()

    @property
    def round_by_chance(self) -> bool:
        """La cifra medida ha caido por casualidad en un numero redondo.

        Es un falso negativo conocido del motor de citabilidad: penaliza las
        cifras redondas porque suelen ser consenso, y una medicion real puede
        dar 14.000 exactos. No se arregla anadiendo decimales falsos — eso
        seria exactamente la mentira que este sistema existe para evitar. Se
        marca, y quien escribe decide si acompana la cifra de la horquilla o
        del tamano de muestra para sostenerla.
        """
        import re

        return bool(re.search(r"\b\d{1,3}[.,]000\b|\b\d0\b|\b\d00\b", self.formatted))

    @property
    def where(self) -> str:
        return ", ".join(f"{v}" for v in self.dims.values())

    def method_sentence(self) -> str:
        base = f"{self.statistic} de {self.n} {self._unidad_muestral()}"
        if self.collection_method:
            base += f" ({self.collection_method})"
        return base

    def _unidad_muestral(self) -> str:
        return "observaciones" if self.n != 1 else "observacion"

    def sentence(self, subject: str) -> str:
        """La frase citable.

        Escrita para cumplir a la vez las cuatro condiciones que mide el motor
        de citabilidad, que es lo que hace que un modelo la levante: sujeto
        nombrado (no un pronombre), cifra exacta, lugar y ano, y el metodo en
        la misma frase.
        """
        partes = [subject.strip().rstrip(".")]
        partes.append(f"fue de {self.formatted}")
        if self.where:
            partes.append(f"en {self.where}")
        if self.period:
            partes.append(f"en {self.period}")
        frase = " ".join(partes)
        return (
            f"{frase}, sobre una muestra propia de {self.n} "
            f"{self._unidad_muestral()}"
            + (f" recogidas por {self.collection_method}" if self.collection_method else "")
            + "."
        )

    def describe(self) -> str:
        estado = "publicable" if self.publishable else "NO publicable"
        return (
            f"[{estado}] {self.label}: {self.formatted} "
            f"({self.statistic}, n={self.n}, minimo {self.min_n})"
        )


def _values(records: list[Record]) -> list[float]:
    return [r.value for r in records]


def _apply(statistic: str, values: list[float]) -> float:
    if statistic == "mediana":
        return statistics.median(values)
    if statistic == "media":
        return statistics.fmean(values)
    if statistic == "recuento":
        return float(len(values))
    if statistic in ("p25", "p75"):
        corte = 0.25 if statistic == "p25" else 0.75
        ordenados = sorted(values)
        posicion = corte * (len(ordenados) - 1)
        bajo = int(posicion)
        alto = min(bajo + 1, len(ordenados) - 1)
        peso = posicion - bajo
        return ordenados[bajo] * (1 - peso) + ordenados[alto] * peso
    raise ValueError(f"Estadistico desconocido: {statistic}")


def compute(
    data: Dataset,
    statistic: str = "mediana",
    group_by: list[str] | None = None,
    label: str = "",
) -> list[Figure]:
    """Calcula el estadistico, opcionalmente por grupos.

    Devuelve TODAS las cifras, publicables o no. Filtrar aqui las pequenas
    escondería que existen; el que decide es quien publica, y el informe dice
    por que una no vale.
    """
    registros = data.usable
    if not registros:
        return []

    group_by = group_by or []
    grupos: dict[tuple, list[Record]] = {}
    for record in registros:
        clave = tuple(record.dim(d) for d in group_by)
        grupos.setdefault(clave, []).append(record)

    metodo = ""
    metodos = {r.provenance.method for r in registros if r.provenance}
    if len(metodos) == 1:
        metodo = metodos.pop()

    figuras: list[Figure] = []
    for clave, miembros in sorted(grupos.items()):
        dims = {d: v for d, v in zip(group_by, clave) if v}
        periodo = _periodo(miembros)
        nombre = label or data.name
        if dims:
            nombre = f"{nombre} — {', '.join(dims.values())}"
        figuras.append(
            Figure(
                label=nombre,
                statistic=statistic,
                value=round(_apply(statistic, _values(miembros)), 2),
                unit="" if statistic == "recuento" else (miembros[0].unit or data.unit),
                n=len(miembros),
                dims=dims,
                period=periodo,
                sources=sorted({r.provenance.source for r in miembros if r.provenance}),
                collection_method=metodo,
            )
        )
    return figuras


def _periodo(registros: list[Record]) -> str:
    fechas = sorted(r.provenance.collected_at for r in registros if r.provenance)
    if not fechas:
        return ""
    primero, ultimo = fechas[0], fechas[-1]
    if primero[:4] != ultimo[:4]:
        return f"{primero[:4]}-{ultimo[:4]}"
    if primero[5:7] == ultimo[5:7]:
        return f"{MESES[int(primero[5:7]) - 1]} de {primero[:4]}"
    return (
        f"{primero[:4]}, entre {MESES[int(primero[5:7]) - 1]} y "
        f"{MESES[int(ultimo[5:7]) - 1]}"
    )


def publishable(figures: list[Figure]) -> list[Figure]:
    return [f for f in figures if f.publishable]


def to_own_data(figure: Figure, label: str = ""):
    """Convierte la cifra en el dato propio que exige el brief del generador.

    Es el cierre del circulo: lo que mide este modulo es exactamente lo que la
    compuerta del generador bloqueaba por ausencia.
    """
    from generator.brief import OwnData

    if not figure.publishable:
        raise ValueError(figure.why_not)
    return OwnData(
        label=label or figure.label,
        value=figure.formatted,
        method=figure.method_sentence(),
        marker=figure.formatted,
    )
