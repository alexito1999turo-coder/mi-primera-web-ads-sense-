"""Interfaz de linea de comandos del M1.

    python3 -m auditor https://ejemplo.com
    python3 -m auditor https://ejemplo.com --impressions gsc.csv --json salida.json
"""

from __future__ import annotations

import argparse
import sys

from .audit import run
from .http import DEFAULT_MIN_INTERVAL, Client
from .report import to_json, to_markdown
from .rules import THIN_WORDS


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="auditor",
        description=(
            "M1 Auditor: archivos indexables finos, canibalizacion "
            "archivo-vs-articulo y distribucion de intencion."
        ),
    )
    parser.add_argument("site", help="Dominio o URL del sitio a auditar")
    parser.add_argument(
        "--impressions",
        metavar="CSV",
        help="Exportacion de Search Console (columnas de pagina e impresiones). "
             "Sin esto, la canibalizacion no se mide.",
    )
    parser.add_argument(
        "--thin-words",
        type=int,
        default=THIN_WORDS,
        metavar="N",
        help=f"Umbral de palabras para considerar un archivo fino (por defecto {THIN_WORDS})",
    )
    parser.add_argument(
        "--interval",
        type=float,
        default=DEFAULT_MIN_INTERVAL,
        metavar="SEG",
        help=f"Segundos minimos entre peticiones (por defecto {DEFAULT_MIN_INTERVAL})",
    )
    parser.add_argument(
        "--max-archives",
        type=int,
        default=60,
        metavar="N",
        help="Maximo de archivos a medir (por defecto 60)",
    )
    parser.add_argument("--json", metavar="RUTA", help="Guarda el informe tambien en JSON")
    parser.add_argument("--out", metavar="RUTA", help="Guarda el informe markdown en fichero")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    audit = run(
        site=args.site,
        client=Client(min_interval=args.interval),
        thin_words=args.thin_words,
        impressions_csv=args.impressions,
        max_archives=args.max_archives,
    )

    markdown = to_markdown(audit)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as handle:
            handle.write(markdown)
        print(f"Informe markdown: {args.out}")
    else:
        print(markdown)

    if args.json:
        with open(args.json, "w", encoding="utf-8") as handle:
            handle.write(to_json(audit))
        print(f"Informe JSON: {args.json}")

    # Codigo de salida util en CI: 1 si hay acciones pendientes.
    return 1 if audit.actionable else 0


if __name__ == "__main__":
    sys.exit(main())
