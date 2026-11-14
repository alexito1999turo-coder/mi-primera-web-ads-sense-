"""Clic de cámara sintetizado (obturador: dos chasquidos secos). Sin samples de terceros."""
from __future__ import annotations

import math
import random
import struct
import wave

FRECUENCIA = 48000


def clic_camara(ruta: str) -> str:
    rnd = random.Random(3)
    n = int(FRECUENCIA * 0.22)
    muestras = [0.0] * n
    for inicio, fuerza, caida in ((0.0, 1.0, 0.006), (0.075, 0.8, 0.010)):   # abre y cierra
        i0 = int(inicio * FRECUENCIA)
        previo = 0.0
        for i in range(i0, n):
            t = (i - i0) / FRECUENCIA
            ruido = rnd.uniform(-1, 1)
            agudo, previo = ruido - 0.85 * previo, ruido          # realce de agudos: chasquido
            cuerpo = math.sin(2 * math.pi * 1900 * t) * 0.5 + math.sin(2 * math.pi * 260 * t) * 0.35
            muestras[i] += fuerza * math.exp(-t / caida) * (0.6 * agudo + cuerpo)
    pico = max(abs(m) for m in muestras)
    with wave.open(ruta, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(FRECUENCIA)
        w.writeframes(b"".join(struct.pack("<h", int(m / pico * 0.9 * 32767)) for m in muestras))
    return ruta
