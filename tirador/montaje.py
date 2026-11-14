"""Montaje final con ffmpeg: plantilla + vídeo de Julen + resaltes + flashes + subtítulos."""
from __future__ import annotations

import json
import re
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


def arranques_voz(ruta: str) -> list[float]:
    """Instantes en que la voz arranca tras una pausa (fin de cada silencio)."""
    r = subprocess.run(["ffmpeg", "-v", "info", "-i", ruta, "-vn", "-af", "silencedetect=noise=-34dB:d=0.16",
                        "-f", "null", "-"], capture_output=True, text=True)
    return [float(x) for x in re.findall(r"silence_end: ([0-9.]+)", r.stderr)]


def montar(video_avatar: str, rutas: dict, tramos: list, ass: str, salida: str, clic: str | None = None) -> str:
    """Un flash y un clic de cámara por partido, justo cuando Julen empieza a hablar de él.
    Nunca hay flashes fuera de esos instantes."""
    dur = duracion(video_avatar)
    bucle = ["-loop", "1", "-framerate", "30", "-t", f"{dur:.3f}"]
    cmd = ["ffmpeg", "-y", "-v", "error", "-i", video_avatar, *bucle, "-i", rutas["base"]]
    filtros = [
        f"[0:v]scale={W}:{AVATAR_H}:force_original_aspect_ratio=increase,crop={W}:{AVATAR_H},setsar=1,fps=30[av]",
        f"[1:v][av]overlay=0:{AVATAR_Y}[v0]",
    ]
    n, actual = 2, "v0"
    for idx, ini, fin in tramos:   # resalte del partido del que se está hablando
        cmd += [*bucle, "-i", rutas["resaltes"][idx]]
        filtros.append(f"[{n}:v]format=rgba,fade=t=in:st={ini:.3f}:d=0.10:alpha=1,"
                       f"fade=t=out:st={max(ini, fin - 0.15):.3f}:d=0.15:alpha=1[r{n}]")
        filtros.append(f"[{actual}][r{n}]overlay=0:0:enable='between(t,{ini:.3f},{fin:.3f})'[v{n}]")
        actual, n = f"v{n}", n + 1
    for _, ini, _ in tramos:       # flash: empieza en el instante exacto, nunca antes
        cmd += [*bucle, "-i", rutas["flash"]]
        filtros.append(f"[{n}:v]format=rgba,fade=t=in:st={ini:.3f}:d=0.04:alpha=1,"
                       f"fade=t=out:st={ini + 0.04:.3f}:d=0.36:alpha=1[f{n}]")
        filtros.append(f"[{actual}][f{n}]overlay=0:0:enable='between(t,{ini:.3f},{ini + 0.42:.3f})'[v{n}]")
        actual, n = f"v{n}", n + 1
    filtros.append(f"[{actual}]ass='{_esc(ass)}':fontsdir='{_esc(str(FUENTES))}'[vf]")
    audio = "0:a?"
    if clic and tramos:
        mezcla = ["[0:a]"]
        for _, ini, _ in tramos:
            cmd += ["-i", clic]
            filtros.append(f"[{n}:a]adelay={int(round(ini * 1000))}:all=1,volume=0.9[c{n}]")
            mezcla.append(f"[c{n}]")
            n += 1
        filtros.append("".join(mezcla) + f"amix=inputs={len(mezcla)}:normalize=0:duration=first[af]")
        audio = "[af]"
    cmd += ["-filter_complex", ";".join(filtros), "-map", "[vf]", "-map", audio,
            "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p", "-r", "30",
            "-c:a", "aac", "-b:a", "192k", "-t", f"{dur:.3f}", "-movflags", "+faststart", salida]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        raise SystemExit("ffmpeg falló:\n" + r.stderr[-2000:])
    return salida
