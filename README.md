# M1 Auditor

Primer módulo de la plataforma de SEO + GEO. Detecta lo que las auditorías de
la competencia no ven, y es a la vez la pieza técnica y el imán de captación:
da un resultado concreto y verificable en una sola pasada.

Solo librería estándar de Python 3.11+. Sin dependencias, sin instalación.

## Qué detecta

| Hallazgo | Por qué importa |
|---|---|
| **Archivos indexables finos** (autor, categoría, etiqueta) | Un archivo con un artículo y 400 palabras es una versión peor de ese artículo, y compite contra él |
| **Canibalización archivo-vs-artículo** | Si el archivo tiene más impresiones que el artículo que lista, está confirmada con cifras de Search Console |
| **Canonicals autorreferenciales** en duplicados de portada | Un archivo de autor en sitio de un solo autor es un duplicado que se declara canónico de sí mismo |
| **Sitemap no declarado** en `robots.txt` | Verificado con petición directa |
| **Distribución de intención** del contenido | Las consultas informacionales tienen 99,9% de cobertura de AI Overviews y 74,3% sin clic: medir la mezcla es medir cuánto tráfico está en riesgo |

## El criterio, que es lo que lo separa de un noindex masivo

> Un archivo con diez artículos es un hub legítimo y Google premia la estructura.
> Un archivo con un artículo y 400 palabras es una versión peor de ese artículo.

Y la preferencia que casi nadie aplica: **si existen artículos huérfanos que
convertirían el archivo fino en un hub real, la recomendación es recategorizar,
no ocultar.** Arreglar la causa en vez del síntoma. El auditor detecta esos
candidatos por solape de términos entre el archivo y los artículos del sitemap.

Hay una guarda explícita contra el error de bulto: si la regla propone noindex
en todas las categorías, el informe lo marca como aviso y pide revisión manual,
porque ocultarlas todas destruye la estructura de silos.

## Uso

```bash
python3 -m auditor https://ejemplo.com
python3 -m auditor https://ejemplo.com --impressions gsc.csv --out informe.md --json informe.json
```

| Opción | Efecto |
|---|---|
| `--impressions CSV` | Exportación de Search Console. **Sin esto la canibalización no se mide**, y el informe lo dice en vez de inventarla |
| `--thin-words N` | Umbral de palabras para archivo fino (600 por defecto) |
| `--interval SEG` | Segundos mínimos entre peticiones (1.5 por defecto) |
| `--max-archives N` | Tope de archivos a medir (60 por defecto) |

El CSV acepta cabeceras en inglés o español (`Page`/`Página`,
`Impressions`/`Impresiones`). Código de salida 1 si hay acciones pendientes,
útil en CI.

## Reglas de la casa

**Nada de memoria.** Cada afirmación lleva detrás una respuesta HTTP con su
hora de consulta, y el informe las lista en la sección de verificaciones duras.
Lo que no se ha medido se declara como no medido.

**Peticiones espaciadas.** Intervalo mínimo entre peticiones y respeto de las
reglas de `robots.txt` que aplican a este agente. Una ráfaga contra el sitio de
un cliente es una forma de rompérselo.

**El HTML servido, no el panel.** Una casilla marcada en Yoast no es una
verificación. Lo único que cuenta es la etiqueta `meta robots` que el servidor
entrega de verdad.

## Estructura

```
auditor/
  http.py       Cliente educado: espaciado, estado, hora de consulta
  robots.py     Declaración de sitemap y reglas a respetar
  sitemaps.py   Descubrimiento y clasificación de sitemaps hijos
  page.py       HTML servido: meta robots, canonical, palabras, enlaces
  intent.py     Intención y supervivencia al clic frente a AI Overviews
  rules.py      Veredictos, acciones y guarda contra el noindex de bulto
  audit.py      Orquestación y carga de Search Console
  report.py     Informe markdown y JSON
  cli.py        Línea de comandos
tests/          46 pruebas, todas sin red
```

## Pruebas

```bash
python3 -m unittest discover -s tests -t .
```

La auditoría completa se verifica de punta a punta con un cliente falso: ningún
test toca la red.

## Siguiente en el plan

M2 grafo de clusters con solape cero → M4 generador con compuertas duras →
M5 publicador WordPress → M8 compuerta editorial que aprende → M9 dossier de
cumplimiento.
