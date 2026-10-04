"""Punto de entrada:  python3 -m webapp"""

from __future__ import annotations

import argparse
import sys

from .server import serve


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="webapp",
        description="Banco de pruebas SEO-GEO: auditoria, citabilidad, "
                    "oportunidad y clusters, en el navegador, y en "
                    "/oferta que se vende y cuanto cuesta.",
    )
    parser.add_argument("--port", type=int, default=8000, metavar="N",
                        help="Puerto (por defecto 8000)")
    parser.add_argument("--allow-private", action="store_true",
                        help="Permite auditar direcciones internas. Solo para "
                             "probar contra un WordPress local.")
    args = parser.parse_args(argv)
    serve(port=args.port, allow_private=args.allow_private)
    return 0


if __name__ == "__main__":
    sys.exit(main())
