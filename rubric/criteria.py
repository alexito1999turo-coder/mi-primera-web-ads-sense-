"""Criterios binarios. Cada uno se contesta con si o no, sin escala.

Una escala del 1 al 5 invita a poner un 3 cuando no se sabe. Un criterio
binario obliga a decidir, y dos personas que apliquen el mismo criterio binario
coinciden mucho mas que dos que repartan estrellas.
"""

from __future__ import annotations

from dataclasses import dataclass, field

# Defectos que se pueden inyectar a proposito en un articulo. La clave se anota
# antes de la prueba; el segundo campo son las compuertas que DEBERIAN cazarlo.
#
# Es una familia y no una sola compuerta porque algunas se excluyen entre si por
# construccion: si se quitan TODOS los enlaces salta "sin_fuentes_enlazadas" y
# nunca "fuente_obligatoria_ausente", que solo se comprueba cuando hay enlaces.
# Exigir las dos marcaba como fallo algo que el codigo hace bien.
DEFECTS: dict[str, tuple[str, tuple[str, ...]]] = {
    "cifra_sin_fuente": (
        "Una afirmacion con cifra sin fuente enlazada cerca",
        ("afirmacion_sin_respaldo",),
    ),
    "dato_propio_omitido": (
        "El dato propio del brief no aparece en el cuerpo",
        ("dato_propio_ausente",),
    ),
    "fuente_no_citada": (
        "La fuente obligatoria del brief no se enlaza",
        ("sin_fuentes_enlazadas", "fuente_obligatoria_ausente"),
    ),
    "relleno_de_keyword": (
        "La keyword primaria repetida hasta pasar el umbral de densidad",
        ("densidad_anomala",),
    ),
    "corto": (
        "Articulo por debajo del minimo de palabras de su rol",
        ("longitud_insuficiente",),
    ),
    "copiado_de_otra": (
        "Reutiliza parrafos de una pagina ya publicada",
        ("solape_con_publicado",),
    ),
    "frases_no_citables": (
        "Los datos van en frases que empiezan por pronombre y sin ano",
        ("sin_frase_citable", "citabilidad_pobre"),
    ),
    "secundaria_olvidada": (
        "La keyword secundaria no aparece",
        ("secundaria_ausente",),
    ),
}


@dataclass
class Criterion:
    """Un criterio binario de la rubrica."""

    key: str
    question: str
    # Si la respuesta esperada para un articulo correcto es si o no.
    expected: bool = True


RUBRIC: list[Criterion] = [
    Criterion("fuente_en_cuerpo", "¿Toda cifra o superlativo tiene una fuente enlazada en su frase o la siguiente?"),
    Criterion("dato_propio", "¿Aparece literal en el cuerpo el dato propio del brief, con su metodo?"),
    Criterion("longitud", "¿Alcanza el minimo de palabras que pide su rol?"),
    Criterion("sin_relleno", "¿Esta libre de frases cuya unica funcion es repetir la keyword?"),
    Criterion("original", "¿No repite parrafos de otra pagina del mismo sitio?"),
    Criterion("citable", "¿Hay al menos una frase que un modelo podria levantar entera y atribuir?"),
    Criterion("contesta", "¿Contesta las preguntas del brief en las primeras lineas de su seccion?"),
    Criterion("cobertura", "¿Cubre las keywords secundarias sin forzarlas?"),
]


@dataclass
class Specimen:
    """Un articulo de la prueba, con sus defectos anotados DE ANTEMANO."""

    slug: str
    body: str
    injected: set[str] = field(default_factory=set)

    @property
    def clean(self) -> bool:
        return not self.injected

    def expected_families(self) -> list[tuple[str, tuple[str, ...]]]:
        """Por cada defecto anotado, las compuertas que valdrian para cazarlo."""
        return [(d, DEFECTS[d][1]) for d in sorted(self.injected) if d in DEFECTS]

    def expected_gates(self) -> set[str]:
        """Todas las compuertas que podrian cazar los defectos anotados."""
        return {g for _d, familia in self.expected_families() for g in familia}

    def describe(self) -> str:
        if self.clean:
            return f"{self.slug}: sin defectos inyectados"
        return f"{self.slug}: {', '.join(sorted(self.injected))}"
