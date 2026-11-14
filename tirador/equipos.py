"""Resolución de equipos: nombre en español -> bandera o escudo.

Selecciones: bandera redonda desde flagcdn (dominio público).
Clubes: escudo oficial desde TheSportsDB.
"""
from __future__ import annotations

import unicodedata
from dataclasses import dataclass

# nombre normalizado -> (código flagcdn, nombre en inglés)
SELECCIONES = {
    "alemania": ("de", "Germany"), "albania": ("al", "Albania"), "andorra": ("ad", "Andorra"),
    "armenia": ("am", "Armenia"), "austria": ("at", "Austria"), "azerbaiyan": ("az", "Azerbaijan"),
    "belgica": ("be", "Belgium"), "bielorrusia": ("by", "Belarus"),
    "bosnia": ("ba", "Bosnia and Herzegovina"), "bosnia y herzegovina": ("ba", "Bosnia and Herzegovina"),
    "bulgaria": ("bg", "Bulgaria"), "chipre": ("cy", "Cyprus"), "croacia": ("hr", "Croatia"),
    "dinamarca": ("dk", "Denmark"), "escocia": ("gb-sct", "Scotland"), "eslovaquia": ("sk", "Slovakia"),
    "eslovenia": ("si", "Slovenia"), "espana": ("es", "Spain"), "estonia": ("ee", "Estonia"),
    "finlandia": ("fi", "Finland"), "francia": ("fr", "France"), "gales": ("gb-wls", "Wales"),
    "georgia": ("ge", "Georgia"), "gibraltar": ("gi", "Gibraltar"), "grecia": ("gr", "Greece"),
    "hungria": ("hu", "Hungary"), "inglaterra": ("gb-eng", "England"), "irlanda": ("ie", "Republic of Ireland"),
    "irlanda del norte": ("gb-nir", "Northern Ireland"), "islandia": ("is", "Iceland"),
    "islas feroe": ("fo", "Faroe Islands"), "israel": ("il", "Israel"), "italia": ("it", "Italy"),
    "kazajistan": ("kz", "Kazakhstan"), "kosovo": ("xk", "Kosovo"), "letonia": ("lv", "Latvia"),
    "liechtenstein": ("li", "Liechtenstein"), "lituania": ("lt", "Lithuania"),
    "luxemburgo": ("lu", "Luxembourg"), "macedonia del norte": ("mk", "North Macedonia"),
    "malta": ("mt", "Malta"), "moldavia": ("md", "Moldova"), "montenegro": ("me", "Montenegro"),
    "noruega": ("no", "Norway"), "paises bajos": ("nl", "Netherlands"), "holanda": ("nl", "Netherlands"),
    "polonia": ("pl", "Poland"), "portugal": ("pt", "Portugal"), "republica checa": ("cz", "Czech Republic"),
    "chequia": ("cz", "Czech Republic"), "rumania": ("ro", "Romania"), "rusia": ("ru", "Russia"),
    "san marino": ("sm", "San Marino"), "serbia": ("rs", "Serbia"), "suecia": ("se", "Sweden"),
    "suiza": ("ch", "Switzerland"), "turquia": ("tr", "Turkey"), "ucrania": ("ua", "Ukraine"),
    # resto del mundo
    "argentina": ("ar", "Argentina"), "brasil": ("br", "Brazil"), "uruguay": ("uy", "Uruguay"),
    "colombia": ("co", "Colombia"), "chile": ("cl", "Chile"), "peru": ("pe", "Peru"),
    "ecuador": ("ec", "Ecuador"), "paraguay": ("py", "Paraguay"), "bolivia": ("bo", "Bolivia"),
    "venezuela": ("ve", "Venezuela"), "mexico": ("mx", "Mexico"), "estados unidos": ("us", "USA"),
    "canada": ("ca", "Canada"), "costa rica": ("cr", "Costa Rica"), "panama": ("pa", "Panama"),
    "honduras": ("hn", "Honduras"), "jamaica": ("jm", "Jamaica"), "marruecos": ("ma", "Morocco"),
    "senegal": ("sn", "Senegal"), "nigeria": ("ng", "Nigeria"), "egipto": ("eg", "Egypt"),
    "argelia": ("dz", "Algeria"), "tunez": ("tn", "Tunisia"), "camerun": ("cm", "Cameroon"),
    "ghana": ("gh", "Ghana"), "costa de marfil": ("ci", "Ivory Coast"), "sudafrica": ("za", "South Africa"),
    "mali": ("ml", "Mali"), "japon": ("jp", "Japan"), "corea del sur": ("kr", "South Korea"),
    "australia": ("au", "Australia"), "arabia saudi": ("sa", "Saudi Arabia"), "iran": ("ir", "Iran"),
    "catar": ("qa", "Qatar"), "qatar": ("qa", "Qatar"), "nueva zelanda": ("nz", "New Zealand"),
}


def normalizar(texto: str) -> str:
    sin_tildes = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    return " ".join(sin_tildes.lower().replace("-", " ").split())


@dataclass
class Equipo:
    nombre: str            # tal cual se pinta en la plantilla
    es_seleccion: bool
    imagen: str            # ruta local del escudo (o bandera de reserva)
    nombre_busqueda: str   # nombre en inglés / oficial para buscar plantilla
    redonda: bool = False  # True solo si no hubo escudo y se usa la bandera


def resolver(nombre: str, datos) -> Equipo:
    """`datos` es el módulo tirador.datos (descargas con caché)."""
    clave = normalizar(nombre)
    if clave in SELECCIONES:
        codigo, ingles = SELECCIONES[clave]
        fed = datos.buscar_seleccion(ingles)       # escudo auténtico de la federación
        if fed:
            return Equipo(nombre, True, datos.descargar(fed["strBadge"], f"escudo_{fed['idTeam']}.png"), ingles)
        print(f"  OJO: sin escudo de federación para «{nombre}»; uso la bandera.")
        ruta = datos.descargar(f"https://flagcdn.com/w640/{codigo}.png", f"bandera_{codigo}.png")
        return Equipo(nombre, True, ruta, ingles, redonda=True)
    club = datos.buscar_club(nombre)
    if not club:
        raise SystemExit(
            f"No encuentro el equipo «{nombre}». Si es una selección, añádela a SELECCIONES en "
            f"tirador/equipos.py; si es un club, escribe su nombre oficial o pon el escudo a mano "
            f"con el campo \"escudos\" del JSON del día."
        )
    if normalizar(club["strTeam"]) != clave:
        # se avisa siempre: un escudo equivocado en un vídeo publicado es un error caro
        print(f"  OJO: «{nombre}» se ha resuelto como «{club['strTeam']}» ({club.get('strCountry')}). "
              f"Si no es ese club, usa su nombre oficial.")
    ruta = datos.descargar(club["strBadge"], f"escudo_{club['idTeam']}.png")
    return Equipo(nombre, False, ruta, club["strTeam"])
