# Notas para Claude

## Vídeo diario de El Tirador (`tirador/`)

Cuando el usuario mande los 4 partidos del día (y, si lo trae, el guion de Julen):

1. Escribe `tirador/dias/AAAA-MM-DD.json` siguiendo `tirador/dias/ejemplo.json`. Guion por bloques
   (`intro` / `partidos` x4 / `cierre`). Si el usuario no da guion, redáctalo y enséñaselo antes de gastar créditos.
2. Elige tú `estrella`: el jugador más famoso entre los ocho equipos que esté convocado/disponible
   (verifícalo con una búsqueda; no te fíes de la memoria). Explica en una línea por qué ese.
3. `python -m tirador <json> --solo-plantilla` y revisa `base.png` (escudos correctos, nombres sin cortar).
4. `python -m tirador <json>` genera con HeyGen: **gasta créditos del usuario; pide confirmación antes**.
   Si se corta, reanuda con `--video-id` (está en `salida/<fecha>/info.json`) para no pagar dos veces.
5. Entrega `tirador/salida/<fecha>/final.mp4` con SendUserFile. `salida/` y `cache/` no se suben a git.

Detalles y límites en `tirador/README.md`. Tests: `python -m pytest tests/test_tirador_subs.py`.
