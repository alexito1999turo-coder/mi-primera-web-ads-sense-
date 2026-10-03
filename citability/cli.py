"""Linea de comandos: que frases de este texto puede citar un buscador.

    python3 -m citability articulo.md
    python3 -m citability articulo.md --fixes-only
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .score import analyse


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="citability",
        description=(
            "Puntua la citabilidad de un texto y lista las frases que un modelo "
            "levantaria de el."
        ),
    )
    parser.add_argument("file", help="Fichero markdown o texto")
    parser.add_argument("--fixes-only", action="store_true",
                        help="Solo la lista de arreglos por impacto")
    parser.add_argument("--min-score", type=int, metavar="N",
                        help="Sale con error si la citabilidad baja de N")
    args = parser.parse_args(argv)

    path = Path(args.file)
    if not path.exists():
        print(f"No existe: {path}", file=sys.stderr)
        return 2

    report = analyse(path.read_text(encoding="utf-8"))

    if not args.fixes_only:
        print(report.describe())
        print()
        if report.liftable:
            print("## Frases citables")
            print()
            for quote in report.liftable:
                print(f"  {quote.describe()}")
                print(f"    «{quote.text}»")
                print()
        else:
            print("Ninguna frase es citable tal como esta escrita.")
            print()

    fixes = report.top_fixes()
    if fixes:
        print("## Arreglos, por cuantas frases afectan")
        print()
        for fix, count in fixes:
            print(f"  x{count}  {fix}")
        print()

    if args.min_score is not None and report.score < args.min_score:
        print(f"Citabilidad {report.score} por debajo del minimo {args.min_score}.",
              file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
