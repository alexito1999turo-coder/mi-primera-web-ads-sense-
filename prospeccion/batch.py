"""Recorrido de una lista de dominios, reutilizando el auditor tal cual.

Aqui no hay nada de SEO. Todo el criterio esta en auditor/: este modulo solo
sabe de tres cosas que el auditor no sabe, porque audita un sitio a la vez y no
cuarenta:

  1. Aislamiento. Un dominio que revienta no puede tumbar el lote. Se guarda el
     motivo en el resultado de ESE dominio y se sigue con el siguiente.
  2. Orden. La lista sale en el mismo orden en que entro, fallos incluidos, para
     que el fichero de dominios y la carpeta de informes se puedan leer en
     paralelo sin cruzar nada.
  3. Cortesia acumulada. Un unico Client para todo el lote, asi el espaciado
     minimo entre peticiones se respeta tambien al cambiar de dominio. Cuarenta
     auditorias seguidas con el cliente por defecto de cada una serian cuarenta
     rafagas.

Compartir el cliente tiene un precio que se paga aqui: `auditor.audit.run`
declara como peticiones de la auditoria el contador absoluto del cliente, que
con un cliente por auditoria es el delta correcto y con uno compartido no. Ese
numero acaba en la primera linea del informe que lee la marca, asi que al
cerrar cada dominio se reescribe con las peticiones que de verdad se le
hicieron a EL. El arreglo de fondo va en auditor/audit.py.

Las guardas no se reimplementan, se piden:
  - robots.txt lo respeta `auditor.audit.run`, que comprueba `allows(url)` antes
    de cada peticion.
  - el espaciado lo impone `auditor.http.Client.min_interval`.
  - el bloqueo de direcciones privadas vive en `webapp.api.normalize_site`, que
    es el UNICO sitio del repo donde existe, y se llama desde aqui por eso. Un
    modulo que use `Client` directamente no hereda ninguna proteccion.

AVISO, dicho en voz alta porque es el estado real y no se arregla de tapadillo:
ese filtro es textual sobre el netloc, no sobre la IP resuelta. Un nombre
publico que resuelva a 127.0.0.1 lo pasa. Si el lote va a comerse una lista de
dominios de origen desconocido, eso es lo que hay que endurecer, y hay que
hacerlo en webapp/api.py para que lo herede todo el repo.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from auditor.audit import Audit, run as run_audit
from auditor.http import DEFAULT_MIN_INTERVAL, Client
from auditor.rules import THIN_WORDS
from webapp.api import BadRequest, normalize_site

DEFAULT_MAX_ARCHIVES = 40
COMMENT = "#"


@dataclass
class ProspectResult:
    """Un dominio del lote, con su hora de consulta y su fallo si lo hubo."""

    raw: str
    site: str = ""
    audit: Audit | None = None
    consulted_at: str = ""
    requests_made: int = 0
    error: str = ""

    @property
    def ok(self) -> bool:
        return self.audit is not None and not self.error


@dataclass
class BatchResult:
    """El lote entero. `results` conserva el orden de entrada, fallos incluidos."""

    results: list[ProspectResult] = field(default_factory=list)
    started_at: str = ""
    finished_at: str = ""
    requests_made: int = 0
    notes: list[str] = field(default_factory=list)

    @property
    def audited(self) -> list[ProspectResult]:
        return [r for r in self.results if r.ok]

    @property
    def failed(self) -> list[ProspectResult]:
        return [r for r in self.results if not r.ok]

    def describe(self) -> str:
        """Una linea para el log del lunes por la manana."""
        return (
            f"{len(self.audited)} de {len(self.results)} dominios auditados, "
            f"{len(self.failed)} con fallo, {self.requests_made} peticiones "
            f"espaciadas entre {self.started_at} y {self.finished_at}."
        )


# -- entrada de dominios ----------------------------------------------------

def parse_domains(text: str) -> list[str]:
    """Un dominio por linea. Se permiten comentarios con # y lineas en blanco.

    Se respeta el orden y se descartan los repetidos, que en una lista pegada a
    mano desde una hoja de calculo son la norma y no la excepcion. El esquema no
    cuenta para decidir si algo es repetido: "ejemplo.test" y
    "https://ejemplo.test" son el mismo sitio, y colarlos los dos significa
    pedirle el doble de peticiones al mismo desconocido y escribir su informe
    dos veces sobre el mismo fichero.
    """
    out: list[str] = []
    seen: set[str] = set()
    for line in text.splitlines():
        entry = line.split(COMMENT, 1)[0].strip()
        if not entry:
            continue
        key = entry.lower().split("://", 1)[-1].rstrip("/")
        if key in seen:
            continue
        seen.add(key)
        out.append(entry)
    return out


def read_domains(path: str | Path) -> list[str]:
    """Lee el fichero de dominios. Es la entrada del lote, no una base de datos."""
    with open(path, encoding="utf-8-sig") as handle:
        return parse_domains(handle.read())


# -- el lote ----------------------------------------------------------------

def run(
    domains: list[str],
    client: Client | None = None,
    interval: float = DEFAULT_MIN_INTERVAL,
    thin_words: int = THIN_WORDS,
    max_archives: int = DEFAULT_MAX_ARCHIVES,
    allow_private: bool = False,
) -> BatchResult:
    """Audita cada dominio en orden. Un fallo se registra y el lote sigue.

    `client` es pato, como en el auditor: cualquier objeto con `.get(url)` y
    `.request_count`. Si no se pasa ninguno se crea uno real con el espaciado
    pedido, y es el mismo para todo el lote.
    """
    batch = BatchResult(started_at=_now())
    client = client or Client(min_interval=interval)
    # El contador del cliente es acumulado y el cliente se comparte a proposito,
    # asi que lo que cuenta este lote es el delta desde aqui. Sumar el absoluto
    # haria que el segundo lote de la manana declarase peticiones que no hizo.
    opening_count = client.request_count

    for raw in domains:
        before = client.request_count
        result = ProspectResult(raw=raw, consulted_at=_now())
        try:
            # El unico bloqueo de direcciones privadas del repo esta aqui dentro.
            result.site = normalize_site(raw, allow_private=allow_private)
            result.audit = run_audit(
                result.site,
                client=client,
                thin_words=thin_words,
                max_archives=max_archives,
            )
        except BadRequest as exc:
            # Dominio que no deberiamos pedir: ni se intenta la peticion.
            result.error = f"Dominio rechazado: {exc}"
        except Exception as exc:  # noqa: BLE001 - un dominio no tumba el lote
            # El cliente real se come la red, el DNS y el TLS y devuelve
            # Response(status=0). Lo que llega hasta aqui es lo inesperado: HTML
            # que rompe el parser, un sitemap monstruoso, un doble mal puesto.
            # Se anota con el tipo de excepcion, que es lo que permite arreglarlo.
            result.error = f"{type(exc).__name__}: {exc}"
        # `auditor.audit.run` ya guarda su propio delta, asi que lo que cuenta
        # aqui coincide con lo que el informe de ese dominio declara.
        result.requests_made = client.request_count - before
        batch.results.append(result)

    batch.requests_made = client.request_count - opening_count
    batch.finished_at = _now()

    if not domains:
        batch.notes.append("La lista de dominios estaba vacia: no se midio nada.")
    for failure in batch.failed:
        batch.notes.append(f"{failure.raw}: {failure.error}")
    return batch


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")
