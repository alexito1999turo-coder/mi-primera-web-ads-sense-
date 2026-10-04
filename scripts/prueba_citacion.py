"""Prueba a ciegas: ¿el motor predice lo que un modelo citaria de verdad?

Metodo, en dos pasos para que el cegado sea real:

  1. `pool` imprime un conjunto de frases barajadas, SIN sus notas, numeradas.
     Un modelo elige, por cada pregunta, que frases citaria para contestarla.
  2. `evaluar` recibe esas elecciones y las compara con lo que el motor habia
     predicho.

Limitaciones que hay que decir antes de ver el resultado, no despues:
  - un solo modelo como sujeto, y es el mismo que escribio el motor;
  - muestra pequena;
  - las frases vienen de un nicho concreto.
Esto no demuestra que el motor acierte en general. Demuestra, como mucho, que
en esta prueba predice las elecciones de un modelo mejor que el azar, y eso ya
es mas de lo que tiene un prior sin tocar.
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path

from citability.score import analyse

PREGUNTAS = [
    "¿Cuánto cuesta instalar un sistema séptico aeróbico en Texas?",
    "¿Cuánto añade el permiso del condado?",
    "¿Cuánto cuesta mantener uno al año?",
]

# Frases de control, escritas a proposito como las escribiria cualquiera: dicen
# cosas verdaderas pero sin cifra exacta, sin fecha o sin metodo.
CONTROLES = [
    "Instalar un sistema séptico aeróbico suele costar unos 15.000 $ en Texas.",
    "El permiso del condado ronda los 600 $ y lo tramita el instalador.",
    "Este cuesta bastante más que un sistema convencional, según los expertos.",
    "El mantenimiento anual es asequible si se contrata con un operador local.",
    "Los precios varían mucho de un condado a otro y conviene pedir varios presupuestos.",
    "La instalación completa costó 15.498,50 $ de mediana en Texas en 2026, sobre una muestra propia de 30 presupuestos reales.",
    "El permiso del condado añadió 612 $ de media en 2026 en esa misma muestra, con un mínimo de 385 $ y un máximo de 940 $.",
    "El mantenimiento anual salió a 487 $ por vivienda en 2026 en nuestra muestra de 30 casos, contando las dos inspecciones obligatorias.",
    "En Travis la mediana fue de 15.720,50 $ sobre 14 presupuestos, y en Bexar de 15.193 $ sobre 13.",
    "Un compresor de membrana de 80 vatios consume unos 110 $ al año según nuestro cálculo con las tarifas de 2026.",
]


def construir_pool(semilla: int = 20261004) -> list[str]:
    cuerpo = Path("specimens/01-coste-instalacion-texas.md").read_text()
    informe = analyse(cuerpo)
    del_articulo = [q.text for q in informe.quotes]
    pool = list(dict.fromkeys(CONTROLES + del_articulo))
    random.Random(semilla).shuffle(pool)
    return pool


def mostrar_pool() -> int:
    pool = construir_pool()
    print("PREGUNTAS\n")
    for i, p in enumerate(PREGUNTAS, 1):
        print(f"  P{i}. {p}")
    print(f"\nFRASES DISPONIBLES ({len(pool)}), sin notas y en orden aleatorio:\n")
    for i, frase in enumerate(pool, 1):
        print(f"  [{i:2}] {frase}")
    print("\nPara cada pregunta: qué frases citarías para contestarla.")
    return 0


def evaluar(elecciones: dict[str, list[int]]) -> int:
    pool = construir_pool()
    notas = {}
    for i, frase in enumerate(pool, 1):
        # Se puntua la frase en el contexto que el motor espera: debajo de un
        # encabezado en forma de pregunta y en primera posicion, para que la
        # comparacion no castigue a unas por donde estaban en su articulo.
        informe = analyse("## ¿Pregunta?\n\n" + frase)
        notas[i] = informe.quotes[0].total if informe.quotes else 0

    elegidas = sorted({n for lista in elecciones.values() for n in lista})
    no_elegidas = [i for i in range(1, len(pool) + 1) if i not in elegidas]

    def media(ids):
        return round(sum(notas[i] for i in ids) / len(ids), 1) if ids else 0.0

    m_si, m_no = media(elegidas), media(no_elegidas)

    # Area bajo la curva ROC por conteo de pares: de todos los pares
    # (elegida, no elegida), en cuantos puntua mas alto la elegida.
    pares = ganados = empates = 0
    for a in elegidas:
        for b in no_elegidas:
            pares += 1
            if notas[a] > notas[b]:
                ganados += 1
            elif notas[a] == notas[b]:
                empates += 1
    auc = (ganados + empates / 2) / pares if pares else 0.0

    print(f"Frases: {len(pool)} · citadas por el modelo: {len(elegidas)} · "
          f"no citadas: {len(no_elegidas)}\n")
    print(f"  Nota media de las CITADAS      {m_si}")
    print(f"  Nota media de las NO citadas   {m_no}")
    print(f"  Diferencia                     {round(m_si - m_no, 1)} puntos")
    print(f"  AUC (0,5 = azar, 1 = perfecto) {round(auc, 3)}\n")

    print("  Detalle, ordenado por lo que predijo el motor:")
    for i in sorted(notas, key=lambda k: -notas[k]):
        marca = "CITADA  " if i in elegidas else "        "
        print(f"    {notas[i]:3}  {marca} [{i:2}] {pool[i-1][:88]}")

    fallos_altos = [i for i in no_elegidas if notas[i] >= 70]
    fallos_bajos = [i for i in elegidas if notas[i] < 50]
    print()
    if fallos_altos:
        print(f"  Predijo alto y no se citó ({len(fallos_altos)}):")
        for i in fallos_altos:
            print(f"    [{i}] {pool[i-1][:92]}")
    if fallos_bajos:
        print(f"  Predijo bajo y sí se citó ({len(fallos_bajos)}):")
        for i in fallos_bajos:
            print(f"    [{i}] {pool[i-1][:92]}")
    if not fallos_altos and not fallos_bajos:
        print("  Sin desacuerdos grandes entre el motor y el modelo.")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="prueba_citacion")
    parser.add_argument("accion", choices=["pool", "evaluar"])
    parser.add_argument("--elecciones", help="JSON {\"P1\": [1,4], ...}")
    args = parser.parse_args(argv)
    if args.accion == "pool":
        return mostrar_pool()
    if not args.elecciones:
        print("Hacen falta las elecciones.", file=sys.stderr)
        return 2
    return evaluar(json.loads(args.elecciones))


if __name__ == "__main__":
    raise SystemExit(main())
