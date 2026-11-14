"""Subtítulos palabra a palabra (ASS) y tramos de tiempo de cada partido."""
from __future__ import annotations

import re

from .equipos import normalizar

# ESTILO_SUBTITULOS_OFICIAL: Montserrat ExtraBold, mayúsculas, contorno negro grueso,
# brillo neón, entrada con zoom y movimiento, 1-3 palabras, palabra a palabra.
# Colores vivos en formato ASS (BGR): turquesa, verde neón, rosa y amarillo; el resto en blanco.
COLORES_ASS = ["&HFFE500&", "&H14FF39&", "&H962DFF&", "&H00E6FF&"]
BLANCO_ASS = "&HFFFFFF&"
SUB_Y = 1036              # entre el vídeo de Julen y las casillas, sin tapar escudos ni partidos
MAX_LETRAS = 13           # por fragmento, para que nunca se salga del ancho


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


def tramos_partidos(palabras, tramos_guion, partidos, duracion, arranques_voz=()) -> list[tuple[int, float, float]]:
    """[(índice de partido, inicio, fin)]: cuándo empieza Julen a hablar de cada partido.

    Con guion por bloques se localiza la primera frase de cada bloque en lo que
    realmente se dijo; con texto libre, la primera mención de cada equipo.
    `arranques_voz` son los instantes en que la voz arranca tras una pausa
    (medidos en el audio): el inicio se ajusta al más cercano, para que flash,
    sonido y resalte caigan exactamente donde empieza la frase.
    """
    n = len(palabras)
    norm = [_n(p) for p, _, _ in palabras]
    inicios: list[tuple[int, int]] = []          # (partido, índice de palabra)
    fin_ultimo = n
    if tramos_guion:
        total = sum(c for _, c in tramos_guion) or 1
        acumulado = 0
        for k, (idx, cuenta) in enumerate(tramos_guion):
            esperado = min(n - 1, round(acumulado * n / total))
            if idx is not None:
                inicios.append((idx, esperado))
            acumulado += cuenta
        fin_ultimo = min(n, round(sum(c for _, c in tramos_guion[: _ultimo(tramos_guion) + 1]) * n / total))
    else:
        desde = 0
        for idx, (local, visitante) in enumerate(partidos):
            pos = _primera_mencion(norm, [normalizar(local.nombre), normalizar(visitante.nombre)], desde)
            if pos is not None:
                pos = _inicio_frase(palabras, pos, desde)
                inicios.append((idx, pos))
                desde = pos + 1
    tiempos: list[float] = []
    for _, pos in inicios:
        t = palabras[pos][1]
        ajustado = _ajustar(t, arranques_voz)
        tiempos.append(ajustado if not tiempos or ajustado > tiempos[-1] else t)
    salida = []
    for k, (idx, pos) in enumerate(inicios):
        ini = tiempos[k]
        if k + 1 < len(inicios):
            fin = max(ini + 0.3, tiempos[k + 1])
        else:
            fin = palabras[fin_ultimo - 1][2] + 0.25 if fin_ultimo < n else duracion
        salida.append((idx, ini, min(fin, duracion)))
    return salida


def _n(palabra: str) -> str:
    return normalizar(re.sub(r"[^\w\s-]", "", palabra))


def _inicio_frase(palabras, pos: int, minimo: int) -> int:
    """Retrocede desde la mención del equipo hasta el principio de su frase. Si esa
    frase ya pertenece al partido anterior, el inicio es la propia mención."""
    ini = pos
    while ini > 0 and palabras[ini - 1][0][-1] not in ".!?":
        ini -= 1
    return ini if ini >= minimo else pos


def _ajustar(t: float, arranques, margen: float = 0.6) -> float:
    cercanos = [a for a in arranques if abs(a - t) <= margen]
    return min(cercanos, key=lambda a: abs(a - t)) if cercanos else t


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


def fragmentar(palabras) -> list[list]:
    """Fragmentos de 1 a 3 palabras que caben en pantalla; se corta tras puntuación."""
    grupos, actual = [], []
    for p in palabras:
        largo = sum(len(x[0]) + 1 for x in actual) + len(p[0])
        if actual and (len(actual) == 3 or largo > MAX_LETRAS):
            grupos.append(actual)
            actual = []
        actual.append(p)
        if p[0][-1] in ".!?,;:":
            grupos.append(actual)
            actual = []
    if actual:
        grupos.append(actual)
    return grupos


def escribir_ass(palabras, ruta: str, fuente: str = "Montserrat ExtraBold") -> None:
    cab = f"""[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
WrapStyle: 2
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Sub,{fuente},100,&H00FFFFFF,&H00FFFFFF,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,9,0,5,20,20,0,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    lineas = []
    for n, g in enumerate(fragmentar(palabras)):
        color = COLORES_ASS[n % len(COLORES_ASS)]
        fin_grupo = g[-1][2]
        for k, (_, ini, fin) in enumerate(g):
            hasta = g[k + 1][1] if k + 1 < len(g) else fin_grupo
            if k == 0:   # entrada con zoom y movimiento
                anim = (f"\\move(540,{SUB_Y + 34},540,{SUB_Y},0,120)\\fscx55\\fscy55"
                        f"\\t(0,110,\\fscx110\\fscy110)\\t(110,190,\\fscx100\\fscy100)")
            else:
                anim = f"\\pos(540,{SUB_Y})"
            brillo, texto = [], []
            for j, (pal, _, _) in enumerate(g):
                limpio = re.sub(r"[{}\\\\]", "", pal).upper().rstrip(",.;:")
                if j == k:   # la palabra que suena: color vivo y halo neón
                    brillo.append(f"{{\\alpha&H30&\\c{color}\\3c{color}}}{limpio}")
                    texto.append(f"{{\\c{color}}}{limpio}")
                else:
                    brillo.append(f"{{\\alpha&HFF&}}{limpio}")
                    texto.append(f"{{\\c{BLANCO_ASS}}}{limpio}")
            t = f"{_t(ini)},{_t(hasta)}"
            lineas.append(f"Dialogue: 0,{t},Sub,,0,0,0,,{{{anim}\\bord14\\blur16}}" + " ".join(brillo))
            lineas.append(f"Dialogue: 1,{t},Sub,,0,0,0,,{{{anim}}}" + " ".join(texto))
    with open(ruta, "w", encoding="utf-8") as f:
        f.write(cab + "\n".join(lineas) + "\n")
