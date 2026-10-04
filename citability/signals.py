"""Senales de texto. Cada una es una hipotesis comprobable, no una corazonada."""

from __future__ import annotations

import re

# --- numeros ---------------------------------------------------------------

FIGURE = re.compile(
    r"(?:(?:\$|€)\s?\d[\d.,]*|\d[\d.,]*\s?(?:%|\$|€|usd|eur|euros|dolares|dólares|"
    r"años|anos|meses|dias|días|horas|minutos|litros|galones|metros|pies|kg|"
    r"libras|grados|veces|puntos))",
    re.I,
)

# Un numero redondo es consenso; uno preciso es una medicion.
#
# "unos 14.000 $" lo dice todo el mundo y el modelo lo saca de su propio peso.
# "14.237 $" solo puede venir de alguien que lo conto. Es la senal mas barata y
# mas discriminante de todo el modulo.
DIGITS = re.compile(r"[\d.,]+")


def is_round(figure: str) -> bool:
    """Decide si la cifra parece de consenso o medida.

    Antes era una expresion regular sobre subcadenas, y eso daba falsos
    positivos caros: en "15.498,50 $" encontraba el "50" de los decimales y
    la trataba como redonda, cuando es justo lo contrario — una cifra con
    decimales no redondos es la huella de una medicion.

    Reglas: si hay parte decimal distinta de cero, no es redonda. Si no, lo es
    cuando el entero acaba en dos ceros o mas (2.500, 14.000), o cuando tiene
    tres digitos o menos y acaba en cero (30, 500, 900).
    """
    m = DIGITS.search(figure)
    if not m:
        return False
    crudo = m.group(0).strip(".,")
    if not crudo:
        return False

    entero, decimal = crudo, ""
    # Un separador seguido de una o dos cifras al final es decimal; tres es
    # grupo de millar.
    ultimo = max(crudo.rfind("."), crudo.rfind(","))
    if ultimo != -1 and 1 <= len(crudo) - ultimo - 1 <= 2:
        entero, decimal = crudo[:ultimo], crudo[ultimo + 1:]

    if decimal and decimal.strip("0"):
        return False  # tiene decimales de verdad: es una medicion

    digitos = re.sub(r"\D", "", entero).lstrip("0")
    if not digitos:
        return False
    # Ceros a la derecha segun la magnitud: dos o mas siempre es redonda
    # (2.500, 14.000); con tres digitos o menos basta uno (30, 500).
    ceros = len(digitos) - len(digitos.rstrip("0"))
    if ceros >= 2:
        return True
    return len(digitos) <= 3 and ceros >= 1
# "entre" solo aproxima cuando va delante de una cifra: "entre 300 y 900 $" es
# una horquilla, pero "recogidos entre enero y junio" es un rango exacto de
# fechas. Sin esta distincion se penalizaba la frase mejor atribuida del texto.
APPROXIMATOR = re.compile(
    r"\b(?:unos|unas|aproximadamente|alrededor de|cerca de|mas o menos|"
    r"más o menos|en torno a|sobre los|about|around|roughly|hasta|"
    r"entre(?=\s+(?:\$|€)?\s*\d))\b",
    re.I,
)

# --- sujeto y anafora ------------------------------------------------------

# Una frase con cifra cuyo sujeto es un pronombre no se puede levantar: fuera
# del parrafo nadie sabe de que habla. Es el fallo mas comun del texto generado.
# "su coste" es anaforico (de quien?) y entra. "lo", "la" y "le" NO entran: al
# principio de una frase son articulo mucho mas a menudo que pronombre, y
# penalizar "La instalacion completa costo..." era un falso positivo que hundia
# frases perfectamente citables.
ANAPHORA_START = re.compile(
    r"^\s*(?:este|esta|estos|estas|ese|esa|esos|esas|aquel|aquella|aquellos|"
    r"aquellas|el mismo|la misma|dicho|dicha|dichos|dichas|su|sus|ello|eso|"
    r"esto|tambien|también|además|ademas|por eso|por tanto|por ello|asi|así|"
    r"it|this|that|these|those|they|their)\b",
    re.I,
)

# --- atribucion ------------------------------------------------------------

DATE = re.compile(r"\b(?:19|20)\d{2}\b|\b\d{1,2}/\d{1,2}/\d{2,4}\b")
METHOD = re.compile(
    r"\b(?:media|mediana|promedio|muestra|encuesta|medicion|medición|medimos|"
    r"recogidos|recogimos|analizamos|registro|registros|auditoria|auditoría|"
    r"presupuestos|casos|observaciones|segun nuestr|según nuestr|de nuestra|"
    r"de nuestro|propia|propio)\b",
    re.I,
)
MARKDOWN_LINK = re.compile(r"\[[^\]]+\]\((https?://[^)]+)\)")
NAMED_SOURCE = re.compile(r"\b(?:[A-Z]{2,6})\b|\b(?:segun|según)\s+[A-Z]\w+")

# --- especificidad ---------------------------------------------------------

# Un calificador acota el dato y lo hace irrepetible: no es "el coste", es "el
# coste en Texas en 2026 por tanque de 1.500 litros".
QUALIFIER = re.compile(
    r"\b(?:en|de|por|para|segun|según|bajo|durante|tras|con)\s+"
    r"(?:[A-Z]\w+|\d{4}|\d[\d.,]*\s?\w+)",
)

# --- alineacion con la pregunta -------------------------------------------

QUESTION_HEADING = re.compile(r"^#{2,4}\s+(.*\?)\s*$", re.M)
HEADING = re.compile(r"^#{1,4}\s+(.+)$", re.M)
SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")
WORD = re.compile(r"[0-9A-Za-zÁÉÍÓÚÜÑáéíóúüñ][0-9A-Za-zÁÉÍÓÚÜÑáéíóúüñ'’\-]*")

# Un modelo levanta de una a tres frases. Una frase de 60 palabras no cabe en
# una respuesta y una de 4 no dice nada.
LIFTABLE_MIN_WORDS = 8
LIFTABLE_MAX_WORDS = 45


def sentences_of(text: str) -> list[str]:
    """Frases, conservando los encabezados como frases propias.

    Las lineas de un mismo parrafo se unen ANTES de partir en frases. Sin esto,
    un texto con los parrafos ajustados a 80 columnas produce fragmentos, y los
    fragmentos puntuan mal por longitud y pierden la mitad de su atribucion: se
    estaba midiendo el ancho del fichero, no la calidad de la prosa.
    """
    out: list[str] = []
    buffer: list[str] = []

    def flush() -> None:
        if not buffer:
            return
        joined = " ".join(" ".join(buffer).split())
        out.extend(s.strip() for s in SENTENCE_SPLIT.split(joined) if s.strip())
        buffer.clear()

    for raw in text.split("\n"):
        line = raw.strip()
        if not line:
            flush()
            continue
        if line.startswith("#"):
            flush()
            out.append(line)
            continue
        buffer.append(line)
    flush()
    return out


def strip_links(text: str) -> str:
    """Deja el texto del ancla y quita la URL, que no es prosa."""
    return MARKDOWN_LINK.sub(lambda m: m.group(0).split("](")[0][1:], text)


APPROXIMATOR_REACH = 24


def is_precise(text: str) -> bool:
    """Hay alguna cifra que parezca medida y no estimada.

    El aproximador se comprueba PEGADO a cada cifra, no en toda la frase. Una
    frase puede llevar "unos 30 dias" y tambien "14.237 $": la segunda sigue
    siendo una medicion, y vetar la frase entera por la primera perdia la senal.
    """
    for match in FIGURE.finditer(text):
        figure = match.group(0)
        if is_round(figure):
            continue
        before = text[max(0, match.start() - APPROXIMATOR_REACH) : match.start()]
        if APPROXIMATOR.search(before):
            continue
        return True
    return False
