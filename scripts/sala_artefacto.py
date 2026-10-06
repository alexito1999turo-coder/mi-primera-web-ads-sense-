"""Arma el artefacto de la sala: una sola pagina con los datos del motor dentro.

La pestana 7 del banco sirve para trabajar, pero vive en `127.0.0.1` y no se
puede ensenar desde el movil ni mandar a nadie. Esto produce la misma sala en
un fichero suelto, sin servidor y sin red: la plantilla es HTML, y aqui dentro
solo se inyecta el JSON que calcula el paquete `estudio`.

La regla de la casa vuelve a ser la misma que con el motor de economia en
JavaScript: **ninguna cifra se escribe a mano en la plantilla.** El fallo, los
turnos, la carrera y la pila salen del mismo codigo que corre en las pruebas,
asi que corregir un peso o un umbral y volver a generar basta para que el
artefacto deje de mentir. Hay una prueba que lo comprueba cruzando las dos
cosas.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from estudio import herramientas as H
from estudio import jueces, plan
from estudio.agentes import COMPUERTAS_HUMANAS, PLANTILLA, compuertas_de_la_sala
from estudio.carrera import Carrera, comparar_rutas
from estudio.sala import Sala

RAIZ = Path(__file__).resolve().parent.parent
PLANTILLA_HTML = RAIZ / "artefactos" / "sala.plantilla.html"
SALIDA = RAIZ / "artefactos" / "sala.html"
MARCA = "__DATOS__"

PASO = 5
PRESUPUESTOS = (0.0, 15.0, 25.0, 50.0, 100.0)


def datos(hoy: date | None = None, vistas: float = 1500.0) -> dict:
    hoy = hoy or date.today()
    carrera = Carrera(hoy=hoy)
    duenos = compuertas_de_la_sala()

    dias = []
    for dia in plan.SEMANA:
        pelicula = Sala.del_dia(dia.indice).pelicula(PASO)
        # El artefacto deja apagar una compuerta para ver la cadena pararse, y
        # para eso necesita saber cuando entra cada turno. Es dato del plan, no
        # logica: la maquina de estados sigue estando en un solo sitio.
        turnos = {t.agente: {"inicio": t.inicio, "minutos": t.minutos}
                  for t in dia.turnos}
        for agente in pelicula["agentes"]:
            agente.update(turnos.get(agente["clave"], {"inicio": -1, "minutos": 0}))
        dias.append(pelicula)

    return {
        "generado": hoy.isoformat(),
        "agentes": [a.to_dict() for a in PLANTILLA],
        "compuertas": {
            "duenos": duenos,
            "humanas": list(COMPUERTAS_HUMANAS),
            "total": len(duenos),
        },
        "dias": dias,
        "plan": {
            "resumen": plan.describe(),
            "horas_semana": plan.horas_semana(),
            "carga": plan.carga_por_agente(),
            "cuello": plan.cuello_de_botella(),
            "dias": [d.to_dict() for d in plan.SEMANA],
        },
        "calendario": [e.to_dict() for e in plan.calendario(hoy, semanas=4)],
        "fallo": jueces.fallo().to_dict(),
        "tabla": jueces.tabla(),
        "jueces": [
            {"clave": j.clave, "nombre": j.nombre, "oficio": j.oficio,
             "mira": j.mira, "veto": j.veto_por_debajo_de,
             "criterios": [{"clave": c.clave, "pregunta": c.pregunta,
                            "peso": c.peso, "enmienda": c.enmienda}
                           for c in j.criterios]}
            for j in jueces.JUECES
        ],
        "candidatas": [
            {"clave": e.clave, "nombre": e.nombre, "resumen": e.resumen,
             "cadencia": e.cadencia, "condiciones": list(e.condiciones)}
            for e in jueces.CANDIDATAS
        ],
        "carrera": carrera.to_dict(vistas_por_largo=vistas),
        "rutas": comparar_rutas(carrera),
        "pilas": {str(int(p)): H.pila(p) for p in PRESUPUESTOS},
        "riesgos": H.riesgos(),
    }


def construir(hoy: date | None = None) -> str:
    plantilla = PLANTILLA_HTML.read_text(encoding="utf-8")
    if MARCA not in plantilla:
        raise ValueError(f"La plantilla no tiene la marca {MARCA}.")
    crudo = json.dumps(datos(hoy), ensure_ascii=False, separators=(",", ":"))
    # Dentro de un <script> cualquier «</script>» del contenido cerraria la
    # etiqueta antes de tiempo. No lo hay hoy, y el dia que lo haya el fallo
    # seria mudo.
    crudo = crudo.replace("</", "<\\/")
    return plantilla.replace(MARCA, crudo)


def main(argv: list[str] | None = None) -> int:
    import argparse

    p = argparse.ArgumentParser(prog="sala_artefacto",
                                description="Genera artefactos/sala.html")
    p.add_argument("--hoy", default="", help="fecha de referencia, AAAA-MM-DD")
    p.add_argument("--salida", default=str(SALIDA))
    args = p.parse_args(argv)

    hoy = date.fromisoformat(args.hoy) if args.hoy else date.today()
    html = construir(hoy)
    destino = Path(args.salida)
    destino.write_text(html, encoding="utf-8")
    print(f"  {destino} · {len(html) / 1024:.0f} KB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
