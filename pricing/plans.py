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


def precio_minimo(plan: Plan, margen_objetivo: float = MARGEN_MINIMO,
                  robusto: bool = True, **kw) -> dict:
    """Que habria que cobrar por este plan para que aguante.

    `robusto` es la diferencia entre un precio que funciona y uno que
    funciona mientras no pase nada: exige el margen objetivo DESPUES de la
    peor de las tres palancas, no antes. Un plan que solo cumple en el caso
    bueno es un plan que incumple en cuanto el primer cliente pide una
    llamada de mas.
    """
    coste = plan.coste(**kw).total * plan.paginas
    if margen_objetivo >= 1:
        raise ValueError("El margen objetivo tiene que ser menor que 1.")
    base = coste / (1 - margen_objetivo)

    if not robusto:
        precio = base
        motivo = f"margen {margen_objetivo * 100:.0f}% en el caso bueno"
    else:
        # La palanca que mas duele es la revision: se calcula el precio que
        # da el margen objetivo con los minutos un 50% por encima.
        minutos = kw.get("minutos_revision", plan.minutos_revision)
        peor = dict(kw, minutos_revision=minutos * 1.5)
        coste_peor = plan.coste(**peor).total * plan.paginas
        precio = max(base, coste_peor / (1 - margen_objetivo))
        motivo = (f"margen {margen_objetivo * 100:.0f}% aun con la revision "
                  f"en {minutos * 1.5:.0f} minutos por pagina")

    precio = round(precio / 10) * 10 or 10   # a decenas, como un precio real
    resultado = evaluar(Plan(plan.nombre, precio, plan.paginas,
                             plan.minutos_revision), **kw)
    return {
        "precio": precio,
        "actual": plan.precio_mes,
        "subida": round(precio - plan.precio_mes, 2),
        "margen_resultante": resultado.margen_pct,
        "motivo": motivo,
        "lectura": (
            f"«{plan.nombre}» a {plan.precio_mes:.0f} $ deja "
            f"{evaluar(plan, **kw).margen_pct:.0f}% de margen. Para {motivo} "
            f"habria que cobrar {precio:.0f} $ "
            f"({plural(plan.paginas, 'pagina')}, "
            f"{precio / plan.paginas:.2f} $ por pagina)."
        ),
    }


def paginas_maximas(plan: Plan, margen_objetivo: float = MARGEN_MINIMO,
                    **kw) -> dict:
    """Cuantas paginas caben en este precio sin bajar del margen objetivo.

    Es la otra salida, y casi siempre la mejor: en vez de subir el precio,
    prometer menos. Un plan de ocho paginas bien hechas se vende mejor que
    uno de doce con prisa, y el cliente no compra paginas — compra que el
    trafico suba.
    """
    coste_unidad = plan.coste(**kw).total
    if coste_unidad <= 0:
        return {"paginas": plan.paginas, "lectura": "Sin coste por pagina que acotar."}

    # No es una division: es un punto fijo.
    #
    # El coste por pagina DEPENDE de cuantas paginas tiene el plan, porque el
    # coste fijo de herramientas se reparte entre ellas. Al bajar de doce
    # paginas a nueve, cada una carga mas herramientas, y el nueve que salia
    # de dividir ya no cumple el margen. Lo encontro su propio test: pedia
    # 35% y daba 31%.
    #
    # Se baja de una en una comprobando de verdad, que para numeros de dos
    # cifras es mas barato que resolverlo bien y no se puede equivocar.
    cabe = 0
    for candidato in range(plan.paginas, 0, -1):
        tentativa = Plan(plan.nombre, plan.precio_mes, candidato,
                         plan.minutos_revision)
        if evaluar(tentativa, **kw).margen_pct >= margen_objetivo * 100:
            cabe = candidato
            break

    if cabe == 0:
        return {
            "paginas": 0, "actuales": plan.paginas, "sobran": plan.paginas,
            "lectura": (
                f"A {plan.precio_mes:.0f} $ no cabe ni una pagina con "
                f"{margen_objetivo * 100:.0f}% de margen: el precio no cubre "
                "el coste fijo del plan, asi que quitar alcance no lo arregla."
            ),
        }

    coste_real = Plan(plan.nombre, plan.precio_mes, cabe,
                      plan.minutos_revision).coste(**kw).total
    return {
        "paginas": cabe,
        "actuales": plan.paginas,
        "sobran": plan.paginas - cabe,
        "lectura": (
            f"A {plan.precio_mes:.0f} $ caben {plural(cabe, 'pagina')} con "
            f"{margen_objetivo * 100:.0f}% de margen ({coste_real:.2f} $ por "
            f"pagina a ese volumen); el plan promete "
            f"{plural(plan.paginas, 'pagina')}."
        ),
    }


def curva_de_cartera(plan: Plan, volumenes: list[int] | None = None,
                     margen_objetivo: float = MARGEN_MINIMO, **kw) -> dict:
    """Margen del plan segun el tamano de la cartera.

    Es la vista que faltaba, y la descubri arreglando un error propio: el
    coste de herramientas es fijo del negocio, no del cliente, asi que el
    primer cliente lo carga entero y el decimo lo carga dividido entre diez.
    Mirando un solo plan aislado, uno pequeno parece inviable; lo que es
    inviable es tenerlo como unico cliente.

    Lo util de esto en una conversacion de precio: no hay que subir la tarifa
    por lo que se ve en el cliente uno. Hay que saber en que numero de
    clientes cambia, y si ese numero se puede alcanzar.
    """
    volumenes = volumenes or [1, 2, 3, 5, 8, 12, 20, 40]
    puntos = []
    umbral = None
    for clientes in volumenes:
        cartera = clientes * plan.paginas
        resultado = evaluar(plan, **dict(kw, paginas_cartera=cartera))
        puntos.append({
            "clientes": clientes,
            "paginas_cartera": cartera,
            "coste_pagina": resultado.coste_pagina,
            "margen_pct": resultado.margen_pct,
            "sano": resultado.margen_pct >= margen_objetivo * 100,
        })
        if umbral is None and puntos[-1]["sano"]:
            umbral = clientes

    if umbral is None:
        lectura = (
            f"«{plan.nombre}» no llega al {margen_objetivo * 100:.0f}% de "
            "margen ni con la cartera mas grande que se ha probado. El "
            "problema no es la escala: es el precio o el alcance."
        )
    elif umbral == 1:
        lectura = (
            f"«{plan.nombre}» ya es rentable con el primer cliente "
            f"({puntos[0]['margen_pct']:.0f}% de margen)."
        )
    else:
        lectura = (
            f"«{plan.nombre}» no aguanta con pocos clientes: con uno deja "
            f"{puntos[0]['margen_pct']:.0f}% y hace falta llegar a "
            f"{plural(umbral, 'cliente')} para pasar del "
            f"{margen_objetivo * 100:.0f}%. Hasta ahi, cada cliente de este "
            "plan carga entero el coste de herramientas."
        )
    return {"puntos": puntos, "umbral_clientes": umbral, "lectura": lectura}
