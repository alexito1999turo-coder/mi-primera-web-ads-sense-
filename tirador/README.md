# El Tirador — generador diario de vídeos

Un comando produce el vídeo vertical (1080x1920) del día con diseño fijo:

1. **Capa 1** — Julen (avatar de HeyGen) arriba, sobre negro limpio, sin marcos.
2. **Capa 2** — jugador estrella de uno de los ocho equipos, integrado en el fondo de estadio.
3. **Capa 3** — cuatro casillas negras con borde verde neón, VS central, bandera/escudo y nombres en blanco.
4. **Capa 4** — subtítulos palabra a palabra (la que suena, en verde), resalte del partido del que se habla y flash en cada cambio.

## Uso diario

Crea `tirador/dias/AAAA-MM-DD.json` (copia `dias/ejemplo.json`) y ejecuta:

```bash
python -m tirador tirador/dias/AAAA-MM-DD.json --solo-plantilla   # gratis: revisa el diseño
python -m tirador tirador/dias/AAAA-MM-DD.json                    # gasta créditos de HeyGen
```

Resultado en `tirador/salida/AAAA-MM-DD/final.mp4`.

| Campo | Obligatorio | Qué es |
|---|---|---|
| `partidos` | sí | Exactamente 4 pares `["Local", "Visitante"]` |
| `guion` | sí | Lo que dice Julen. Mejor por bloques: `{"intro", "partidos": [4 textos], "cierre"}`; así el resalte de cada casilla es exacto. También admite un texto único (se detecta la primera mención de cada equipo). |
| `estrella` | recomendado | Nombre del jugador. Si falta se intenta calcular por visitas a Wikipedia, que falla a menudo desde servidores en la nube. |
| `foto_estrella` | no | PNG propio (recortado, con transparencia) en lugar de la foto automática |
| `escudos` | no | `{"Nombre": "ruta.png"}` para forzar un escudo |

Otras opciones: `--video-id ID` reutiliza un vídeo de HeyGen ya pagado; `--avatar-video F.mp4 [--srt F.srt]`
monta sobre un vídeo local; `python -m tirador avatares` lista tus avatares.

## Configuración

`config.json` fija el avatar y la voz de Julen. La clave de HeyGen se lee de `HEYGEN_API_KEY`
(en las sesiones en la nube la inyecta el entorno `tirador-videos`; nunca va en el repositorio).
Requisitos: Python 3.10+, `pillow`, `requests`, y `ffmpeg` con libass.

## Límites conocidos

- **Selecciones**: banderas de flagcdn; la lista está en `equipos.py`.
- **Clubes**: escudo de TheSportsDB con clave gratuita, cuya búsqueda es pobre. Si el nombre no casa, el
  programa se detiene en vez de pintar un escudo ajeno: usa el nombre oficial (p. ej. «Real Betis») o `escudos`.
- **Foto del jugador**: recorte de TheSportsDB, que suele ir con la camiseta del club, no de la selección.
- **Derechos**: escudos de clubes y fotos de jugadores son de terceros. Revisa su uso antes de monetizar.
- **Subtítulos**: HeyGen da tiempos por frase; dentro de cada frase el tiempo se reparte por longitud de palabra.
