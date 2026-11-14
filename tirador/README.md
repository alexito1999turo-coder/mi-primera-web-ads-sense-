# El Tirador — generador diario de vídeos

Un comando produce el vídeo vertical (1080x1920) del día con diseño fijo:

1. **Capa 1** — Julen (avatar de HeyGen) arriba, sobre negro limpio, sin marcos.
2. **Capa 2** — jugador estrella de uno de los ocho equipos, integrado en el fondo de estadio.
3. **Capa 3** — cuatro casillas negras con borde verde neón, VS central, bandera/escudo y nombres en blanco.
4. **Capa 4** — subtítulos, resalte del partido del que se habla, flashes y clic de cámara.

### ESTILO_SUBTITULOS_OFICIAL (`subs.py`)
Montserrat ExtraBold, MAYÚSCULAS, contorno negro grueso, halo neón, entrada con zoom y movimiento,
fragmentos de 1 a 3 palabras, palabra a palabra. La palabra que suena va en color vivo (turquesa, verde
neón, rosa, amarillo, rotando por fragmento) y el resto en blanco. Posición: entre el vídeo de Julen y las
casillas, sin tapar escudos ni partidos.

### Flashes (`montaje.py`)
Exactamente cuatro, uno por partido, en el instante en que Julen empieza a hablar de él: destello breve +
clic de cámara + cambio de resalte, los tres en el mismo instante. No hay tiempos fijos: el inicio se
localiza en el guion y se ajusta al arranque real de la voz medido en el audio. Nunca se adelantan al
audio ni aparecen en frases intermedias; si el guion no permite localizar los 4 partidos en orden, el
programa se detiene antes de gastar créditos.

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
| `foto_estrella` | no | PNG propio (recortado, con transparencia) para el retrato principal |
| `foto_secundaria` | no | Segundo PNG del mismo jugador, otro ángulo; se pinta detrás en verde oscuro. Si falta, se usa la principal en espejo |
| `escudos` | no | `{"Nombre": "ruta.png"}` para forzar un escudo |

Otras opciones: `--video-id ID` reutiliza un vídeo de HeyGen ya pagado; `--avatar-video F.mp4 [--srt F.srt]`
monta sobre un vídeo local; `python -m tirador avatares` lista tus avatares.

## Configuración

`config.json` fija el avatar y la voz de Julen. La clave de HeyGen se lee de `HEYGEN_API_KEY`
(en las sesiones en la nube la inyecta el entorno `tirador-videos`; nunca va en el repositorio).
Requisitos: Python 3.10+, `pillow`, `requests`, y `ffmpeg` con libass.

## Límites conocidos

- **Selecciones**: escudo de la federación (TheSportsDB); si no existe, bandera de flagcdn. La lista está en `equipos.py`.
- **Clubes**: escudo de TheSportsDB con clave gratuita, cuya búsqueda es pobre. Si el nombre no casa, el
  programa se detiene en vez de pintar un escudo ajeno: usa el nombre oficial (p. ej. «Real Betis») o `escudos`.
- **Foto del jugador**: recorte de TheSportsDB, que suele ir con la camiseta del club, no de la selección.
- **Derechos**: escudos de clubes y fotos de jugadores son de terceros. Revisa su uso antes de monetizar.
- **Subtítulos**: HeyGen da tiempos por frase; dentro de cada frase el tiempo se reparte por longitud de palabra.
