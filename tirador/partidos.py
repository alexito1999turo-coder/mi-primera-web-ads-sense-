"""Partidos del día desde TheSportsDB y selección de los 4 con más tirón.

Criterio de selección (lo que hacen las cuentas que funcionan, p. ej. @winapicks):
competiciones grandes primero y, dentro de ellas, partidos con clubes o
selecciones de mucha audiencia. Es una heurística: Claude o el usuario revisan
la propuesta antes de gastar créditos.

Límite conocido: con la clave gratuita la API devuelve como mucho 3 partidos por
competición y día, así que en jornadas cargadas puede faltar alguno.
"""
from __future__ import annotations

import json
import time
from datetime import date, datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from . import datos
from .equipos import SELECCIONES, normalizar

# id TheSportsDB -> (nombre corto, peso de la competición)
COMPETICIONES = {
    4480: ("Champions League", 10), 4490: ("Nations League", 8), 4335: ("LaLiga", 8),
    4328: ("Premier League", 8), 4481: ("Europa League", 6), 4332: ("Serie A", 6),
    4331: ("Bundesliga", 6), 4334: ("Ligue 1", 5), 5071: ("Conference League", 4),
    4344: ("Liga Portugal", 3), 4337: ("Eredivisie", 3),
}

# equipos que por sí solos disparan visualizaciones en público hispanohablante
GRANDES = {
    "real madrid": 6, "barcelona": 6, "atletico madrid": 4, "manchester city": 3, "liverpool": 3,
    "arsenal": 3, "manchester united": 3, "chelsea": 2, "bayern munich": 3, "paris sg": 3,
    "paris saint germain": 3, "inter milan": 2, "juventus": 2, "ac milan": 2, "napoli": 1,
    "borussia dortmund": 2, "tottenham hotspur": 1, "athletic bilbao": 1, "sevilla": 1,
    "real betis": 1, "villarreal": 1, "real sociedad": 1, "benfica": 1, "porto": 1,
    "spain": 6, "england": 4, "france": 4, "portugal": 4, "germany": 3, "italy": 3,
    "netherlands": 2, "belgium": 2, "croatia": 2,
}
INGLES_A_ESPANOL = {normalizar(ing): es for es, (_, ing) in
                    sorted(SELECCIONES.items(), key=lambda kv: -len(kv[0]))}
# nombres bonitos (con tildes) para pintar en la plantilla
BONITOS = {"espana": "España", "turquia": "Turquía", "belgica": "Bélgica", "paises bajos": "Países Bajos",
           "republica checa": "Chequia", "chequia": "Chequia", "hungria": "Hungría", "mexico": "México",
           "japon": "Japón", "peru": "Perú", "canada": "Canadá", "azerbaiyan": "Azerbaiyán",
           "kazajistan": "Kazajistán", "macedonia del norte": "Macedonia del Norte"}
MADRID = ZoneInfo("Europe/Madrid")


def _nombre(equipo_api: str) -> str:
    clave = normalizar(equipo_api)
    if clave in INGLES_A_ESPANOL:
        es = INGLES_A_ESPANOL[clave]
        return BONITOS.get(es, es.title())
    return equipo_api


def _hora_madrid(e: dict) -> str:
    ts = e.get("strTimestamp")
    if ts:
        try:
            t = datetime.fromisoformat(ts.replace("Z", "+00:00"))
            if t.tzinfo is None:
                t = t.replace(tzinfo=timezone.utc)
            return t.astimezone(MADRID).strftime("%H:%M")
        except ValueError:
            pass
    return (e.get("strTime") or "")[:5]


def del_dia(dia: date) -> list[dict]:
    salida = []
    for liga, (corto, peso) in COMPETICIONES.items():
        d = datos._json_cacheado(f"ev:{dia}:{liga}", f"{datos.SPORTSDB}/eventsday.php",
                                 {"d": dia.isoformat(), "l": liga}, horas=6)
        for e in d.get("events") or []:
            local, visit = e.get("strHomeTeam") or "", e.get("strAwayTeam") or ""
            tiron = GRANDES.get(normalizar(local), 0) + GRANDES.get(normalizar(visit), 0)
            salida.append({"competicion": corto, "local": _nombre(local), "visitante": _nombre(visit),
                           "hora": _hora_madrid(e), "puntos": peso + 2 * tiron})
        time.sleep(0.4)          # la clave gratuita limita la frecuencia
    return sorted(salida, key=lambda p: -p["puntos"])


def proponer(dia: date, carpeta_dias: Path) -> Path | None:
    todos = del_dia(dia)
    if not todos:
        print(f"No encuentro partidos de las competiciones seguidas el {dia}.")
        return None
    print(f"Partidos encontrados el {dia} (hora de Madrid), de más a menos tirón:")
    for p in todos:
        print(f"  {p['puntos']:>3}  {p['hora']}  {p['competicion']:<18} {p['local']} - {p['visitante']}")
    elegidos = sorted(todos[:4], key=lambda p: p["hora"])
    if len(elegidos) < 4:
        print(f"AVISO: solo hay {len(elegidos)} partidos; la plantilla necesita 4. Añádelos a mano.")
    ruta = carpeta_dias / f"{dia.isoformat()}.json"
    if ruta.exists():
        print(f"Ya existe {ruta}; no lo sobrescribo.")
        return ruta
    borrador = {
        "fecha": dia.isoformat(),
        "partidos": [[p["local"], p["visitante"]] for p in elegidos],
        "competiciones": [p["competicion"] for p in elegidos],
        "estrella": "",
        "guion": {"intro": "", "partidos": ["", "", "", ""], "cierre": ""},
    }
    ruta.write_text(json.dumps(borrador, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Borrador escrito en {ruta}: falta elegir estrella y escribir el guion.")
    return ruta
