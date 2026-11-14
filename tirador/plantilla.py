"""Plantilla fija de El Tirador (1080x1920). Siempre el mismo diseño:
negro profundo, verde neón, jugador estrella y cuatro casillas de partido.

Genera: base.png, resalte_0..3.png (partido activo) y flash.png.
"""
from __future__ import annotations

import random
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont

W, H = 1080, 1920
AVATAR_Y, AVATAR_H = 110, 608          # vídeo de Julen: 1080x608 (16:9)
ZONA_Y = AVATAR_Y + AVATAR_H           # 718: empieza el jugador
CAJAS_Y, CAJA_H, CAJA_SEP, CAJA_MX = 1250, 126, 14, 20
NEON = (57, 255, 20)
NEON_CLARO = (190, 255, 170)
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


def _fondo_estadio() -> Image.Image:
    rnd = random.Random(7)  # semilla fija: el fondo es idéntico todos los días
    img = Image.new("RGBA", (W, H), (0, 0, 0, 255))
    # resplandor verde general tras el jugador
    img.alpha_composite(_resplandor((W, H), lambda d: d.ellipse((90, ZONA_Y + 40, W - 90, CAJAS_Y + 120), fill=120), 110, (20, 150, 30)))
    # gradas: bandas curvas tenues
    for k in range(5):
        y = ZONA_Y + 70 + k * 46
        img.alpha_composite(_resplandor((W, H), lambda d, y=y: d.arc((-200, y, W + 200, y + 420), 180, 360, fill=70, width=5), 5, (40, 200, 60)))
    # focos de estadio en las esquinas
    def focos(d):
        for lado in (0, 1):
            for fila in range(3):
                for col in range(6):
                    x = 40 + col * 34 + fila * 10
                    x = x if lado == 0 else W - x
                    y = ZONA_Y + 40 + fila * 30 + col * 6
                    d.ellipse((x - 9, y - 9, x + 9, y + 9), fill=255)
    img.alpha_composite(_resplandor((W, H), focos, 16, (120, 255, 120)))
    img.alpha_composite(_resplandor((W, H), focos, 3, (235, 255, 235)))
    # humo verde en la base del jugador y detrás de las casillas
    def humo(d):
        for _ in range(70):
            x, y = rnd.randint(-60, W + 60), rnd.randint(CAJAS_Y - 190, H - 60)
            r = rnd.randint(50, 150)
            d.ellipse((x - r, y - r // 2, x + r, y + r // 2), fill=rnd.randint(35, 110))
    img.alpha_composite(_resplandor((W, H), humo, 38, (30, 200, 40)))
    # negro limpio arriba (zona del avatar) y fundido corto en la unión
    d = ImageDraw.Draw(img)
    d.rectangle((0, 0, W, ZONA_Y), fill=(0, 0, 0, 255))
    fundido = Image.new("RGBA", (W, 70), (0, 0, 0, 0))
    fd = ImageDraw.Draw(fundido)
    for y in range(70):
        fd.line((0, y, W, y), fill=(0, 0, 0, int(255 * (1 - y / 70) ** 1.6)))
    img.alpha_composite(fundido, (0, ZONA_Y))
    return img


def _pegar_jugador(img: Image.Image, ruta: str, es_recorte: bool) -> None:
    foto = Image.open(ruta).convert("RGBA")
    alto_zona = CAJAS_Y - ZONA_Y
    if es_recorte and foto.getchannel("A").getextrema()[0] < 250:
        foto = foto.crop(foto.getchannel("A").getbbox())
        alto = alto_zona + 20
        ancho = int(foto.width * alto / foto.height)
        if ancho > W - 80:
            ancho, alto = W - 80, int(foto.height * (W - 80) / foto.width)
        foto = foto.resize((ancho, alto), Image.LANCZOS)
    else:
        # foto normal: se encaja y se difuminan los bordes para integrarla en el fondo
        alto = alto_zona + 20
        ancho = int(foto.width * alto / foto.height)
        foto = foto.resize((ancho, alto), Image.LANCZOS)
        if ancho > 760:
            x0 = (ancho - 760) // 2
            foto = foto.crop((x0, 0, x0 + 760, alto))
        m = Image.new("L", foto.size, 0)
        ImageDraw.Draw(m).ellipse((40, 30, foto.width - 40, foto.height + 160), fill=255)
        foto.putalpha(m.filter(ImageFilter.GaussianBlur(45)))
    x, y = (W - foto.width) // 2, CAJAS_Y + 24 - foto.height
    # halo verde alrededor de la silueta
    halo = Image.new("RGBA", (W, H), NEON + (0,))
    mascara = Image.new("L", (W, H), 0)
    mascara.paste(foto.getchannel("A"), (x, y))
    halo.putalpha(mascara.filter(ImageFilter.GaussianBlur(22)).point(lambda v: int(v * 0.55)))
    img.alpha_composite(halo)
    img.alpha_composite(foto, (x, y))
    # la unión con el avatar siempre queda en negro limpio
    ImageDraw.Draw(img).rectangle((0, 0, W, ZONA_Y), fill=(0, 0, 0, 255))


def _insignia(ruta: str, es_seleccion: bool, tam: int = 96) -> Image.Image:
    src = Image.open(ruta).convert("RGBA")
    lienzo = Image.new("RGBA", (tam + 12, tam + 12), (0, 0, 0, 0))
    if es_seleccion:
        lado = min(src.size)
        src = src.crop(((src.width - lado) // 2, (src.height - lado) // 2,
                        (src.width + lado) // 2, (src.height + lado) // 2)).resize((tam * 2, tam * 2), Image.LANCZOS)
        m = Image.new("L", (tam * 2, tam * 2), 0)
        ImageDraw.Draw(m).ellipse((0, 0, tam * 2 - 1, tam * 2 - 1), fill=255)
        src.putalpha(m)
        src = src.resize((tam, tam), Image.LANCZOS)
        aro = Image.new("RGBA", ((tam + 12) * 2, (tam + 12) * 2), (0, 0, 0, 0))
        ImageDraw.Draw(aro).ellipse((2, 2, aro.width - 3, aro.height - 3), fill=(255, 255, 255, 255))
        lienzo.alpha_composite(aro.resize(lienzo.size, Image.LANCZOS))
        lienzo.alpha_composite(src, (6, 6))
    else:
        src.thumbnail((tam + 8, tam + 8), Image.LANCZOS)
        lienzo.alpha_composite(src, ((lienzo.width - src.width) // 2, (lienzo.height - src.height) // 2))
    return lienzo


def _texto_ajustado(d: ImageDraw.ImageDraw, texto: str, cx: int, cy: int, ancho_max: int, tam: int = 62) -> None:
    while tam > 26:
        f = ImageFont.truetype(FUENTE, tam)
        if d.textlength(texto, font=f) <= ancho_max:
            break
        tam -= 2
    d.text((cx + 2, cy + 3), texto, font=f, fill=(0, 0, 0, 200), anchor="mm")
    d.text((cx, cy), texto, font=f, fill=(255, 255, 255, 255), anchor="mm")


def _borde_neon(img: Image.Image, rect, intensidad: float = 1.0) -> None:
    r = CAJA_H // 2
    img.alpha_composite(_resplandor((W, H), lambda d: d.rounded_rectangle(rect, r, outline=int(255 * min(1, intensidad)), width=int(12 * intensidad)), 12 * intensidad, NEON))
    ImageDraw.Draw(img).rounded_rectangle(rect, r, outline=NEON_CLARO + (255,), width=4)


def generar(partidos: list[tuple], foto_jugador: tuple[str, bool] | None, carpeta: Path) -> dict:
    """partidos: [(Equipo local, Equipo visitante)] x4."""
    carpeta.mkdir(parents=True, exist_ok=True)
    img = _fondo_estadio()
    if foto_jugador:
        _pegar_jugador(img, *foto_jugador)
    for i, (local, visitante) in enumerate(partidos):
        rect = caja_rect(i)
        x0, y0, x1, y1 = rect
        cy = (y0 + y1) // 2
        relleno = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        ImageDraw.Draw(relleno).rounded_rectangle(rect, CAJA_H // 2, fill=(2, 10, 3, 238))
        img.alpha_composite(relleno)
        # destello central vertical y horizontal bajo el VS
        img.alpha_composite(_resplandor((W, H), lambda d: d.ellipse((W // 2 - 150, cy - 10, W // 2 + 150, cy + 10), fill=200), 22, NEON))
        img.alpha_composite(_resplandor((W, H), lambda d: d.line((W // 2, y0 - 6, W // 2, y1 + 6), fill=255, width=3), 3, NEON_CLARO))
        _borde_neon(img, rect)
        img.alpha_composite(_insignia(local.imagen, local.es_seleccion), (x0 + 16, cy - 54))
        img.alpha_composite(_insignia(visitante.imagen, visitante.es_seleccion), (x1 - 16 - 108, cy - 54))
        d = ImageDraw.Draw(img)
        _texto_ajustado(d, local.nombre.upper(), 304, cy - 2, 310)
        _texto_ajustado(d, visitante.nombre.upper(), W - 304, cy - 2, 310)
        fvs = ImageFont.truetype(FUENTE, 70)
        img.alpha_composite(_resplandor((W, H), lambda d2: d2.text((W // 2, cy - 2), "VS", font=fvs, fill=255, anchor="mm"), 9, NEON))
        ImageDraw.Draw(img).text((W // 2, cy - 2), "VS", font=fvs, fill=NEON + (255,), anchor="mm")
    rutas = {"base": str(carpeta / "base.png"), "resaltes": [], "flash": str(carpeta / "flash.png")}
    img.convert("RGB").save(rutas["base"])

    # resalte del partido activo: los otros tres se apagan, el activo brilla
    for i in range(len(partidos)):
        capa = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        d = ImageDraw.Draw(capa)
        for j in range(len(partidos)):
            if j != i:
                x0, y0, x1, y1 = caja_rect(j)
                d.rounded_rectangle((x0 - 8, y0 - 6, x1 + 8, y1 + 6), CAJA_H // 2, fill=(0, 0, 0, 150))
        rect = caja_rect(i)
        capa.alpha_composite(_resplandor((W, H), lambda dd: dd.rounded_rectangle(rect, CAJA_H // 2, outline=255, width=14), 16, NEON))
        capa.alpha_composite(_resplandor((W, H), lambda dd: dd.rounded_rectangle(rect, CAJA_H // 2, fill=22), 2, NEON))
        ImageDraw.Draw(capa).rounded_rectangle(rect, CAJA_H // 2, outline=(255, 255, 255, 255), width=5)
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
