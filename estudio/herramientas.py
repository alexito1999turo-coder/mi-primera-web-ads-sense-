"""Que herramientas, y la regla para decidirlo: minutos, no promesas.

La pregunta llego como "cuales son las mejores herramientas de edicion", y
contestada asi no tiene respuesta: la mejor herramienta depende de cual es tu
cuello de botella, y el cuello de botella de este plan esta calculado turno a
turno en `plan.carga_por_agente()`. El guionista se lleva 300 minutos a la
semana y el montador 240; el portadista, 40. Una suscripcion que acelera
miniaturas no mueve nada, y es la que primero se compra.

Asi que la regla es la enmienda del tercer juez puesta en aritmetica: **se paga
solo lo que quita minutos del turno de alguien, y se paga por minuto quitado.**
`pila()` ordena por minutos ahorrados entre euro y corta por presupuesto.

Dos honestidades que este modulo no se puede saltar:

* Los minutos que dice que quita cada herramienta son **hipotesis declaradas**,
  no mediciones. La primera vez que se cronometra un montaje, se corrigen. Por
  eso `medido` es `False` en todas y el informe lo dice.
* El precio de ElevenLabs no esta verificado aqui, y en vez de poner un numero
  aproximado se queda en `None`. Un precio inventado en una hoja de costes es
  exactamente el error que el modulo de economia del repositorio existe para
  no cometer.

Y una que es de riesgo y no de dinero: la voz sintetica y el troceado
automatico son justo las dos palancas que acercan el canal a la politica de
contenido no autentico. Se pueden usar —la IA como herramienta no desmonetiza—,
pero cada una enciende una compuerta: `declaracion` y `variacion`.
"""

from __future__ import annotations

from dataclasses import dataclass

from textos import cifra, lista, plural

from .plan import carga_por_agente, minutos_semana

# Ninguna herramienta quita mas del 60% del turno de un agente. No es
# prudencia: es que el 40% restante es el juicio del oficio —que caso, que
# frase, que plano— y una herramienta que se lo lleva no esta ahorrando
# minutos, esta cambiando el producto.
TOPE_AHORRO = 0.6


@dataclass(frozen=True)
class Herramienta:
    clave: str
    nombre: str
    oficio: str
    # Agente -> minutos a la semana que le quita. Hipotesis, no medicion.
    quita: dict[str, int]
    coste_mes: float | None
    hay_plan_gratis: bool
    nota: str
    riesgo: str = ""
    precio_verificado: bool = True
    medido: bool = False

    @property
    def minutos(self) -> int:
        return sum(self.quita.values())

    def to_dict(self) -> dict:
        return {
            "clave": self.clave,
            "nombre": self.nombre,
            "oficio": self.oficio,
            "quita": dict(self.quita),
            "minutos": self.minutos,
            "coste_mes": self.coste_mes,
            "hay_plan_gratis": self.hay_plan_gratis,
            "nota": self.nota,
            "riesgo": self.riesgo,
            "precio_verificado": self.precio_verificado,
            "medido": self.medido,
        }


CATALOGO: tuple[Herramienta, ...] = (
    Herramienta(
        clave="davinci",
        nombre="DaVinci Resolve",
        oficio="montador",
        quita={},
        coste_mes=0.0,
        hay_plan_gratis=True,
        nota="La base, y es gratis: montaje, color y audio de nivel profesional "
             "sin suscripcion. No quita minutos porque ES el turno de montaje; "
             "quitarla no ahorra, cambia de herramienta.",
    ),
    Herramienta(
        clave="descript",
        nombre="Descript",
        oficio="guionista y montador",
        quita={"guionista": 60, "montador": 60},
        coste_mes=24.0,
        hay_plan_gratis=True,
        nota="Edicion sobre la transcripcion: se corta el video borrando texto. "
             "En un canal de narracion, que es todo guion leido, ataca justo a "
             "los dos turnos mas grandes. El plan gratis da unos 60 minutos de "
             "material al mes, que no llegan a una semana de este plan.",
    ),
    Herramienta(
        clave="opusclip",
        nombre="OpusClip",
        oficio="troceador",
        quita={"troceador": 60},
        coste_mes=14.5,
        hay_plan_gratis=True,
        nota="Saca los verticales del largo solo. Es el ahorro mas limpio del "
             "catalogo porque el troceado es la tarea mas mecanica de la semana. "
             "14,50 al mes es el precio anual; al mes suelto son 29.",
        riesgo="El corte automatico tiende a la plantilla, que es el patron que "
               "castiga la politica de contenido repetitivo. Los cinco Shorts "
               "siguen teniendo que pasar la compuerta de variacion, y el "
               "troceador sigue escribiendo cinco aperturas distintas a mano.",
    ),
    Herramienta(
        clave="capcut",
        nombre="CapCut",
        oficio="troceador y portadista",
        quita={"troceador": 25, "portadista": 10},
        coste_mes=9.99,
        hay_plan_gratis=True,
        nota="Subtitulado y vertical rapidos, y el plan gratis sirve de verdad "
             "para los Shorts. Standard 9,99 y Pro 19,99 tras el cambio de "
             "planes de principios de 2026.",
    ),
    Herramienta(
        clave="elevenlabs",
        nombre="ElevenLabs",
        oficio="voz",
        quita={"voz": 30},
        coste_mes=None,
        hay_plan_gratis=True,
        precio_verificado=False,
        nota="Narracion sintetica. Quita media hora a la semana de grabar y "
             "repetir tomas. El precio NO esta verificado en este catalogo: "
             "antes de meterlo en la hoja de costes hay que mirarlo.",
        riesgo="Enciende dos compuertas a la vez: `declaracion` —hay que "
               "declararla en el ajuste de contenido alterado— y `politica_ia`, "
               "porque YouTube limita las personas sinteticas que tratan "
               "finanzas, y un canal de fraudes trata finanzas todos los dias. "
               "Pide autor humano identificado y analisis propio.",
    ),
    Herramienta(
        clave="audacity",
        nombre="Audacity o Reaper",
        oficio="voz",
        quita={"voz": 10},
        coste_mes=0.0,
        hay_plan_gratis=True,
        nota="Voz propia limpia con compresion y puerta de ruido. Es la opcion "
             "que no enciende ninguna compuerta, y la que mejor envejece: una "
             "voz propia es lo unico del canal que nadie puede replicar.",
    ),
    Herramienta(
        clave="estudio",
        nombre="Este repositorio",
        oficio="guionista, archivero y contable",
        quita={"guionista": 20, "archivero": 15},
        coste_mes=0.0,
        hay_plan_gratis=True,
        nota="Las compuertas de gancho, fuentes y dato propio corren sobre el "
             "guion antes de grabar: un gancho que no pasa se arregla en dos "
             "minutos escribiendo, y no en una hora regrabando.",
    ),
    Herramienta(
        clave="hoja",
        nombre="Hoja de calculo y carpeta de documentos",
        oficio="archivero y medidor",
        quita={"archivero": 10, "medidor": 10},
        coste_mes=0.0,
        hay_plan_gratis=True,
        nota="El expediente de fuentes con su fecha de consulta y la lectura "
             "semanal. Suena a poco y es la mitad de la compuerta de fuentes.",
    ),
)

CATALOGO_POR_CLAVE = {h.clave: h for h in CATALOGO}


def _ahorro_bruto(elegidas: list[Herramienta]) -> dict[str, int]:
    bruto: dict[str, int] = {}
    for h in elegidas:
        for agente_, minutos in h.quita.items():
            bruto[agente_] = bruto.get(agente_, 0) + minutos
    return bruto


def ahorro(elegidas: list[Herramienta]) -> dict[str, int]:
    """Minutos que se quitan de cada agente, con el tope del 60% aplicado."""
    carga = carga_por_agente()
    tope = {a: int(m * TOPE_AHORRO) for a, m in carga.items()}
    return {
        a: min(m, tope.get(a, 0))
        for a, m in sorted(_ahorro_bruto(elegidas).items())
        if min(m, tope.get(a, 0)) > 0
    }


def pila(presupuesto: float = 0.0) -> dict:
    """La pila que entra en el presupuesto, ordenada por minutos entre euro.

    Las gratuitas entran siempre: no hay nada que decidir con ellas. Las de
    pago se ordenan por minutos ahorrados entre euro al mes, que es la unica
    comparacion que no depende de lo bien que este escrita su pagina de ventas.
    """
    gratis = [h for h in CATALOGO if h.coste_mes == 0.0]
    de_pago = [h for h in CATALOGO if h.coste_mes]
    sin_precio = [h for h in CATALOGO if h.coste_mes is None]

    de_pago.sort(key=lambda h: (-(h.minutos / h.coste_mes), h.clave))

    elegidas = list(gratis)
    gastado = 0.0
    descartadas = []
    for h in de_pago:
        if gastado + h.coste_mes <= presupuesto:
            elegidas.append(h)
            gastado += h.coste_mes
        else:
            descartadas.append(h)

    quitado = ahorro(elegidas)
    minutos = minutos_semana() - sum(quitado.values())
    base = minutos_semana()
    return {
        "presupuesto": presupuesto,
        "coste_mes": round(gastado, 2),
        "elegidas": [h.to_dict() for h in elegidas],
        "descartadas": [h.to_dict() for h in descartadas],
        "sin_precio": [h.to_dict() for h in sin_precio],
        "ahorro_por_agente": quitado,
        "minutos_semana": minutos,
        "horas_semana": round(minutos / 60, 1),
        "horas_sin_herramientas": round(base / 60, 1),
        "coste_por_hora_ahorrada": (
            round(gastado / ((base - minutos) / 60), 2)
            if base > minutos and gastado else 0.0
        ),
        "resumen": _resumen(gastado, base, minutos, elegidas, descartadas),
    }


def _resumen(gastado: float, base: int, minutos: int,
             elegidas: list[Herramienta], descartadas: list[Herramienta]) -> str:
    horas = round((base - minutos) / 60, 1)
    if not gastado:
        return (f"Con la pila gratuita la semana baja de {cifra(base / 60, 1)} a "
                f"{cifra(minutos / 60, 1)} horas: {cifra(horas, 1)} menos sin "
                "pagar nada. Es por donde se empieza.")
    coste_hora = round(gastado / max(horas, 0.1), 2)
    cola = ""
    if descartadas:
        cola = (f" Fuera por presupuesto: "
                f"{lista([h.nombre for h in descartadas])}.")
    return (f"{cifra(gastado, 2)} al mes quitan {cifra(horas, 1)} horas a la "
            f"semana, a {cifra(coste_hora, 2)} por hora ahorrada. "
            f"{plural(len(elegidas), 'herramienta')} en la pila.{cola}")


def riesgos() -> list[dict]:
    """Las herramientas que encienden una compuerta, con cual."""
    return [
        {"nombre": h.nombre, "riesgo": h.riesgo}
        for h in CATALOGO if h.riesgo
    ]
