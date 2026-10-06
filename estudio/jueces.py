"""Tres jueces, tres rubricas, un fallo. Y el fallo no lo escribe nadie a mano.

El encargo pedia pasar la estrategia por tres jueces. La forma facil de hacer
eso es escribir tres parrafos de opinion y declarar ganadora la que ya se habia
decidido antes de empezar: es un concurso amanado, y se nota porque los tres
jueces estan de acuerdo.

Aqui la nota sale de una rubrica con pesos declarados, cada juez puntua de 0 a
5 los criterios de SU oficio, y el ganador es aritmetica. Dos consecuencias que
no se podian pactar de antemano:

1. **El juez de riesgo tiene veto.** Por debajo de 2,5 sobre 5 una estrategia
   queda fuera aunque gane las otras dos rubricas. Es la misma regla que el
   resto del repositorio: una compuerta bloquea, no avisa.
2. **Los jueces no se ponen de acuerdo.** La mayoria (dos de tres) prefiere la
   estrategia prudente; el agregado prefiere la compuesta. Eso no es un fallo
   del metodo, es el resultado, y el fallo lo dice en vez de esconderlo.

Y las enmiendas tampoco se escriben a mano: cada criterio lleva colgada la
enmienda que se activa si la ganadora saca menos de 3 sobre 5 en el. Asi la
estrategia que sale no es la que mas gusta, es la que gana con las condiciones
de quien la ha puntuado peor.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from textos import cifra, lista, plural

NOTA_MAX = 5
UMBRAL_ENMIENDA = 3.0


@dataclass(frozen=True)
class Criterio:
    clave: str
    pregunta: str
    peso: float
    enmienda: str


@dataclass(frozen=True)
class Juez:
    clave: str
    nombre: str
    oficio: str
    mira: str
    criterios: tuple[Criterio, ...]
    veto_por_debajo_de: float = 0.0

    def __post_init__(self) -> None:
        suma = round(sum(c.peso for c in self.criterios), 6)
        if suma != 1.0:
            raise ValueError(
                f"Los pesos de {self.clave} suman {suma} y no 1,0. Una rubrica "
                "cuyos pesos no suman uno no compara nada."
            )

    def criterio(self, clave: str) -> Criterio:
        for c in self.criterios:
            if c.clave == clave:
                return c
        raise KeyError(f"{self.clave} no tiene el criterio «{clave}».")


@dataclass(frozen=True)
class Estrategia:
    clave: str
    nombre: str
    resumen: str
    cadencia: str
    # criterio -> (nota 0-5, por que)
    notas: dict[str, tuple[int, str]]
    # Lo que tiene que seguir siendo verdad para que la nota valga.
    condiciones: tuple[str, ...] = ()


JUEZ_ALGORITMO = Juez(
    clave="algoritmo",
    nombre="Juez 1",
    oficio="Crecimiento y algoritmo",
    mira="Si el sistema produce minutos vistos y si la plataforma puede sembrarlo.",
    criterios=(
        Criterio("minutos_por_publicacion",
                 "Cuantos minutos vistos deja cada pieza que se publica",
                 0.30,
                 "Subir la duracion objetivo del documental o la retencion antes "
                 "de subir la frecuencia: la puerta se mide en minutos, no en subidas."),
        Criterio("siembra_en_frio",
                 "Cadencia estable y a la misma hora, sin rafagas",
                 0.20,
                 "Una sola publicacion al dia, hora fija por formato y nada de "
                 "subir tres de golpe el domingo."),
        Criterio("embudo_short_a_largo",
                 "El Short devuelve vistas al largo, y se mide",
                 0.25,
                 "Cada Short cierra nombrando el titulo del largo, y la "
                 "conversion se anota cada semana o el embudo es una creencia."),
        Criterio("palanca_de_ctr",
                 "Hay con que mover el CTR cuando no llega",
                 0.15,
                 "Dos miniaturas y dos titulos por largo, y cambio a las 48 horas "
                 "si el CTR no pasa del 4%."),
        Criterio("tiempo_hasta_la_puerta",
                 "Llega a los requisitos de monetizacion antes de que suban",
                 0.10,
                 "Si no se llega al 01-02-2027, decirlo y planificar para la "
                 "puerta nueva: el doble de minutos, no el mismo plan con prisa."),
    ),
)

JUEZ_RIESGO = Juez(
    clave="riesgo",
    nombre="Juez 2",
    oficio="Riesgo, politica y derecho",
    mira="Que es lo que puede cerrar el canal, y si el plan lo toca todos los dias.",
    veto_por_debajo_de=2.5,
    criterios=(
        Criterio("contenido_no_autentico",
                 "Exposicion a la politica de contenido producido en masa o repetitivo",
                 0.30,
                 "Compuerta de variacion obligatoria entre las piezas de la "
                 "semana: similitud medida y ningun par de angulos iguales seguidos."),
        Criterio("personas_vivas",
                 "Que se afirma de alguien con nombre y apellidos",
                 0.25,
                 "Nombre solo con sentencia, acta o expediente publico delante. "
                 "Sin eso, iniciales y cargo."),
        Criterio("licencias_de_archivo",
                 "De donde sale cada plano y con que permiso",
                 0.15,
                 "Registro de licencias por plano, o el montaje no se cierra."),
        Criterio("persona_ia_en_temas_limitados",
                 "Voz o persona sintetica tratando finanzas, salud, legal o medico",
                 0.20,
                 "Autor humano identificado en pantalla y en la descripcion, con "
                 "analisis propio, o narracion con voz propia."),
        Criterio("reversibilidad",
                 "Que queda si manana llega un aviso de la plataforma",
                 0.10,
                 "Copia del catalogo fuera de la plataforma y una lista de correo "
                 "propia desde el primer video."),
    ),
)

JUEZ_OPERACION = Juez(
    clave="operacion",
    nombre="Juez 3",
    oficio="Operacion y economia",
    mira="Si esto lo puede hacer una persona doce semanas seguidas sin dejar de comer.",
    criterios=(
        Criterio("horas_de_una_persona",
                 "Horas a la semana que pide de una sola persona",
                 0.30,
                 "Colchon de una semana de reserva antes de publicar el primer "
                 "video, y un modo minimo de tres publicaciones para la semana mala."),
        Criterio("coste_por_mil_minutos_vistos",
                 "Lo que cuesta producir mil minutos de atencion",
                 0.25,
                 "Bajar el coste por pieza antes de subir el volumen: el volumen "
                 "multiplica el coste y no la retencion."),
        Criterio("sostenibilidad_doce_semanas",
                 "Aguanta tres meses sin que el operador se queme",
                 0.20,
                 "Un dia de produccion en lote y un dia a la semana sin estudio, "
                 "en el calendario y no en la intencion."),
        Criterio("ingresos_no_publicitarios",
                 "Hay ingreso que no dependa del RPM de la plataforma",
                 0.15,
                 "Abrir la via de pago directo antes de cruzar la puerta: el RPM "
                 "de Shorts no paga un canal ni cuando funciona."),
        Criterio("coste_de_herramientas",
                 "Lo que se paga al mes antes del primer euro de ingreso",
                 0.10,
                 "Pila gratuita primero y se paga solo la herramienta que quita "
                 "horas medidas, no la que promete calidad."),
    ),
)

JUECES: tuple[Juez, ...] = (JUEZ_ALGORITMO, JUEZ_RIESGO, JUEZ_OPERACION)


# --- las tres candidatas -------------------------------------------------

FABRICA = Estrategia(
    clave="fabrica",
    nombre="A · La fabrica",
    resumen=(
        "Volumen y automatizacion: tres o cuatro Shorts al dia generados con "
        "plantilla, voz sintetica y un largo semanal ensamblado de los Shorts. "
        "Es la estrategia que vende el 90% de los tutoriales de canal sin rostro."
    ),
    cadencia="21-28 publicaciones a la semana, casi todas Shorts",
    notas={
        "minutos_por_publicacion": (1, "Un Short de 40 segundos con 60% de "
            "retencion deja 24 segundos vistos. Para las 4.000 horas hacen falta "
            "diez millones de vistas: la ruta mas cara que existe."),
        "siembra_en_frio": (4, "La cadencia diaria es lo unico que esta "
            "estrategia hace bien, y de verdad mejora la siembra en frio."),
        "embudo_short_a_largo": (2, "El largo es un refrito de los Shorts, asi "
            "que quien vio los Shorts no tiene nada que ir a ver."),
        "palanca_de_ctr": (3, "Hay miniaturas de sobra para probar, pero el "
            "catalogo es intercambiable y el CTR no depende de la portada."),
        "tiempo_hasta_la_puerta": (2, "Por la ruta de Shorts hacen falta diez "
            "millones de vistas en 90 dias. Es alcanzable y es improbable."),
        "contenido_no_autentico": (1, "Plantilla repetida varias veces al dia "
            "con poca variacion discernible: es la descripcion literal de lo que "
            "la politica del 15-07-2025 persigue."),
        "personas_vivas": (2, "El volumen no deja pasar cada afirmacion por "
            "registro publico. Un canal de fraudes acusa a gente con nombre."),
        "licencias_de_archivo": (2, "Archivo de stock y de terceros a destajo, "
            "sin registro por plano."),
        "persona_ia_en_temas_limitados": (1, "Voz sintetica hablando de dinero "
            "ajeno sin autor humano identificable: la combinacion limitada."),
        "reversibilidad": (2, "Si cae la monetizacion no queda nada: ni lista "
            "propia, ni catalogo que se pueda defender pieza a pieza."),
        "horas_de_una_persona": (4, "Es su unica ventaja real: la mayor parte "
            "del trabajo lo hace la plantilla."),
        "coste_por_mil_minutos_vistos": (2, "Barato por pieza y carisimo por "
            "minuto visto, que es la unidad que importa."),
        "sostenibilidad_doce_semanas": (3, "Se sostiene mientras no haya aviso; "
            "el riesgo no es cansancio, es terminacion."),
        "ingresos_no_publicitarios": (1, "Nada que vender: no hay autoridad que "
            "sostenga un pago directo."),
        "coste_de_herramientas": (2, "Generacion y voz de pago desde el primer "
            "mes, antes del primer euro de ingreso."),
    },
)

DOSSIER = Estrategia(
    clave="dossier",
    nombre="B · El dossier",
    resumen=(
        "Profundidad: un unico documental de 25 a 35 minutos a la semana, con "
        "documento primario en pantalla, dato propio y nada mas. Sin Shorts, sin "
        "publicacion diaria."
    ),
    cadencia="1 publicacion a la semana",
    notas={
        "minutos_por_publicacion": (5, "Treinta minutos al 45% dejan 13,5 "
            "minutos vistos por vista: la ruta mas corta a la puerta."),
        "siembra_en_frio": (2, "Una cita a la semana es poca superficie para que "
            "la plataforma aprenda a quien ensenartelo."),
        "embudo_short_a_largo": (1, "No hay embudo. Todo depende de que la "
            "plataforma encuentre el largo por su cuenta."),
        "palanca_de_ctr": (3, "Cuatro portadas al mes para aprender que funciona "
            "es aprender despacio."),
        "tiempo_hasta_la_puerta": (3, "Pocas vistas necesarias, pero tambien "
            "pocas puertas de entrada al canal."),
        "contenido_no_autentico": (5, "Imposible confundirlo con produccion en "
            "masa: una pieza, una investigacion."),
        "personas_vivas": (4, "El tiempo por pieza permite pasar cada nombre por "
            "registro publico."),
        "licencias_de_archivo": (4, "Pocos planos y revisables uno a uno."),
        "persona_ia_en_temas_limitados": (4, "Hay sitio para firmar la autoria y "
            "poner analisis propio."),
        "reversibilidad": (5, "Un catalogo de piezas defendibles una por una es "
            "lo que mejor sobrevive a una revision."),
        "horas_de_una_persona": (3, "Doce o catorce horas, pero concentradas en "
            "dos dias: menos horas y peor repartidas."),
        "coste_por_mil_minutos_vistos": (4, "El coste se reparte entre muchos "
            "minutos vistos."),
        "sostenibilidad_doce_semanas": (4, "Doce semanas son doce piezas: se "
            "aguanta."),
        "ingresos_no_publicitarios": (3, "La autoridad que construye se puede "
            "cobrar, pero tarda en llegar publico."),
        "coste_de_herramientas": (4, "Montaje y archivo. Nada mas."),
    },
    condiciones=(
        "La nota de riesgo depende de que el ritmo siga siendo uno a la semana: "
        "si se acelera sin compuertas, cae a la de la fabrica.",
    ),
)

CATALOGO = Estrategia(
    clave="catalogo",
    nombre="C · El catalogo compuesto",
    resumen=(
        "Una investigacion a la semana, siete publicaciones de ella: el "
        "documental del viernes, el expediente del martes y cinco Shorts de "
        "cinco angulos distintos, con compuerta de variacion entre ellos y una "
        "semana de reserva por delante."
    ),
    cadencia="7 publicaciones a la semana, una al dia",
    notas={
        "minutos_por_publicacion": (4, "Los dos largos cargan los minutos; los "
            "Shorts no restan porque no sustituyen a nadie."),
        "siembra_en_frio": (5, "Una al dia, a la misma hora por formato, con el "
            "tope de dos para que no haya rafagas."),
        "embudo_short_a_largo": (5, "Los cinco Shorts son cinco entradas al mismo "
            "largo, cada una por un angulo distinto, y la conversion se mide."),
        "palanca_de_ctr": (4, "Dos portadas por largo y cinco titulos a la semana "
            "de los que aprender."),
        "tiempo_hasta_la_puerta": (5, "Dos largos a la semana por la ruta de "
            "horas: 412 veces menos vistas que por la de Shorts."),
        "contenido_no_autentico": (4, "Siete piezas al dia de la misma "
            "investigacion es el patron de riesgo, y por eso la variacion aqui es "
            "una compuerta que bloquea y no un consejo."),
        "personas_vivas": (4, "La misma regla de registro publico que el dossier, "
            "aplicada una vez por investigacion y heredada por las siete piezas."),
        "licencias_de_archivo": (4, "El registro de licencias se hace una vez y "
            "sirve para las siete."),
        "persona_ia_en_temas_limitados": (4, "Autor humano identificado y dato "
            "propio en cada pieza, que es lo que la politica pide."),
        "reversibilidad": (4, "El catalogo se defiende pieza a pieza, pero hay "
            "mas superficie que en el dossier."),
        "horas_de_una_persona": (2, "19,1 horas a la semana calculadas turno a "
            "turno. Es un segundo trabajo, y el plan no puede fingir que no."),
        "coste_por_mil_minutos_vistos": (4, "Una investigacion paga siete piezas: "
            "es el mejor reparto de coste de las tres."),
        "sostenibilidad_doce_semanas": (2, "Doce semanas a 19 horas sin colchon "
            "no las aguanta una persona con otro trabajo."),
        "ingresos_no_publicitarios": (4, "El dato propio semanal es material que "
            "se puede cobrar aparte del canal."),
        "coste_de_herramientas": (3, "Montaje, voz y recorte: la pila mas larga "
            "de las tres, aunque se puede empezar gratis."),
    },
    condiciones=(
        "La nota de riesgo vale solo con las compuertas puestas: sin la de "
        "variacion, esta estrategia ES la fabrica con mejor guion.",
        "Lo que se publica una semana se produjo la anterior. Sin reserva, la "
        "cadencia diaria depende de que a una persona no le pase nada siete dias "
        "seguidos.",
    ),
)

CANDIDATAS: tuple[Estrategia, ...] = (FABRICA, DOSSIER, CATALOGO)


# --- puntuacion ----------------------------------------------------------


@dataclass
class Puntuacion:
    juez: str
    estrategia: str
    nota: float
    desglose: list[dict] = field(default_factory=list)
    veto: bool = False

    def to_dict(self) -> dict:
        return {
            "juez": self.juez,
            "estrategia": self.estrategia,
            "nota": self.nota,
            "veto": self.veto,
            "desglose": self.desglose,
        }


def puntuar(juez: Juez, estrategia: Estrategia) -> Puntuacion:
    desglose, total = [], 0.0
    for criterio in juez.criterios:
        if criterio.clave not in estrategia.notas:
            raise KeyError(
                f"«{estrategia.clave}» no tiene nota para «{criterio.clave}», que "
                f"{juez.clave} pondera al {criterio.peso:.0%}. Una rubrica con un "
                "hueco puntua menos a quien no se ha evaluado."
            )
        nota, porque = estrategia.notas[criterio.clave]
        if not 0 <= nota <= NOTA_MAX:
            raise ValueError(f"Nota fuera de rango en {criterio.clave}: {nota}.")
        total += nota * criterio.peso
        desglose.append({
            "criterio": criterio.clave,
            "pregunta": criterio.pregunta,
            "peso": criterio.peso,
            "nota": nota,
            "porque": porque,
            "enmienda": criterio.enmienda if nota < UMBRAL_ENMIENDA else "",
        })
    nota = round(total, 2)
    return Puntuacion(
        juez=juez.clave,
        estrategia=estrategia.clave,
        nota=nota,
        desglose=desglose,
        veto=bool(juez.veto_por_debajo_de) and nota < juez.veto_por_debajo_de,
    )


@dataclass
class Fallo:
    puntuaciones: list[Puntuacion]
    ganadora: Estrategia
    vetadas: list[tuple[str, str]]
    enmiendas: list[dict]
    mayoria: str
    medias: dict[str, float]

    @property
    def hubo_discrepancia(self) -> bool:
        return self.mayoria != self.ganadora.clave

    def nota(self, juez: str, estrategia: str) -> float:
        for p in self.puntuaciones:
            if p.juez == juez and p.estrategia == estrategia:
                return p.nota
        raise KeyError(f"No hay nota de {juez} para {estrategia}.")

    def describe(self) -> str:
        lineas = [
            f"Gana {self.ganadora.nombre} con "
            f"{cifra(self.medias[self.ganadora.clave], 2)} sobre {NOTA_MAX}."
        ]
        if self.vetadas:
            veto = lista([f"{c} ({motivo})" for c, motivo in self.vetadas])
            lineas.append(f"Vetada por el juez de riesgo: {veto}.")
        if self.hubo_discrepancia:
            lineas.append(
                f"Dos de los tres jueces preferian «{self.mayoria}»; gana la otra "
                "por agregado. La discrepancia se resuelve con enmiendas, no "
                "ignorandola."
            )
        if self.enmiendas:
            lineas.append(
                f"{plural(len(self.enmiendas), 'enmienda obligatoria', 'enmiendas obligatorias')} "
                "sobre la ganadora, de quien la ha puntuado peor."
            )
        return " ".join(lineas)

    def to_dict(self) -> dict:
        return {
            "ganadora": self.ganadora.clave,
            "nombre": self.ganadora.nombre,
            "medias": self.medias,
            "vetadas": [{"estrategia": c, "motivo": m} for c, m in self.vetadas],
            "enmiendas": self.enmiendas,
            "mayoria": self.mayoria,
            "discrepancia": self.hubo_discrepancia,
            "condiciones": list(self.ganadora.condiciones),
            "resumen": self.describe(),
            "puntuaciones": [p.to_dict() for p in self.puntuaciones],
        }


def fallo(candidatas: tuple[Estrategia, ...] = CANDIDATAS,
          jueces: tuple[Juez, ...] = JUECES) -> Fallo:
    puntuaciones = [puntuar(j, e) for e in candidatas for j in jueces]

    medias = {
        e.clave: round(
            sum(p.nota for p in puntuaciones if p.estrategia == e.clave) / len(jueces), 2
        )
        for e in candidatas
    }

    vetadas: list[tuple[str, str]] = []
    for e in candidatas:
        for p in puntuaciones:
            if p.estrategia == e.clave and p.veto:
                juez = next(j for j in jueces if j.clave == p.juez)
                vetadas.append((
                    e.nombre,
                    f"{cifra(p.nota, 2)} en {juez.oficio.lower()}, por debajo de "
                    f"{cifra(juez.veto_por_debajo_de, 1)}",
                ))

    claves_vetadas = {nombre for nombre, _ in vetadas}
    elegibles = [e for e in candidatas if e.nombre not in claves_vetadas]
    if not elegibles:
        raise ValueError("Las tres candidatas estan vetadas: no hay fallo posible.")
    ganadora = max(elegibles, key=lambda e: medias[e.clave])

    # Mayoria: cuantas rubricas gana cada candidata, contando solo elegibles.
    victorias: dict[str, int] = {e.clave: 0 for e in elegibles}
    for juez in jueces:
        notas = {e.clave: next(p.nota for p in puntuaciones
                               if p.juez == juez.clave and p.estrategia == e.clave)
                 for e in elegibles}
        victorias[max(notas, key=lambda k: notas[k])] += 1
    mayoria = max(victorias, key=lambda k: (victorias[k], medias[k]))

    enmiendas = []
    for juez in jueces:
        punto = next(p for p in puntuaciones
                     if p.juez == juez.clave and p.estrategia == ganadora.clave)
        for fila in punto.desglose:
            if fila["enmienda"]:
                enmiendas.append({
                    "juez": juez.nombre,
                    "oficio": juez.oficio,
                    "criterio": fila["criterio"],
                    "nota": fila["nota"],
                    "porque": fila["porque"],
                    "enmienda": fila["enmienda"],
                })

    return Fallo(puntuaciones=puntuaciones, ganadora=ganadora, vetadas=vetadas,
                 enmiendas=enmiendas, mayoria=mayoria, medias=medias)


def tabla() -> list[dict]:
    """Fila por estrategia, columna por juez. Lo que dibuja la pagina."""
    f = fallo()
    filas = []
    for e in CANDIDATAS:
        fila = {"estrategia": e.clave, "nombre": e.nombre, "cadencia": e.cadencia,
                "resumen": e.resumen, "media": f.medias[e.clave],
                "vetada": any(e.nombre == n for n, _ in f.vetadas),
                "ganadora": e.clave == f.ganadora.clave}
        for juez in JUECES:
            fila[juez.clave] = f.nota(juez.clave, e.clave)
        filas.append(fila)
    return filas
