"""Plantilla fija de El Tirador (1080x1920). Siempre el mismo diseño:
negro profundo, verde neón, jugador estrella y cuatro casillas de partido.

Genera: base.png, resalte_0..3.png (partido activo) y flash.png.
"""
from __future__ import annotations

import random
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageEnhance, ImageFilter, ImageFont, ImageOps

W, H = 1080, 1920
AVATAR_Y, AVATAR_H = 110, 608          # vídeo de Julen: 1080x608 (16:9)
ZONA_Y = AVATAR_Y + AVATAR_H           # 718: empieza el jugador
CAJAS_Y, CAJA_H, CAJA_SEP, CAJA_MX = 1152, 136, 46, 44
RADIO = 34
CELDA = 150                            # ancho de la celda del escudo
NEON = (57, 255, 20)
LIMA = (190, 255, 60)
NEON_CLARO = (200, 255, 185)
FUENTE = str(Path(__file__).resolve().parent / "fuentes" / "BarlowCondensed-ExtraBoldItalic.ttf")


def caja_rect(i: int) -> tuple[int, int, int, int]:
    y = CAJAS_Y + i * (CAJA_H + CAJA_SEP)
    return CAJA_MX, y, W - CAJA_MX, y + CAJA_H


def _resplandor(tam, dibujar, radio, color) -> Image.Image:
    """Dibuja una máscara con `dibujar(draw)` y la devuelve desenfocada y teñida."""
    m = Image.new("L", tam, 0)
    dibujar(ImageDraw.Draw(m))
    m = m.filter(ImageFilter.GaussianBlur(radio))
    capa = Image.new("RGBA", tam, color + (0,))
    capa.putalpha(m)
    return capa


def _nubes(tam, semilla: int, escalas=((9, 16, 1.0), (18, 32, 0.6), (36, 64, 0.35))) -> Image.Image:
    """Humo volumétrico: ruido en varias octavas, suave. Devuelve máscara L."""
    rnd = random.Random(semilla)
    total, norma = None, sum(p for _, _, p in escalas)
    for w, h, peso in escalas:
        peq = Image.new("L", (w, h))
        peq.putdata([rnd.randint(0, 255) for _ in range(w * h)])
        capa = peq.resize(tam, Image.BICUBIC).point(lambda v, p=peso / norma: int(v * p))
        total = capa if total is None else ImageChops.add(total, capa)
    return total.point(lambda v: max(0, min(255, int((v - 95) * 2.6))))


def _fondo_estadio() -> Image.Image:
    """Estadio nocturno: focos, haces de luz en diagonal, humo verde y chispas.
    Semilla fija: el fondo es idéntico todos los días."""
    rnd = random.Random(7)
    img = Image.new("RGBA", (W, H), (0, 6, 1, 255))
    alto = H - ZONA_Y
    # ambiente verde general, más intenso tras el jugador
    img.alpha_composite(_resplandor((W, H), lambda d: d.ellipse((-80, ZONA_Y - 60, W + 80, CAJAS_Y + 260), fill=120), 130, (8, 84, 18)))
    # gradas: bandas curvas con público sugerido (puntos)
    def gradas(d):
        for k in range(9):
            y = ZONA_Y + 20 + k * 30
            d.arc((-260, y, W + 260, y + 520), 180, 360, fill=40 + k * 6, width=10)
    img.alpha_composite(_resplandor((W, H), gradas, 7, (30, 150, 50)))
    def publico(d):
        for _ in range(2600):
            x, y = rnd.randint(0, W), rnd.randint(ZONA_Y + 10, ZONA_Y + 330)
            d.point((x, y), fill=rnd.randint(60, 200))
    img.alpha_composite(_resplandor((W, H), publico, 1.1, (120, 230, 130)))
    # focos del estadio: racimos en las esquinas con destello
    focos = []
    for lado in (0, 1):
        for fila in range(4):
            for col in range(7):
                x = 26 + col * 38 + fila * 12
                y = ZONA_Y + 52 + fila * 30 - col * 7
                focos.append((x if lado == 0 else W - x, y, rnd.randint(7, 12)))
    def pinta_focos(d):
        for x, y, r in focos:
            d.ellipse((x - r, y - r, x + r, y + r), fill=255)
    img.alpha_composite(_resplandor((W, H), pinta_focos, 34, (90, 255, 110)))
    img.alpha_composite(_resplandor((W, H), pinta_focos, 9, (190, 255, 190)))
    img.alpha_composite(_resplandor((W, H), pinta_focos, 2, (255, 255, 255)))
    def destellos(d):
        for x, y, r in focos[::5]:
            d.line((x - 70, y, x + 70, y), fill=255, width=2)
            d.line((x, y - 40, x, y + 40), fill=200, width=2)
    img.alpha_composite(_resplandor((W, H), destellos, 2.5, (220, 255, 220)))
    # haces de luz en diagonal que cruzan toda la zona
    def haces(d):
        for (x0, y0, x1, y1, g) in ((-60, ZONA_Y + 240, 330, ZONA_Y - 10, 7), (W + 60, ZONA_Y + 250, W - 300, ZONA_Y - 10, 7),
                                    (-40, H - 250, 190, ZONA_Y + 300, 5), (W + 40, H - 300, W - 170, ZONA_Y + 320, 5),
                                    (-30, H - 30, 120, H - 420, 4), (W + 30, H - 60, W - 110, H - 470, 4)):
            d.line((x0, y0, x1, y1), fill=255, width=g)
    img.alpha_composite(_resplandor((W, H), haces, 22, NEON))
    img.alpha_composite(_resplandor((W, H), haces, 5, (170, 255, 150)))
    img.alpha_composite(_resplandor((W, H), haces, 1.2, (240, 255, 235)))
    # humo volumétrico verde (dos capas con distinta escala)
    for semilla, color, fuerza in ((11, (14, 130, 30), 0.50), (23, (70, 235, 80), 0.20)):
        nube = _nubes((W, alto), semilla).point(lambda v, f=fuerza: int(v * f))
        capa = Image.new("RGBA", (W, alto), color + (0,))
        capa.putalpha(nube)
        img.alpha_composite(capa, (0, ZONA_Y))
    # chispas
    def chispas(d):
        for _ in range(170):
            x, y = rnd.randint(0, W), rnd.randint(ZONA_Y + 30, H - 10)
            r = rnd.choice((1, 1, 2, 2, 3))
            d.ellipse((x - r, y - r, x + r, y + r), fill=rnd.randint(120, 255))
    img.alpha_composite(_resplandor((W, H), chispas, 1.4, (170, 255, 140)))
    # viñeta para dar contraste cinematográfico
    vin = Image.new("L", (W, alto), 0)
    ImageDraw.Draw(vin).ellipse((-240, -160, W + 240, alto + 200), fill=255)
    vin = ImageChops.invert(vin.filter(ImageFilter.GaussianBlur(150))).point(lambda v: int(v * 0.95))
    sombra = Image.new("RGBA", (W, alto), (0, 0, 0, 0))
    sombra.putalpha(vin)
    img.alpha_composite(sombra, (0, ZONA_Y))
    _techo_negro(img)
    return img


def _techo_negro(img: Image.Image) -> None:
    """Zona de Julen: negro limpio, con un fundido corto en la unión."""
    ImageDraw.Draw(img).rectangle((0, 0, W, ZONA_Y), fill=(0, 0, 0, 255))
    fundido = Image.new("RGBA", (W, 56), (0, 0, 0, 0))
    fd = ImageDraw.Draw(fundido)
    for y in range(56):
        fd.line((0, y, W, y), fill=(0, 0, 0, int(255 * (1 - y / 56) ** 1.8)))
    img.alpha_composite(fundido, (0, ZONA_Y))


def _recorte(ruta: str, es_recorte: bool) -> Image.Image:
    foto = Image.open(ruta).convert("RGBA")
    if es_recorte and foto.getchannel("A").getextrema()[0] < 250:
        return foto.crop(foto.getchannel("A").getbbox())
    # foto normal: se difuminan los bordes para integrarla
    m = Image.new("L", foto.size, 0)
    ImageDraw.Draw(m).ellipse((foto.width * 0.04, foto.height * 0.02, foto.width * 0.96, foto.height * 1.3), fill=255)
    foto.putalpha(m.filter(ImageFilter.GaussianBlur(foto.width // 14)))
    return foto


def _escalar(foto: Image.Image, alto: int) -> Image.Image:
    return foto.resize((max(1, int(foto.width * alto / foto.height)), alto), Image.LANCZOS)


def _pegar_jugador(img: Image.Image, ruta: str, es_recorte: bool, ruta2: str | None = None,
                   es_recorte2: bool = True) -> None:
    """Retrato principal grande con luz de contorno neón y, detrás a un lado, un
    segundo retrato en verde oscuro (otra foto si la hay; si no, la misma en espejo)."""
    base_y = CAJAS_Y + 190                       # el torso se hunde tras la primera casilla
    principal = _recorte(ruta, es_recorte)
    secundario = _recorte(ruta2, es_recorte2) if ruta2 else ImageOps.mirror(principal)

    # --- secundario: monocromo verde oscuro, algo más pequeño, a la derecha
    sec = _escalar(secundario, 560)
    alfa = sec.getchannel("A")
    gris = ImageOps.autocontrast(ImageOps.grayscale(sec.convert("RGB")), cutoff=1)
    sec = ImageOps.colorize(gris, (2, 22, 6), (150, 235, 150), mid=(26, 110, 44)).convert("RGBA")
    sec.putalpha(alfa.point(lambda v: int(v * 0.92)))
    sx, sy = 770 - sec.width // 2, base_y - sec.height + 30
    halo = Image.new("L", (W, H), 0)
    halo.paste(alfa, (sx, sy))
    capa = Image.new("RGBA", (W, H), (60, 220, 80, 0))
    capa.putalpha(halo.filter(ImageFilter.GaussianBlur(26)).point(lambda v: int(v * 0.45)))
    img.alpha_composite(capa)
    img.alpha_composite(sec, (sx, sy))

    # --- principal: grande, con más contraste y contorno verde neón
    pri = _escalar(principal, 640)
    alfa = pri.getchannel("A")
    rgb = ImageEnhance.Contrast(pri.convert("RGB")).enhance(1.18)
    rgb = ImageEnhance.Color(rgb).enhance(1.12)
    rgb = ImageEnhance.Sharpness(rgb).enhance(1.35)
    # luz de contorno: borde interior de la silueta, más fuerte por la derecha y arriba
    borde = ImageChops.subtract(alfa, ImageChops.offset(alfa, -9, 5).filter(ImageFilter.GaussianBlur(3)))
    borde = borde.filter(ImageFilter.GaussianBlur(2.2)).point(lambda v: min(255, int(v * 1.5)))
    rgb = Image.composite(Image.new("RGB", pri.size, (150, 255, 120)), rgb, borde)
    # sombra de atmósfera en la parte baja para fundirlo con el humo
    pri = rgb.convert("RGBA")
    pri.putalpha(alfa)
    px, py = 350 - pri.width // 2, base_y - pri.height
    halo = Image.new("L", (W, H), 0)
    halo.paste(alfa, (px, py))
    capa = Image.new("RGBA", (W, H), NEON + (0,))
    capa.putalpha(halo.filter(ImageFilter.GaussianBlur(20)).point(lambda v: int(v * 0.6)))
    img.alpha_composite(capa)
    img.alpha_composite(pri, (px, py))
    # humo por delante de la base de los dos retratos
    nube = _nubes((W, 260), 41).point(lambda v: int(v * 0.55))
    degradado = Image.linear_gradient("L").resize((W, 260))
    frente = Image.new("RGBA", (W, 260), (16, 120, 30, 0))
    frente.putalpha(ImageChops.multiply(nube, degradado))
    img.alpha_composite(frente, (0, CAJAS_Y - 220))
    _techo_negro(img)


def _insignia(ruta: str, redonda: bool, tam: int = 112) -> Image.Image:
    """Escudo auténtico tal cual (encajado). `redonda` = bandera de reserva en círculo."""
    src = Image.open(ruta).convert("RGBA")
    lienzo = Image.new("RGBA", (tam, tam), (0, 0, 0, 0))
    if redonda:
        lado = min(src.size)
        src = src.crop(((src.width - lado) // 2, (src.height - lado) // 2,
                        (src.width + lado) // 2, (src.height + lado) // 2)).resize((tam * 2, tam * 2), Image.LANCZOS)
        m = Image.new("L", (tam * 2, tam * 2), 0)
        ImageDraw.Draw(m).ellipse((8, 8, tam * 2 - 9, tam * 2 - 9), fill=255)
        src.putalpha(m)
        aro = Image.new("RGBA", (tam * 2, tam * 2), (0, 0, 0, 0))
        ImageDraw.Draw(aro).ellipse((0, 0, tam * 2 - 1, tam * 2 - 1), fill=(255, 255, 255, 255))
        aro.alpha_composite(src)
        return aro.resize((tam, tam), Image.LANCZOS)
    if src.getchannel("A").getbbox():
        src = src.crop(src.getchannel("A").getbbox())
    src.thumbnail((tam, tam), Image.LANCZOS)
    lienzo.alpha_composite(src, ((tam - src.width) // 2, (tam - src.height) // 2))
    return lienzo


def _texto_ajustado(d: ImageDraw.ImageDraw, texto: str, cx: int, cy: int, ancho_max: int, tam: int = 62) -> None:
    while tam > 26:
        f = ImageFont.truetype(FUENTE, tam)
        if d.textlength(texto, font=f) <= ancho_max:
            break
        tam -= 2
    d.text((cx + 2, cy + 3), texto, font=f, fill=(0, 0, 0, 200), anchor="mm")
    d.text((cx, cy), texto, font=f, fill=(255, 255, 255, 255), anchor="mm")


def _casilla(img: Image.Image, i: int, local, visitante) -> None:
    rect = caja_rect(i)
    x0, y0, x1, y1 = rect
    cy = (y0 + y1) // 2
    # sombra y relleno negro
    img.alpha_composite(_resplandor((W, H), lambda d: d.rounded_rectangle((x0 - 6, y0 - 4, x1 + 6, y1 + 10), RADIO, fill=230), 14, (0, 0, 0)))
    relleno = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(relleno).rounded_rectangle(rect, RADIO, fill=(3, 9, 4, 246))
    img.alpha_composite(relleno)
    # brillo interior suave en el centro y rayo diagonal tras el VS
    img.alpha_composite(_resplandor((W, H), lambda d: d.ellipse((W // 2 - 210, cy - 26, W // 2 + 210, cy + 26), fill=150), 34, (20, 170, 30)))
    img.alpha_composite(_resplandor((W, H), lambda d: d.line((W // 2 + 62, y0 + 6, W // 2 - 62, y1 - 6), fill=255, width=4), 7, NEON))
    img.alpha_composite(_resplandor((W, H), lambda d: d.line((W // 2 + 62, y0 + 6, W // 2 - 62, y1 - 6), fill=255, width=2), 1, (235, 255, 220)))
    # borde neón: halo ancho + halo corto + línea nítida
    img.alpha_composite(_resplandor((W, H), lambda d: d.rounded_rectangle(rect, RADIO, outline=255, width=12), 16, NEON))
    img.alpha_composite(_resplandor((W, H), lambda d: d.rounded_rectangle(rect, RADIO, outline=255, width=6), 4, (120, 255, 90)))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle(rect, RADIO, outline=NEON_CLARO + (255,), width=3)
    # separadores de las celdas de escudo
    for x in (x0 + CELDA, x1 - CELDA):
        img.alpha_composite(_resplandor((W, H), lambda dd, x=x: dd.line((x, y0 + 22, x, y1 - 22), fill=255, width=2), 2, NEON))
    # pestaña superior «PARTIDOS DE HOY»
    px0, px1, py0, py1 = W // 2 - 226, W // 2 + 226, y0 - 21, y0 + 21
    forma = [(px0, py0), (px1, py0), (px1 - 26, py1), (px0 + 26, py1)]
    img.alpha_composite(_resplandor((W, H), lambda dd: dd.polygon(forma, outline=255, width=8), 7, NEON))
    d = ImageDraw.Draw(img)
    d.polygon(forma, fill=(3, 9, 4, 255))
    d.line(forma + [forma[0]], fill=NEON_CLARO + (255,), width=3, joint="curve")
    ft = ImageFont.truetype(FUENTE, 33)
    _texto_espaciado(d, "PARTIDOS DE HOY", W // 2, y0 - 2, ft, 3)
    # escudos y nombres
    img.alpha_composite(_insignia(local.imagen, local.redonda), (x0 + CELDA // 2 - 56, cy - 56))
    img.alpha_composite(_insignia(visitante.imagen, visitante.redonda), (x1 - CELDA // 2 - 56, cy - 56))
    d = ImageDraw.Draw(img)
    centro_izq = (x0 + CELDA + W // 2 - 78) // 2
    ancho = W // 2 - 78 - (x0 + CELDA) - 20
    _texto_ajustado(d, local.nombre.upper(), centro_izq, cy + 6, ancho, 66)
    _texto_ajustado(d, visitante.nombre.upper(), W - centro_izq, cy + 6, ancho, 66)
    _vs(img, W // 2, cy + 6)


def _texto_espaciado(d, texto, cx, cy, fuente, espacio) -> None:
    anchos = [d.textlength(c, font=fuente) for c in texto]
    x = cx - (sum(anchos) + espacio * (len(texto) - 1)) / 2
    for c, a in zip(texto, anchos):
        d.text((x, cy), c, font=fuente, fill=(255, 255, 255, 255), anchor="lm")
        x += a + espacio


def _vs(img: Image.Image, cx: int, cy: int) -> None:
    """VS grande con degradado lima → verde neón y halo."""
    f = ImageFont.truetype(FUENTE, 104)
    m = Image.new("L", (W, H), 0)
    ImageDraw.Draw(m).text((cx, cy), "VS", font=f, fill=255, anchor="mm")
    for radio, color, fuerza in ((22, NEON, 0.9), (7, (120, 255, 60), 1.0)):
        capa = Image.new("RGBA", (W, H), color + (0,))
        capa.putalpha(m.filter(ImageFilter.GaussianBlur(radio)).point(lambda v, k=fuerza: int(v * k)))
        img.alpha_composite(capa)
    # contorno oscuro fino para separar del halo
    capa = Image.new("RGBA", (W, H), (0, 40, 0, 0))
    capa.putalpha(m.filter(ImageFilter.MaxFilter(5)))
    img.alpha_composite(capa)
    x0, y0, x1, y1 = m.getbbox()
    grad = Image.new("RGB", (1, 256))
    grad.putdata([tuple(int(LIMA[k] + (NEON[k] - LIMA[k]) * t / 255) for k in range(3)) for t in range(256)])
    grad = grad.resize((x1 - x0, y1 - y0))
    lleno = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    lleno.paste(grad, (x0, y0))
    lleno.putalpha(m)
    img.alpha_composite(lleno)


def generar(partidos: list[tuple], foto_jugador: tuple | None, carpeta: Path) -> dict:
    """partidos: [(Equipo local, Equipo visitante)] x4.
    foto_jugador: (ruta, es_recorte[, ruta_secundaria, es_recorte_secundaria])."""
    carpeta.mkdir(parents=True, exist_ok=True)
    fondo = _fondo_estadio()
    img = fondo.copy()
    if foto_jugador:
        _pegar_jugador(img, *foto_jugador)
        corte = CAJAS_Y + 70          # el torso muere tras la primera casilla, no asoma entre ellas
        img.paste(fondo.crop((0, corte, W, H)), (0, corte))
    for i, (local, visitante) in enumerate(partidos):
        _casilla(img, i, local, visitante)
    rutas = {"base": str(carpeta / "base.png"), "resaltes": [], "flash": str(carpeta / "flash.png")}
    img.convert("RGB").save(rutas["base"])

    # resalte del partido activo: los otros tres se apagan, el activo brilla
    for i in range(len(partidos)):
        capa = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        d = ImageDraw.Draw(capa)
        for j in range(len(partidos)):
            if j != i:
                x0, y0, x1, y1 = caja_rect(j)
                d.rounded_rectangle((x0 - 8, y0 - 26, x1 + 8, y1 + 8), RADIO, fill=(0, 0, 0, 150))
        rect = caja_rect(i)
        capa.alpha_composite(_resplandor((W, H), lambda dd: dd.rounded_rectangle(rect, RADIO, outline=255, width=14), 16, NEON))
        capa.alpha_composite(_resplandor((W, H), lambda dd: dd.rounded_rectangle(rect, RADIO, fill=18), 2, NEON))
        ImageDraw.Draw(capa).rounded_rectangle(rect, RADIO, outline=(255, 255, 255, 255), width=5)
        # la pestaña «PARTIDOS DE HOY» de la casilla activa queda intacta
        x0, y0, x1, y1 = rect
        hueco = Image.new("L", (W, H), 255)
        ImageDraw.Draw(hueco).polygon([(W // 2 - 228, y0 - 23), (W // 2 + 228, y0 - 23),
                                       (W // 2 + 201, y0 + 22), (W // 2 - 201, y0 + 22)], fill=0)
        capa.putalpha(ImageChops.multiply(capa.getchannel("A"), hueco))
        ruta = str(carpeta / f"resalte_{i}.png")
        capa.save(ruta)
        rutas["resaltes"].append(ruta)

    # flash verde-blanco para los cambios de partido (solo zona inferior)
    grad = ImageChops.invert(Image.radial_gradient("L")).resize((W * 2, (H - ZONA_Y) * 2))
    grad = grad.crop((W // 2, (H - ZONA_Y) // 2, W // 2 + W, (H - ZONA_Y) // 2 + H - ZONA_Y))
    flash = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    zona = Image.new("RGBA", (W, H - ZONA_Y), (200, 255, 190, 0))
    zona.putalpha(grad.point(lambda v: min(255, int(v * 1.15))))
    flash.alpha_composite(zona, (0, ZONA_Y))
    flash.save(rutas["flash"])
    return rutas
