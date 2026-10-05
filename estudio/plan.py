"""La semana canonica: siete publicaciones al dia desde una sola investigacion.

El encargo era publicar todos los dias. La trampa de ese encargo es que se lee
como "siete investigaciones", y siete investigaciones a la semana no las hace
una persona ni las tolera la politica de contenido no autentico: lo que se
castiga es subir varias piezas al dia **sin variacion discernible**, que es
exactamente lo que sale de intentar llenar siete dias con el material de uno.

La forma que si aguanta es la contraria: **una investigacion a la semana, siete
publicaciones distintas de ella.** Dos largos (el documental del viernes y el
expediente del martes, que es donde viven los minutos vistos) y cinco Shorts,
cada uno de un angulo distinto —la cifra, el documento, la cronologia, el
desmentido, la pregunta—, que es lo que la compuerta de variacion comprueba
midiendo la similitud de los guiones.

Y una decision de calendario que no es cosmetica: **lo que se publica esta
semana se produjo la anterior.** Sin ese colchon, un dia malo es un dia sin
publicar, y el canal depende de que a una persona no le pase nada siete dias
seguidos. Con colchon, un dia malo se come la reserva y la cadencia no se
entera. Por eso el calendario arranca con una semana 0 que produce y no
publica, y por eso los turnos de cada dia fabrican la semana siguiente.

Los minutos de cada turno no son adorno: de ellos sale la carga semanal real
que el tercer juez usa para juzgar la estrategia, y la que dice si esto lo
puede sostener una persona con un trabajo.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

from textos import cifra, plural

from .agentes import EXPEDIENTE, LARGO, SHORT, agente
from .compuertas import cadencia

# Horas de publicacion, en minutos desde medianoche. Los largos a las 19:00,
# los Shorts a las 14:00: no es superticion, es que la compuerta de cadencia
# mide la desviacion dentro de cada formato y mezclar horas en el mismo
# formato es lo que rompe la siembra en frio.
HORA_LARGO = 19 * 60
HORA_SHORT = 14 * 60

# Duraciones objetivo. El documental manda porque los minutos vistos por vista
# son lineales con la duracion y la retencion, y la puerta se mide en minutos.
DURACION = {LARGO: 22.0, EXPEDIENTE: 10.0, SHORT: 0.7}


@dataclass(frozen=True)
class Turno:
    """Un bloque de trabajo de un agente dentro de la jornada."""

    agente: str
    inicio: int
    minutos: int
    tarea: str
    entrega: str
    relevo: str = ""

    @property
    def fin(self) -> int:
        return self.inicio + self.minutos

    def to_dict(self) -> dict:
        a = agente(self.agente)
        return {
            "agente": self.agente,
            "nombre": a.nombre,
            "figura": a.figura,
            "color": a.color,
            "inicio": self.inicio,
            "minutos": self.minutos,
            "fin": self.fin,
            "tarea": self.tarea,
            "entrega": self.entrega,
            "relevo": self.relevo,
        }


@dataclass(frozen=True)
class Dia:
    indice: int
    nombre: str
    formato: str
    tipo: str
    titulo: str
    turnos: tuple[Turno, ...]

    @property
    def minutos(self) -> int:
        return sum(t.minutos for t in self.turnos)

    @property
    def hora(self) -> int:
        return HORA_SHORT if self.formato == SHORT else HORA_LARGO

    @property
    def jornada(self) -> int:
        """Lo que ocupa el dia de punta a punta, huecos incluidos."""
        return max((t.fin for t in self.turnos), default=0)

    def to_dict(self) -> dict:
        return {
            "indice": self.indice,
            "nombre": self.nombre,
            "formato": self.formato,
            "tipo": self.tipo,
            "titulo": self.titulo,
            "hora": self.hora,
            "minutos": self.minutos,
            "jornada": self.jornada,
            "duracion_publicacion": DURACION[self.formato],
            "turnos": [t.to_dict() for t in self.turnos],
        }


SEMANA: tuple[Dia, ...] = (
    Dia(
        indice=1, nombre="lunes", formato=SHORT, tipo="cifra",
        titulo="La cifra que no sale en ningun titular",
        turnos=(
            Turno("medidor", 0, 25, "Lee la semana que acaba: retencion, CTR y "
                  "conversion de Short a largo", "lectura semanal", "cazador"),
            Turno("cazador", 25, 45, "Elige el caso de la semana entre los "
                  "candidatos y escribe por que no son los otros",
                  "caso y angulo en una frase", "archivero"),
            Turno("archivero", 70, 90, "Reune tres fuentes independientes y el "
                  "documento primario, con la hora de consulta",
                  "expediente de fuentes", "contable"),
            Turno("publicador", 160, 10, "Publica el Short de la reserva y "
                  "comprueba la hora", "Short del dia"),
        ),
    ),
    Dia(
        indice=2, nombre="martes", formato=EXPEDIENTE, tipo="dossier",
        titulo="El expediente: lo que dicen los papeles",
        turnos=(
            Turno("contable", 0, 80, "Agrega el dato propio: mediana, reparto o "
                  "total por victima, con metodo escrito",
                  "cifra propia con metodo", "guionista"),
            Turno("guionista", 80, 150, "Escribe el documental: gancho de treinta "
                  "segundos, contexto, el enganio, la caida",
                  "guion del documental"),
            Turno("publicador", 230, 10, "Publica el expediente de la reserva",
                  "expediente del dia"),
        ),
    ),
    Dia(
        indice=3, nombre="miercoles", formato=SHORT, tipo="documento",
        titulo="El documento que lo dice con letra pequena",
        turnos=(
            Turno("guionista", 0, 90, "Cierra el guion y saca los cinco ganchos "
                  "de Short, uno por angulo", "cinco ganchos", "abogado"),
            Turno("abogado", 90, 45, "Pasa el guion por registro publico y por "
                  "politica: nombres, atribucion y temas limitados",
                  "guion con atribucion", "voz"),
            Turno("voz", 135, 50, "Graba la narracion y rellena la declaracion "
                  "de contenido alterado si la voz es sintetica",
                  "pista de narracion", "montador"),
            Turno("publicador", 185, 10, "Publica el Short de la reserva",
                  "Short del dia"),
        ),
    ),
    Dia(
        indice=4, nombre="jueves", formato=SHORT, tipo="cronologia",
        titulo="Diez anios en noventa segundos",
        turnos=(
            Turno("montador", 0, 180, "Monta el documental: archivo con licencia "
                  "anotada y el documento en pantalla el tiempo de leerlo",
                  "documental montado"),
            Turno("publicador", 180, 10, "Publica el Short de la reserva",
                  "Short del dia"),
        ),
    ),
    Dia(
        indice=5, nombre="viernes", formato=LARGO, tipo="caso",
        titulo="El caso completo",
        turnos=(
            Turno("montador", 0, 60, "Cierra el montaje y el registro de "
                  "licencias", "registro de licencias", "portadista"),
            Turno("portadista", 60, 40, "Dos miniaturas y dos titulos, y "
                  "comprueba que la promesa esta dentro del video",
                  "dos miniaturas y dos titulos", "troceador"),
            Turno("troceador", 100, 110, "Corta los cinco Shorts, uno de cada "
                  "angulo, y mide la similitud entre guiones",
                  "cinco Shorts verticales", "publicador"),
            Turno("publicador", 210, 15, "Publica el documental a la hora fija y "
                  "programa la reserva de la semana que viene",
                  "documental y reserva programada"),
        ),
    ),
    Dia(
        indice=6, nombre="sabado", formato=SHORT, tipo="desmentido",
        titulo="Lo que se dijo y lo que pasa con los papeles delante",
        turnos=(
            Turno("medidor", 0, 45, "Responde comentarios y anota las preguntas "
                  "que se repiten: son el caso siguiente",
                  "preguntas repetidas", "cazador"),
            Turno("publicador", 45, 10, "Publica el Short de la reserva",
                  "Short del dia"),
        ),
    ),
    Dia(
        indice=7, nombre="domingo", formato=SHORT, tipo="pregunta",
        titulo="La pregunta que sigue sin respuesta",
        turnos=(
            Turno("guionista", 0, 60, "Adelanta el gancho del caso siguiente: la "
                  "reserva empieza aqui", "gancho adelantado"),
            Turno("publicador", 60, 10, "Publica el Short y lanza la encuesta de "
                  "la comunidad con los dos casos candidatos",
                  "Short del dia y encuesta"),
        ),
    ),
)


def minutos_semana() -> int:
    return sum(d.minutos for d in SEMANA)


def horas_semana() -> float:
    return round(minutos_semana() / 60, 1)


def carga_por_agente() -> dict[str, int]:
    """Minutos a la semana de cada agente. Dice quien es el cuello de botella."""
    carga: dict[str, int] = {}
    for dia in SEMANA:
        for turno in dia.turnos:
            carga[turno.agente] = carga.get(turno.agente, 0) + turno.minutos
    return dict(sorted(carga.items(), key=lambda kv: -kv[1]))


def cuello_de_botella() -> tuple[str, int]:
    carga = carga_por_agente()
    clave = next(iter(carga))
    return clave, carga[clave]


def publicaciones() -> dict[str, int]:
    """Dia -> publicaciones. Una al dia, que es lo que mira la cadencia."""
    return {d.nombre: 1 for d in SEMANA}


def veredicto_cadencia() -> list:
    """La cadencia de los dos formatos por separado.

    Mezclar las horas de Short y de largo en una sola medicion daba una
    desviacion de cinco horas y un bloqueo falso: no es que la hora baile, es
    que son dos citas distintas con dos publicos distintos.
    """
    largos = [d.hora for d in SEMANA if d.formato != SHORT]
    shorts = [d.hora for d in SEMANA if d.formato == SHORT]
    return [
        cadencia(publicaciones(), largos),
        cadencia(publicaciones(), shorts),
    ]


# --- calendario ----------------------------------------------------------

DIAS_ES = ("lunes", "martes", "miercoles", "jueves", "viernes", "sabado", "domingo")


@dataclass
class Entrada:
    fecha: date
    semana: int
    dia: Dia | None
    publica: bool
    nota: str = ""

    def dia_semana_corto(self) -> str:
        return DIAS_ES[self.fecha.weekday()][:3]

    def to_dict(self) -> dict:
        return {
            "fecha": self.fecha.isoformat(),
            "dia_semana": DIAS_ES[self.fecha.weekday()],
            "semana": self.semana,
            "publica": self.publica,
            "formato": self.dia.formato if self.dia else "",
            "tipo": self.dia.tipo if self.dia else "",
            "titulo": self.dia.titulo if self.dia else "",
            "hora": self.dia.hora if self.dia else 0,
            "nota": self.nota,
        }


def calendario(desde: date, semanas: int = 4, con_reserva: bool = True) -> list[Entrada]:
    """El calendario de lanzamiento, con la semana 0 que produce y no publica.

    `desde` se mueve al lunes de su semana: la semana canonica empieza en lunes
    porque el caso se elige el lunes, y arrancar un jueves parte la unica
    investigacion de la semana en dos.
    """
    lunes = desde - timedelta(days=desde.weekday())
    entradas: list[Entrada] = []

    if con_reserva:
        for i in range(7):
            dia = SEMANA[i]
            entradas.append(Entrada(
                fecha=lunes + timedelta(days=i),
                semana=0,
                dia=None,
                publica=False,
                nota=f"Reserva: se produce «{dia.titulo}» y no se publica nada.",
            ))
        lunes += timedelta(days=7)

    for s in range(semanas):
        for i in range(7):
            entradas.append(Entrada(
                fecha=lunes + timedelta(days=7 * s + i),
                semana=s + 1,
                dia=SEMANA[i],
                publica=True,
            ))
    return entradas


def describe() -> str:
    cuello, minutos = cuello_de_botella()
    return (f"Siete publicaciones a la semana desde una investigacion: "
            f"{plural(sum(1 for d in SEMANA if d.formato != SHORT), 'largo')} y "
            f"{plural(sum(1 for d in SEMANA if d.formato == SHORT), 'Short', 'Shorts')}. "
            f"Carga de una persona: {cifra(horas_semana(), 1)} horas a la semana, "
            f"y el cuello de botella es {agente(cuello).nombre} con "
            f"{plural(minutos, 'minuto')}.")
