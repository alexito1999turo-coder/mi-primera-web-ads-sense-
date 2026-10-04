"""Genera variantes con defectos a partir de un articulo correcto.

Las variantes se construyen mecanicamente, no a mano, por dos razones: el
defecto queda anotado exactamente igual que se inyecta, y el experimento se
puede repetir sobre cualquier articulo sin reescribirlo.
"""

from __future__ import annotations

import re

from .criteria import Specimen

MARKDOWN_LINK = re.compile(r"\[([^\]]+)\]\((https?://[^)]+)\)")


def quitar_fuentes(texto: str) -> str:
    """Deja el texto del ancla y se lleva el enlace: la cifra queda sin respaldo."""
    return MARKDOWN_LINK.sub(lambda m: m.group(1), texto)


def quitar_dato_propio(texto: str, marcador: str) -> str:
    return texto.replace(marcador, "una cantidad considerable")


def recortar(texto: str, palabras: int = 300) -> str:
    trozos = texto.split()
    return " ".join(trozos[:palabras])


def rellenar_keyword(texto: str, keyword: str, veces: int = 45) -> str:
    relleno = ("\n\n## Mas sobre el tema\n\n"
               + f"{keyword.capitalize()}. " * veces)
    return texto + relleno


def despersonalizar(texto: str) -> str:
    """Convierte las frases citables en frases que empiezan por pronombre.

    Es el defecto mas sutil de la lista: el articulo sigue diciendo la verdad y
    sigue teniendo sus fuentes, pero ningun modelo puede levantar una frase
    porque ninguna se sostiene fuera de su parrafo.
    """
    salida = []
    for linea in texto.split("\n"):
        if linea.startswith(("#", "-", "1.", "2.", "3.", "4.", "5.")) or not linea.strip():
            salida.append(linea)
            continue
        linea = re.sub(r"^(La|El|Los|Las)\s+\w+", "Este", linea)
        linea = linea.replace(" en 2026", "").replace(" de 2026", "")
        linea = linea.replace("sobre una muestra propia de 30 presupuestos reales "
                              "pedidos por telefono entre enero y junio", "segun vimos")
        linea = linea.replace("en esa misma muestra de 30 presupuestos", "")
        salida.append(linea)
    return "\n".join(salida)


def variantes(slug: str, cuerpo: str, keyword: str, marcador: str) -> list[Specimen]:
    """El articulo limpio y cinco variantes con defectos anotados."""
    return [
        Specimen(slug=slug, body=cuerpo),
        Specimen(slug=slug + "-sin-fuentes", body=quitar_fuentes(cuerpo),
                 injected={"cifra_sin_fuente", "fuente_no_citada"}),
        Specimen(slug=slug + "-sin-dato", body=quitar_dato_propio(cuerpo, marcador),
                 injected={"dato_propio_omitido"}),
        Specimen(slug=slug + "-corto", body=recortar(cuerpo),
                 injected={"corto"}),
        Specimen(slug=slug + "-relleno", body=rellenar_keyword(cuerpo, keyword),
                 injected={"relleno_de_keyword"}),
        Specimen(slug=slug + "-no-citable", body=despersonalizar(cuerpo),
                 injected={"frases_no_citables"}),
    ]
