"""La sala: once agentes, un reloj y quien tiene el relevo.

Esto es lo que se ve. El resto del paquete decide; esta clase solo responde a
una pregunta, la misma que uno se hace cuando lleva un canal solo: *a esta hora
de hoy, quien tendria que estar haciendo que, y quien esta parado esperando a
otro.*

La respuesta sale del plan, no de un reloj de verdad, y es deterministica: con
el mismo dia y el mismo minuto da el mismo estado. Por eso la pagina la puede
animar a la velocidad que quiera —un segundo por minuto de jornada, o la
jornada entera en veinte segundos— sin que el estado dependa de cuando se abrio
el navegador.

Un agente esta en uno de cinco estados. Cuatro son evidentes: libre (hoy no le
toca), esperando (le toca luego), trabajando y entregado. El quinto es el que
hace que esto sirva para algo: **bloqueado**. Cuando una compuerta no pasa, el
agente que la posee se pone en rojo con el motivo escrito, y los que esperaban
su entrega se quedan esperando. Es la unica forma honesta de dibujar una
cadena de produccion: si la compuerta de fuentes no pasa, el montador no esta
"pendiente", esta parado por culpa de alguien, y con nombre.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from textos import plural

from .agentes import PLANTILLA, agente
from .compuertas import Parte
from .plan import SEMANA, Dia, Turno

LIBRE = "libre"
ESPERANDO = "esperando"
TRABAJANDO = "trabajando"
ENTREGADO = "entregado"
BLOQUEADO = "bloqueado"

# Como se dibuja cada estado cuando no hay pantalla: la sala en el terminal.
GLIFOS = {
    LIBRE: "·",
    ESPERANDO: "o",
    TRABAJANDO: "@",
    ENTREGADO: "v",
    BLOQUEADO: "X",
}


@dataclass
class EstadoAgente:
    clave: str
    nombre: str
    rol: str
    figura: str
    color: str
    estado: str
    tarea: str = ""
    entrega: str = ""
    relevo: str = ""
    progreso: float = 0.0
    minutos_restantes: int = 0
    motivo: str = ""

    def to_dict(self) -> dict:
        return {
            "clave": self.clave,
            "nombre": self.nombre,
            "rol": self.rol,
            "figura": self.figura,
            "color": self.color,
            "estado": self.estado,
            "tarea": self.tarea,
            "entrega": self.entrega,
            "relevo": self.relevo,
            "progreso": round(self.progreso, 3),
            "minutos_restantes": self.minutos_restantes,
            "motivo": self.motivo,
            "glifo": GLIFOS[self.estado],
        }


@dataclass
class Sala:
    """Los once agentes de un dia, con el reloj de la jornada.

    `bloqueos` es compuerta -> motivo. Viene del parte de compuertas, asi que
    la sala no decide nada sobre calidad: dibuja lo que la compuerta dijo.
    """

    dia: Dia
    bloqueos: dict[str, str] = field(default_factory=dict)

    @classmethod
    def del_dia(cls, indice: int, bloqueos: dict[str, str] | None = None) -> "Sala":
        if not 1 <= indice <= len(SEMANA):
            raise ValueError(f"La semana tiene {len(SEMANA)} dias; pediste el {indice}.")
        return cls(dia=SEMANA[indice - 1], bloqueos=dict(bloqueos or {}))

    @classmethod
    def desde_parte(cls, indice: int, parte: Parte) -> "Sala":
        """La sala con los bloqueos que salgan de un parte de compuertas."""
        return cls.del_dia(indice, {v.dueno: v.motivo for v in parte.bloqueantes})

    @property
    def jornada(self) -> int:
        return self.dia.jornada

    def turno_de(self, clave: str) -> Turno | None:
        for t in self.dia.turnos:
            if t.agente == clave:
                return t
        return None

    # -- el estado a una hora ---------------------------------------------
    def estado(self, minuto: int) -> list[EstadoAgente]:
        reloj = max(0, min(minuto, self.jornada))
        estados: list[EstadoAgente] = []

        for a in PLANTILLA:
            turno = self.turno_de(a.clave)
            base = EstadoAgente(
                clave=a.clave, nombre=a.nombre, rol=a.rol, figura=a.figura,
                color=a.color, estado=LIBRE,
            )
            if turno is None:
                base.tarea = "Hoy no le toca"
                estados.append(base)
                continue

            base.tarea = turno.tarea
            base.entrega = turno.entrega
            base.relevo = agente(turno.relevo).nombre if turno.relevo else ""

            motivo = self.bloqueos.get(a.clave, "")
            if motivo and reloj >= turno.inicio:
                base.estado = BLOQUEADO
                base.motivo = motivo
                base.progreso = 1.0
            elif reloj < turno.inicio:
                base.estado = ESPERANDO
                base.minutos_restantes = turno.inicio - reloj
            elif reloj >= turno.fin:
                base.estado = ENTREGADO
                base.progreso = 1.0
            else:
                base.estado = TRABAJANDO
                base.progreso = (reloj - turno.inicio) / turno.minutos
                base.minutos_restantes = turno.fin - reloj
            estados.append(base)
        return estados

    def relevo_en(self, minuto: int, margen: int = 5) -> dict | None:
        """El relevo que esta pasando ahora mismo, si lo hay.

        Dibuja la flecha entre dos munequitos. Sin margen no se veria nunca:
        el instante exacto del relevo dura un minuto de jornada y la pagina
        pinta cada varios.
        """
        for t in self.dia.turnos:
            if t.relevo and 0 <= minuto - t.fin <= margen:
                # Un relevo hacia un agente bloqueado no es un relevo, es un
                # paquete que se queda en la puerta.
                if t.relevo in self.bloqueos:
                    continue
                return {
                    "de": t.agente,
                    "a": t.relevo,
                    "entrega": t.entrega,
                }
        return None

    def to_dict(self, minuto: int) -> dict:
        estados = self.estado(minuto)
        cuenta = {e: 0 for e in GLIFOS}
        for s in estados:
            cuenta[s.estado] += 1
        return {
            "dia": self.dia.to_dict(),
            "minuto": max(0, min(minuto, self.jornada)),
            "jornada": self.jornada,
            "agentes": [s.to_dict() for s in estados],
            "relevo": self.relevo_en(minuto),
            "cuenta": cuenta,
            "bloqueada": any(s.estado == BLOQUEADO for s in estados),
            "resumen": self.describe(minuto),
        }

    def pelicula(self, paso: int = 5) -> dict:
        """La jornada entera en una peticion, para que la pagina la reproduzca.

        La primera version pedia un fotograma por minuto al servidor. Funciona
        y es insostenible por una razon que no tiene nada que ver con la carga:
        el servidor escribe una linea de registro por peticion, y a cuatro
        fotogramas por segundo el registro deja de servir para ver cualquier
        otra cosa. La alternativa —copiar la maquina de estados en JavaScript—
        es peor: dos copias de la misma regla que se corrigen por separado, que
        es el fallo que el resto del repositorio ya cometio una vez con el
        motor de economia y que ahora tiene una prueba cruzada vigilandolo.

        Asi que el estado sigue calculandose en un solo sitio y viaja entero.
        Lo que no cambia —nombre, oficio, tarea, relevo, motivo del bloqueo—
        va una vez; de cada fotograma solo viajan las tres cosas que se mueven.
        """
        paso = max(1, min(paso, 60))
        agentes = []
        for a in PLANTILLA:
            turno = self.turno_de(a.clave)
            agentes.append({
                "clave": a.clave,
                "nombre": a.nombre,
                "rol": a.rol,
                "responsable_de": a.responsable_de,
                "figura": a.figura,
                "color": a.color,
                "tarea": turno.tarea if turno else "Hoy no le toca",
                "entrega": turno.entrega if turno else "",
                "relevo": (agente(turno.relevo).nombre
                           if turno and turno.relevo else ""),
                "motivo": self.bloqueos.get(a.clave, ""),
            })

        fotogramas = []
        for minuto in range(0, self.jornada + paso, paso):
            tope = min(minuto, self.jornada)
            fotogramas.append({
                "minuto": tope,
                "estados": [
                    {"e": s.estado, "p": round(s.progreso, 3),
                     "r": s.minutos_restantes}
                    for s in self.estado(tope)
                ],
                "relevo": self.relevo_en(tope, margen=paso),
                "resumen": self.describe(tope),
            })
        return {
            "dia": self.dia.to_dict(),
            "jornada": self.jornada,
            "paso": paso,
            "agentes": agentes,
            "fotogramas": fotogramas,
        }

    def describe(self, minuto: int) -> str:
        estados = self.estado(minuto)
        trabajando = [s.nombre for s in estados if s.estado == TRABAJANDO]
        bloqueados = [s for s in estados if s.estado == BLOQUEADO]
        if bloqueados:
            primero = bloqueados[0]
            return (f"{self.dia.nombre.capitalize()}, minuto {minuto}: parada en "
                    f"{primero.nombre}. {primero.motivo}")
        if not trabajando:
            hechos = sum(1 for s in estados if s.estado == ENTREGADO)
            if hechos == len(self.dia.turnos):
                return (f"{self.dia.nombre.capitalize()}: jornada cerrada, "
                        f"{plural(hechos, 'entrega')} y la publicacion del dia fuera.")
            return f"{self.dia.nombre.capitalize()}, minuto {minuto}: nadie en marcha."
        return (f"{self.dia.nombre.capitalize()}, minuto {minuto} de "
                f"{self.jornada}: trabajando {', '.join(trabajando)}.")

    def lineas(self, minuto: int, ancho: int = 24) -> list[str]:
        """La sala en texto, para el terminal y para las pruebas."""
        salida = []
        for s in self.estado(minuto):
            barra = ""
            if s.estado in (TRABAJANDO, ENTREGADO, BLOQUEADO):
                lleno = int(round(s.progreso * ancho))
                barra = "#" * lleno + "-" * (ancho - lleno)
            elif s.estado == ESPERANDO:
                barra = "-" * ancho
            etiqueta = s.motivo or s.tarea
            salida.append(f" {GLIFOS[s.estado]} {s.nombre:<18} [{barra}] {etiqueta}")
        return salida
