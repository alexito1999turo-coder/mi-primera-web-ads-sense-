"""El estudio por linea de comandos.

    python3 -m estudio                     # fallo de los jueces, plan y carrera
    python3 -m estudio --sala 5 --minuto 120
    python3 -m estudio --animar 5          # la sala moviendose en el terminal
    python3 -m estudio --calendario 4
"""

from __future__ import annotations

import argparse
import sys
import time
from datetime import date

from textos import cifra, plural

from . import herramientas as H
from .carrera import Carrera, comparar_rutas
from .jueces import JUECES, fallo, tabla
from .plan import SEMANA, calendario, carga_por_agente, describe as describe_plan
from .sala import Sala


def _titulo(texto: str) -> None:
    print(f"\n{texto}\n{'-' * len(texto)}")


def _fallo() -> None:
    f = fallo()
    _titulo("El tribunal")
    for juez in JUECES:
        print(f"  {juez.nombre} · {juez.oficio}: {juez.mira}")
    print()
    cabecera = f"  {'':28}" + "".join(f"{j.clave[:9]:>10}" for j in JUECES) + f"{'media':>10}"
    print(cabecera)
    for fila in tabla():
        marcas = " VETADA" if fila["vetada"] else (" <- GANA" if fila["ganadora"] else "")
        notas = "".join(f"{fila[j.clave]:>10.2f}" for j in JUECES)
        print(f"  {fila['nombre']:28}{notas}{fila['media']:>10.2f}{marcas}")
    print(f"\n  {f.describe()}")

    if f.enmiendas:
        _titulo("Enmiendas obligatorias sobre la ganadora")
        for e in f.enmiendas:
            print(f"  {e['juez']} ({e['criterio']}, {e['nota']}/5): {e['enmienda']}")
    if f.ganadora.condiciones:
        _titulo("Condiciones sin las que la nota no vale")
        for c in f.ganadora.condiciones:
            print(f"  - {c}")


def _plan() -> None:
    _titulo("La semana canonica")
    print(f"  {describe_plan()}\n")
    for dia in SEMANA:
        hora = f"{dia.hora // 60:02d}:{dia.hora % 60:02d}"
        print(f"  {dia.nombre:<10} {hora}  {dia.formato:<11} {dia.tipo:<11} "
              f"{plural(dia.minutos, 'minuto'):>11}  {dia.titulo}")
    print()
    for clave, minutos in carga_por_agente().items():
        print(f"  {clave:<12} {plural(minutos, 'minuto')} a la semana")


def _carrera(hoy: date, vistas: float) -> None:
    c = Carrera(hoy=hoy)
    _titulo("La carrera contra la puerta")
    print(f"  {c.veredicto(vistas)}")
    rutas = comparar_rutas(c)
    print(f"\n  Ruta de horas:  {cifra(rutas['ruta_horas']['vistas'])} vistas de "
          f"documental -> {cifra(rutas['ruta_horas']['ingreso'][0])}-"
          f"{cifra(rutas['ruta_horas']['ingreso'][1])} $ de publicidad")
    print(f"  Ruta de Shorts: {cifra(rutas['ruta_shorts']['vistas'])} vistas -> "
          f"{cifra(rutas['ruta_shorts']['ingreso'][0])}-"
          f"{cifra(rutas['ruta_shorts']['ingreso'][1])} $")
    print(f"  La ruta de Shorts pide {cifra(rutas['veces_mas_vistas'], 1)} veces "
          "mas vistas por la misma puerta.")
    print(f"  RPM: {rutas['fuente_rpm']}.")


def _pila(presupuesto: float) -> None:
    r = H.pila(presupuesto)
    _titulo(f"Pila de herramientas con {cifra(presupuesto, 2)} al mes")
    print(f"  {r['resumen']}\n")
    for h in r["elegidas"]:
        coste = "gratis" if not h["coste_mes"] else f"{cifra(h['coste_mes'], 2)}/mes"
        print(f"  {h['nombre']:<34} {coste:>12}  {h['oficio']}")
    for h in r["sin_precio"]:
        print(f"  {h['nombre']:<34} {'NO VERIFICADO':>12}  {h['oficio']}")
    if r["ahorro_por_agente"]:
        print(f"\n  Quita: {r['ahorro_por_agente']}")
        print(f"  Semana: {cifra(r['horas_sin_herramientas'], 1)} -> "
              f"{cifra(r['horas_semana'], 1)} horas")


def _sala(indice: int, minuto: int) -> None:
    s = Sala.del_dia(indice)
    _titulo(f"La sala · {s.dia.nombre}, minuto {minuto} de {s.jornada}")
    print("\n".join(s.lineas(minuto)))
    print(f"\n  {s.describe(minuto)}")


def _animar(indice: int, velocidad: float, paso: int) -> None:
    s = Sala.del_dia(indice)
    for minuto in range(0, s.jornada + paso, paso):
        sys.stdout.write("\x1b[H\x1b[2J")
        print(f"La sala · {s.dia.nombre} · minuto {minuto} de {s.jornada}\n")
        print("\n".join(s.lineas(minuto)))
        relevo = s.relevo_en(minuto, margen=paso)
        if relevo:
            print(f"\n  relevo: {relevo['de']} -> {relevo['a']} ({relevo['entrega']})")
        else:
            print(f"\n  {s.describe(minuto)}")
        sys.stdout.flush()
        time.sleep(velocidad)


def _calendario(semanas: int, desde: date) -> None:
    _titulo(f"Calendario de {plural(semanas, 'semana')} desde el {desde.isoformat()}")
    for e in calendario(desde, semanas=semanas):
        if not e.publica:
            print(f"  {e.fecha}  {e.dia_semana_corto()}  semana 0   {e.nota}")
            continue
        hora = f"{e.dia.hora // 60:02d}:{e.dia.hora % 60:02d}"
        print(f"  {e.fecha}  {e.dia_semana_corto()}  semana {e.semana}  {hora}  "
              f"{e.dia.formato:<11} {e.dia.tipo:<11} {e.dia.titulo}")


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        prog="estudio",
        description="El estudio del canal: jueces, plan, carrera y sala.",
    )
    p.add_argument("--sala", type=int, metavar="DIA", help="dia de la semana, 1-7")
    p.add_argument("--minuto", type=int, default=0)
    p.add_argument("--animar", type=int, metavar="DIA",
                   help="anima la jornada de ese dia en el terminal")
    p.add_argument("--velocidad", type=float, default=0.08,
                   help="segundos por fotograma al animar")
    p.add_argument("--paso", type=int, default=5, help="minutos por fotograma")
    p.add_argument("--calendario", type=int, metavar="SEMANAS")
    p.add_argument("--desde", default="", help="fecha de arranque, AAAA-MM-DD")
    p.add_argument("--presupuesto", type=float, default=0.0)
    p.add_argument("--vistas", type=float, default=0.0,
                   help="hipotesis de vistas por documental")
    args = p.parse_args(argv)

    desde = date.fromisoformat(args.desde) if args.desde else date.today()

    if args.animar:
        _animar(args.animar, args.velocidad, args.paso)
        return 0
    if args.sala:
        _sala(args.sala, args.minuto)
        return 0
    if args.calendario:
        _calendario(args.calendario, desde)
        return 0

    _fallo()
    _plan()
    _carrera(desde, args.vistas)
    _pila(args.presupuesto)
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
