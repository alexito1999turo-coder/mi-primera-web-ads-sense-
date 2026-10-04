"""El almacen de la cartera: la guarda que no cabe en un solo sitio.

`compliance.fingerprint` compara sitios entre si, pero exigia tener todos los
cuerpos de todas las paginas de todos los clientes en memoria a la vez. Con
veinte clientes eso no se hace nunca, asi que la guarda mas importante del
sistema — la del quinto patron, repartir la salida entre varios sitios para
ocultar la escala — era la que no se ejecutaba.

Aqui se arregla cambiando lo que se guarda. Por cada sitio: una firma MinHash
acumulada y el conjunto de encabezados distintos. Las dos crecen hacia un
techo, no con el numero de paginas:

  - La firma es de tamano fijo y las paginas nuevas se fusionan dentro.
  - Los encabezados se guardan sin repetir, y un sitio con plantilla tiene
    pocos encabezados distintos por definicion. Lo que delata la plantilla es
    justo lo que hace el fichero pequeno.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from compliance.fingerprint import (
    MAX_OUTLINE_SIMILARITY,
    MAX_PHRASE_SIMILARITY,
    Collision,
    PortfolioAudit,
    outline,
)

from .archivo import Esquema, read_json, write_json
from .sketch import Sketch, merge, similarity

CARTERA = "cartera.json"
ESQUEMA = Esquema(version=1, migraciones={})


def _ahora() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@dataclass
class SiteRecord:
    """Lo que la cartera guarda de un sitio, en tamano acotado."""

    site: str
    sketch: Sketch = field(default_factory=Sketch)
    headings: set[str] = field(default_factory=set)
    pages: int = 0
    updated: str = ""

    def add_page(self, body: str) -> None:
        self.sketch = merge(self.sketch, Sketch.of(body))
        self.headings |= set(outline(body))
        self.pages += 1
        self.updated = _ahora()

    def to_dict(self) -> dict:
        return {"sketch": self.sketch.to_dict(),
                "headings": sorted(self.headings),
                "pages": self.pages, "updated": self.updated}

    @classmethod
    def from_dict(cls, site: str, row: dict) -> "SiteRecord":
        return cls(site=site, sketch=Sketch.from_dict(row.get("sketch") or {}),
                   headings=set(row.get("headings") or []),
                   pages=int(row.get("pages", 0)),
                   updated=row.get("updated", ""))


def _heading_similarity(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / min(len(a), len(b))


class PortfolioStore:
    """La cartera entera en un fichero que se puede abrir y leer."""

    def __init__(self, root: str | Path):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.path = self.root / CARTERA
        data = read_json(self.path, default=None) or {"schema": ESQUEMA.version,
                                                      "sites": {}}
        data, self.migrations = ESQUEMA.upgrade(data)
        self.sites: dict[str, SiteRecord] = {
            site: SiteRecord.from_dict(site, row)
            for site, row in (data.get("sites") or {}).items()
        }

    def add_page(self, site: str, body: str) -> SiteRecord:
        registro = self.sites.setdefault(site, SiteRecord(site=site))
        registro.add_page(body)
        self._flush()
        return registro

    def drop_site(self, site: str) -> bool:
        """Un cliente que se va sale de la cartera: ya no es nuestra escala."""
        if site not in self.sites:
            return False
        del self.sites[site]
        self._flush()
        return True

    def audit(self) -> PortfolioAudit:
        """Mismos umbrales que `compliance.fingerprint`, sobre las firmas.

        El parecido de frases sale de las firmas, asi que es una estimacion. Se
        compara igual contra el mismo umbral, porque un 8% estimado con un
        error del 6% ya es motivo de mirar el par a mano: la guarda tiene que
        avisar, no sentenciar.
        """
        registros = list(self.sites.values())
        resultado = PortfolioAudit(sites=len(registros))
        for indice, primero in enumerate(registros):
            for segundo in registros[indice + 1:]:
                resultado.collisions.append(Collision(
                    site_a=primero.site, site_b=segundo.site,
                    phrase_similarity=round(
                        similarity(primero.sketch, segundo.sketch), 4),
                    outline_similarity=round(
                        _heading_similarity(primero.headings,
                                            segundo.headings), 4),
                ))
        return resultado

    def would_collide(self, site: str, body: str) -> list[Collision]:
        """Comprueba una pagina ANTES de publicarla, contra el resto de sitios.

        Es la version util de la guarda. Auditar la cartera despues de publicar
        encuentra el problema cuando ya esta en Google; esto lo encuentra
        cuando todavia es un borrador.
        """
        candidata = Sketch.of(body)
        encabezados = set(outline(body))
        salida: list[Collision] = []
        for otro, registro in self.sites.items():
            if otro == site:
                continue
            salida.append(Collision(
                site_a=f"{site} (borrador)", site_b=otro,
                phrase_similarity=round(similarity(candidata, registro.sketch), 4),
                outline_similarity=round(
                    _heading_similarity(encabezados, registro.headings), 4),
            ))
        return sorted(salida, key=lambda c: -c.phrase_similarity)

    def _flush(self) -> None:
        write_json(self.path, {
            "schema": ESQUEMA.version,
            "updated": _ahora(),
            "sites": {s: r.to_dict() for s, r in self.sites.items()},
        })

    def describe(self) -> str:
        if not self.sites:
            return "Cartera vacia: no hay huella cruzada que medir."
        paginas = sum(r.pages for r in self.sites.values())
        peso = self.path.stat().st_size if self.path.exists() else 0
        auditoria = self.audit()
        lineas = [
            f"Cartera: {len(self.sites)} sitio(s), {paginas} pagina(s), "
            f"{peso} bytes en disco",
            f"  umbrales: frases {MAX_PHRASE_SIMILARITY * 100:.0f}%, "
            f"esqueleto {MAX_OUTLINE_SIMILARITY * 100:.0f}%",
            f"  {auditoria.describe()}",
        ]
        for colision in auditoria.blocking:
            lineas.append(f"  {colision.describe()}")
        return "\n".join(lineas)
