"""Coste de una pagina, desglosado, y que pasa con el margen al cambiar algo."""

from __future__ import annotations

from dataclasses import dataclass, field

# Precios por millon de tokens. Son datos externos que cambian, asi que van
# declarados en un sitio y con fecha, no repartidos por el codigo.
#
# ULTIMA REVISION: 2026-10-04. Si esta fecha tiene mas de un trimestre, el
# calculo sigue corriendo pero los numeros ya no son los de la factura.
TARIFAS: dict[str, dict[str, float]] = {
    "claude-opus-5-5": {"in": 15.0, "out": 75.0, "cache_write": 18.75,
                        "cache_read": 1.50},
    "claude-sonnet-5-5": {"in": 3.0, "out": 15.0, "cache_write": 3.75,
                          "cache_read": 0.30},
    "claude-haiku-4-5": {"in": 1.0, "out": 5.0, "cache_write": 1.25,
                         "cache_read": 0.10},
}
TARIFAS_REVISADAS = "2026-10-04"

DESCUENTO_LOTES = 0.50   # la API de lotes cobra la mitad

MEDIDO = "medido"
SUPUESTO = "supuesto"


@dataclass
class Entrada:
    """Un numero del calculo, con si se midio o se supuso."""

    nombre: str
    valor: float
    origen: str = SUPUESTO
    nota: str = ""

    @property
    def medida(self) -> bool:
        return self.origen == MEDIDO


@dataclass
class CostePagina:
    """El desglose de una pagina. Todo en dolares."""

    modelo: float = 0.0
    revision: float = 0.0
    herramientas: float = 0.0
    entradas: list[Entrada] = field(default_factory=list)

    @property
    def total(self) -> float:
        return round(self.modelo + self.revision + self.herramientas, 4)

    @property
    def reparto(self) -> dict[str, int]:
        """Que porcentaje se lleva cada parte. Es la cifra que decide todo."""
        total = self.total
        if total <= 0:
            return {"modelo": 0, "revision": 0, "herramientas": 0}
        return {
            "modelo": round(100 * self.modelo / total),
            "revision": round(100 * self.revision / total),
            "herramientas": round(100 * self.herramientas / total),
        }

    @property
    def medido(self) -> int:
        if not self.entradas:
            return 0
        return round(100 * len([e for e in self.entradas if e.medida])
                     / len(self.entradas))

    def describe(self) -> str:
        r = self.reparto
        mayor = max(r, key=r.get)
        return (
            f"{self.total:.2f} $ por pagina: modelo {self.modelo:.2f} $ "
            f"({r['modelo']}%), revision {self.revision:.2f} $ "
            f"({r['revision']}%), herramientas {self.herramientas:.2f} $ "
            f"({r['herramientas']}%). Manda {mayor}. "
            f"{self.medido}% del calculo son datos medidos."
        )


def coste_modelo(usage, modelo: str = "claude-opus-5-5",
                 lotes: bool = False) -> float:
    """Dolares de una tirada de tokens. Cache aparte, que se factura distinto."""
    tarifa = TARIFAS.get(modelo)
    if tarifa is None:
        raise KeyError(
            f"No hay tarifa declarada para {modelo!r}. Anadela a TARIFAS con "
            "su fecha de revision en vez de estimarla aqui."
        )
    bruto = (
        getattr(usage, "input_tokens", 0) * tarifa["in"]
        + getattr(usage, "output_tokens", 0) * tarifa["out"]
        + getattr(usage, "cache_write_tokens", 0) * tarifa["cache_write"]
        + getattr(usage, "cache_read_tokens", 0) * tarifa["cache_read"]
    ) / 1_000_000
    if lotes:
        bruto *= DESCUENTO_LOTES
    return round(bruto, 6)


def por_pagina(
    usage=None,
    modelo: str = "claude-opus-5-5",
    lotes: bool = False,
    minutos_revision: float = 12.0,
    coste_hora: float = 45.0,
    herramientas_mes: float = 0.0,
    paginas_mes: int = 1,
    paginas_cartera: int = 0,
    reparaciones: float = 0.0,
    minutos_medidos: bool = False,
) -> CostePagina:
    """Coste completo de una pagina.

    `reparaciones` es el numero medio de reintentos por pagina. Multiplica el
    coste de modelo y no el de revision, porque una reparacion la hace la
    maquina. Es tambien la palanca mas facil de olvidar al presupuestar: con
    0,6 reparaciones de media, el gasto de modelo es un 60% mayor que el de la
    hoja de calculo que solo conto una llamada por pagina.
    """
    coste = CostePagina()

    if usage is not None and getattr(usage, "calls", 0):
        bruto = coste_modelo(usage, modelo=modelo, lotes=lotes)
        llamadas = max(getattr(usage, "calls", 1), 1)
        coste.modelo = round(bruto / llamadas * (1 + reparaciones), 4)
        coste.entradas.append(Entrada(
            "tokens por llamada", bruto / llamadas, MEDIDO,
            f"{llamadas} llamada(s) registradas"))
    else:
        # Sin uso medido no se inventa: se deja a cero y se declara. Un coste
        # de modelo supuesto es justo el numero que acaba en la propuesta.
        coste.entradas.append(Entrada(
            "tokens por llamada", 0.0, SUPUESTO,
            "sin llamadas registradas: el coste de modelo no se ha medido"))

    coste.revision = round(minutos_revision / 60 * coste_hora, 4)
    coste.entradas.append(Entrada(
        "minutos de revision", minutos_revision,
        MEDIDO if minutos_medidos else SUPUESTO,
        "cronometrados" if minutos_medidos else "estimados, no cronometrados"))
    coste.entradas.append(Entrada(
        "coste por hora", coste_hora, SUPUESTO,
        "depende de quien revise; declararlo es decision del negocio"))

    # El reparto de las herramientas: el error que tenia esto y que cambiaba
    # la conclusion.
    #
    # Dividir el coste de herramientas entre las paginas DE UN PLAN supone que
    # cada cliente paga su propia caja de herramientas entera. En una agencia
    # eso es falso: se paga una vez y sirve para todos. Con el reparto malo, un
    # plan de 8 paginas cargaba 15 $ por pagina y uno de 60 cargaba 2 $ por las
    # MISMAS herramientas, y el plan pequeno salia inviable por un artefacto
    # del calculo, no por su economia.
    #
    # `paginas_cartera` es el volumen mensual de toda la cartera. Sin el se
    # reparte sobre el plan, que es el caso de un solo cliente, y la entrada lo
    # declara para que nadie lea ese numero como si fuera el de una agencia.
    denominador = paginas_cartera if paginas_cartera > 0 else paginas_mes
    if denominador > 0 and herramientas_mes:
        coste.herramientas = round(herramientas_mes / denominador, 4)
        coste.entradas.append(Entrada(
            "herramientas al mes", herramientas_mes, SUPUESTO,
            f"repartido entre {denominador} pagina(s) "
            + ("de toda la cartera" if paginas_cartera > 0 else
               "de este plan: supone un solo cliente")))
    return coste
