"""Arte cinemático del jugador generado con Gemini (API Interactions).

Gemini pinta SOLO el arte: doble retrato del jugador sobre el estadio. Casillas,
nombres y escudos los compone plantilla.py, para que sean idénticos cada día y
los escudos sean siempre archivos auténticos.

SIN PROBAR contra la API real: está escrito según la documentación de noviembre
de 2026 y falta ejecutarlo con una clave. La clave se lee de GEMINI_API_KEY (o la
inyecta el proxy del entorno en la nube).
"""
from __future__ import annotations

import base64
import os
from pathlib import Path

import requests

RAIZ = Path(__file__).resolve().parent
MAESTRA = RAIZ / "referencia" / "maestra.png"
URL = "https://generativelanguage.googleapis.com/v1beta/interactions"

PROMPT = """Crea SOLO el arte superior de un póster deportivo, formato horizontal 16:9, sin ningún texto,
sin logotipos, sin escudos, sin casillas ni marcos.

Protagonista: {jugador}, futbolista de {equipo}, con la equipación actual de {equipo}.
- Retrato principal grande (rostro y torso), fotorrealista, calidad editorial deportiva, encuadre
  cinematográfico ligeramente desde abajo, expresión intensa o de celebración, situado centro-izquierda.
- Segundo retrato del mismo jugador en otro ángulo (de espaldas o de perfil, celebrando), detrás y a la
  derecha, en monocromo verde oscuro.
- Fondo: estadio nocturno, focos intensos, humo volumétrico verde, haces de luz verde neón en diagonal.
- Paleta obligatoria: negro profundo y verde neón/lima. Luz de contorno verde neón sobre el jugador.
- El tercio inferior debe fundirse en humo verde oscuro (ahí se superponen gráficos después).

La primera imagen adjunta es la REFERENCIA MAESTRA de estilo: iguala su realismo, iluminación, color y
composición de la parte superior. No copies sus textos ni sus casillas.{extra}"""


def _img(ruta: str | Path) -> dict:
    ruta = Path(ruta)
    tipo = "image/png" if ruta.suffix.lower() == ".png" else "image/jpeg"
    return {"type": "image", "data": base64.b64encode(ruta.read_bytes()).decode(), "mime_type": tipo}


def generar(jugador: str, equipo: str, salida: str, modelo: str = "gemini-3-pro-image",
            fotos_identidad: list[str] | None = None) -> str:
    extra = ""
    entradas = [_img(MAESTRA)]
    for f in fotos_identidad or []:
        entradas.append(_img(f))
        extra = "\nLas demás imágenes adjuntas son fotos reales del jugador: úsalas solo para clavar su parecido."
    cuerpo = {
        "model": modelo,
        "generation_config": {"response_modalities": ["image"]},
        "response_format": {"type": "image", "aspect_ratio": "16:9", "image_size": "2K", "mime_type": "image/png"},
        "input": [{"type": "text", "text": PROMPT.format(jugador=jugador, equipo=equipo, extra=extra)}, *entradas],
    }
    r = requests.post(URL, json=cuerpo, timeout=300, headers={
        "x-goog-api-key": os.environ.get("GEMINI_API_KEY", "proxy-injected"), "Content-Type": "application/json"})
    if r.status_code >= 400:
        raise SystemExit(f"Gemini respondió {r.status_code}: {r.text[:600]}")
    for paso in r.json().get("steps", []):
        for c in paso.get("content", []) or []:
            if c.get("type") == "image" and c.get("data"):
                Path(salida).write_bytes(base64.b64decode(c["data"]))
                return salida
    raise SystemExit("Gemini no devolvió imagen (puede haber rechazado el retrato de una persona real): "
                     + r.text[:400])
