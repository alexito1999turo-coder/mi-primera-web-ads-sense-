"""Subtítulos palabra a palabra (ASS) y tramos de tiempo de cada partido."""
from __future__ import annotations

import re

from .equipos import normalizar

VERDE_ASS = "&H14FF39&"   # (57,255,20) en orden BGR
BLANCO_ASS = "&HFFFFFF&"
SUB_Y = 668               # sobre el borde inferior del vídeo de Julen


def aplanar_guion(guion) -> tuple[str, list[tuple[int | None, int]]]:
    """Admite texto libre o {"intro","partidos":[4],"cierre"}.
    Devuelve (texto completo, [(índice de partido o None, nº de palabras)])."""
    if isinstance(guion, str):
        return guion.strip(), []
    bloques: list[tuple[int | None, str]] = []
    if guion.get("intro"):
        bloques.append((None, guion["intro"]))
    bloques += [(i, t) for i, t in enumerate(guion.get("partidos", [])) if t]
    if guion.get("cierre"):
        bloques.append((None, guion["cierre"]))
    texto = " ".join(t.strip() for _, t in bloques)
    return texto, [(i, len(t.split())) for i, t in bloques]


def _seg(t: str) -> float:
    h, m, s = t.replace(",", ".").split(":")
    return int(h) * 3600 + int(m) * 60 + float(s)


def leer_srt(texto: str) -> list[tuple[float, float, str]]:
    cues = []
    for bloque in re.split(r"\n\s*\n", texto.replace("\r", "").strip()):
        lineas = [l for l in bloque.split("\n") if l.strip()]
        for k, l in enumerate(lineas):
            if "-->" in l:
                a, b = l.split("-->")
                frase = re.sub(r"<[^>]+>", "", " ".join(lineas[k + 1:])).strip()
                if frase:
                    cues.append((_seg(a.strip()), _seg(b.strip().split()[0]), frase))
                break
    return cues


def _repartir(palabras: list[str], ini: float, fin: float) -> list[tuple[str, float, float]]:
    """Reparte el tiempo entre palabras según su longitud (más pausa tras puntuación)."""
    pesos = [len(p) + 2 + (3 if p[-1] in ".,;:!?" else 0) for p in palabras]
    total, t, salida = sum(pesos), ini, []
    for p, w in zip(palabras, pesos):
        dur = (fin - ini) * w / total
        salida.append((p, t, t + dur))
        t += dur
    return salida


def tiempos_palabras(texto: str, cues: list, duracion: float) -> list[tuple[str, float, float]]:
    if cues:
        salida = []
        for a, b, frase in cues:
            salida += _repartir(frase.split(), a, b)
        return salida
    return _repartir(texto.split(), 0.15, max(0.5, duracion - 0.2))


def tramos_partidos(palabras, tramos_guion, partidos, duracion) -> list[tuple[int, float, float]]:
    """[(índice de partido, inicio, fin)]. Con guion estructurado es exacto por
    bloques; con texto libre se detecta la primera mención de cada equipo."""
    n = len(palabras)
    inicios: list[tuple[int, int]] = []          # (partido, índice de palabra)
    if tramos_guion:
        total = sum(c for _, c in tramos_guion) or 1
        acumulado = 0
        for idx, cuenta in tramos_guion:
            if idx is not None:
                inicios.append((idx, min(n - 1, round(acumulado * n / total))))
            acumulado += cuenta
        fin_ultimo = min(n, round(sum(c for i, c in tramos_guion[: _ultimo(tramos_guion) + 1]) * n / total))
    else:
        norm = [normalizar(re.sub(r"[^\w\s-]", "", p)) for p, _, _ in palabras]
        desde = 0
        for idx, (local, visitante) in enumerate(partidos):
            pos = _primera_mencion(norm, [normalizar(local.nombre), normalizar(visitante.nombre)], desde)
            if pos is not None:
                inicios.append((idx, pos))
                desde = pos + 1
        fin_ultimo = n
    salida = []
    for k, (idx, pos) in enumerate(inicios):
        ini = max(0.0, palabras[pos][1] - 0.12)
        if k + 1 < len(inicios):
            fin = max(ini + 0.3, palabras[inicios[k + 1][1]][1] - 0.12)
        else:
            fin = palabras[fin_ultimo - 1][2] + 0.25 if fin_ultimo < n else duracion
        salida.append((idx, ini, min(fin, duracion)))
    return salida


def _ultimo(tramos_guion) -> int:
    return max(k for k, (i, _) in enumerate(tramos_guion) if i is not None)


def _primera_mencion(norm: list[str], nombres: list[str], desde: int) -> int | None:
    mejor = None
    for nombre in nombres:
        partes = nombre.split()
        for i in range(desde, len(norm) - len(partes) + 1):
            if norm[i:i + len(partes)] == partes:
                mejor = i if mejor is None else min(mejor, i)
                break
    return mejor


def _t(s: float) -> str:
    s = max(0.0, s)
    return f"{int(s // 3600)}:{int(s % 3600 // 60):02d}:{s % 60:05.2f}"


def escribir_ass(palabras, ruta: str, fuente: str = "Barlow Condensed ExtraBold") -> None:
    """Grupos de hasta 3 palabras en mayúsculas; la palabra que suena, en verde neón."""
    grupos, actual = [], []
    for p in palabras:
        actual.append(p)
        letras = sum(len(x[0]) for x in actual)
        if len(actual) == 3 or letras >= 16 or p[0][-1] in ".!?,;:":
            grupos.append(actual)
            actual = []
    if actual:
        grupos.append(actual)
    cab = f"""[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
WrapStyle: 2
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Sub,{fuente},84,&H00FFFFFF,&H00FFFFFF,&H00000000,&HAA000000,0,-1,0,0,100,100,1,0,1,6,3,5,40,40,0,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    lineas = []
    for g in grupos:
        fin_grupo = g[-1][2]
        for k, (_, ini, fin) in enumerate(g):
            hasta = g[k + 1][1] if k + 1 < len(g) else fin_grupo
            partes = []
            for j, (pal, _, _) in enumerate(g):
                limpio = re.sub(r"[{}\\]", "", pal).upper().rstrip(",.;:")
                partes.append(f"{{\\c{VERDE_ASS if j == k else BLANCO_ASS}}}{limpio}")
            efecto = "\\fscx86\\fscy86\\t(0,90,\\fscx100\\fscy100)" if k == 0 else ""
            lineas.append(f"Dialogue: 0,{_t(ini)},{_t(hasta)},Sub,,0,0,0,,{{\\pos(540,{SUB_Y}){efecto}}}" + " ".join(partes))
    with open(ruta, "w", encoding="utf-8") as f:
        f.write(cab + "\n".join(lineas) + "\n")
