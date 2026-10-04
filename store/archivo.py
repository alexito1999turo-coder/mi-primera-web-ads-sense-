"""Primitivas de disco: escritura atomica e historico de solo anadir.

Aqui no hay nada ingenioso a proposito. Es el sitio del sistema donde un fallo
no se nota hasta que ya ha pasado, y lo que evita eso es hacer lo aburrido bien:

  - Nunca se escribe encima de un fichero bueno. Se escribe al lado y se
    renombra, que en POSIX es atomico: o esta el viejo entero o el nuevo
    entero, nunca medio fichero.
  - Nunca se reescribe el historico. Una medicion equivocada se corrige
    anadiendo la correccion, no borrando el error. Borrar el pasado deja un
    sistema que no puede explicar como llego a sus numeros.
"""

from __future__ import annotations

import json
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Iterator


def write_atomic(path: str | Path, text: str) -> None:
    """Escribe por fichero temporal y renombrado.

    `fsync` antes del renombrado no es paranoia gratis: sin el, el renombrado
    puede llegar al disco antes que el contenido y un corte deja un fichero
    nuevo vacio, que es peor que no haber escrito.
    """
    destino = Path(path)
    destino.parent.mkdir(parents=True, exist_ok=True)
    fd, temporal = tempfile.mkstemp(dir=str(destino.parent), prefix=".tmp-",
                                    suffix=destino.suffix)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(text)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(temporal, destino)
    except BaseException:
        Path(temporal).unlink(missing_ok=True)
        raise


def write_json(path: str | Path, payload: Any) -> None:
    write_atomic(path, json.dumps(payload, indent=2, ensure_ascii=False,
                                  sort_keys=True) + "\n")


def read_json(path: str | Path, default: Any = None) -> Any:
    fichero = Path(path)
    if not fichero.exists():
        return default
    texto = fichero.read_text(encoding="utf-8")
    if not texto.strip():
        return default
    return json.loads(texto)


def append_line(path: str | Path, payload: Any) -> None:
    """Anade una linea al historico y la fuerza a disco.

    Se abre en modo `a` en cada llamada a proposito: un fichero abierto durante
    toda la ejecucion es un buffer que se pierde si el proceso muere, y el
    historico es justo lo que no se puede perder.
    """
    fichero = Path(path)
    fichero.parent.mkdir(parents=True, exist_ok=True)
    linea = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    with open(fichero, "a", encoding="utf-8") as fh:
        # Si lo ultimo que hay en el fichero es una linea a medias, hay que
        # cerrarla antes de escribir. Sin esto, el apunte nuevo se pega a la
        # linea rota y se pierden DOS registros: el roto por el corte y el
        # bueno que se acaba de escribir. Lo encontro su propio test, que
        # esperaba perder uno y perdia dos.
        if _acaba_sin_salto(fichero):
            fh.write("\n")
        fh.write(linea + "\n")
        fh.flush()
        os.fsync(fh.fileno())


def _acaba_sin_salto(fichero: Path) -> bool:
    try:
        tamano = fichero.stat().st_size
    except OSError:
        return False
    if tamano == 0:
        return False
    with open(fichero, "rb") as fh:
        fh.seek(-1, os.SEEK_END)
        return fh.read(1) != b"\n"


def read_lines(path: str | Path) -> Iterator[dict]:
    """Lee el historico saltandose lineas corruptas.

    Una linea a medias solo puede ser la ultima, por un corte durante la
    escritura. Abortar la lectura entera por ella seria perder todo el
    historico por un byte.
    """
    fichero = Path(path)
    if not fichero.exists():
        return
    with open(fichero, "r", encoding="utf-8") as fh:
        for linea in fh:
            linea = linea.strip()
            if not linea:
                continue
            try:
                row = json.loads(linea)
            except json.JSONDecodeError:
                continue
            if isinstance(row, dict):
                yield row


# -- esquema versionado ---------------------------------------------------
#
# El fichero lleva su version dentro. Cuando el formato cambia se declara una
# migracion y los datos viejos siguen leyendose. La alternativa real no es
# «no cambiar el formato»: es un KeyError dentro de seis meses sobre el unico
# fichero que no se puede regenerar.

Migracion = Callable[[dict], dict]


@dataclass
class Esquema:
    version: int
    migraciones: dict[int, Migracion]

    def upgrade(self, data: dict) -> tuple[dict, list[str]]:
        actual = int(data.get("schema", 1))
        if actual > self.version:
            raise ValueError(
                f"El fichero es de esquema {actual} y este codigo entiende "
                f"hasta {self.version}. Actualiza el codigo antes de abrirlo: "
                "escribirlo con un esquema viejo perderia campos."
            )
        pasos: list[str] = []
        while actual < self.version:
            migracion = self.migraciones.get(actual)
            if migracion is None:
                raise ValueError(
                    f"Falta la migracion de esquema {actual} a {actual + 1}."
                )
            data = migracion(data)
            actual += 1
            data["schema"] = actual
            pasos.append(f"esquema {actual - 1} -> {actual}")
        data["schema"] = self.version
        return data, pasos
