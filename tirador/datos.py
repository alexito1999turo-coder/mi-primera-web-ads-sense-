"""Descargas con caché en disco: banderas, escudos, plantillas y fotos de jugadores."""
from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path

import requests

RAIZ = Path(__file__).resolve().parent
CACHE = RAIZ / "cache"
UA = {"User-Agent": "ElTiradorVideos/1.0 (generador interno de plantillas)"}
SPORTSDB = "https://www.thesportsdb.com/api/v1/json/123"
WIKI = "https://en.wikipedia.org/w/api.php"


def _get(url: str, params: dict | None = None, intentos: int = 4) -> requests.Response:
    espera = 2.0
    for i in range(intentos):
        r = requests.get(url, params=params, headers=UA, timeout=40)
        if r.status_code == 429 and i < intentos - 1:
            time.sleep(espera)
            espera *= 2
            continue
        r.raise_for_status()
        return r
    raise RuntimeError("inalcanzable")


def _json_cacheado(clave: str, url: str, params: dict | None = None, horas: float = 24) -> dict:
    CACHE.mkdir(exist_ok=True)
    f = CACHE / (hashlib.sha1(clave.encode()).hexdigest()[:16] + ".json")
    if f.exists() and time.time() - f.stat().st_mtime < horas * 3600:
        return json.loads(f.read_text())
    datos = _get(url, params).json()
    f.write_text(json.dumps(datos))
    return datos


def descargar(url: str, nombre: str) -> str:
    CACHE.mkdir(exist_ok=True)
    destino = CACHE / nombre
    if not destino.exists() or destino.stat().st_size == 0:
        destino.write_bytes(_get(url).content)
    return str(destino)


# ---------------------------------------------------------------- TheSportsDB

def buscar_club(nombre: str) -> dict | None:
    from .equipos import normalizar
    d = _json_cacheado(f"club:{nombre}", f"{SPORTSDB}/searchteams.php", {"t": nombre}, horas=24 * 30)
    validos = [t for t in d.get("teams") or [] if t.get("strSport") == "Soccer" and t.get("strBadge")]
    clave = normalizar(nombre)
    for t in validos:  # primero coincidencia exacta con el nombre o un alias oficial
        alias = [normalizar(a) for a in (t.get("strTeamAlternate") or "").split(",")]
        if clave == normalizar(t["strTeam"]) or clave in alias:
            return t
    # la búsqueda gratuita es difusa: solo se acepta si comparte alguna palabra con lo pedido
    # y no es el equipo femenino (salvo que se pida). Mejor fallar que pintar un escudo ajeno.
    for t in validos:
        comun = set(clave.split()) & set(normalizar(t["strTeam"]).split())
        femenino = t.get("strGender") == "Female" and "fem" not in clave
        if comun and not femenino:
            return t
    return None


def foto_jugador(nombre: str) -> tuple[str, bool] | None:
    """Devuelve (ruta, es_recorte). Prefiere el recorte con transparencia."""
    d = _json_cacheado(f"jug:{nombre}", f"{SPORTSDB}/searchplayers.php", {"p": nombre}, horas=24 * 7)
    for p in d.get("player") or []:
        if p.get("strSport") != "Soccer":
            continue
        for campo, recorte in (("strCutout", True), ("strRender", True), ("strThumb", False)):
            if p.get(campo):
                ext = p[campo].rsplit(".", 1)[-1]
                clave = hashlib.sha1(p[campo].encode()).hexdigest()[:12]
                return descargar(p[campo], f"jugador_{clave}.{ext}"), recorte
    return None


# ------------------------------------------------------------------ Wikipedia
# Ranking de fama: visitas a Wikipedia en los últimos 30 días de cada jugador
# de la plantilla actual. Es un criterio objetivo y reproducible, no una opinión.

def _plantilla_wiki(equipo_ingles: str, es_seleccion: bool) -> list[str]:
    consulta = f"{equipo_ingles} national football team" if es_seleccion else f"{equipo_ingles} football club"
    busq = _json_cacheado(f"wsearch:{consulta}", WIKI, {
        "action": "query", "list": "search", "srsearch": consulta, "srlimit": 1, "format": "json"})
    resultados = busq.get("query", {}).get("search", [])
    if not resultados:
        return []
    pagina = resultados[0]["title"]
    secs = _json_cacheado(f"wsecs:{pagina}", WIKI, {
        "action": "parse", "page": pagina, "prop": "sections", "format": "json"})
    indice = None
    for patron in ("current squad", "first-team squad", "first team squad", "squad", "players"):
        for s in secs.get("parse", {}).get("sections", []):
            if patron in s["line"].lower():
                indice = s["index"]
                break
        if indice:
            break
    if not indice:
        return []
    enlaces = _json_cacheado(f"wlinks:{pagina}:{indice}", WIKI, {
        "action": "parse", "page": pagina, "section": indice, "prop": "links", "format": "json"})
    return [e["*"] for e in enlaces.get("parse", {}).get("links", []) if e.get("ns") == 0]


def ranking_fama(equipos: list[tuple[str, bool]]) -> list[tuple[str, int]]:
    """[(nombre_ingles, es_seleccion)] -> [(jugador, visitas_30d)] de mayor a menor."""
    titulos: list[str] = []
    for nombre, es_sel in equipos:
        for t in _plantilla_wiki(nombre, es_sel):
            if t not in titulos:
                titulos.append(t)
    visitas: dict[str, int] = {}
    for i in range(0, len(titulos), 50):
        lote = titulos[i:i + 50]
        params = {"action": "query", "prop": "description|pageviews", "pvipdays": 30,
                  "titles": "|".join(lote), "format": "json"}
        while True:
            d = _json_cacheado("wpv:" + "|".join(lote) + str(params.get("pvipcontinue", "")), WIKI, params)
            for p in d.get("query", {}).get("pages", {}).values():
                desc = (p.get("description") or "").lower()
                if "footballer" not in desc and "soccer player" not in desc:
                    continue
                total = sum(v or 0 for v in (p.get("pageviews") or {}).values())
                visitas[p["title"]] = visitas.get(p["title"], 0) + total
            if "continue" not in d:
                break
            params = {**params, **d["continue"]}
    return sorted(visitas.items(), key=lambda x: -x[1])
