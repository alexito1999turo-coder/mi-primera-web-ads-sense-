"""Las compuertas del estudio: lo que impide que salga algo porque toca.

La diferencia entre un canal diario y una granja de contenido no esta en el
numero de subidas, esta en si existe algun punto del dia que pueda decir no.
Por eso el plan de publicacion diaria se implementa como compuertas y no como
calendario: el calendario solo dice cuando, y la politica de contenido no
autentico de YouTube —actualizada el 15-07-2025 para alcanzar lo
«producido en masa o repetitivo»— castiga precisamente publicar sin variacion
discernible.

Que comprueban y que no. Una compuerta comprueba **la forma**: que haya tres
fuentes, que la cifra no sea redonda, que dos Shorts no compartan el texto,
que la miniatura prometa algo que esta dentro del video. La **verdad** del dato
la pone una persona, y eso no se automatiza: `difamacion`, `licencias` y
`saturacion` dan su veredicto sobre datos que ha escrito un humano, asi que el
parte las marca como revision humana en vez de contarlas como automaticas.
Contar once compuertas automaticas cuando ocho lo son seria el mismo folleto
que el modulo de calibracion existe para desmontar.

Se reutiliza lo que ya hay: `citability.signals.is_precise` para distinguir
cifra medida de cifra de consenso, y `compliance.fingerprint.shingles` para la
similitud entre guiones. Son el mismo problema que en texto escrito.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from citability.signals import is_precise
from compliance.fingerprint import shingles
from textos import cifra, lista, plural

from .agentes import COMPUERTAS_HUMANAS, compuertas_de_la_sala

# --- umbrales ------------------------------------------------------------

MIN_FUENTES_INDEPENDIENTES = 3
MIN_DOCUMENTOS_PRIMARIOS = 1

# Mas flojo que el 0,08 de cartera de `compliance/fingerprint.py`, y a
# proposito: alli se comparan sitios de clientes distintos, donde la similitud
# legitima es casi nula. Aqui cinco Shorts hablan del MISMO caso y comparten
# nombres y cifras por necesidad. Lo que no pueden compartir es el texto.
MAX_SIMILITUD_ENTRE_PIEZAS = 0.15

# Treinta segundos de narracion en castellano son 75-90 palabras. Un gancho de
# 140 palabras no es un gancho, es el primer capitulo.
GANCHO_MAX_PALABRAS = 90

# Dos subidas al dia es el techo. No es una regla de la plataforma: es que la
# siembra en frio de cinco subidas de golpe se reparte entre cinco, y la
# segunda del dia ya canibaliza a la primera.
MAX_SUBIDAS_DIA = 2
MAX_DESVIACION_HORA = 30

# YouTube limita los canales que usan personas generadas por IA para tratar
# salud, finanzas, asuntos legales y medicos. Un canal de fraudes vive en
# «finanzas» por definicion, asi que esta compuerta no es teorica.
TEMAS_SENSIBLES = frozenset({"finanzas", "salud", "legal", "medico"})

APERTURAS_PROHIBIDAS = re.compile(
    r"\b(bienvenid[oa]s?\s+(a|al)\b|hola\s+a\s+todos|en\s+el\s+video\s+de\s+hoy|"
    r"antes\s+de\s+empezar|no\s+olvides\s+suscribirte|suscr[ií]bete\s+y)",
    re.I,
)

PALABRAS = re.compile(r"[0-9A-Za-zÁÉÍÓÚÜÑáéíóúüñ]+")
VACIAS = frozenset(
    "el la los las un una unos unas de del al a y o que en por para con sin "
    "sobre su sus se lo le les es son fue fueron ser mas mas muy ya no si "
    "como cuando donde quien cual este esta esto ese esa eso aquel".split()
)


# --- veredictos ----------------------------------------------------------


@dataclass
class Veredicto:
    compuerta: str
    pasa: bool
    motivo: str
    bloqueante: bool = True

    @property
    def revision_humana(self) -> bool:
        """El veredicto es automatico; el dato de entrada lo pone una persona."""
        return self.compuerta in COMPUERTAS_HUMANAS

    @property
    def dueno(self) -> str:
        return compuertas_de_la_sala()[self.compuerta]

    def to_dict(self) -> dict:
        return {
            "compuerta": self.compuerta,
            "pasa": self.pasa,
            "motivo": self.motivo,
            "bloqueante": self.bloqueante,
            "revision_humana": self.revision_humana,
            "dueno": self.dueno,
        }


def _ok(compuerta: str, motivo: str) -> Veredicto:
    return Veredicto(compuerta=compuerta, pasa=True, motivo=motivo)


def _no(compuerta: str, motivo: str, bloqueante: bool = True) -> Veredicto:
    return Veredicto(compuerta=compuerta, pasa=False, motivo=motivo,
                     bloqueante=bloqueante)


# --- entradas ------------------------------------------------------------


@dataclass
class Fuente:
    dominio: str
    titulo: str
    primaria: bool = False
    consultada: str = ""


@dataclass
class Persona:
    nombre: str
    viva: bool = True
    # Referencia de registro publico: sentencia, acta, expediente, boletin.
    registro: str = ""


@dataclass
class Plano:
    descripcion: str
    licencia: str = ""


@dataclass
class Pieza:
    """Una publicacion con todo lo que hace falta para juzgarla."""

    clave: str
    # `formato` es documental, expediente o short: manda sobre la duracion.
    # `tipo` es el angulo —cifra, documento, cronologia, desmentido,
    # pregunta—, y es lo que mira la compuerta de variacion: cinco Shorts son
    # cinco formatos iguales y tienen que ser cinco angulos distintos.
    formato: str
    tipo: str
    titulo: str
    guion: str
    gancho: str = ""
    duracion_min: float = 0.0
    fuentes: list[Fuente] = field(default_factory=list)
    personas: list[Persona] = field(default_factory=list)
    planos: list[Plano] = field(default_factory=list)
    dato_propio: str = ""
    metodo: str = ""
    n_muestra: int = 0
    temas: tuple[str, ...] = ()
    voz_sintetica: bool = False
    voz_declarada: bool = False
    autor_humano_visible: bool = False
    canales_que_lo_cuentan: int = 0
    angulo_propio: str = ""


# --- compuertas ----------------------------------------------------------


def fuentes(pieza: Pieza) -> Veredicto:
    dominios = {f.dominio.lower().strip() for f in pieza.fuentes if f.dominio.strip()}
    primarias = [f for f in pieza.fuentes if f.primaria]
    sin_fecha = [f.dominio for f in pieza.fuentes if not f.consultada.strip()]

    if len(dominios) < MIN_FUENTES_INDEPENDIENTES:
        return _no("fuentes", f"{plural(len(dominios), 'dominio independiente', 'dominios independientes')}: "
                              f"hacen falta {MIN_FUENTES_INDEPENDIENTES}.")
    if len(primarias) < MIN_DOCUMENTOS_PRIMARIOS:
        return _no("fuentes", "Ningun documento primario. Tres periodicos "
                              "contando lo mismo son una fuente, no tres.")
    if sin_fecha:
        return _no("fuentes", f"Sin fecha de consulta: {lista(sorted(set(sin_fecha)))}.")
    return _ok("fuentes", f"{plural(len(dominios), 'dominio independiente', 'dominios independientes')} y "
                          f"{plural(len(primarias), 'documento primario', 'documentos primarios')}, "
                          "con fecha de consulta.")


def dato_propio(pieza: Pieza) -> Veredicto:
    if not pieza.dato_propio.strip():
        return _no("dato_propio", "No hay cifra propia. Sin ella el video es un "
                                  "resumen de lo que ya hay en los otros.")
    if not pieza.metodo.strip():
        return _no("dato_propio", "La cifra no lleva metodo. Un numero sin «de "
                                  "donde sale» no es un dato, es una afirmacion.")
    if pieza.n_muestra < 5:
        return _no("dato_propio", f"Muestra de {cifra(pieza.n_muestra)}: por debajo "
                                  "de cinco casos la mediana no agrega nada.")
    if not is_precise(pieza.dato_propio):
        return _no("dato_propio", "La cifra es redonda o va con aproximador. Un "
                                  "numero redondo es consenso; uno preciso es una "
                                  "medicion, y es lo unico que solo puedes tener tu.")
    return _ok("dato_propio", f"Cifra medida sobre {plural(pieza.n_muestra, 'caso')}, "
                              "con metodo.")


def gancho(pieza: Pieza) -> Veredicto:
    texto = pieza.gancho.strip() or pieza.guion[:600]
    if not texto:
        return _no("gancho", "No hay gancho escrito.")

    palabras = PALABRAS.findall(texto)
    if len(palabras) > GANCHO_MAX_PALABRAS:
        return _no("gancho", f"{plural(len(palabras), 'palabra')} de gancho: por "
                             f"encima de {GANCHO_MAX_PALABRAS} ya no entra en los "
                             "treinta segundos.")
    if APERTURAS_PROHIBIDAS.search(texto):
        return _no("gancho", "Abre con presentacion o con peticion de suscripcion. "
                             "Los treinta primeros segundos no se gastan en el canal.")
    faltan = []
    if not is_precise(texto):
        faltan.append("una cifra medida")
    if not pieza.personas:
        faltan.append("alguien con algo en juego")
    if "?" not in texto:
        faltan.append("una pregunta sin responder")
    if faltan:
        return _no("gancho", f"Al gancho le falta {lista(faltan)}.")
    return _ok("gancho", f"{plural(len(palabras), 'palabra')}, con cifra, persona y "
                         "pregunta abierta.")


def declaracion(pieza: Pieza) -> Veredicto:
    if not pieza.voz_sintetica:
        return _ok("declaracion", "Voz propia: no hay nada que declarar.")
    if not pieza.voz_declarada:
        return _no("declaracion", "Voz sintetica sin declarar. Declararla no baja "
                                  "el alcance ni la monetizacion; ocultarla es lo "
                                  "que cuesta el canal.")
    return _ok("declaracion", "Voz sintetica declarada en el ajuste de contenido "
                              "alterado y en la descripcion.")


def politica_ia(pieza: Pieza) -> Veredicto:
    sensibles = sorted(set(pieza.temas) & TEMAS_SENSIBLES)
    if not sensibles:
        return _ok("politica_ia", "Ningun tema de la lista limitada.")
    if not pieza.voz_sintetica:
        return _ok("politica_ia", f"Toca {lista(sensibles)}, pero con voz propia "
                                  "y autoria identificable.")
    if pieza.autor_humano_visible and pieza.dato_propio.strip():
        return _ok("politica_ia", f"Toca {lista(sensibles)} con voz sintetica, pero "
                                  "hay autor humano identificado y analisis propio.")
    return _no("politica_ia", f"Persona sintetica tratando {lista(sensibles)}: es la "
                              "combinacion que YouTube limita. Hace falta autor "
                              "humano identificado y dato propio, o voz propia.")


def promesa(pieza: Pieza) -> Veredicto:
    titulo = [w.lower() for w in PALABRAS.findall(pieza.titulo)]
    utiles = [w for w in titulo if w not in VACIAS and len(w) > 2]
    if not utiles:
        return _no("promesa", "El titulo no promete nada comprobable.")
    cuerpo = {w.lower() for w in PALABRAS.findall(pieza.guion)}
    huerfanas = [w for w in utiles if w not in cuerpo]
    cubierto = 1 - len(huerfanas) / len(utiles)
    if cubierto < 0.7:
        return _no("promesa", f"El guion no toca {lista(huerfanas)}. Una promesa que "
                              "el video no cumple es cebo de interaccion, y lo paga "
                              "la retencion del minuto dos.")
    return _ok("promesa", f"El guion cubre {cifra(cubierto * 100)}% de lo que promete "
                          "el titulo.")


def difamacion(pieza: Pieza) -> Veredicto:
    sin_registro = [p.nombre for p in pieza.personas if p.viva and not p.registro.strip()]
    if sin_registro:
        return _no("difamacion", f"Sin referencia de registro publico: "
                                 f"{lista(sin_registro)}. O sentencia, acta o "
                                 "expediente, o el nombre no se dice.")
    return _ok("difamacion", f"{plural(len(pieza.personas), 'persona')} con nombre, "
                             "cada una con su referencia publica.")


def licencias(pieza: Pieza) -> Veredicto:
    sin_licencia = [p.descripcion for p in pieza.planos if not p.licencia.strip()]
    if sin_licencia:
        return _no("licencias", f"{plural(len(sin_licencia), 'plano')} de archivo sin "
                                "linea de licencia.")
    return _ok("licencias", f"{plural(len(pieza.planos), 'plano')} de archivo, cada uno "
                            "con su origen anotado.")


def saturacion(pieza: Pieza) -> Veredicto:
    if pieza.canales_que_lo_cuentan >= 20 and not pieza.angulo_propio.strip():
        return _no("saturacion", f"{plural(pieza.canales_que_lo_cuentan, 'canal', 'canales')} "
                                 "cuentan ya este caso y no hay angulo propio escrito.")
    if pieza.canales_que_lo_cuentan >= 50 and not pieza.dato_propio.strip():
        return _no("saturacion", "Caso saturado y sin cifra propia: el video seria el "
                                 "numero cincuenta y uno.")
    return _ok("saturacion", f"{plural(pieza.canales_que_lo_cuentan, 'canal', 'canales')} "
                             "lo cuentan; hay angulo propio.")


def variacion(piezas: list[Pieza]) -> Veredicto:
    """La compuerta contra la plantilla, medida entre las piezas de la semana."""
    if len(piezas) < 2:
        return _ok("variacion", "Una sola pieza: no hay con que compararla.")

    peor, par = 0.0, ("", "")
    for i, a in enumerate(piezas):
        sa = shingles(a.guion)
        for b in piezas[i + 1:]:
            sb = shingles(b.guion)
            if not sa or not sb:
                continue
            similitud = len(sa & sb) / min(len(sa), len(sb))
            if similitud > peor:
                peor, par = similitud, (a.clave, b.clave)

    seguidos = [
        (piezas[i].clave, piezas[i + 1].clave)
        for i in range(len(piezas) - 1)
        if piezas[i].tipo == piezas[i + 1].tipo
    ]
    if seguidos:
        a, b = seguidos[0]
        return _no("variacion", f"«{a}» y «{b}» son del mismo tipo y van seguidos. "
                                "Dos piezas iguales un dia detras de otro son la "
                                "plantilla que busca la politica de contenido "
                                "repetitivo.")
    if peor > MAX_SIMILITUD_ENTRE_PIEZAS:
        return _no("variacion", f"«{par[0]}» y «{par[1]}» comparten el "
                                f"{cifra(peor * 100)}% del texto, por encima del "
                                f"{cifra(MAX_SIMILITUD_ENTRE_PIEZAS * 100)}% que se "
                                "explica por hablar del mismo caso.")
    return _ok("variacion", f"Similitud maxima entre guiones {cifra(peor * 100)}%, "
                            "y ningun par de tipos seguidos.")


def cadencia(subidas: dict[str, int], horas: list[int]) -> Veredicto:
    """`subidas` es dia -> numero de publicaciones; `horas` minutos del dia."""
    if not subidas:
        return _no("cadencia", "No hay calendario.")
    vacios = [d for d, n in subidas.items() if n < 1]
    if vacios:
        return _no("cadencia", f"{plural(len(vacios), 'dia')} sin publicacion: "
                               f"{lista(sorted(vacios))}.")
    exceso = [d for d, n in subidas.items() if n > MAX_SUBIDAS_DIA]
    if exceso:
        return _no("cadencia", f"Mas de {MAX_SUBIDAS_DIA} subidas en {lista(sorted(exceso))}. "
                               "Una rafaga se siembra peor que una al dia.")
    if horas:
        desviacion = max(horas) - min(horas)
        if desviacion > MAX_DESVIACION_HORA:
            return _no("cadencia", f"La hora de subida baila {plural(desviacion, 'minuto')}; "
                                   f"el margen es {MAX_DESVIACION_HORA}.", bloqueante=False)
    return _ok("cadencia", f"{plural(len(subidas), 'dia')} con publicacion, ninguno "
                           f"por encima de {MAX_SUBIDAS_DIA}, y hora estable.")


# --- parte del dia -------------------------------------------------------

INDIVIDUALES = (fuentes, dato_propio, gancho, declaracion, politica_ia,
                promesa, difamacion, licencias, saturacion)


@dataclass
class Parte:
    """Lo que se puede publicar y lo que no, con el dueno de cada no."""

    veredictos: list[Veredicto] = field(default_factory=list)

    @property
    def bloqueantes(self) -> list[Veredicto]:
        return [v for v in self.veredictos if not v.pasa and v.bloqueante]

    @property
    def avisos(self) -> list[Veredicto]:
        return [v for v in self.veredictos if not v.pasa and not v.bloqueante]

    @property
    def pasa(self) -> bool:
        return not self.bloqueantes

    @property
    def automaticas(self) -> int:
        return sum(1 for v in self.veredictos if not v.revision_humana)

    def describe(self) -> str:
        if self.pasa:
            cola = f" {plural(len(self.avisos), 'aviso')}." if self.avisos else ""
            return (f"Sale. {plural(len(self.veredictos), 'compuerta pasada', 'compuertas pasadas')}, "
                    f"{plural(self.automaticas, 'automatica')}.{cola}")
        culpables = lista([f"{v.compuerta} ({v.dueno})" for v in self.bloqueantes])
        return f"No sale hoy. Bloquea {culpables}."

    def to_dict(self) -> dict:
        return {
            "pasa": self.pasa,
            "automaticas": self.automaticas,
            "veredictos": [v.to_dict() for v in self.veredictos],
            "resumen": self.describe(),
        }


def revisar(pieza: Pieza, semana: list[Pieza] | None = None) -> Parte:
    """Todas las compuertas sobre una pieza, mas la de variacion si hay semana."""
    parte = Parte([f(pieza) for f in INDIVIDUALES])
    if semana:
        parte.veredictos.append(variacion(semana))
    return parte
