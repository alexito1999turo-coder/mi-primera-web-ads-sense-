"""Firmas MinHash: parecido entre textos sin guardar los textos.

El problema practico: para detectar que una pagina repite otra hace falta
comparar sus frases, y guardar las frases de cada pagina publicada hace que el
fichero crezca sin limite. Con mil paginas de 1.500 palabras serian millones de
fragmentos.

La solucion clasica: de todos los fragmentos de un texto, guardar solo los K
hashes mas pequenos. La proporcion de hashes compartidos entre dos firmas
estima la proporcion de fragmentos compartidos, y el error baja con la raiz de
K. Con K=256 el fichero por pagina son dos kilobytes y el error ronda el 6%.

Aqui se usa bottom-k sobre un solo hash, que es la variante que mejor estima
Jaccard cuando los conjuntos tienen tamanos distintos.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field

TAMANO = 256
SHINGLE = 5
PALABRA = re.compile(r"[0-9A-Za-zÁÉÍÓÚÜÑáéíóúüñ][0-9A-Za-zÁÉÍÓÚÜÑáéíóúüñ'’\-]*")


def shingles(texto: str, tamano: int = SHINGLE) -> list[str]:
    palabras = [p.lower() for p in PALABRA.findall(texto)]
    if len(palabras) < tamano:
        return [" ".join(palabras)] if palabras else []
    return [" ".join(palabras[i:i + tamano]) for i in range(len(palabras) - tamano + 1)]


def _hash(fragmento: str) -> int:
    return int.from_bytes(hashlib.blake2b(fragmento.encode(), digest_size=8).digest(), "big")


@dataclass
class Sketch:
    """Los K hashes mas pequenos de un texto, y cuantos fragmentos tenia."""

    hashes: list[int] = field(default_factory=list)
    size: int = 0          # fragmentos distintos del original
    k: int = TAMANO

    @classmethod
    def of(cls, texto: str, k: int = TAMANO) -> "Sketch":
        unicos = {_hash(s) for s in shingles(texto)}
        return cls(hashes=sorted(unicos)[:k], size=len(unicos), k=k)

    @property
    def exact(self) -> bool:
        """Si cupo entero, el parecido que calcula no es estimado: es exacto."""
        return self.size <= self.k

    def to_dict(self) -> dict:
        return {"h": self.hashes, "n": self.size, "k": self.k}

    @classmethod
    def from_dict(cls, d: dict) -> "Sketch":
        return cls(hashes=list(d.get("h", [])), size=int(d.get("n", 0)),
                   k=int(d.get("k", TAMANO)))


def similarity(a: Sketch, b: Sketch) -> float:
    """Proporcion de fragmentos de la mas pequena que estan en la otra.

    Se usa el minimo como denominador, no la union, porque la pregunta operativa
    es «cuanto de esta pagina esta ya publicado», y una pagina corta copiada
    entera dentro de una larga tiene que dar casi uno.
    """
    if not a.hashes or not b.hashes:
        return 0.0
    if a.exact and b.exact:
        ia, ib = set(a.hashes), set(b.hashes)
        return len(ia & ib) / min(len(ia), len(ib))

    # Con firmas truncadas se compara sobre el prefijo comun, que es la forma
    # correcta de estimar con bottom-k de tamanos distintos.
    limite = min(max(a.hashes), max(b.hashes))
    pa = [h for h in a.hashes if h <= limite]
    pb = [h for h in b.hashes if h <= limite]
    if not pa or not pb:
        return 0.0
    comunes = len(set(pa) & set(pb))
    return comunes / min(len(pa), len(pb))


MAXIMO_HASH = 1 << 64


def merge(*sketches: Sketch, k: int | None = None) -> Sketch:
    """Firma de la union, calculada desde las firmas y sin los textos.

    Esta es la propiedad que hace que bottom-k sirva para una cartera: los K
    hashes mas pequenos de la union son los K mas pequenos del conjunto de
    todos los hashes guardados. Se puede ir acumulando la huella de un sitio
    pagina a pagina sin guardar ni una frase y sin que el fichero crezca.

    El tamano de la union no se puede saber desde las firmas, porque el solape
    entre ellas es justo lo que no se guardo. Si nada se trunco, la union es
    exacta y se cuenta. Si algo se trunco, se estima con el estimador de
    cardinalidad de bottom-k y la firma queda marcada como estimada, que es lo
    que corresponde decir.
    """
    vivos = [s for s in sketches if s.hashes]
    if not vivos:
        return Sketch(k=k or TAMANO)
    destino = k or min(s.k for s in vivos)
    union = sorted({h for s in vivos for h in s.hashes})[:destino]

    if all(s.exact for s in vivos):
        return Sketch(hashes=union, size=len(union), k=destino)

    # Estimador bottom-k: con los K hashes mas pequenos de un hash uniforme,
    # la cardinalidad es aproximadamente (K-1) * 2^64 / h_K.
    if len(union) < destino:
        estimado = len(union)
    else:
        estimado = max(destino + 1, round((destino - 1) * MAXIMO_HASH / union[-1]))
    return Sketch(hashes=union, size=estimado, k=destino)
