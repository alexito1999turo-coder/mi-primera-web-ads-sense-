# Notas para Claude

## Vídeo diario de El Tirador (`tirador/`)

Cuando el usuario mande los 4 partidos del día (y, si lo trae, el guion de Julen):

1. Los 4 partidos los da siempre el usuario; no proponerlos. Escribe `tirador/dias/AAAA-MM-DD.json`
   siguiendo `tirador/dias/ejemplo.json`. Guion por bloques
   (`intro` / `partidos` x4 / `cierre`). Si el usuario no da guion, redáctalo y enséñaselo antes de gastar créditos.
2. Elige tú `estrella`: el jugador más famoso entre los ocho equipos que esté convocado/disponible
   (verifícalo con una búsqueda; no te fíes de la memoria). Explica en una línea por qué ese.
3. `python -m tirador <json> --solo-plantilla` y revisa `base.png` (escudos correctos, nombres sin cortar).
4. `python -m tirador <json>` genera con HeyGen: **gasta créditos del usuario; pide confirmación antes**.
   Si se corta, reanuda con `--video-id` (está en `salida/<fecha>/info.json`) para no pagar dos veces.
5. Entrega `tirador/salida/<fecha>/final.mp4` con SendUserFile. `salida/` y `cache/` no se suben a git.

Detalles y límites en `tirador/README.md`. Tests: `python -m pytest tests/test_tirador_subs.py`.

### Sistema visual oficial (contexto permanente, no preguntar por el estilo)

«Hazme la plantilla / el vídeo de los partidos de mañana» significa siempre la plantilla oficial:
negro profundo y verde neón/lima, estadio nocturno con focos, humo y haces de luz; arriba negro limpio
para Julen; en el centro el jugador más destacado (retrato principal + secundario en verde oscuro);
abajo cuatro casillas idénticas `ESCUDO — NOMBRE — VS — NOMBRE — ESCUDO` con pestaña «PARTIDOS DE HOY».
Solo cambian: jugador, su segunda foto, los cuatro partidos y los ocho escudos/nombres. El diseño vive en
`tirador/plantilla.py` y no se retoca día a día.

- Escudos: siempre archivos auténticos (federación o club). Nunca generarlos ni recrearlos.
- Jugador: comprobar convocatoria antes de elegirlo. La foto automática es tipo ficha y con camiseta de
  club; el nivel «cinemático» de la referencia solo se alcanza si el usuario aporta `foto_estrella` y
  `foto_secundaria` (PNG recortados). Decírselo si no las trae; no fingir que el resultado es equivalente.
- Arte del jugador: la vía buena es `"arte": "ruta.png"` (imagen 16:9 generada con IA a partir de
  `tirador/referencia/maestra.png`, sin textos ni escudos). La IA solo pinta el arte; casillas, nombres y
  escudos son siempre de `plantilla.py`. `arte_gemini` (API) está escrito pero sin probar: falta la clave.
- Subtítulos: ESTILO_SUBTITULOS_OFICIAL. Flashes: cuatro, uno por partido, con clic de cámara.
- No afirmar que algo es «idéntico» o «verificado» sin haber comparado la imagen con la referencia.

### Formato que funciona en el nicho (medido en @winapicks y @pedrosure, nov 2026)
- Un vídeo al día, título fijo «Predicciones DD mes fútbol» + 4-5 hashtags (#tiktokfutbol + competición + clubes).
- 60-75 s. Estructura del guion: 1) gancho de acierto («mirad lo que dije ayer… lo acerté todo»),
  2) un pick por partido, una o dos frases de motivo cada uno, 3) el partido gordo se deja sin pick y se
  manda al grupo de la bio («el dato clave ya está en el grupo»). Eso convierte vistas en comunidad.
- Los días de Champions y de selección grande rinden el doble (220-270 mil vistas frente a ~90 mil).
- No afirmar aciertos que no hayan ocurrido: el gancho solo con resultados reales del día anterior.
