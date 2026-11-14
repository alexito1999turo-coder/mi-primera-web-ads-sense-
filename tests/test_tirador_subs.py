"""Subtítulos y tramos de partido del generador de vídeos (sin red)."""
from types import SimpleNamespace as E

from tirador import subs

PARTIDOS = [(E(nombre="Países Bajos"), E(nombre="Grecia")), (E(nombre="Eslovenia"), E(nombre="Suiza")),
            (E(nombre="Serbia"), E(nombre="Alemania")), (E(nombre="Luxemburgo"), E(nombre="Estonia"))]
SRT = """1
00:00:00,200 --> 00:00:02,000
Hoy juegan los Países Bajos contra Grecia.

2
00:00:02,300 --> 00:00:04,000
Luego Suiza visita a Eslovenia,

3
00:00:04,100 --> 00:00:06,000
Alemania va a Serbia y Estonia a Luxemburgo.
"""


def test_srt_reparte_palabras_dentro_de_cada_frase():
    cues = subs.leer_srt(SRT)
    assert len(cues) == 3 and cues[0][:2] == (0.2, 2.0)
    palabras = subs.tiempos_palabras("", cues, 6.5)
    assert palabras[0][1] == 0.2 and abs(palabras[6][2] - 2.0) < 1e-6
    assert all(a <= b for (_, _, a), (_, b, _) in zip(palabras, palabras[1:]))


def test_texto_libre_detecta_los_cuatro_partidos_en_orden():
    palabras = subs.tiempos_palabras("", subs.leer_srt(SRT), 6.5)
    tramos = subs.tramos_partidos(palabras, [], PARTIDOS, 6.5)
    assert [i for i, _, _ in tramos] == [0, 1, 2, 3]
    assert all(ini < fin for _, ini, fin in tramos)
    assert all(t1[2] <= t2[1] + 1e-6 for t1, t2 in zip(tramos, tramos[1:]))


def test_guion_por_bloques_no_resalta_intro_ni_cierre():
    guion = {"intro": "uno dos tres cuatro", "partidos": ["a b", "c d", "e f", "g h"], "cierre": "fin del video ya"}
    texto, bloques = subs.aplanar_guion(guion)
    palabras = subs.tiempos_palabras(texto, [], 16.0)
    tramos = subs.tramos_partidos(palabras, bloques, PARTIDOS, 16.0)
    assert [i for i, _, _ in tramos] == [0, 1, 2, 3]
    assert tramos[0][1] > 2.0          # la intro queda sin resalte
    assert tramos[-1][2] < 14.0        # el cierre también


def test_ass_marca_en_verde_solo_la_palabra_activa(tmp_path):
    palabras = subs.tiempos_palabras("hola qué tal", [], 3.0)
    ruta = tmp_path / "s.ass"
    subs.escribir_ass(palabras, str(ruta))
    lineas = [l for l in ruta.read_text().splitlines() if l.startswith("Dialogue")]
    assert len(lineas) == 3 and all(l.count(subs.VERDE_ASS) == 1 for l in lineas)
