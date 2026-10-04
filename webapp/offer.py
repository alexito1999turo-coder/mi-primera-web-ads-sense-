"""La pagina que dice que se vende, y cuanto cuesta.

La aplicacion ya era la demostracion: cuatro herramientas que miden un sitio en
vivo, con el codigo HTTP detras de cada afirmacion. Lo que no habia en ninguna
parte es la frase que contesta "y esto que es, y cuanto vale". Una demo sin
oferta deja al visitante admirando la maquina y marchandose sin preguntar el
precio, y eso no es humildad: es dejar el trabajo a medias.

Va dentro de webapp y no en un folleto aparte por una razon de producto: la
pagina que vende y la herramienta que demuestra las sirve el mismo proceso, asi
que la oferta queda a un clic de la prueba y la prueba a un clic de la oferta.
Es la ventaja de tener el banco de pruebas: no hay que creerse esta pagina.

Reutiliza views.STYLE y solo anade las reglas que esta pagina necesita. Una
segunda copia del CSS serian dos sitios donde cambiar un color, y el color
acabaria distinto. Sin JavaScript: aqui no hay nada que medir, es texto.

Y la seccion de prueba dice en voz alta que todavia no hay cliente en
produccion, con tabla de medido y no medido. Es la misma regla que se le aplica
a los informes de los clientes, aplicada primero a lo propio: lo que no se ha
medido se declara como no medido, y menos que a nadie se le miente al que
todavia no ha firmado.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from clusters.validate import MONTHLY_CAP

from .views import STYLE

# El tope que se vende como virtud es el mismo que el planificador impone de
# verdad. Se lee de clusters.validate para que la pagina no pueda prometer un
# numero que el motor ya no cumple: si alli cambia, aqui cambia.
CAP_PAGES = MONTHLY_CAP
COMPETITOR_PAGES = 30

STATE_MEASURED = "medido"
STATE_UNMEASURED = "no medido"

# Las seis preguntas que una portada tiene que dejar contestadas. El orden es
# el del encargo y tambien el de lectura: primero que es, al final cuanto vale.
QUESTIONS = (
    ("que-se-vende", "Qué se vende"),
    ("que-hacemos", "Qué se hace, y en qué sector"),
    ("a-quien", "A qué cliente se le habla"),
    ("prueba", "Qué prueba hay, y qué prueba no hay"),
    ("producto", "Qué producto es"),
    ("planes", "Cuál es el plan que te toca"),
)


@dataclass
class Plan:
    """Un plan de la oferta. El precio es dato, no texto incrustado en el HTML."""

    name: str
    price_eur: int
    pitch: str
    includes: list[str] = field(default_factory=list)
    pages_per_month: int = 0
    for_whom: str = ""
    featured: bool = False

    @property
    def price(self) -> str:
        """Separador de miles espanol: 1.490, no 1490. La cifra se lee de un golpe."""
        return f"{self.price_eur:,}".replace(",", ".") + " €"


@dataclass
class Claim:
    """Una afirmacion con su estado. Sin estado no entra en la pagina."""

    statement: str
    state: str
    evidence: str

    @property
    def measured(self) -> bool:
        return self.state == STATE_MEASURED


PLANS = (
    Plan(
        name="Esencial",
        price_eur=490,
        pages_per_month=4,
        pitch="Para dejar de discutir si esto mueve algo y verlo con cifras.",
        includes=[
            "4 páginas al mes",
            "Plan de clusters con solape cero",
            "Informe mensual",
        ],
        for_whom="Si tienes que demostrar el resultado antes de que te aprueben "
                 "un presupuesto mayor, empieza aquí.",
    ),
    Plan(
        name="Crecimiento",
        price_eur=890,
        pages_per_month=8,
        pitch="El volumen al que el dato propio compensa: ocho páginas medidas "
              "valen más que treinta publicadas a ciegas.",
        includes=[
            "8 páginas al mes",
            "Medición de citabilidad frase a frase",
            "Dato propio con procedencia",
            "Informe mensual",
        ],
        for_whom="Si ya tienes tráfico informacional que no convierte, este es "
                 "el que te toca. Es el plan que se vende.",
        featured=True,
    ),
    Plan(
        name="Completo",
        price_eur=1490,
        pages_per_month=16,
        pitch="Cuando además de resultado hay que responder por el riesgo "
              "delante de alguien.",
        includes=[
            "Hasta 16 páginas al mes",
            "Todo lo anterior",
            "Dossier de cumplimiento",
            "Reasignación mensual de clusters",
        ],
        for_whom="Si hay un comité, un legal o una matriz que pregunta en qué "
                 "se basa lo que publicas, el dossier es para esa conversación.",
    ),
)

PROOF = (
    Claim(
        "El auditor mide un WordPress de verdad por HTTP",
        STATE_MEASURED,
        "gzip, charset declarado, redirección de barra final, 401 real y API REST "
        "con sus códigos, contra el WordPress del banco de pruebas",
    ),
    Claim(
        "El publicador actualiza la página en vez de duplicarla",
        STATE_MEASURED,
        "busca por slug antes de crear; verificado con el transporte inyectado",
    ),
    Claim(
        "Nada se publica sin pasar la compuerta editorial",
        STATE_MEASURED,
        "con una compuerta bloqueante sin resolver, el publicador se niega y no "
        "hace ni una petición",
    ),
    Claim(
        "El dato propio que produce el sistema es citable sin retocarlo a mano",
        STATE_MEASURED,
        "87 sobre 100 en el motor de citabilidad, cruzando los dos módulos",
    ),
    Claim(
        "Ninguna prueba de la batería toca la red",
        STATE_MEASURED,
        "dobles de transporte; el único socket es un WordPress simulado dentro "
        "del propio proceso de pruebas",
    ),
    Claim(
        "Posiciones y citaciones conseguidas en el sitio de un cliente",
        STATE_UNMEASURED,
        "no hay todavía ningún sitio en producción. Cuando lo haya, la cifra irá "
        "aquí con su fecha de medición, y no antes",
    ),
    Claim(
        "Coste real por página en llamadas al modelo",
        STATE_UNMEASURED,
        "0,30-0,60 $ con precios de API verificados, pero el pipeline no se ha "
        "ejecutado todavía contra la API: es una estimación con fuente, no una "
        "medición",
    ),
)


# -- estilo: extiende el de la herramienta, no lo repite --------------------

OFFER_STYLE = """
.hero{padding:30px 0 22px;border-bottom:1px solid var(--edge);margin-bottom:22px}
.hero h1{font-size:30px;line-height:1.18;max-width:30ch;letter-spacing:-.015em}
.hero p.lede{font-size:17px;color:var(--soft);max-width:64ch;margin:14px 0 0}
nav.indice{display:flex;gap:4px;flex-wrap:wrap;margin-bottom:24px}
nav.indice a{font-size:13px;padding:8px 14px;border:1px solid var(--edge);
  background:var(--panel);color:var(--soft);border-radius:6px;text-decoration:none}
nav.indice a:hover{border-color:var(--signal);color:var(--signal)}
section{margin-bottom:28px;scroll-margin-top:14px}
section>h2{font-size:21px;margin-bottom:10px}
.q{display:block;font-family:var(--mono);font-size:11px;letter-spacing:.1em;
  text-transform:uppercase;color:var(--faint);margin-bottom:4px}
.two{display:grid;gap:12px;grid-template-columns:repeat(auto-fit,minmax(270px,1fr))}
.contra,.pro{border-radius:8px;padding:14px 16px;font-size:14px}
.contra{background:var(--bad-bg);border:1px solid var(--bad)}
.pro{background:var(--good-bg);border:1px solid var(--good)}
.contra h3{color:var(--bad)}
.pro h3{color:var(--good)}
.contra p:last-child,.pro p:last-child{margin-bottom:0}
ul.hace{margin:0;padding-left:0;list-style:none;display:grid;gap:9px;font-size:14px}
ul.hace b{font-family:var(--mono);font-size:11px;letter-spacing:.06em;
  color:var(--measured);background:var(--measured-bg);border-radius:4px;
  padding:2px 6px;margin-right:7px;white-space:nowrap}
.planes{display:grid;gap:14px;align-items:start;margin-top:14px;
  grid-template-columns:repeat(auto-fit,minmax(252px,1fr))}
.plan{display:flex;flex-direction:column;gap:11px;background:var(--panel);
  border:1px solid var(--edge);border-radius:8px;padding:18px}
.plan.destacado{border:2px solid var(--signal);padding:17px}
.plan .cinta{align-self:flex-start;font-family:var(--mono);font-size:11px;
  letter-spacing:.08em;text-transform:uppercase;color:var(--signal);
  background:var(--signal-bg);border-radius:10px;padding:3px 9px}
.plan h3{margin:0;font-size:17px}
.plan .precio{font-family:var(--mono);font-size:27px;font-weight:600;
  font-variant-numeric:tabular-nums;line-height:1.1}
.plan .precio small{display:block;margin-top:3px;font-family:var(--sans);
  font-size:12px;font-weight:400;color:var(--faint)}
.plan ul{margin:0;padding-left:18px;font-size:13px;display:grid;gap:5px}
.plan .para{margin:auto 0 0;padding-top:11px;font-size:13px;color:var(--soft);
  border-top:1px solid var(--edge)}
a.go{display:inline-block;font-weight:600;font-size:14px;padding:10px 18px;
  border-radius:6px;border:1px solid var(--signal);background:var(--signal);
  color:#fff;text-decoration:none}
footer.pie{border-top:1px solid var(--edge);padding-top:16px;margin-top:8px}
"""


# -- piezas -----------------------------------------------------------------

def _tile(value: str, text: str) -> str:
    """El mismo azulejo con el que la herramienta pinta sus cifras."""
    return f'<div class="tile"><b>{value}</b><span>{text}</span></div>'


def _plan_card(plan: Plan) -> str:
    """Una tarjeta por plan. El destacado se marca, no se deja a la suerte del orden."""
    clase = "plan destacado" if plan.featured else "plan"
    cinta = '<span class="cinta">El que se vende</span>' if plan.featured else ""
    puntos = "".join(f"<li>{item}</li>" for item in plan.includes)
    return (
        f'<div class="{clase}">{cinta}'
        f"<h3>{plan.name}</h3>"
        f'<div class="precio">{plan.price}<small>al mes</small></div>'
        f"<p>{plan.pitch}</p>"
        f"<ul>{puntos}</ul>"
        f'<p class="para">{plan.for_whom}</p>'
        "</div>"
    )


def _claim_row(claim: Claim) -> str:
    """Una fila por afirmacion, con su estado y como se comprueba."""
    pastilla = "g" if claim.measured else "b"
    return (
        f"<tr><td>{claim.statement}</td>"
        f'<td><span class="pill {pastilla}">{claim.state}</span></td>'
        f"<td>{claim.evidence}</td></tr>"
    )


def _index() -> str:
    enlaces = "".join(
        f'<a href="#{clave}">{pregunta}</a>' for clave, pregunta in QUESTIONS
    )
    return f'<nav class="indice">{enlaces}</nav>'


def _max_pages() -> int:
    """El plan mas grande. Se lee de los planes para que no se quede desfasado."""
    return max(plan.pages_per_month for plan in PLANS)


def _body() -> str:
    pregunta = dict(QUESTIONS)
    return f"""
<div class="wrap">
<header class="hero">
  <h1>Menos páginas, mejores y medidas.</h1>
  <p class="lede">Posiciones donde el clic sobrevive y citaciones donde la
  respuesta se da sin clic. Tope de {CAP_PAGES} páginas al mes por sitio, y eso
  es la ventaja del producto, no su letra pequeña.</p>
</header>

{_index()}

<section id="que-se-vende">
  <span class="q">Pregunta 1</span>
  <h2>{pregunta["que-se-vende"]}</h2>
  <div class="panel">
    <p>Se venden páginas que siguen recibiendo la visita, y frases que un
    buscador puede citar cuando ya no hay visita que recibir. La unidad de venta
    no es el artículo publicado: es la <b>posición donde el clic sobrevive</b> y
    la <b>citación donde la respuesta se da sin clic</b>. Son dos cosas
    distintas y las dos se miden.</p>
    <div class="tiles">
      {_tile("99,9%", "de las consultas informacionales ya llevan una respuesta generada encima")}
      {_tile("74,3%", "de las búsquedas terminan sin que nadie haga clic")}
      {_tile(str(COMPETITOR_PAGES), "artículos al mes que vende la categoría, en autopiloto")}
      {_tile(str(CAP_PAGES), "páginas al mes como tope aquí, por decisión y no por capacidad")}
    </div>
    <div class="two">
      <div class="contra">
        <h3>Lo que vende la competencia</h3>
        <p>{COMPETITOR_PAGES} artículos al mes publicados en autopiloto. Es un
        producto de 2023 vendido en 2026: el artefacto que fabrica esa máquina se
        publica, se indexa y no recibe la visita, porque la respuesta ya está
        escrita arriba del resultado.</p>
      </div>
      <div class="pro">
        <h3>Lo que se vende aquí</h3>
        <p>Hasta {CAP_PAGES} páginas al mes, con dato propio con método, revisión
        humana y medición de citabilidad frase a frase. Menos volumen es además
        menos exposición a <i>scaled content abuse</i>: la restricción de riesgo
        y la ventaja de producto son la misma decisión.</p>
      </div>
    </div>
    <p class="note" style="margin-top:14px">El tope es la parte que cuesta
    explicar y la que hay que explicar primero. Nadie compra volumen aquí porque
    el volumen es exactamente lo que dejó de funcionar.</p>
  </div>
</section>

<section id="que-hacemos">
  <span class="q">Pregunta 2</span>
  <h2>{pregunta["que-hacemos"]}</h2>
  <div class="panel">
    <ul class="hace">
      <li><b>Auditar</b> El sitio en vivo: listados indexables finos, canonicals
      duplicados, canibalización entre un archivo y su propio artículo y el
      reparto de intención de todo el contenido. Cada fila lleva detrás su
      código HTTP y la hora exacta de consulta.</li>
      <li><b>Planificar</b> Clusters con solape cero: ninguna keyword primaria se
      usa dos veces, así que dos páginas tuyas no compiten entre ellas. Y reparto
      mensual respetando el tope.</li>
      <li><b>Producir</b> Ocho compuertas duras antes de publicar. Sin dato
      propio con método y sin fuente verificable, el proceso aborta antes de la
      primera llamada al modelo: no se gasta en generar con un brief incompleto.</li>
      <li><b>Medir</b> Qué frases de la página puede levantar un buscador,
      atribuir y no encontrar en otras cincuenta fuentes. La señal más
      discriminante es la más simple: un número redondo es consenso, un número
      preciso es una medición.</li>
      <li><b>Publicar</b> En tu WordPress, en borrador por defecto. Publicar es
      un acto explícito de alguien, nunca el valor por defecto de una casilla.</li>
      <li><b>Responder</b> Informe mensual con lo medido y, en su propia
      sección, lo que no se ha medido.</li>
    </ul>
    <p style="margin-top:14px">El sector donde está construido el corpus de
    datos propios es concreto: <b>instalación y servicios residenciales en
    Estados Unidos</b> — tratamiento de agua y sistemas sépticos — y <b>marcas
    de e-commerce</b> con catálogo y blog. En esos dos el dato propio ya existe:
    medianas por condado sobre presupuestos reales pedidos uno a uno.</p>
    <p class="note">Fuera de esos dos el sistema funciona igual, pero el dato
    propio hay que construirlo desde cero, y eso se dice antes de firmar y no
    después.</p>
  </div>
</section>

<section id="a-quien">
  <span class="q">Pregunta 3</span>
  <h2>{pregunta["a-quien"]}</h2>
  <div class="panel">
    <p>A quien firma la factura: el responsable de marketing o de e-commerce de
    un sitio que ya tiene tráfico y un blog que no lo convierte en nada. No hace
    falta que sepas lo que es un archivo indexable; para eso está el informe.</p>
    <div class="two">
      <div class="quote">
        <span class="tag">Sí, si te reconoces aquí</span>
        Tienes tráfico informacional que no deja dinero, un catálogo o un
        servicio que sí vende, y alguien arriba que pregunta por el retorno de
        lo que se publica.
      </div>
      <div class="quote no">
        <span class="tag">No, si lo que buscas es esto</span>
        {COMPETITOR_PAGES} artículos al mes, publicación automática sin revisión,
        intercambio de enlaces o contenido alojado en dominios de terceros. Nada
        de eso se hace aquí, y no por precio: está implementado como compuerta
        que bloquea.
      </div>
    </div>
  </div>
</section>

<section id="prueba">
  <span class="q">Pregunta 4</span>
  <h2>{pregunta["prueba"]}</h2>
  <div class="panel">
    <p>La prueba social que suele ir en este sitio de la página — logos de
    clientes y casos con porcentajes — <b>no la hay</b>: el sistema todavía no se
    ha ejecutado contra un sitio en producción. Se dice aquí arriba y sin
    maquillar, porque es la misma regla que se le aplica a los informes de los
    clientes: lo que no se ha medido se declara como no medido.</p>
    <div class="scroll">
      <table>
        <thead><tr><th>Afirmación</th><th>Estado</th><th>Cómo se comprueba</th></tr></thead>
        <tbody>{"".join(_claim_row(claim) for claim in PROOF)}</tbody>
      </table>
    </div>
    <p class="note" style="margin-top:14px">Un proveedor que no distingue entre
    lo medido y lo supuesto en su propia página tampoco lo va a distinguir en el
    informe que te manda. Esta tabla es la muestra de producto.</p>
  </div>
</section>

<section id="producto">
  <span class="q">Pregunta 5</span>
  <h2>{pregunta["producto"]}</h2>
  <div class="panel">
    <p>Es un servicio con software propio detrás: un sistema en Python 3.11 con
    <b>cero dependencias</b>, solo librería estándar, y una batería de pruebas en
    la que ninguna toca la red. No es una reventa de la API de nadie ni un
    envoltorio de una herramienta de terceros.</p>
    <p>Y no hay que creerse esta página: <b>el banco de pruebas que la está
    sirviendo es el producto</b>. Corre en tu máquina, atado a 127.0.0.1, y no
    envía nada a ningún sitio.</p>
    <ul class="hace">
      <li><b>1</b> <a href="/#auditoria">Auditoría</a> de un dominio en vivo, con
      barra de progreso y verificación HTTP por fila.</li>
      <li><b>2</b> <a href="/#citabilidad">Citabilidad</a> de un texto: las
      frases que un buscador levantaría, y lo que le falta a cada una de las
      demás.</li>
      <li><b>3</b> <a href="/#oportunidad">Oportunidad</a> desde tu exportación
      de Search Console, descontada por respuesta generada y ordenada por valor
      en vez de por clics.</li>
      <li><b>4</b> <a href="/#clusters">Plan de clusters</a> desde un CSV de
      keywords, con solape cero y tope mensual.</li>
    </ul>
  </div>
</section>

<section id="planes">
  <span class="q">Pregunta 6</span>
  <h2>{pregunta["planes"]}</h2>
  <div class="planes">{"".join(_plan_card(plan) for plan in PLANS)}</div>
  <div class="panel" style="margin-top:16px">
    <h3>Cómo se elige</h3>
    <p>Por el trabajo que tienes delante, no por el número de páginas. Si hay que
    demostrar que esto mueve algo, <b>Esencial</b>. Si ya hay tráfico que no
    convierte y lo que falta es dato propio y citabilidad,
    <b>Crecimiento</b>: es el que se vende y es el que cubre el caso de la
    mayoría. Si además hay que responder por el riesgo delante de alguien,
    <b>Completo</b>, por el dossier.</p>
    <p class="note">El tope de {CAP_PAGES} páginas al mes por sitio está por
    encima del plan más grande, que llega a {_max_pages()}: el límite no es
    comercial y no se compra pagando más. Ningún plan incluye
    {COMPETITOR_PAGES} artículos al mes, y ninguno lo va a incluir.</p>
  </div>
</section>

<section class="cta">
  <div class="panel">
    <h2>Cómo se empieza</h2>
    <p>Por la auditoría, que es gratis y no te pide nada a cambio: mide tu
    dominio en vivo, con peticiones espaciadas y respetando tu robots.txt, y te
    deja un informe donde cada afirmación lleva su código HTTP y su hora de
    consulta. Si no encuentra nada, lo dice tal cual.</p>
    <p><a class="go" href="/#auditoria">Auditar un dominio</a></p>
    <p class="note">Una ráfaga contra el sitio de un cliente es una forma de
    rompérselo: por defecto va un segundo entre peticiones.</p>
  </div>
  <footer class="pie">
    <p class="note">Esta página se sirve en 127.0.0.1 desde el mismo proceso que
    la herramienta. Los precios son por sitio y por mes.</p>
  </footer>
</section>
</div>
"""


def page() -> str:
    """La pagina de oferta. Sin red externa y sin JavaScript: es texto."""
    # noindex como el resto de la aplicacion: esto se sirve en 127.0.0.1, donde
    # ningun rastreador llega. Declararla indexable seria afirmar algo que no se
    # puede cumplir desde aqui.
    return (
        "<!doctype html>\n<html lang=\"es\">\n<head>\n"
        '<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        '<meta name="robots" content="noindex, nofollow">\n'
        "<title>Qué se vende — SEO y GEO medidos</title>\n"
        f"<style>{STYLE}{OFFER_STYLE}</style>\n</head>\n<body>\n{_body()}\n"
        "</body>\n</html>\n"
    )
