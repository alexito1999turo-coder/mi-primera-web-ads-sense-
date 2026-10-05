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
| **M8b** | `calibration/` | Mide las propias compuertas contra el criterio del revisor |
| **M9** | `compliance/` | Dossier mensual mapeado contra la política, huella de similitud de cartera |
| **M3** | `insight/` | Oportunidad descontada por AI Overviews y reasignación de clusters |
| **M7a** | `citability/` | Qué frases puede citar un buscador, y qué le falta a las demás |
| **M6a** | `dataset/` | Datos propios con procedencia: el activo enlazable que sustituye a la red de enlaces |
| **M13** | `estudio/` | El mismo motor aplicado a vídeo: once agentes con compuerta, semana canónica, tribunal de tres rúbricas y la carrera contra el listón de YouTube |

## Las tres cosas que la competencia no hace

**Datos propios con procedencia** (`dataset/`). Existe porque había un agujero
en mi propio diseño: el generador **bloquea** cualquier página sin dato propio
con método, y nada en el sistema producía uno. Un requisito obligatorio sin forma
de cumplirlo no es rigor, es un callejón sin salida.

Lo resuelve una idea simple: **la agregación crea originalidad.** Cuarenta
presupuestos pueden ser públicos uno a uno; su mediana por condado no existe en
ningún otro sitio. De ahí salen tres cosas a la vez: el dato que exige la
compuerta, el activo enlazable que sustituye a la red recíproca, y la cifra
precisa que el motor de citabilidad premia.

Y el módulo **escribe la frase**, construida para cumplir las cuatro condiciones
de citabilidad. Hay una prueba que lo verifica cruzando los dos módulos: lo que
produce el de datos tiene que ser citable según el de citabilidad, sin retocarlo
a mano. Sale 87 sobre 100.

**Ingeniería de citabilidad** (`citability/`). Ellos *rastrean* citaciones en
ChatGPT, Perplexity, Gemini y Claude. Eso es un termómetro: dice lo que ya pasó.
Este módulo invierte el problema — un modelo no cita páginas, cita **frases** que
puede levantar enteras, atribuir a alguien y que no encuentra en otras cincuenta
fuentes. De ahí salen cuatro factores medibles sobre el texto, y la salida útil
no es una nota: es la lista de frases que un modelo levantaría, y el arreglo
concreto que le falta a cada una de las demás.

La señal más discriminante es la más simple: **un número redondo es consenso, un
número preciso es una medición.** "Unos 14.000 $" ya lo sabe el modelo y no
necesita citarte; "14.237 $" solo puede venir de quien lo contó.

**Calibración de las propias compuertas** (`calibration/`). Las compuertas son
heurísticas escritas por alguien. Una que marca páginas que el revisor luego
aprueba consume minutos para nada y entrena al revisor a ignorarla; lo que el
revisor rechaza sin que ninguna compuerta avisara es una compuerta que falta.
Este módulo convierte el veredicto humano en verdad de referencia y recomienda
subir, bajar, crear o retirar cada una — con el límite inferior de Wilson, porque
3 aciertos de 3 es 0,44 y no 1,00, y por debajo del tamaño mínimo dice "muestra
insuficiente" en vez de inventar un número.

Y dice en voz alta el problema metodológico que nadie menciona: **una compuerta
bloqueante impide que la página llegue al revisor, así que su precisión es
inmedible** sin revisar a propósito una muestra de lo que bloquea.

**Oportunidad por valor, no por clics** (`insight/`). El SEO clásico dice que la
zona de oportunidad es la posición 11-30. Pero subir de la 12 a la 5 en una
consulta informacional vale mucho menos que el mismo salto en una comercial,
porque la AI Overview se queda el clic.

Comprobado con números, y por eso está en una prueba: **el descuento por AI
Overviews solo casi nunca da la vuelta al orden** — una informacional de 10.000
impresiones sigue ganando a una comercial de 2.200 aunque le quites la mitad del
clic. Lo que sí lo invierte es el descuento *más* el valor del clic: por clics
gana la informacional de 10.000; por valor, la transaccional de 900.

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

## La aplicación

```bash
python3 -m webapp
# → http://127.0.0.1:8000
```

Siete pestañas en el navegador, sin instalar nada y sin enviar datos a
ningún sitio: **auditoría** de un dominio en vivo con barra de progreso,
**citabilidad** de un texto, **oportunidad** desde una exportación de Search
Console, **plan de clusters** desde un CSV de keywords, **memoria** por sitio,
**negocio** con el coste por página y el **estudio** del canal, donde los once
agentes se ven trabajando turno a turno: azul el que produce, verde el que ya
entregó y rojo el que está parado por una compuerta, con el motivo escrito y el
nombre de quien la posee.

Hasta aquí esto eran diez paquetes y una batería de pruebas: un motor, no un
producto. Su producto se usa sin tocar código; el mío no se podía usar. Esta es
la carcasa que faltaba.

Se ata a `127.0.0.1` a propósito, y rechaza auditar direcciones internas
(`192.168.*`, `10.*`, `localhost`, el endpoint de metadatos) salvo que pases
`--allow-private`. Sin ese guardia, la herramienta sería un escáner de la red
de quien la levanta.

## El estudio: las compuertas aplicadas a vídeo

El encargo era un canal de YouTube con publicación **diaria** y monetización.
Las dos mitades se contradicen, y el módulo existe porque la contradicción se
puede medir en vez de discutirla.

**El dato que ordena todo.** El 01-02-2027 el listón de entrada al Programa de
Socios pasa de 4.000 a 8.000 horas de visualización en 365 días, y de 10 a 20
millones de vistas de Shorts en 90 días; quien ya está dentro no se ve afectado.
Y 4.000 horas son 240.000 minutos: un documental de 22 minutos al 45% de
retención deja 9,9 minutos por vista, así que la ruta de horas se cierra con
**24.243 vistas** y la de Shorts con **diez millones**. Cuatrocientas doce veces
más vistas por la misma puerta, y pagadas a un RPM entre treinta y cien veces
menor. De ahí sale la arquitectura entera: el Short es el tráiler, el documental
es el producto, y la métrica del canal son los minutos vistos por publicación.

**Tres estrategias, tres jueces, un veto.** `jueces.py` no escribe la conclusión:
la calcula. Tres rúbricas con pesos declarados puntúan de 0 a 5, el juez de
riesgo tiene veto por debajo de 2,5 —y lo usa, contra la estrategia de volumen
automatizado— y las enmiendas se activan solas cuando la ganadora saca menos de
3 en un criterio. Dos de los tres jueces preferían la estrategia prudente y gana
la compuesta por agregado: **el fallo dice la discrepancia en vez de esconderla.**

**La semana canónica.** Una investigación, siete publicaciones: dos largos y
cinco Shorts de cinco ángulos distintos. Son **19,1 horas semanales**, sumadas
turno a turno y no estimadas a ojo, y el cuello de botella es el guionista con
300 minutos — que es lo que decide qué herramienta merece la pena pagar, y no al
contrario.

**La compuerta que hace que esto no sea una granja.** Siete publicaciones diarias
de la misma investigación es exactamente el patrón que la política de contenido
no auténtico de YouTube persigue desde el 15-07-2025. Por eso la variación es
una compuerta que bloquea —similitud de guiones medida con los mismos *shingles*
que `compliance/fingerprint.py`, y ningún par de ángulos iguales seguidos— y hay
una prueba que comprueba que **la semana que se vende pasa la compuerta que se
vende con ella**, sin retocar nada a mano.

De las once compuertas, ocho dan su veredicto sobre datos que escribe una
persona y tres son irreductiblemente humanas: saturación del caso, difamación y
licencias de archivo. El parte las cuenta por separado en vez de presentarlas
todas como automáticas.

```bash
python3 -m estudio                      # fallo, semana, carrera y pila
python3 -m estudio --animar 5           # la sala moviéndose en el terminal
python3 -m estudio --calendario 4
python3 -m scripts.sala_artefacto       # artefactos/sala.html, sin servidor
```

La sala vive en tres sitios y en ninguno se escriben las cifras a mano: la
pestaña 7 del banco, el terminal, y `artefactos/sala.html` — una página suelta
que se abre sin servidor y lleva el JSON del motor dentro. Una prueba cruza las
dos cosas, igual que la que vigila el puerto JavaScript del módulo de economía.

## Uso por línea de comandos

```bash
# M1: auditar un sitio en vivo
python3 -m auditor https://ejemplo.com --impressions gsc.csv --out informe.md

# M2: keywords -> clusters -> plan mensual
python3 -m clusters keywords.csv --cap 24 --out plan.md --strict

# M7a: qué frases puede citar un buscador de este texto
python3 -m citability articulo.md --min-score 60

# M3: oportunidad real y reasignación de clusters
python3 -m insight gsc-actual.csv --before gsc-anterior.csv --keywords kw.csv --pages 12

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

**La extraibilidad multiplica, no suma.** Lo tenía mal: con la extraibilidad
como un sumando más, una frase imposible de levantar pero perfectamente atribuida
y exclusiva salía citable. Una condición necesaria no se promedia con las
deseables. Lo destapó una prueba que escribí esperando que pasara.

**Los tokens del nicho no agrupan.** Y en citabilidad, `entre` solo aproxima
cuando va delante de una cifra: "entre 300 y 900 $" es una horquilla, pero
"recogidos entre enero y junio" es un rango exacto. Sin esa distinción se
penalizaba la frase mejor atribuida del texto.

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

El sistema **no se ha ejecutado contra un sitio en producción ni contra la API
del modelo**. Lo que sí está hecho:

- El auditor y el publicador pasan por **HTTP real** contra el WordPress del
  banco de pruebas: gzip, charset, redirecciones, marcado de tema, 401 real, y
  actualizar en vez de duplicar.
- El cliente del modelo está **verificado contra el SDK 1.11.0 instalado**: los
  seis parámetros que usa, el método del stream y los campos de respuesta
  (`stop_reason`, `stop_details`) existen todos, y la forma de la petición de
  lote valida contra los tipos del SDK.

Lo que falta es una clave de API, un WordPress en producción y ocho semanas de
Search Console.

En particular: el 100% de publicables tal cual del test de integración es sobre
un fixture escrito para pasar las compuertas. **No es evidencia de calidad del
producto**, y usarlo para vender sería exactamente lo que se le critica a la
competencia. La cifra que vale hay que medirla a ciegas, con rúbrica escrita
antes de generar, sobre contenido real.

Y tres cosas son **priores declarados, no mediciones**, cada una en su propio
módulo para que se vean y se puedan sustituir:

- Los pesos de citabilidad (`citability/score.py`). Salen de cómo funciona la
  generación con recuperación, no de un experimento. Se calibran cuando haya
  citaciones reales medidas.
- La curva de CTR por posición y la exposición a AI Overviews
  (`insight/curves.py`). Son de mercado. Con ocho semanas de datos propios se
  calculan con ellos.
- El valor relativo del clic por intención (`insight/curves.py`). Es un prior de
  nicho de servicios; se sustituye por los datos de conversión del cliente.

Que estén aislados no es casualidad: el día que haya datos, se cambian ahí y
todo lo demás sigue funcionando igual.
