"""Generador diario de vídeos de El Tirador.

    python -m tirador avatares                 lista tus avatares de HeyGen
    python -m tirador partidos [AAAA-MM-DD]    propone los 4 partidos del día y crea el borrador
    python -m tirador tirador/dias/HOY.json    genera el vídeo del día
      --solo-plantilla        solo pinta la plantilla (gratis, no llama a HeyGen)
      --video-id ID           reutiliza un vídeo de HeyGen ya generado (no vuelve a cobrar)
      --avatar-video F.mp4    usa un vídeo local de Julen en vez de llamar a HeyGen
      --srt F.srt             subtítulos con tiempos para ese vídeo local
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import arte, datos, maestra as maestra_mod, heygen, montaje, partidos as partidos_mod, plantilla, sonido, subs
from .equipos import Equipo, normalizar, resolver

RAIZ = Path(__file__).resolve().parent


def _config() -> dict:
    return json.loads((RAIZ / "config.json").read_text(encoding="utf-8"))


def _elegir_estrella(dia: dict, equipos: list[Equipo]) -> tuple[str | None, tuple[str, bool] | None]:
    if dia.get("foto_estrella"):
        return dia.get("estrella"), (dia["foto_estrella"], dia.get("foto_es_recorte", True),
                                     dia.get("foto_secundaria"), dia.get("foto_secundaria_es_recorte", True))
    if dia.get("estrella"):
        candidatos = [dia["estrella"]]
    else:
        print("Calculando el jugador más famoso (visitas a Wikipedia, 30 días)…")
        try:
            ranking = datos.ranking_fama([(e.nombre_busqueda, e.es_seleccion) for e in equipos])
        except Exception as e:  # Wikipedia limita a menudo las IP de centros de datos
            raise SystemExit(f"No pude calcular la estrella automáticamente ({e}). "
                             f"Añade \"estrella\": \"Nombre Apellido\" al JSON del día.")
        for nombre, visitas in ranking[:5]:
            print(f"   {visitas:>9,}  {nombre}")
        candidatos = [n.split(" (")[0] for n, _ in ranking[:5]]
    for nombre in candidatos:
        foto = datos.foto_jugador(nombre)
        if foto:
            return nombre, foto
    raise SystemExit(f"No hay foto disponible para {candidatos}. Pon \"foto_estrella\": \"ruta.png\" en el JSON.")


def generar(args) -> None:
    dia = json.loads(Path(args.dia).read_text(encoding="utf-8"))
    cfg = _config()
    if len(dia["partidos"]) != 4:
        raise SystemExit("La plantilla es de exactamente 4 partidos.")
    carpeta = RAIZ / "salida" / (dia.get("fecha") or Path(args.dia).stem)
    carpeta.mkdir(parents=True, exist_ok=True)

    manuales = {normalizar(k): v for k, v in (dia.get("escudos") or {}).items()}
    def equipo(nombre: str) -> Equipo:
        if dia.get("plantilla_imagen") and not dia.get("maestra"):   # escudos ya pintados en la imagen
            return Equipo(nombre, False, "", nombre)
        if normalizar(nombre) in manuales:
            return Equipo(nombre, False, manuales[normalizar(nombre)], nombre)
        return resolver(nombre, datos)
    partidos = [(equipo(a), equipo(b)) for a, b in dia["partidos"]]
    ruta_arte, foto = dia.get("arte"), None
    if dia.get("plantilla_imagen"):                 # plantilla completa hecha fuera (ChatGPT)
        estrella = dia.get("estrella") or "(en la imagen)"
    elif ruta_arte:                                   # arte ya hecho (p. ej. en la app de Gemini)
        estrella = dia.get("estrella")
    elif dia.get("arte_gemini"):                    # arte por API: gasta saldo de Gemini
        estrella = dia.get("estrella") or sys.exit('Con "arte_gemini" hace falta "estrella".')
        ruta_arte = str(carpeta / "arte.jpg")
        if not Path(ruta_arte).exists():
            identidad = datos.foto_jugador(estrella)
            print("Generando arte con Gemini…")
            arte.generar(estrella, dia.get("equipo_estrella", ""), ruta_arte, cfg.get("modelo_arte", "gemini-3-pro-image"),
                         [identidad[0]] if identidad else None)
    else:
        estrella, foto = _elegir_estrella(dia, [e for p in partidos for e in p])
    print(f"Jugador estrella: {estrella}")
    if dia.get("maestra"):
        rutas = maestra_mod.componer(partidos, foto, carpeta, estrella)
    elif dia.get("plantilla_imagen"):
        rutas = plantilla.desde_imagen(dia["plantilla_imagen"], carpeta)
        if not rutas["casillas"]:
            print("AVISO: no localizo las 4 casillas en la plantilla; el vídeo irá con flashes pero sin resalte.",
                  file=sys.stderr)
    else:
        rutas = plantilla.generar(partidos, foto, carpeta, ruta_arte)
    print(f"Plantilla: {rutas['base']}")
    if args.solo_plantilla:
        return

    texto, tramos_guion = subs.aplanar_guion(dia["guion"])
    # antes de gastar créditos: el guion tiene que dejar claro dónde empieza cada partido
    previo = subs.tramos_partidos(subs.tiempos_palabras(texto, [], 60.0), tramos_guion, partidos, 60.0)
    if [i for i, _, _ in previo] != [0, 1, 2, 3]:
        raise SystemExit("El guion no permite localizar los 4 partidos en orden (hacen falta 4 flashes, uno por "
                         "partido). Escríbelo por bloques: intro / partidos x4 / cierre.")
    info_f = carpeta / "info.json"
    info = json.loads(info_f.read_text()) if info_f.exists() else {}
    cues = []
    if args.avatar_video:
        video = args.avatar_video
        if args.srt:
            cues = subs.leer_srt(Path(args.srt).read_text(encoding="utf-8"))
    else:
        video_id = args.video_id or (info.get("video_id") if info.get("guion") == texto else None)
        if not video_id:
            print(f"Enviando guion a HeyGen ({len(texto.split())} palabras)…")
            video_id = heygen.crear_video(texto, cfg["avatar_id"], cfg.get("voice_id"),
                                          cfg.get("velocidad", 1.0), f"El Tirador {carpeta.name}")
            info_f.write_text(json.dumps({"video_id": video_id, "guion": texto}, ensure_ascii=False))
        else:
            print(f"Reutilizando vídeo de HeyGen {video_id} (sin coste nuevo)")
        d = heygen.esperar_video(video_id)
        video = heygen.bajar(d["video_url"], str(carpeta / "julen_heygen.mp4"))
        if d.get("subtitle_url"):
            srt = heygen.bajar(d["subtitle_url"], str(carpeta / "julen.srt"))
            cues = subs.leer_srt(Path(srt).read_text(encoding="utf-8"))

    dur = montaje.duracion(video)
    palabras = subs.tiempos_palabras(texto, cues, dur)
    tramos = subs.tramos_partidos(palabras, tramos_guion, partidos, dur, montaje.arranques_voz(video))
    for idx, ini, _ in tramos:
        print(f"  flash + clic  {ini:6.2f} s  →  {partidos[idx][0].nombre} - {partidos[idx][1].nombre}")
    if not cues:
        print("AVISO: sin SRT de HeyGen; los subtítulos van con tiempos estimados.", file=sys.stderr)
    ass = str(carpeta / "subtitulos.ass")
    subs.escribir_ass(palabras, ass, y=rutas.get("sub_y"))
    final = montaje.montar(video, rutas, tramos, ass, str(carpeta / "final.mp4"),
                           sonido.clic_camara(str(carpeta / "clic.wav")))
    print(f"LISTO: {final}  ({dur:.1f} s)")


def main() -> None:
    ap = argparse.ArgumentParser(prog="tirador", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("dia", help="JSON del día, o las palabras 'avatares' / 'partidos'")
    ap.add_argument("fecha", nargs="?", help="con 'partidos': AAAA-MM-DD (por defecto, hoy)")
    ap.add_argument("--solo-plantilla", action="store_true")
    ap.add_argument("--video-id")
    ap.add_argument("--avatar-video")
    ap.add_argument("--srt")
    args = ap.parse_args()
    if args.dia == "maestra":
        maestra_mod.preparar(args.fecha or sys.exit("Uso: python -m tirador maestra RUTA.png"))
        return
    if args.dia == "partidos":
        from datetime import date
        partidos_mod.proponer(date.fromisoformat(args.fecha) if args.fecha else date.today(), RAIZ / "dias")
        return
    if args.dia == "avatares":
        for a in heygen.listar_avatares():
            print(f"{a['id']}  voz={a.get('default_voice_id')}  {a.get('preferred_orientation')}  {a['name']}")
        return
    generar(args)


if __name__ == "__main__":
    main()
