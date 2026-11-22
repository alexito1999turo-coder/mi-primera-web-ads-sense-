"""Plantilla maestra: el diseño de ChatGPT fijo para siempre; cada día solo cambian
escudos, nombres y jugador.

    python -m tirador maestra RUTA.png    prepara la maestra UNA vez a partir de una plantilla
                                          de ChatGPT (mejor si viene sin jugador y con casillas vacías)

Preparar: se encaja la imagen bajo Julen, se localizan las 4 casillas, se toma el color
de acento del borde y se vacía el interior de cada casilla (se conserva el borde).
Componer (cada día): sobre esa maestra se pinta el jugador en su zona, y en cada casilla
escudo auténtico – NOMBRE – VS – NOMBRE – escudo auténtico, siempre en la misma posición.
"""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageEnhance, ImageFilter, ImageFont

from . import casillas, plantilla
from .plantilla import FUENTE, W, _insignia, _recorte, _resplandor

CARPETA = Path(__file__).resolve().parent / "maestra"


def _acento(zona: Image.Image, cajas) -> tuple[int, int, int]:
    px = zona.load()
    votos = Counter()
    for x0, y0, x1, y1 in cajas:
        for y in (y0, y1):
            for dy in range(-3, 4):
                for x in range(x0 + 40, x1 - 40, 6):
                    p = px[x, min(zona.height - 1, max(0, y + dy))]
                    mx, mn = max(p), min(p)
                    if mx > 185 and mx - mn > 0.55 * mx:
                        votos[tuple(c // 24 * 24 + 12 for c in p)] += 1
    return votos.most_common(1)[0][0] if votos else (57, 255, 20)


def preparar(ruta: str) -> Path:
    CARPETA.mkdir(exist_ok=True)
    zona = plantilla.encajar_zona(Image.open(ruta))
    tmp = CARPETA / "_zona.png"
    zona.save(tmp)
    cajas = casillas.detectar(str(tmp))
    tmp.unlink()
    if not cajas:
        raise SystemExit("No localizo 4 casillas iguales en esa imagen. Pide a ChatGPT casillas con borde "
                         "de neón claro, iguales y separadas, y vuelve a intentarlo.")
    acento = _acento(zona, cajas)
    limpia = zona.copy()
    d = ImageDraw.Draw(limpia)
    for x0, y0, x1, y1 in cajas:
        alto = y1 - y0
        borde = max(8, alto // 11)            # se conserva el neón del borde
        d.rounded_rectangle((x0 + borde + 6, y0 + borde, x1 - borde - 6, y1 - borde), alto // 4, fill=(6, 7, 9))
    limpia.save(CARPETA / "maestra.png")
    primera = cajas[0]
    conf = {
        "cajas": cajas,
        "acento": acento,
        # el jugador acaba encima del título que va sobre la primera casilla
        "jugador_base_y": max(120, primera[1] - round((primera[3] - primera[1]) * 1.05)),
        "jugador_centro_x": 0.5,
        "pintar_vs": True,
        "pintar_nombre_jugador": True,
        "nombre_x": 0.80,
        "nombre_y": 0.11,
        "origen": str(ruta),
    }
    (CARPETA / "maestra.json").write_text(json.dumps(conf, indent=2), encoding="utf-8")
    print(f"Maestra lista en {CARPETA}: casillas {cajas}, acento {acento}.")
    return CARPETA / "maestra.png"


def _nombre(d: ImageDraw.ImageDraw, texto: str, cx: int, cy: int, ancho: int, alto: int) -> None:
    texto = texto.upper()
    tam = int(alto * 0.42)
    f = ImageFont.truetype(FUENTE, tam)
    lineas = [texto]
    while d.textlength(texto, font=f) > ancho and tam > alto * 0.30:
        tam -= 2
        f = ImageFont.truetype(FUENTE, tam)
    if d.textlength(texto, font=f) > ancho and " " in texto:      # a dos líneas, como en la referencia
        palabras = texto.split()
        corte = min(range(1, len(palabras)), key=lambda k: abs(len(" ".join(palabras[:k])) - len(texto) / 2))
        lineas = [" ".join(palabras[:corte]), " ".join(palabras[corte:])]
        tam = int(alto * 0.34)
        f = ImageFont.truetype(FUENTE, tam)
        while max(d.textlength(l, font=f) for l in lineas) > ancho and tam > 18:
            tam -= 2
            f = ImageFont.truetype(FUENTE, tam)
    salto = tam * 0.92
    y = cy - salto * (len(lineas) - 1) / 2
    for l in lineas:
        d.text((cx + 2, y + 3), l, font=f, fill=(0, 0, 0, 200), anchor="mm")
        d.text((cx, y), l, font=f, fill=(255, 255, 255, 255), anchor="mm")
        y += salto


def _vs(img: Image.Image, cx: int, cy: int, alto: int, acento) -> None:
    f = ImageFont.truetype(FUENTE, int(alto * 0.5))
    img.alpha_composite(_resplandor(img.size, lambda d: d.text((cx, cy), "VS", font=f, fill=255, anchor="mm"), 10, acento))
    ImageDraw.Draw(img).text((cx, cy), "VS", font=f, fill=acento + (255,), anchor="mm")


def _jugador(img: Image.Image, foto: tuple, conf: dict) -> None:
    ruta, recorte = foto[0], foto[1]
    p = _recorte(ruta, recorte)
    if p.height > p.width * 1.1:              # foto de cuerpo: se encuadra de pecho para arriba
        p = p.crop((0, 0, p.width, round(p.height * 0.62)))
    base_y = conf["jugador_base_y"]
    alto = round(base_y * 1.12)
    p = p.resize((max(1, round(p.width * alto / p.height)), alto), Image.LANCZOS)
    rgb = ImageEnhance.Contrast(p.convert("RGB")).enhance(1.15)
    rgb = ImageEnhance.Sharpness(rgb).enhance(1.3)
    alfa = p.getchannel("A")
    acento = tuple(conf["acento"])
    borde = ImageChops.subtract(alfa, ImageChops.offset(alfa, -8, 4).filter(ImageFilter.GaussianBlur(3)))
    borde = borde.filter(ImageFilter.GaussianBlur(2)).point(lambda v: min(255, int(v * 1.4)))
    rgb = Image.composite(Image.new("RGB", p.size, tuple(min(255, c + 60) for c in acento)), rgb, borde)
    # se funde por abajo para no cortar en seco encima del título
    fundido = Image.linear_gradient("L").resize((p.width, p.height)).point(lambda v: 255 if v < 180 else int(255 * (255 - v) / 75))
    alfa = ImageChops.multiply(alfa, fundido)
    p = rgb.convert("RGBA")
    p.putalpha(alfa)
    x = round(W * conf.get("jugador_centro_x", 0.5) - p.width / 2)
    y = base_y - p.height
    halo = Image.new("L", img.size, 0)
    halo.paste(alfa, (x, y))
    capa = Image.new("RGBA", img.size, acento + (0,))
    capa.putalpha(halo.filter(ImageFilter.GaussianBlur(18)).point(lambda v: int(v * 0.55)))
    img.alpha_composite(capa)
    img.alpha_composite(p, (x, y))


def _vivo(c):
    m = max(c) or 1
    return tuple(min(255, round(v * 255 / m)) for v in c)


def _nombre_jugador(img: Image.Image, nombre: str, conf: dict) -> None:
    """Nombre del jugador en dos líneas, arriba a la derecha (posición fija de la maestra)."""
    partes = nombre.upper().split()
    lineas = [partes[0], " ".join(partes[1:])] if len(partes) > 1 else partes
    x, y = conf.get("nombre_x", 0.80) * W, conf.get("nombre_y", 0.11) * img.height
    f = ImageFont.truetype(FUENTE, 58)
    acento = _vivo(tuple(conf["acento"]))
    for i, l in enumerate(lineas):
        color = (255, 255, 255) if i == 0 else acento
        img.alpha_composite(_resplandor(img.size, lambda d, l=l, i=i: d.text((x, y + i * 56), l, font=f, fill=200, anchor="mm"), 8, acento))
        ImageDraw.Draw(img).text((x, y + i * 56), l, font=f, fill=color + (255,), anchor="mm")


def componer(partidos: list[tuple], foto: tuple | None, carpeta: Path, nombre_estrella: str | None = None) -> dict:
    conf_f = CARPETA / "maestra.json"
    if not conf_f.exists():
        raise SystemExit("Aún no hay plantilla maestra. Prepárala una vez: python -m tirador maestra RUTA.png")
    conf = json.loads(conf_f.read_text(encoding="utf-8"))
    acento = tuple(conf["acento"])
    zona = Image.open(CARPETA / "maestra.png").convert("RGBA")
    if foto:
        _jugador(zona, foto, conf)
    if nombre_estrella and conf.get("pintar_nombre_jugador", True):
        _nombre_jugador(zona, nombre_estrella, conf)
    for (local, visit), (x0, y0, x1, y1) in zip(partidos, conf["cajas"]):
        alto, ancho = y1 - y0, x1 - x0
        cy = (y0 + y1) // 2
        tam = round(alto * 0.66)
        for eq, cx in ((local, x0 + round(ancho * 0.10)), (visit, x1 - round(ancho * 0.10))):
            esc = _insignia(eq.imagen, eq.redonda, tam)
            zona.alpha_composite(esc, (cx - tam // 2, cy - tam // 2))
        d = ImageDraw.Draw(zona)
        _nombre(d, local.nombre, x0 + round(ancho * 0.31), cy, round(ancho * 0.26), alto)
        _nombre(d, visit.nombre, x1 - round(ancho * 0.31), cy, round(ancho * 0.26), alto)
        if conf.get("pintar_vs", True):
            _vs(zona, (x0 + x1) // 2, cy, alto, _vivo(acento))
    carpeta.mkdir(parents=True, exist_ok=True)
    zona_f = carpeta / "zona_maestra.png"
    zona.convert("RGB").save(zona_f)
    return plantilla.desde_imagen(str(zona_f), carpeta, cajas_conocidas=conf["cajas"])
