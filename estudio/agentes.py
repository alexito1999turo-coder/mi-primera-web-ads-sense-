"""La clase que faltaba: quien se encarga de que, y con que derecho dice no.

Un canal diario no se cae por falta de ideas. Se cae porque una sola persona
hace once oficios a la vez sin saber en cual esta, y el oficio que se come las
horas es siempre el que no tiene entregable propio. El movimiento de todo el
modulo es el mismo que el del resto del repositorio: convertir una intencion
en un objeto con entrada, salida y una compuerta que puede bloquear.

Lo importante no es el reparto de tareas, que es facil. Es que **cada agente
posee una compuerta**, y por tanto tiene permiso explicito para parar la
produccion del dia. Un plan de publicacion diaria sin ningun punto que pueda
decir "esto no sale hoy" es exactamente el patron que la politica de contenido
no autentico de YouTube castiga desde el 15-07-2025: publicar porque toca.

Siete de las diez compuertas se comprueban con codigo (`compuertas.py`). Tres
no: saturacion del caso, difamacion y licencias de archivo. Esas se declaran
como revision humana y se cuentan en minutos, en vez de fingir que un `grep`
sabe de derecho al honor.
"""

from __future__ import annotations

from dataclasses import dataclass

# Tipos de publicacion. El tipo manda sobre la duracion y sobre la compuerta
# de variacion: dos Shorts del mismo tipo seguidos son la plantilla que la
# politica de contenido repetitivo busca.
LARGO = "documental"
EXPEDIENTE = "expediente"
SHORT = "short"


@dataclass(frozen=True)
class Agente:
    """Un oficio del estudio.

    `compuertas` son las que posee: las que puede invocar para bloquear. Que
    un agente no tenga ninguna no es una rebaja, es una decision — el medidor
    no bloquea nada, mide, y si pudiera bloquear acabaria siendo el que decide
    el contenido por correlacion.
    """

    clave: str
    nombre: str
    rol: str
    responsable_de: str
    entradas: tuple[str, ...]
    salidas: tuple[str, ...]
    compuertas: tuple[str, ...] = ()
    # Para los munequitos: que figura dibuja la interfaz y de que color.
    figura: str = "persona"
    color: str = "#8a8f98"

    @property
    def puede_bloquear(self) -> bool:
        return bool(self.compuertas)

    def to_dict(self) -> dict:
        return {
            "clave": self.clave,
            "nombre": self.nombre,
            "rol": self.rol,
            "responsable_de": self.responsable_de,
            "entradas": list(self.entradas),
            "salidas": list(self.salidas),
            "compuertas": list(self.compuertas),
            "figura": self.figura,
            "color": self.color,
            "puede_bloquear": self.puede_bloquear,
        }


# El orden es el de la cadena de produccion, no el de importancia: la pagina
# dibuja la sala en este orden y los relevos van de arriba a abajo.
PLANTILLA: tuple[Agente, ...] = (
    Agente(
        clave="cazador",
        nombre="Cazador",
        rol="Elige el caso de la semana",
        responsable_de=(
            "Un caso con registro publico, con documento que se pueda ensenar "
            "en pantalla y con un angulo que no esten contando ya cincuenta "
            "canales."
        ),
        entradas=("lista de casos candidatos", "lectura del medidor de la semana anterior"),
        salidas=("caso elegido", "angulo en una frase", "razon del descarte de los otros"),
        compuertas=("saturacion",),
        figura="lupa",
        color="#d32f2f",
    ),
    Agente(
        clave="archivero",
        nombre="Archivero",
        rol="Fuentes con procedencia y hora",
        responsable_de=(
            "Tres fuentes independientes y al menos un documento primario, "
            "cada uno con la fecha en que se consulto."
        ),
        entradas=("caso elegido",),
        salidas=("expediente de fuentes", "documentos para pantalla"),
        compuertas=("fuentes",),
        figura="archivo",
        color="#b8860b",
    ),
    Agente(
        clave="contable",
        nombre="Contable forense",
        rol="Fabrica el dato propio",
        responsable_de=(
            "La cifra que no existe en ningun otro sitio porque nadie la "
            "habia agregado: la mediana, el reparto, el total por victima."
        ),
        entradas=("expediente de fuentes",),
        salidas=("cifra propia con metodo", "grafico de una sola idea"),
        compuertas=("dato_propio",),
        figura="calculadora",
        color="#2e7d32",
    ),
    Agente(
        clave="abogado",
        nombre="Abogado de la casa",
        rol="Personas vivas y politica de plataforma",
        responsable_de=(
            "Que cada afirmacion sobre alguien con nombre y apellidos tenga "
            "detras un hecho de registro publico, y que la narracion no de "
            "consejo financiero ni legal con una voz que no es de nadie."
        ),
        entradas=("guion", "expediente de fuentes"),
        salidas=("guion con atribucion", "lista de frases reescritas"),
        compuertas=("difamacion", "politica_ia"),
        figura="balanza",
        color="#5e35b1",
    ),
    Agente(
        clave="guionista",
        nombre="Guionista",
        rol="El documental y los treinta segundos",
        responsable_de=(
            "Un gancho que abre con una cifra medida, una persona con algo en "
            "juego y una pregunta sin responder. Nunca con «bienvenidos al canal»."
        ),
        entradas=("caso elegido", "cifra propia con metodo", "expediente de fuentes"),
        salidas=("guion del documental", "cinco gancho de Short"),
        compuertas=("gancho",),
        figura="pluma",
        color="#1565c0",
    ),
    Agente(
        clave="voz",
        nombre="Voz",
        rol="Narracion y su declaracion",
        responsable_de=(
            "Si la voz es sintetica, se declara en el ajuste de contenido "
            "alterado y se dice en la descripcion. Declararlo no baja el alcance; "
            "ocultarlo es lo que cuesta el canal."
        ),
        entradas=("guion con atribucion",),
        salidas=("pista de narracion", "declaracion de contenido alterado"),
        compuertas=("declaracion",),
        figura="microfono",
        color="#00838f",
    ),
    Agente(
        clave="montador",
        nombre="Montador",
        rol="Montaje y archivo con licencia",
        responsable_de=(
            "Que cada plano de archivo tenga una linea de licencia con su "
            "origen, y que el documento se vea en pantalla el tiempo que se "
            "tarda en leerlo."
        ),
        entradas=("pista de narracion", "documentos para pantalla"),
        salidas=("documental montado", "registro de licencias"),
        compuertas=("licencias",),
        figura="tijeras",
        color="#ef6c00",
    ),
    Agente(
        clave="troceador",
        nombre="Troceador",
        rol="Los Shorts, uno de cada tipo",
        responsable_de=(
            "Que los cinco Shorts de la semana no sean el mismo Short cinco "
            "veces. Tipos distintos, aperturas distintas, y la similitud "
            "medida entre guiones."
        ),
        entradas=("documental montado", "cinco gancho de Short"),
        salidas=("cinco Shorts verticales",),
        compuertas=("variacion",),
        figura="trozos",
        color="#c2185b",
    ),
    Agente(
        clave="portadista",
        nombre="Portadista",
        rol="Miniatura, titulo y la promesa",
        responsable_de=(
            "Que lo que promete la miniatura este dentro del video. Una "
            "promesa que el video no cumple no es marketing: es cebo de "
            "interaccion, y lo paga la retencion del minuto dos."
        ),
        entradas=("documental montado", "guion con atribucion"),
        salidas=("dos miniaturas", "dos titulos"),
        compuertas=("promesa",),
        figura="marco",
        color="#6d4c41",
    ),
    Agente(
        clave="publicador",
        nombre="Publicador",
        rol="Calendario, hora fija y tope",
        responsable_de=(
            "Una publicacion al dia a la misma hora. El tope diario existe "
            "porque cinco subidas de golpe siembran peor que una al dia."
        ),
        entradas=("documental montado", "cinco Shorts verticales", "dos miniaturas"),
        salidas=("calendario de la semana", "subidas programadas"),
        compuertas=("cadencia",),
        figura="calendario",
        color="#37474f",
    ),
    Agente(
        clave="medidor",
        nombre="Medidor",
        rol="Retencion, CTR y la carrera",
        responsable_de=(
            "Los minutos vistos por publicacion, la conversion de Short a "
            "largo y los dias que quedan para la puerta de monetizacion. Lo "
            "que no se ha medido se escribe NO MEDIDO."
        ),
        entradas=("datos de YouTube Studio",),
        salidas=("lectura semanal", "caso siguiente recomendado"),
        compuertas=(),
        figura="grafico",
        color="#455a64",
    ),
)

SALA: dict[str, Agente] = {a.clave: a for a in PLANTILLA}

# Las tres que no se comprueban con codigo. Se declaran aqui para que el
# informe pueda decir cuales son de verdad automaticas, y no las cuente todas
# como si lo fueran.
COMPUERTAS_HUMANAS = ("saturacion", "difamacion", "licencias")


def agente(clave: str) -> Agente:
    try:
        return SALA[clave]
    except KeyError:
        raise KeyError(f"No hay ningun agente con la clave «{clave}».") from None


def compuertas_de_la_sala() -> dict[str, str]:
    """Compuerta -> agente que la posee. Sirve de indice y de comprobacion."""
    duenos: dict[str, str] = {}
    for a in PLANTILLA:
        for c in a.compuertas:
            if c in duenos:
                raise ValueError(
                    f"La compuerta «{c}» tiene dos duenos: {duenos[c]} y {a.clave}. "
                    "Una compuerta con dos duenos no la revisa nadie."
                )
            duenos[c] = a.clave
    return duenos
