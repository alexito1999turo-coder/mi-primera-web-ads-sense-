"""Registros con procedencia por campo.

Cada valor sabe de donde salio y cuando se recogio. Sin eso no se puede
publicar una cifra agregada y defenderla, y defenderla es justo lo que separa
un dato propio de una invencion.
"""

from __future__ import annotations

import csv
import re
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path

ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


@dataclass
class Provenance:
    """De donde viene un registro. Es obligatoria, no decorativa."""

    source: str                  # quien lo dio: empresa, organismo, encuesta
    collected_at: str            # cuando se recogio, en ISO
    method: str                  # como: presupuesto pedido, registro publico...
    url: str = ""                # si es publico y verificable

    @property
    def valid(self) -> bool:
        return bool(
            self.source
            and self.method
            and ISO_DATE.match(self.collected_at or "")
        )

    def problems(self) -> list[str]:
        gaps: list[str] = []
        if not self.source:
            gaps.append("sin fuente")
        if not self.method:
            gaps.append("sin metodo de recogida")
        if not ISO_DATE.match(self.collected_at or ""):
            gaps.append("fecha de recogida ausente o no es AAAA-MM-DD")
        return gaps

    @property
    def year(self) -> int:
        try:
            return int(self.collected_at[:4])
        except (ValueError, TypeError):
            return 0


@dataclass
class Record:
    """Una observacion. `dims` son las dimensiones por las que se agrupa."""

    value: float
    unit: str
    dims: dict[str, str] = field(default_factory=dict)
    provenance: Provenance | None = None

    @property
    def usable(self) -> bool:
        return self.provenance is not None and self.provenance.valid

    def dim(self, name: str) -> str:
        return self.dims.get(name, "")


@dataclass
class Dataset:
    name: str
    unit: str = ""
    records: list[Record] = field(default_factory=list)
    rejected: list[tuple[int, list[str]]] = field(default_factory=list)

    @property
    def usable(self) -> list[Record]:
        return [r for r in self.records if r.usable]

    @property
    def size(self) -> int:
        return len(self.usable)

    @property
    def period(self) -> str:
        """El periodo real cubierto. No se declara mas amplio del que es."""
        years = sorted({r.provenance.year for r in self.usable if r.provenance})
        years = [y for y in years if y]
        if not years:
            return ""
        return str(years[0]) if len(years) == 1 else f"{years[0]}-{years[-1]}"

    @property
    def sources(self) -> list[str]:
        return sorted({r.provenance.source for r in self.usable if r.provenance})

    def dimensions(self) -> list[str]:
        names: set[str] = set()
        for record in self.usable:
            names.update(record.dims)
        return sorted(names)

    def describe(self) -> str:
        parte = f"{self.name}: {self.size} observacion(es) utilizables"
        if self.rejected:
            parte += f", {len(self.rejected)} descartada(s) por procedencia incompleta"
        if self.period:
            parte += f", periodo {self.period}"
        return parte + "."


def load(path: str | Path, name: str = "", unit: str = "") -> Dataset:
    """Carga un CSV de observaciones.

    Columnas reservadas: `valor`/`value`, `unidad`/`unit`, `fuente`/`source`,
    `fecha`/`date`, `metodo`/`method`, `url`. Cualquier otra columna se trata
    como dimension por la que se puede agrupar.
    """
    path = Path(path)
    data = Dataset(name=name or path.stem, unit=unit)

    with open(path, newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames:
            return data
        campos = {f.lower().strip(): f for f in reader.fieldnames}

        def col(*nombres: str) -> str | None:
            for nombre in nombres:
                if nombre in campos:
                    return campos[nombre]
            return None

        c_valor = col("valor", "value", "importe", "cifra")
        c_unidad = col("unidad", "unit")
        c_fuente = col("fuente", "source", "empresa", "proveedor")
        c_fecha = col("fecha", "date", "collected_at", "recogido")
        c_metodo = col("metodo", "método", "method")
        c_url = col("url", "enlace", "link")
        if not c_valor:
            raise ValueError(
                "El CSV no tiene columna de valor. Cabeceras: "
                + ", ".join(reader.fieldnames)
            )

        reservadas = {c for c in (c_valor, c_unidad, c_fuente, c_fecha, c_metodo, c_url) if c}

        for indice, fila in enumerate(reader, start=2):
            try:
                valor = float(str(fila.get(c_valor, "")).replace(",", ".").strip())
            except ValueError:
                data.rejected.append((indice, ["el valor no es un numero"]))
                continue

            prov = Provenance(
                source=(fila.get(c_fuente) or "").strip() if c_fuente else "",
                collected_at=(fila.get(c_fecha) or "").strip() if c_fecha else "",
                method=(fila.get(c_metodo) or "").strip() if c_metodo else "",
                url=(fila.get(c_url) or "").strip() if c_url else "",
            )
            if not prov.valid:
                data.rejected.append((indice, prov.problems()))
                continue

            dims = {
                k: (v or "").strip()
                for k, v in fila.items()
                if k not in reservadas and (v or "").strip()
            }
            unidad = (fila.get(c_unidad) or "").strip() if c_unidad else data.unit
            data.records.append(
                Record(value=valor, unit=unidad or data.unit, dims=dims, provenance=prov)
            )

    if not data.unit and data.usable:
        data.unit = data.usable[0].unit
    return data


def today() -> str:
    return date.today().isoformat()


def parse_date(raw: str) -> datetime | None:
    try:
        return datetime.strptime(raw, "%Y-%m-%d")
    except (ValueError, TypeError):
        return None
