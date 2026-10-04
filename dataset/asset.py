"""El activo enlazable: la pagina de datos.

Esto es lo que sustituye a su red reciproca de enlaces. Un dataset con metodo
declarado y cifras que no existen en otro sitio se enlaza solo, se cita en las
respuestas generadas porque es la fuente del numero, y no es un esquema de
enlaces por ninguna definicion.

Mas lento y mas caro que intercambiar enlaces. Tambien es lo unico que no se
cae con una actualizacion de spam.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .aggregate import Figure, compute, publishable
from .records import Dataset, today


@dataclass
class AssetPage:
    title: str
    slug: str
    markdown: str
    figures: list[Figure] = field(default_factory=list)
    withheld: list[Figure] = field(default_factory=list)

    @property
    def citable_sentences(self) -> list[str]:
        return [f.sentence(f.label.split(" — ")[0]) for f in self.figures]


def build(
    data: Dataset,
    title: str,
    subject: str,
    group_by: list[str] | None = None,
    statistic: str = "mediana",
    slug: str = "",
    author: str = "",
) -> AssetPage:
    """Construye la pagina de datos a partir del dataset."""
    globales = compute(data, statistic, label=subject)
    por_grupo = compute(data, statistic, group_by=group_by or [], label=subject) \
        if group_by else []
    todas = globales + [f for f in por_grupo if f.dims]

    buenas = publishable(todas)
    retenidas = [f for f in todas if not f.publishable]

    lineas: list[str] = [f"# {title}", ""]
    lineas.append(
        f"Datos propios recogidos por {author or 'nosotros'}. "
        f"{data.size} observaciones utilizables"
        + (f" del periodo {data.period}" if data.period else "")
        + f", de {len(data.sources)} fuentes distintas. "
        "Consultado y publicado el " + today() + "."
    )
    lineas.append("")

    # La cifra principal va primera y en su propia frase citable.
    if buenas:
        lineas += ["## " + _pregunta(subject), "", buenas[0].sentence(subject), ""]

    if len(buenas) > 1:
        dimension = (group_by or ["grupo"])[0]
        lineas += [f"## Desglose por {dimension}", "",
                   f"| {dimension.capitalize()} | {statistic.capitalize()} | "
                   "Observaciones | Periodo |",
                   "|---|---|---|---|"]
        for figura in buenas[1:]:
            lineas.append(
                f"| {figura.where or '—'} | {figura.formatted} | {figura.n} | "
                f"{figura.period or '—'} |"
            )
        lineas.append("")
        for figura in buenas[1:]:
            # El sujeto NO lleva el lugar: la frase ya lo anade. Ponerlo en los
            # dos sitios daba "en Bexar ... en Bexar".
            lineas.append(figura.sentence(subject))
        lineas.append("")

    # Lo que NO se publica y por que. Es la parte que da credibilidad al resto.
    if retenidas:
        lineas += ["## Lo que no publicamos", "",
                   "Estos grupos tienen muestra insuficiente. Darlos por "
                   "medicion seria dar por buena una anecdota con decimales:",
                   ""]
        for figura in retenidas:
            lineas.append(f"- **{figura.where or figura.label}**: {figura.why_not}")
        lineas.append("")

    lineas += ["## Metodo", ""]
    metodos = sorted({r.provenance.method for r in data.usable if r.provenance})
    for metodo in metodos:
        lineas.append(f"- {metodo}")
    lineas += ["",
               f"Fuentes: {len(data.sources)} distintas"
               + (f" ({', '.join(data.sources[:8])}" +
                  (", y mas" if len(data.sources) > 8 else "") + ")"
                  if data.sources else "") + ".",
               ""]
    if data.rejected:
        lineas += [
            f"Se descartaron {len(data.rejected)} observaciones por procedencia "
            "incompleta: sin fuente, sin fecha de recogida o sin metodo. No se "
            "usa un dato que no se puede defender.",
            "",
        ]

    return AssetPage(
        title=title,
        slug=slug or _slug(title),
        markdown="\n".join(lineas),
        figures=buenas,
        withheld=retenidas,
    )


def _pregunta(subject: str) -> str:
    """El encabezado en forma de pregunta, que el motor de citabilidad premia.

    Partir el sujeto por " de " producia frases rotas ("cuanto cuesta
    instalacion de un sistema"). Se conserva el sujeto entero: menos elegante,
    pero siempre gramatical, y una pregunta mal escrita en la pagina de datos
    tira por tierra justo lo que la pagina quiere demostrar.
    """
    limpio = subject.strip().rstrip(".")
    bajo = limpio.lower()
    if bajo.startswith(("el coste", "el precio", "el importe")):
        return f"¿Cuánto es {bajo}?"
    return f"¿Cuál es {bajo}?"


def _slug(texto: str) -> str:
    import re
    import unicodedata

    plano = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", plano.lower()).strip("-")
