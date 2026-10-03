"""Linea de comandos del M2.

    python3 -m clusters keywords.csv
    python3 -m clusters keywords.csv --cap 12 --out plan.md
"""

from __future__ import annotations

import argparse
import sys

from .graph import MERGE_THRESHOLD, build as build_graph
from .keywords import load
from .plan import build as build_plan, to_markdown
from .validate import MONTHLY_CAP, validate


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="clusters",
        description="M2: grafo de clusters con solape cero y plan mensual.",
    )
    parser.add_argument("keywords", help="CSV de keywords (Semrush, Ahrefs, DataForSEO o a mano)")
    parser.add_argument("--cap", type=int, default=MONTHLY_CAP, metavar="N",
                        help=f"Tope de paginas por mes (por defecto {MONTHLY_CAP})")
    parser.add_argument("--merge-threshold", type=float, default=MERGE_THRESHOLD, metavar="F",
                        help=f"Similitud para fusionar keywords (por defecto {MERGE_THRESHOLD})")
    parser.add_argument("--out", metavar="RUTA", help="Guarda el plan en markdown")
    parser.add_argument("--strict", action="store_true",
                        help="Sale con error si hay hallazgos bloqueantes")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    keywords = load(args.keywords)
    if not keywords:
        print("El CSV no contiene keywords.", file=sys.stderr)
        return 2

    graph = build_graph(keywords, merge_threshold=args.merge_threshold)
    result = validate(graph, monthly_cap=args.cap)
    plan = build_plan(graph, cap=args.cap)

    markdown = to_markdown(graph, plan, result)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as handle:
            handle.write(markdown)
        print(f"Plan: {args.out}")
    else:
        print(markdown)

    if args.strict and not result.passed:
        print(f"\n{len(result.blocking)} hallazgo(s) bloqueante(s).", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
