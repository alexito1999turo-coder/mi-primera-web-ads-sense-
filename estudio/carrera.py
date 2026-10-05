"""La carrera contra la puerta: cuantos minutos vistos hacen falta y cuando.

Aqui esta la decision que ordena todo lo demas, y no es de estilo ni de nicho.

El 01-02-2027 sube el liston de entrada al Programa de Socios de YouTube: los
canales que soliciten desde esa fecha necesitaran 1.000 suscriptores mas
**8.000** horas de visualizacion validas en 365 dias, o 20 millones de vistas
de Shorts validas en 90 dias. Hasta ese dia el liston es la mitad: 4.000 horas
o 10 millones de vistas de Shorts. Quien ya esta dentro no se ve afectado.

De ahi sale lo unico que de verdad importa de este modulo: **las dos rutas no
cuestan lo mismo, y no se parecen ni de lejos.** 4.000 horas son 240.000
minutos; un documental de 22 minutos con 45% de retencion deja 9,9 minutos por
vista, asi que la ruta de horas se cierra con unas 24.000 vistas. La ruta de
Shorts pide 10.000.000. Cuatrocientas veces mas vistas por la misma puerta.

Por eso el Short no es el producto: es el trailer. Y por eso la metrica del
canal no son las vistas, son **los minutos vistos por publicacion**.

Lo que este modulo NO hace es prever. Las vistas por video de un canal sin
historial no son estimables, y cualquier numero que dijera aqui seria el mismo
folleto que el resto del repositorio existe para no escribir. Esto es una
ecuacion: se le mete una hipotesis de vistas y dice que sale. La hipotesis la
pone quien la asume.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from textos import cifra, plural

MINUTOS_POR_HORA = 60

# Rangos de RPM publicados por terceros para el nicho (sucesos y fraude), no
# medidos en este canal. Se guardan con la etiqueta puesta: en el informe
# salen como NO MEDIDO hasta que haya tres meses de datos propios.
RPM_LARGO = (4.0, 10.0)
RPM_SHORT = (0.03, 0.12)
RPM_FUENTE = "rangos publicados por terceros, sin medir en este canal"


@dataclass(frozen=True)
class Puerta:
    nombre: str
    suscriptores: int
    horas: int
    vistas_shorts: int
    desde: date

    @property
    def minutos(self) -> int:
        return self.horas * MINUTOS_POR_HORA

    def to_dict(self) -> dict:
        return {
            "nombre": self.nombre,
            "suscriptores": self.suscriptores,
            "horas": self.horas,
            "minutos": self.minutos,
            "vistas_shorts": self.vistas_shorts,
            "desde": self.desde.isoformat(),
        }


CAMBIO = date(2027, 2, 1)

PUERTA_ACTUAL = Puerta(
    nombre="hasta el 31-01-2027",
    suscriptores=1000,
    horas=4000,
    vistas_shorts=10_000_000,
    desde=date(2023, 6, 13),
)

PUERTA_NUEVA = Puerta(
    nombre="desde el 01-02-2027",
    suscriptores=1000,
    horas=8000,
    vistas_shorts=20_000_000,
    desde=CAMBIO,
)


def puerta_vigente(hoy: date) -> Puerta:
    return PUERTA_ACTUAL if hoy < CAMBIO else PUERTA_NUEVA


@dataclass
class Carrera:
    """El estado de la carrera con una hipotesis de duracion y retencion."""

    hoy: date
    duracion_min: float = 22.0
    retencion: float = 0.45
    horas_acumuladas: float = 0.0
    suscriptores: int = 0
    puerta: Puerta | None = None

    def __post_init__(self) -> None:
        if self.duracion_min <= 0:
            raise ValueError("La duracion de un video no puede ser cero.")
        if not 0 < self.retencion <= 1:
            raise ValueError("La retencion va entre 0 y 1.")
        if self.puerta is None:
            self.puerta = puerta_vigente(self.hoy)

    # -- la aritmetica de la puerta ---------------------------------------
    @property
    def minutos_por_vista(self) -> float:
        return round(self.duracion_min * self.retencion, 2)

    @property
    def minutos_objetivo(self) -> int:
        return self.puerta.minutos

    @property
    def minutos_hechos(self) -> float:
        return round(self.horas_acumuladas * MINUTOS_POR_HORA, 1)

    @property
    def minutos_que_faltan(self) -> float:
        return max(0.0, self.minutos_objetivo - self.minutos_hechos)

    @property
    def vistas_necesarias(self) -> int:
        return int(-(-self.minutos_que_faltan // self.minutos_por_vista))

    @property
    def dias_hasta_el_cambio(self) -> int:
        return (CAMBIO - self.hoy).days

    @property
    def ventaja_sobre_shorts(self) -> float:
        """Cuantas veces mas vistas pide la ruta de Shorts por la misma puerta."""
        if not self.vistas_necesarias:
            return 0.0
        return round(self.puerta.vistas_shorts / self.vistas_necesarias, 1)

    def vistas_por_dia(self, dias: int | None = None) -> int:
        plazo = self.dias_hasta_el_cambio if dias is None else dias
        if plazo <= 0:
            return 0
        return int(-(-self.vistas_necesarias // plazo))

    # -- la hipotesis -----------------------------------------------------
    def semanas_hasta_la_puerta(self, vistas_por_largo: float,
                                largos_por_semana: int = 2) -> float | None:
        """Con esta hipotesis de vistas, cuantas semanas. None si no llega nunca."""
        if vistas_por_largo <= 0 or largos_por_semana <= 0:
            return None
        minutos_semana = vistas_por_largo * largos_por_semana * self.minutos_por_vista
        if minutos_semana <= 0:
            return None
        return round(self.minutos_que_faltan / minutos_semana, 1)

    def llega_al_cambio(self, vistas_por_largo: float,
                        largos_por_semana: int = 2) -> bool:
        semanas = self.semanas_hasta_la_puerta(vistas_por_largo, largos_por_semana)
        if semanas is None:
            return False
        return semanas * 7 <= self.dias_hasta_el_cambio

    # -- como se cuenta ---------------------------------------------------
    def veredicto(self, vistas_por_largo: float = 0.0,
                  largos_por_semana: int = 2) -> str:
        if self.dias_hasta_el_cambio <= 0:
            return (f"La puerta ya es la nueva: {plural(self.puerta.horas, 'hora')} "
                    f"en 365 dias. Hacen falta {cifra(self.vistas_necesarias)} vistas "
                    f"de documental a {self.minutos_por_vista} minutos por vista.")
        if not vistas_por_largo:
            return (f"Quedan {plural(self.dias_hasta_el_cambio, 'dia')} de puerta "
                    f"baja. Son {cifra(self.vistas_necesarias)} vistas de documental, "
                    f"o {cifra(self.vistas_por_dia())} al dia. Sin una hipotesis de "
                    "vistas por video no se puede decir si se llega: eso es NO MEDIDO.")
        semanas = self.semanas_hasta_la_puerta(vistas_por_largo, largos_por_semana)
        if semanas is None:
            return "La hipotesis no llega a la puerta en ningun plazo."
        if self.llega_al_cambio(vistas_por_largo, largos_por_semana):
            return (f"Con {cifra(vistas_por_largo)} vistas por documental y "
                    f"{plural(largos_por_semana, 'largo')} a la semana, la puerta "
                    f"baja se cruza en {cifra(semanas, 1)} semanas, dentro del plazo "
                    f"de {plural(self.dias_hasta_el_cambio, 'dia')}.")
        return (f"Con {cifra(vistas_por_largo)} vistas por documental harian falta "
                f"{cifra(semanas, 1)} semanas y solo quedan "
                f"{plural(self.dias_hasta_el_cambio, 'dia')}. O sube la hipotesis, "
                "o el objetivo es la puerta nueva: el doble de minutos.")

    def to_dict(self, vistas_por_largo: float = 0.0,
                largos_por_semana: int = 2) -> dict:
        return {
            "hoy": self.hoy.isoformat(),
            "puerta": self.puerta.to_dict(),
            "dias_hasta_el_cambio": self.dias_hasta_el_cambio,
            "duracion_min": self.duracion_min,
            "retencion": self.retencion,
            "minutos_por_vista": self.minutos_por_vista,
            "minutos_objetivo": self.minutos_objetivo,
            "minutos_hechos": self.minutos_hechos,
            "minutos_que_faltan": self.minutos_que_faltan,
            "vistas_necesarias": self.vistas_necesarias,
            "vistas_por_dia": self.vistas_por_dia(),
            "ventaja_sobre_shorts": self.ventaja_sobre_shorts,
            "suscriptores": self.suscriptores,
            "suscriptores_objetivo": self.puerta.suscriptores,
            "semanas": self.semanas_hasta_la_puerta(vistas_por_largo, largos_por_semana),
            "llega": self.llega_al_cambio(vistas_por_largo, largos_por_semana),
            "veredicto": self.veredicto(vistas_por_largo, largos_por_semana),
        }


def ingreso(vistas: float, rango: tuple[float, float]) -> tuple[float, float]:
    """Ingreso por publicidad para un rango de RPM. RPM es por mil vistas."""
    bajo, alto = rango
    return round(vistas / 1000 * bajo, 2), round(vistas / 1000 * alto, 2)


def comparar_rutas(carrera: Carrera) -> dict:
    """Las dos rutas a la misma puerta, en vistas y en dinero.

    La comparacion que nadie hace, y la que decide la arquitectura del canal:
    por la ruta de Shorts hay que mover cientos de veces mas vistas, y esas
    vistas pagan entre treinta y cien veces menos cada mil.
    """
    vistas_largo = carrera.vistas_necesarias
    vistas_short = carrera.puerta.vistas_shorts
    return {
        "ruta_horas": {
            "vistas": vistas_largo,
            "ingreso": ingreso(vistas_largo, RPM_LARGO),
            "rpm": RPM_LARGO,
        },
        "ruta_shorts": {
            "vistas": vistas_short,
            "ingreso": ingreso(vistas_short, RPM_SHORT),
            "rpm": RPM_SHORT,
        },
        "veces_mas_vistas": carrera.ventaja_sobre_shorts,
        "fuente_rpm": RPM_FUENTE,
    }
