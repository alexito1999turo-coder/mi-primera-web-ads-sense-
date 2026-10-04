"""Tarifas, margen y lo que de verdad se lo come.

La parte util de esto no es el margen: es la sensibilidad. Un plan con 60% de
margen sobre el papel y 40% de margen si la revision pasa de 12 a 18 minutos
no es un plan con 60% de margen, es un plan que depende de una cifra que nadie
ha cronometrado.
"""

from __future__ import annotations

from textos import plural

from dataclasses import dataclass, field

from .unit import CostePagina, por_pagina

# Margen por debajo del cual un plan no aguanta un mes malo: una pagina
# rechazada, una reunion de mas, un cliente que contesta tarde.
MARGEN_MINIMO = 0.35


@dataclass
class Plan:
    """Un plan de la tarifa. `paginas` es lo que se compromete, no lo maximo."""

    nombre: str
    precio_mes: float
    paginas: int
    minutos_revision: float = 12.0
    incluye: list[str] = field(default_factory=list)
    no_incluye: list[str] = field(default_factory=list)

    def coste(self, **kw) -> CostePagina:
        argumentos = dict(minutos_revision=self.minutos_revision,
                          paginas_mes=self.paginas)
        argumentos.update(kw)
        return por_pagina(**argumentos)


@dataclass
class Resultado:
    plan: Plan
    coste_pagina: float
    coste_mes: float
    margen_mes: float
    margen_pct: float
    reparto: dict[str, int]
    medido: int

    @property
    def sano(self) -> bool:
        return self.margen_pct >= MARGEN_MINIMO * 100

    @property
    def precio_pagina(self) -> float:
        return round(self.plan.precio_mes / self.plan.paginas, 2) if self.plan.paginas else 0.0

    def describe(self) -> str:
        estado = "ok" if self.sano else "AJUSTADO"
        return (
            f"[{estado}] {self.plan.nombre}: {self.plan.precio_mes:.0f} $/mes "
            f"por {plural(self.plan.paginas, 'pagina')} = {self.precio_pagina:.2f} $/pagina. "
            f"Cuesta {self.coste_pagina:.2f} $. Margen {self.margen_pct:.0f}% "
            f"({self.margen_mes:.0f} $/mes). "
            f"{self.medido}% del calculo son datos medidos."
        )


def evaluar(plan: Plan, **kw) -> Resultado:
    coste = plan.coste(**kw)
    coste_mes = round(coste.total * plan.paginas, 2)
    margen = round(plan.precio_mes - coste_mes, 2)
    pct = round(100 * margen / plan.precio_mes, 1) if plan.precio_mes else 0.0
    return Resultado(plan=plan, coste_pagina=coste.total, coste_mes=coste_mes,
                     margen_mes=margen, margen_pct=pct, reparto=coste.reparto,
                     medido=coste.medido)


@dataclass
class Sensibilidad:
    """Que pasa con el margen al mover una sola palanca."""

    palanca: str
    desde: str
    hasta: str
    margen_antes: float
    margen_despues: float

    @property
    def caida(self) -> float:
        return round(self.margen_antes - self.margen_despues, 1)

    @property
    def rompe(self) -> bool:
        return self.margen_despues < MARGEN_MINIMO * 100

    def describe(self) -> str:
        signo = "cae" if self.caida > 0 else "sube"
        aviso = "  <- rompe el plan" if self.rompe else ""
        return (f"{self.palanca}: de {self.desde} a {self.hasta}, el margen "
                f"{signo} {abs(self.caida):.0f} puntos hasta "
                f"{self.margen_despues:.0f}%{aviso}")


def sensibilidad(plan: Plan, base: dict | None = None) -> list[Sensibilidad]:
    """Mueve una palanca cada vez. Es lo que convierte la tarifa en un plan.

    Las palancas elegidas no son arbitrarias: son las tres que de verdad se
    mueven solas en un mes real. Los minutos de revision suben cuando entra un
    cliente nuevo, las reparaciones suben cuando el nicho es raro, y el precio
    baja cuando el cliente negocia.
    """
    argumentos = dict(base or {})
    partida = evaluar(plan, **argumentos).margen_pct
    salida: list[Sensibilidad] = []

    minutos = argumentos.get("minutos_revision", plan.minutos_revision)
    peor = dict(argumentos, minutos_revision=minutos * 1.5)
    salida.append(Sensibilidad(
        "Minutos de revision por pagina", f"{minutos:.0f}",
        f"{minutos * 1.5:.0f}", partida, evaluar(plan, **peor).margen_pct))

    reparaciones = argumentos.get("reparaciones", 0.0)
    mas = dict(argumentos, reparaciones=reparaciones + 1.0)
    salida.append(Sensibilidad(
        "Reparaciones por pagina", f"{reparaciones:.1f}",
        f"{reparaciones + 1:.1f}", partida, evaluar(plan, **mas).margen_pct))

    rebajado = Plan(nombre=plan.nombre, precio_mes=plan.precio_mes * 0.85,
                    paginas=plan.paginas,
                    minutos_revision=plan.minutos_revision)
    salida.append(Sensibilidad(
        "Precio negociado", f"{plan.precio_mes:.0f} $",
        f"{plan.precio_mes * 0.85:.0f} $", partida,
        evaluar(rebajado, **argumentos).margen_pct))
    return salida


def punto_muerto(plan: Plan, fijos_mes: float, **kw) -> dict:
    """Cuantos clientes de este plan pagan la estructura.

    Es la unica cifra que decide si esto es un negocio o un trabajo: si hacen
    falta mas clientes de los que una persona puede atender, el plan esta mal
    puesto por mucho que el margen por cliente sea bonito.
    """
    resultado = evaluar(plan, **kw)
    if resultado.margen_mes <= 0:
        return {"clientes": None, "margen_cliente": resultado.margen_mes,
                "lectura": ("Este plan pierde dinero por cliente: no hay punto "
                            "muerto, hay un agujero que crece con las ventas.")}
    import math

    clientes = math.ceil(fijos_mes / resultado.margen_mes)
    paginas = clientes * plan.paginas
    return {
        "clientes": clientes,
        "margen_cliente": resultado.margen_mes,
        "paginas_mes": paginas,
        "horas_revision_mes": round(
            paginas * kw.get("minutos_revision", plan.minutos_revision) / 60, 1),
        "lectura": (
            f"{clientes} cliente(s) de «{plan.nombre}» cubren "
            f"{fijos_mes:.0f} $/mes de estructura. Son {paginas} paginas y "
            f"{round(paginas * kw.get('minutos_revision', plan.minutos_revision) / 60, 1)} "
            "horas de revision al mes."
        ),
    }


# Lo que este calculo NO cuenta.
#
# Un modelo de margen que no declara lo que omite no es un modelo, es un
# argumento de venta. Estas cuatro partidas son las que convierten un 73% sobre
# el papel en un 40% real, y ninguna cabe en un coste por pagina porque no
# escalan con las paginas: escalan con los clientes.
NO_CONTADO: tuple[tuple[str, str], ...] = (
    ("Captacion", "Lo que cuesta conseguir el cliente. Reparte sobre la vida "
                  "del contrato, no sobre el mes."),
    ("Alta y auditoria inicial", "El primer mes de un cliente nuevo lleva una "
                                 "auditoria, un plan de clusters y una reunion. "
                                 "No se parece a los siguientes."),
    ("Gestion de cuenta", "Correos, llamadas, el informe mensual y la reunion "
                          "de revision. Crece con clientes, no con paginas."),
    ("Bajas", "Un cliente que se va a los tres meses no amortiza su alta. Sin "
              "una tasa de bajas medida, el valor de vida es un deseo."),
)


@dataclass
class Tarifa:
    """La tarifa entera, evaluada, con lo que no cuenta declarado."""

    resultados: list[Resultado] = field(default_factory=list)
    sensibilidades: dict[str, list[Sensibilidad]] = field(default_factory=dict)
    fijos_mes: float = 0.0
    puntos_muertos: dict[str, dict] = field(default_factory=dict)

    @property
    def medido(self) -> int:
        if not self.resultados:
            return 0
        return round(sum(r.medido for r in self.resultados) / len(self.resultados))

    @property
    def planes_fragiles(self) -> list[str]:
        """Planes que un solo cambio razonable deja por debajo del minimo."""
        return sorted({
            nombre for nombre, casos in self.sensibilidades.items()
            if any(c.rompe for c in casos)
        })

    def to_markdown(self) -> str:
        out = ["# Tarifa y economia unitaria", "",
               f"_El {self.medido}% de las cifras de este calculo son "
               "mediciones; el resto son supuestos declarados. Un precio que "
               "no sale de un coste medido es una cifra de folleto._", ""]

        out += ["## Planes", "",
                "| Plan | Precio/mes | Paginas | $/pagina | Coste/pagina | "
                "Margen | Reparto del coste |",
                "|---|---:|---:|---:|---:|---:|---|"]
        for r in self.resultados:
            rep = r.reparto
            out.append(
                f"| {r.plan.nombre} | {r.plan.precio_mes:.0f} $ | "
                f"{r.plan.paginas} | {r.precio_pagina:.2f} $ | "
                f"{r.coste_pagina:.2f} $ | {r.margen_pct:.0f}% | "
                f"modelo {rep['modelo']}% · revision {rep['revision']}% · "
                f"herramientas {rep['herramientas']}% |"
            )
        out.append("")

        if self.resultados:
            peor = max(self.resultados, key=lambda r: r.reparto["revision"])
            out += [
                "El reparto es la conclusion, no el margen: en «"
                f"{peor.plan.nombre}» el modelo es el "
                f"{peor.reparto['modelo']}% del coste y la revision el "
                f"{peor.reparto['revision']}%. Quien venda esto compitiendo en "
                "precio de tokens esta optimizando la parte barata. Y bajar de "
                "modelo no ahorra: sube los minutos de revision, que es la cara.",
                "",
            ]

        out += ["## Que pasa si se mueve una palanca", "",
                "Un plan con buen margen que se rompe al cronometrar la "
                "revision no es un plan con buen margen: es un plan que "
                "depende de una cifra que nadie ha medido.", ""]
        for nombre, casos in self.sensibilidades.items():
            out.append(f"**{nombre}**")
            out.append("")
            out += [f"- {c.describe()}" for c in casos]
            out.append("")

        if self.planes_fragiles:
            out += ["> Frágiles: " + ", ".join(self.planes_fragiles) +
                    ". Un solo cambio razonable los deja por debajo del "
                    f"{MARGEN_MINIMO * 100:.0f}% de margen.", ""]

        if self.puntos_muertos:
            out += ["## Punto muerto", "",
                    f"Con {self.fijos_mes:.0f} $/mes de estructura:", ""]
            for nombre, dato in self.puntos_muertos.items():
                out.append(f"- {dato['lectura']}")
            out.append("")

        out += ["## Lo que este calculo NO cuenta", "",
                "Estas partidas no caben en un coste por pagina porque no "
                "escalan con las paginas: escalan con los clientes. Son las "
                "que convierten un margen de folleto en el margen real.", ""]
        out += [f"- **{nombre}.** {detalle}" for nombre, detalle in NO_CONTADO]
        out.append("")
        out.append(f"_Tarifas de modelo revisadas el {_revision_tarifas()}._")
        return "\n".join(out)


def _revision_tarifas() -> str:
    from .unit import TARIFAS_REVISADAS
    return TARIFAS_REVISADAS


def tarifa(planes: list[Plan], fijos_mes: float = 0.0, **kw) -> Tarifa:
    """Evalua la tarifa entera: margen, sensibilidad y punto muerto."""
    salida = Tarifa(fijos_mes=fijos_mes)
    for plan in planes:
        salida.resultados.append(evaluar(plan, **kw))
        salida.sensibilidades[plan.nombre] = sensibilidad(plan, kw)
        if fijos_mes:
            salida.puntos_muertos[plan.nombre] = punto_muerto(
                plan, fijos_mes, **kw)
    return salida
