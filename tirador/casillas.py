"""Localiza las 4 casillas de partido en una plantilla hecha fuera (p. ej. ChatGPT).

Las casillas de este nicho son rectángulos oscuros con borde de neón que ocupan casi
todo el ancho. Se buscan las filas donde el borde brilla (color vivo y saturado en
la franja central), se agrupan en líneas y se emparejan arriba/abajo. Si no salen
exactamente 4 casillas plausibles, devuelve None y el vídeo va sin resalte: mejor
eso que resaltar el sitio equivocado.
"""
from __future__ import annotations

from PIL import Image


def _viva(p) -> bool:
    r, g, b = p
    mx, mn = max(p), min(p)
    return mx > 185 and (mx - mn) > 0.55 * mx


def _oscura(img, y0, y1, x0, x1) -> float:
    px, n, s = img.load(), 0, 0
    for y in range(y0, y1, 4):
        for x in range(x0, x1, 12):
            s += sum(px[x, y]) / 3
            n += 1
    return s / max(n, 1)


def detectar(ruta: str, ancho: int = 1080) -> list[tuple[int, int, int, int]] | None:
    img = Image.open(ruta).convert("RGB")
    img = img.resize((ancho, round(img.height * ancho / img.width)))
    W, H = img.size
    px = img.load()
    xs = range(int(W * .12), int(W * .88), 3)
    perfil = [sum(1 for x in xs if _viva(px[x, y])) / len(xs) for y in range(H)]
    # líneas candidatas: centros de grupos de filas con borde brillante
    lineas, actual = [], []
    for y, v in enumerate(perfil):
        if v > 0.18:
            actual.append(y)
        elif actual:
            lineas.append((actual[0] + actual[-1]) / 2)
            actual = []
    if len(lineas) < 8:
        return None

    def dist(y):
        return min(abs(l - y) for l in lineas)

    def cerca(y, tol=9):
        return dist(y) <= tol

    # cuatro casillas iguales y equiespaciadas: arriba t+k*paso, abajo arriba+alto.
    # Se exige que los 8 bordes coincidan con líneas reales y que el interior no sea claro.
    mejor = None
    for t in lineas:
        for paso in range(100, 300, 2):
            if t + 3 * paso > H:
                break
            for alto in range(60, min(260, paso - 8), 2):
                if not all(cerca(t + k * paso) and cerca(t + k * paso + alto) for k in range(4)):
                    continue
                cajas = [(round(t + k * paso), round(t + k * paso + alto)) for k in range(4)]
                if any(_oscura(img, a + alto // 4, b - alto // 4, int(W * .3), int(W * .7)) > 120 for a, b in cajas):
                    continue
                error = sum(dist(t + k * paso) + dist(t + k * paso + alto) for k in range(4))
                clave = (round(error / 4), -alto)   # el ajuste más exacto; a igualdad, el borde exterior
                if mejor is None or clave < mejor[1]:
                    mejor = (cajas, clave)
    if not mejor:
        return None
    mejor = mejor[0]
    # el ancho se fija: los bordes laterales se confunden con las luces del fondo
    return [(round(W * .04), a, round(W * .96), b) for a, b in mejor]
