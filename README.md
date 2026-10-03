# Plataforma de SEO + GEO

Sistema propio de auditoría, planificación, producción y publicación de
contenido, con cumplimiento de políticas como condición de diseño y no como
advertencia al final.

Referente a batir: BabyLoveGrowth.ai. Se le copia la ingeniería y el modelo
comercial; se rechazan sus tres pasivos.

**Python 3.11+, cero dependencias.** Solo librería estándar. 185 pruebas,
ninguna toca la red.

## La tesis

Toda la categoría vende *"30 artículos al mes publicados en autopiloto"*. Es un
producto de 2023 vendido en 2026: las consultas informacionales tienen 99,9% de
cobertura de AI Overviews y 74,3% de búsquedas sin clic, así que el artefacto
que fabrican esas máquinas ya no recibe la visita.

Aquí la unidad de venta es otra: **posiciones donde el clic sobrevive y
citaciones donde la respuesta se da sin clic.** Menos páginas, mejores, medidas.
Y como efecto colateral, menos volumen es menos exposición a *scaled content
abuse*: la restricción de riesgo y la ventaja de producto son la misma decisión.

## Módulos

| | Módulo | Qué hace |
|---|---|---|
| **M1** | `auditor/` | Archivos indexables finos, canibalización archivo-vs-artículo, canonicals duplicados, distribución de intención |
| **M2** | `clusters/` | Grafo de clusters con solape cero, plan mensual con tope |
| **M4** | `generator/` | Briefs con dato propio obligatorio, ocho compuertas duras, bucle de reparación |
| **M5** | `publisher/` | WordPress REST, JSON-LD, enlazado pilar↔satélite. Borrador por defecto |
| **M8** | `review/` | Triaje de revisión humana y registro de rechazos que vuelve al brief |
| **M9** | `compliance/` | Dossier mensual mapeado contra la política, huella de similitud de cartera |

Pendientes: M3 planificador adaptativo con datos de Search Console, M6
autoridad sin esquema de enlaces, M7 volante de citaciones.

## Las siete prohibiciones

No son opiniones: están implementadas como compuertas que bloquean.

1. **Sin red recíproca de enlaces.** Es un esquema de enlaces por la letra de la
   política.
2. **Sin alojar contenido de terceros** en dominios propios ni de clientes. Es
   *site reputation abuse*, con aplicación distinta en el EEE desde el 30-08-2026.
3. **Sin publicar sin compuerta editorial.** El autopiloto ciego es el patrón
   penalizado. `publisher` se niega a publicar lo que no pasó.
4. **Sin traducción automática sin revisión nativa.** La política nombra
   literalmente el "sinonimizado o traducción automatizados".
5. **Sin comentarios automáticos con marca** en Reddit o Quora. Va contra su
   acuerdo de usuario y puede provocar el baneo de la marca del cliente.
6. **Tope de 24 páginas al mes por sitio**, no 120. Se vende como virtud.
7. **Sin artefactos compartidos entre sitios de clientes.** `compliance/
   fingerprint.py` mide frases y esqueletos de encabezados de toda la cartera y
   bloquea. Es la guarda contra el quinto patrón, el que mata el negocio entero
   de golpe en vez de cliente a cliente.

## Uso

```bash
# M1: auditar un sitio en vivo
python3 -m auditor https://ejemplo.com --impressions gsc.csv --out informe.md

# M2: keywords -> clusters -> plan mensual
python3 -m clusters keywords.csv --cap 24 --out plan.md --strict

# Pruebas
python3 -m unittest discover -s tests -t .
```

## Decisiones que costaron iteración

**La prioridad pondera el volumen por supervivencia al clic al cuadrado.** Con
factor lineal, una keyword informacional de 10.000 búsquedas ganaba a una
comercial de 2.000, que es la decisión equivocada en 2026.

**Los tokens presentes en más del 40% de las keywords son el nombre del nicho,
no un tema.** Sin descartarlos, "alarma séptica" caía en el cluster de "bomba de
aire séptica" por compartir la palabra "séptica".

**Los modificadores de intención se normalizan.** "cuánto cuesta X" y "precio X"
son una página, no dos clusters.

**El validador comparte la regla del constructor.** Texto parecido con la misma
intención bloquea; con intención distinta solo avisa, porque la cabecera explica
y la comercial vende. Antes las dos piezas se contradecían.

**Las notas no son avisos.** La primera página de un lote arrastra "corpus no
comprobado" porque todavía no hay nada con lo que comparar. Si eso contara como
defecto, ninguna primera página podría ser "publicable tal cual" y la métrica de
venta mediría la cobertura del sistema en vez de la calidad de la página.

**Recategorizar antes que ocultar.** Cuando un archivo fino tiene artículos
huérfanos reasignables, M1 los detecta por solape de términos y recomienda
moverlos. Y si los candidatos no alcanzan el umbral de hub, lo dice: *"reasignarlos
deja el archivo a 2 artículos de ser un hub real"*, en vez de prometer un hub que
no se consigue.

## Reglas de la casa

**Nada de memoria.** Cada afirmación sobre un sitio lleva detrás una respuesta
HTTP con su hora de consulta. Lo que no se ha medido se declara como no medido:
el dossier tiene una fila `NO MEDIDO` precisamente para no escribir `cumple`.

**Peticiones espaciadas.** Intervalo mínimo y respeto de `robots.txt`. Una
ráfaga contra el sitio de un cliente es una forma de rompérselo.

**El HTML servido, no el panel.** Una casilla marcada en Yoast no es una
verificación.

**No se gasta en generar con un brief incompleto.** Sin dato propio con método,
sin fuente verificable y sin la respuesta a "qué aporta esto que no esté ya en
el top 10", el pipeline aborta antes de la primera llamada al modelo.

## Economía

Precios de API verificados. Por página, con pipeline de cuatro pasos, caché de
prompt y API de lotes al 50%: **$0.30-0.60 con `claude-opus-5-5`**. Doce páginas
al mes son $4-8 en modelo.

El coste dominante es el revisor humano: 25-35 minutos por artículo es el número
medido del competidor. Gastar diez veces más en generación cuesta $30-50 al mes y
ahorra $120-300 en edición. **El gasto en calidad se paga doce veces.** Su
calidad de 2,1/5 es una decisión, no un límite de coste.

## Lo que todavía no se puede afirmar

El sistema **no se ha ejecutado nunca contra un sitio real ni contra la API**.
Está verificado de punta a punta con dobles de prueba, sin red y sin clave.

En particular: el 100% de publicables tal cual del test de integración es sobre
un fixture escrito para pasar las compuertas. **No es evidencia de calidad del
producto**, y usarlo para vender sería exactamente lo que se le critica a la
competencia. La cifra que vale hay que medirla a ciegas, con rúbrica escrita
antes de generar, sobre contenido real.
