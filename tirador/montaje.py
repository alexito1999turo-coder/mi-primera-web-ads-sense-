"""Montaje final con ffmpeg: plantilla + vídeo de Julen + resaltes + flashes + subtítulos."""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

from .plantilla import AVATAR_H, AVATAR_Y, W

FUENTES = Path(__file__).resolve().parent / "fuentes"


def duracion(ruta: str) -> float:
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "json", ruta],
                         capture_output=True, text=True, check=True).stdout
    return float(json.loads(out)["format"]["duration"])


def _esc(ruta: str) -> str:
    return ruta.replace("\\", "/").replace(":", "\\:").replace("'", "\\'")


def montar(video_avatar: str, rutas: dict, tramos: list, ass: str, salida: str) -> str:
    dur = duracion(video_avatar)
    bucle = ["-loop", "1", "-framerate", "30", "-t", f"{dur:.3f}"]
    cmd = ["ffmpeg", "-y", "-v", "error", "-i", video_avatar, *bucle, "-i", rutas["base"]]
    filtros = [
        f"[0:v]scale={W}:{AVATAR_H}:force_original_aspect_ratio=increase,crop={W}:{AVATAR_H},setsar=1,fps=30[av]",
        f"[1:v][av]overlay=0:{AVATAR_Y}[v0]",
    ]
    n, actual = 2, "v0"
    # resalte del partido del que se está hablando
    for idx, ini, fin in tramos:
        cmd += [*bucle, "-i", rutas["resaltes"][idx]]
        filtros.append(f"[{n}:v]format=rgba,fade=t=in:st={ini:.2f}:d=0.18:alpha=1,"
                       f"fade=t=out:st={max(ini, fin - 0.18):.2f}:d=0.18:alpha=1[r{n}]")
        filtros.append(f"[{actual}][r{n}]overlay=0:0:enable='between(t,{ini:.2f},{fin:.2f})'[v{n}]")
        actual, n = f"v{n}", n + 1
    # flash en cada cambio de partido
    for _, ini, _ in tramos:
        cmd += [*bucle, "-i", rutas["flash"]]
        a = max(0.0, ini - 0.05)
        filtros.append(f"[{n}:v]format=rgba,fade=t=in:st={a:.2f}:d=0.05:alpha=1,"
                       f"fade=t=out:st={a + 0.05:.2f}:d=0.38:alpha=1[f{n}]")
        filtros.append(f"[{actual}][f{n}]overlay=0:0:enable='between(t,{a:.2f},{a + 0.45:.2f})'[v{n}]")
        actual, n = f"v{n}", n + 1
    filtros.append(f"[{actual}]ass='{_esc(ass)}':fontsdir='{_esc(str(FUENTES))}'[vf]")
    cmd += ["-filter_complex", ";".join(filtros), "-map", "[vf]", "-map", "0:a?",
            "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p", "-r", "30",
            "-c:a", "aac", "-b:a", "192k", "-t", f"{dur:.3f}", "-movflags", "+faststart", salida]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        raise SystemExit("ffmpeg falló:\n" + r.stderr[-2000:])
    return salida
