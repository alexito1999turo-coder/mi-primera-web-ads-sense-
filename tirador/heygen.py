"""Cliente mínimo de la API v3 de HeyGen (v1/v2 se retiraron el 31-10-2026).

La clave se lee de HEYGEN_API_KEY. En las sesiones en la nube de Claude Code la
inyecta el proxy del entorno, así que si la variable no existe se envía un
marcador que el proxy sustituye.
"""
from __future__ import annotations

import os
import time

import requests

API = "https://api.heygen.com"


def _cabeceras() -> dict:
    return {"X-Api-Key": os.environ.get("HEYGEN_API_KEY", "proxy-injected"),
            "Content-Type": "application/json"}


def _comprobar(r: requests.Response) -> dict:
    if r.status_code >= 400:
        raise SystemExit(f"HeyGen respondió {r.status_code}: {r.text[:500]}")
    return r.json()


def listar_avatares() -> list[dict]:
    salida, token = [], None
    while True:
        params = {"ownership": "private", "limit": 50}
        if token:
            params["token"] = token
        d = _comprobar(requests.get(f"{API}/v3/avatars/looks", params=params, headers=_cabeceras(), timeout=60))
        salida += d.get("data", [])
        token = d.get("next_token")
        if not d.get("has_more") or not token:
            return salida


def crear_video(guion: str, avatar_id: str, voice_id: str | None, velocidad: float = 1.0,
                titulo: str | None = None) -> str:
    cuerpo = {
        "type": "avatar",
        "avatar_id": avatar_id,
        "script": guion,
        "aspect_ratio": "16:9",
        "resolution": "1080p",
        "caption": {"file_format": "srt"},
        "title": titulo,
    }
    if voice_id:
        cuerpo["voice_id"] = voice_id
    if velocidad != 1.0:
        cuerpo["voice_settings"] = {"speed": velocidad}
    d = _comprobar(requests.post(f"{API}/v3/videos", json=cuerpo, headers=_cabeceras(), timeout=60))
    return d["data"]["video_id"]


def esperar_video(video_id: str, max_minutos: int = 30, aviso=print) -> dict:
    limite = time.time() + max_minutos * 60
    ultimo = None
    while time.time() < limite:
        d = _comprobar(requests.get(f"{API}/v3/videos/{video_id}", headers=_cabeceras(), timeout=60))["data"]
        if d["status"] != ultimo:
            ultimo = d["status"]
            aviso(f"  HeyGen: {ultimo}")
        if d["status"] == "completed":
            return d
        if d["status"] == "failed":
            raise SystemExit(f"HeyGen falló: {d.get('failure_code')} — {d.get('failure_message')}")
        time.sleep(10)
    raise SystemExit(f"HeyGen no terminó en {max_minutos} min (video_id={video_id}). "
                     f"Reanuda con --video-id {video_id} para no pagar dos veces.")


def bajar(url: str, destino: str) -> str:
    # Las URL de descarga van firmadas: no se les envía la clave.
    with requests.get(url, stream=True, timeout=300) as r:
        r.raise_for_status()
        with open(destino, "wb") as f:
            for trozo in r.iter_content(1 << 20):
                f.write(trozo)
    return destino
