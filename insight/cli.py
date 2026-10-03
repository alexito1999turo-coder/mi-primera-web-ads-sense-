"""Linea de comandos: donde esta la oportunidad de verdad.

    python3 -m insight gsc-actual.csv
    python3 -m insight gsc-actual.csv --before gsc-anterior.csv --keywords kw.csv --pages 12
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from clusters.graph import build as build_graph
from clusters.keywords import load as load_keywords

from .gsc import Report, load
from .opportunity import analyse
from .reallocate import reallocate


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="insight",
        description=(
            "Oportunidad descontada por AI Overviews y ordenada por valor, no "
            "por clics."
        ),
    )
    parser.add_argument("current", help="Exportacion de Search Console del periodo actual")
    parser.add_argument("--before", metavar="CSV",
                        help="Periodo anterior, para decidir reasignacion")
    parser.add_argument("--keywords", metavar="CSV",
                        help="Keywords para reconstruir los clusters")
    parser.add_argument("--pages", type=int, default=0, metavar="N",
                        help="Paginas del mes a repartir entre clusters")
    parser.add_argument("--top", type=int, default=15, metavar="N",
                        help="Cuantas oportunidades mostrar")
    args = parser.parse_args(argv)

    if not Path(args.current).exists():
        print(f"No existe: {args.current}", file=sys.stderr)
        return 2

    now = load(args.current)
    for note in now.notes:
        print(f"nota: {note}")
    if not now.rows:
        print("La exportacion no trae filas utilizables.", file=sys.stderr)
        return 2

    opportunities = analyse(now)
    print()
    print(opportunities.describe())
    print()
    print("## Por valor esperado (el orden en el que trabajar)")
    print()
    for index, opportunity in enumerate(opportunities.ranked[: args.top], start=1):
        print(f"  {index}. {opportunity.describe()}")
    print()

    demoted = opportunities.demoted()
    promoted = opportunities.promoted()
    if demoted or promoted:
        print("## Lo que cambia respecto a priorizar por clics")
        print()
        for subject, before, after in demoted:
            print(f"  baja  «{subject}»: puesto {before} -> {after}")
        for subject, before, after in promoted:
            print(f"  sube  «{subject}»: puesto {before} -> {after}")
        print()

    if args.before and args.keywords:
        graph = build_graph(load_keywords(args.keywords))
        before = load(args.before)
        result = reallocate(graph, before, now, opportunities)
        print("## Reasignacion de clusters")
        print()
        print(result.describe(pages=args.pages))
        print()
        for decision in result.decisions:
            print(f"  - {decision.describe()}")
        print()
    elif args.before or args.keywords:
        print("Para la reasignacion hacen falta --before y --keywords a la vez.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
