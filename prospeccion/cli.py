"""Interfaz de linea de comandos del M11.

    python3 -m prospeccion dominios.txt --out informes/

Un fichero de dominios, uno por linea, con comentarios con #. Sale una carpeta
con un informe por marca, el mensaje de tres lineas en su propio fichero (para
copiarlo al correo sin arrastrar el informe entero) y un indice del lote.

El codigo de salida es 1 si algun dominio fallo. Es lo util en una tarea
programada de los lunes: el lote entero se completa igual, pero el fallo se ve.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from auditor.http import DEFAULT_MIN_INTERVAL, Client
from auditor.rules import THIN_WORDS

from .batch import DEFAULT_MAX_ARCHIVES, BatchResult, read_domains, run
from .outreach import Outreach, build, nothing_measured

MESSAGE_SUFFIX = "-mensaje.txt"
INDEX_NAME = "lote.md"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="prospeccion",
        description=(
            "M11 Prospeccion: convierte una lista de dominios en informes de "
            "auditoria listos para enviar a cada marca."
        ),
    )
    parser.add_argument(
        "domains",
        metavar="FICHERO",
        help="Fichero de dominios, uno por linea. Se permiten comentarios con #.",
    )
    parser.add_argument(
        "--out",
        metavar="CARPETA",
        default="informes",
        help="Carpeta donde escribir los informes (por defecto informes/)",
    )
    parser.add_argument(
        "--interval",
        type=float,
        default=DEFAULT_MIN_INTERVAL,
        metavar="SEG",
        help=f"Segundos minimos entre peticiones (por defecto {DEFAULT_MIN_INTERVAL}). "
             "El espaciado es el mismo para todo el lote, no por dominio.",
    )
    parser.add_argument(
        "--thin-words",
        type=int,
        default=THIN_WORDS,
        metavar="N",
        help=f"Umbral de palabras para considerar un listado fino (por defecto {THIN_WORDS})",
    )
    parser.add_argument(
        "--max-archives",
        type=int,
        default=DEFAULT_MAX_ARCHIVES,
        metavar="N",
        help=f"Maximo de listados a medir por dominio (por defecto {DEFAULT_MAX_ARCHIVES})",
    )
    parser.add_argument(
        "--allow-private",
        action="store_true",
        help="Permite dominios internos. Solo para probar contra un WordPress local.",
    )
    return parser


def main(argv: list[str] | None = None, client: Client | None = None) -> int:
    """Audita el lote y escribe la carpeta de envio.

    `client` es inyectable por el mismo motivo que en el auditor: asi esto se
    puede probar de punta a punta sin una sola peticion de red.
    """
    args = build_parser().parse_args(argv)

    domains = read_domains(args.domains)
    if not domains:
        print(f"{args.domains} no tiene ni un dominio. Nada que medir.")
        return 1

    # El espaciado lo lleva el cliente, y es UNO para todo el lote: por eso se
    # construye aqui y no dentro de run().
    batch = run(
        domains,
        client=client or Client(min_interval=args.interval),
        thin_words=args.thin_words,
        max_archives=args.max_archives,
        allow_private=args.allow_private,
    )

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    # Un solo build() por dominio: el informe cuesta lo mismo de generar que de
    # contar, y antes se generaba una vez para el fichero y otra para el indice.
    envios = [build(r.audit) if r.ok and r.audit is not None else None
              for r in batch.results]
    written = _write(batch, out, envios)

    print(batch.describe())
    for path in written:
        print(f"Informe: {path}")
    index = out / INDEX_NAME
    index.write_text(_index(batch, envios), encoding="utf-8")
    print(f"Indice del lote: {index}")

    # Codigo de salida util en una tarea programada: 1 si algo fallo.
    return 1 if batch.failed else 0


def _write(batch: BatchResult, out: Path,
           envios: list[Outreach | None]) -> list[Path]:
    """Un informe y un mensaje por dominio auditado. El orden es el de entrada."""
    written: list[Path] = []
    for outreach in envios:
        if outreach is None:
            continue
        report = out / f"{outreach.slug}.md"
        report.write_text(outreach.markdown, encoding="utf-8")
        message = out / f"{outreach.slug}{MESSAGE_SUFFIX}"
        message.write_text(outreach.summary + "\n", encoding="utf-8")
        written.append(report)
    return written


def _index(batch: BatchResult, envios: list[Outreach | None]) -> str:
    """Indice del lote: a quien se le puede escribir y a quien no, y por que."""
    lines: list[str] = []
    add = lines.append

    add("# Lote de prospeccion")
    add("")
    add(batch.describe())
    add("")
    add("| # | Dominio | Estado | Hallazgos | Hora de consulta |")
    add("|---|---|---|---|---|")
    for position, (result, outreach) in enumerate(zip(batch.results, envios),
                                                  start=1):
        if outreach is not None and result.audit is not None:
            count = len(outreach.findings)
            state = "auditado"
            if count:
                hallazgos = str(count)
            elif nothing_measured(result.audit):
                # No es lo mismo que "ninguno": aqui no se midio nada, y el
                # indice es lo que se mira para decidir a quien se le escribe.
                hallazgos = "SIN MEDIR (no se leyo el sitemap)"
            else:
                hallazgos = "ninguno (no se inventa)"
        else:
            state = "FALLO"
            hallazgos = result.error
        add(f"| {position} | {result.raw} | {state} | {hallazgos} "
            f"| {result.consulted_at} |")
    add("")

    if batch.failed:
        add("## Fallos")
        add("")
        add("Estos dominios no se midieron. El lote siguio con el resto:")
        add("")
        for result in batch.failed:
            add(f"- **{result.raw}**: {result.error}")
        add("")

    if batch.notes:
        add("## Notas")
        add("")
        for note in batch.notes:
            add(f"- {note}")
        add("")

    return "\n".join(lines)


if __name__ == "__main__":
    sys.exit(main())
