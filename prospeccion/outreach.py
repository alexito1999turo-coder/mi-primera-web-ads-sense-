"""Traduccion de una auditoria a algo que un desconocido abra y entienda.

El informe del M1 esta escrito para quien ya sabe lo que es un archivo
indexable. La persona que decide si nos contrata en una marca de e-commerce no
lo sabe, y el correo frio tiene una frase y media para demostrar que merece la
pena seguir leyendo. Por eso aqui cada hallazgo se parte en tres piezas fijas:

  que pasa (con la cifra medida), por que cuesta dinero o es un riesgo, y que
  hay que hacer para arreglarlo.

Las dos salidas no son la misma cosa escrita dos veces. El informe en Markdown
es lo que se adjunta y se lee con calma. El resumen de TRES LINEAS es lo que
decide si el informe se abre, y por eso tiene que nombrar el hallazgo mas
concreto que haya, con su cifra: "tienes 3 archivos de categoria compitiendo
con tus propios articulos" se lee; "hemos detectado oportunidades de mejora en
tu SEO" se borra.

Y la regla que protege el unico activo de esta pieza: si la auditoria no
encontro nada, no se inventa nada. El resumen dice que esta limpio y usa eso
como argumento. Una marca que recibe un problema falso y lo comprueba no vuelve
a abrir un correo nuestro.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from urllib.parse import urlparse

from auditor.audit import Audit
from auditor.rules import (
    ACTION_DISABLE,
    ACTION_NOINDEX,
    ACTION_RECATEGORIZE,
)

SUMMARY_LINES = 3

CODE_AUTHOR = "archivo_autor"
CODE_THIN = "archivo_fino"
CODE_RECATEGORIZE = "recategorizable"
CODE_SITEMAP = "sitemap_no_declarado"
CODE_INTENT = "intencion_en_riesgo"
CODE_CANNIBAL = "canibalizacion"

# Por debajo de esto el reparto de intencion no es un hallazgo, es ruido.
INTENT_RISK_PCT = 40.0


@dataclass
class Finding:
    """Un hallazgo ya traducido. Las tres piezas son obligatorias por diseno."""

    code: str
    headline: str          # que pasa, con la cifra dentro
    why: str               # por que cuesta dinero o es un riesgo
    fix: str               # que se hace para arreglarlo
    figure: str = ""       # la cifra desnuda, para el resumen de tres lineas
    priority: int = 2      # 1 = primero
    samples: list[str] = field(default_factory=list)
    evidence: list[str] = field(default_factory=list)


@dataclass
class Outreach:
    """Lo que se envia a una marca: el informe y las tres lineas del mensaje."""

    site: str
    brand: str = ""
    consulted_at: str = ""
    findings: list[Finding] = field(default_factory=list)
    markdown: str = ""
    summary_lines: list[str] = field(default_factory=list)
    unmeasured: list[str] = field(default_factory=list)

    @property
    def has_findings(self) -> bool:
        return bool(self.findings)

    @property
    def summary(self) -> str:
        return "\n".join(self.summary_lines)

    @property
    def slug(self) -> str:
        """Nombre de fichero estable: un informe por dominio, sin sorpresas."""
        host = _host(self.site) or "dominio"
        return "".join(c if c.isalnum() else "-" for c in host).strip("-").lower()


# -- lectura del dominio ----------------------------------------------------

def _host(site: str) -> str:
    parsed = urlparse(site if "://" in site else f"https://{site}")
    return (parsed.netloc or parsed.path).split(":")[0]


def brand_for(site: str) -> str:
    """El nombre con el que se dirige uno a la marca, sacado del dominio.

    No es cosmetica: un correo que empieza por "ejemplo.test" se lee como un
    envio masivo, que es justo lo que es, y lo unico que lo disimula es que el
    resto este medido de verdad.
    """
    host = _host(site)
    if host.startswith("www."):
        host = host[4:]
    name = (host.split(".")[0] or host).replace("-", " ").strip()
    return name[:1].upper() + name[1:] if name else host


def nothing_measured(audit: Audit) -> bool:
    """Cierto cuando no se pudo leer ni un listado ni un articulo declarado.

    Existe porque "no hay hallazgos" y "no se ha medido nada" dan los dos una
    lista de hallazgos vacia, y decir lo mismo en los dos casos es la unica
    mentira que esta pieza no se puede permitir. Un sitio cuyo sitemap no se
    deja leer no es un sitio sin problemas: es un sitio sin medir, y al
    desconocido que recibe el correo le costaria diez segundos comprobar que
    "lo tecnico esta limpio" no sale de ninguna medicion.
    """
    return not audit.archives and not audit.post_count


# -- traduccion de hallazgos ------------------------------------------------

def findings_for(audit: Audit) -> list[Finding]:
    """Convierte veredictos tecnicos en hallazgos con cifra, dinero y arreglo.

    Agrupa por tipo de problema en vez de por URL: a una marca se le dice
    "tienes 3 categorias asi", no se le mandan tres fichas identicas.
    """
    found: list[Finding] = []
    pending = audit.actionable

    authors = [a for a in pending if a.action == ACTION_DISABLE]
    if authors:
        found.append(Finding(
            code=CODE_AUTHOR,
            figure=_count(len(authors), "archivo") + " de autor",
            headline=(
                f"Tienes {_count(len(authors), 'pagina')} de autor que Google "
                "indexa como contenido propio"
            ),
            why=(
                "Esa pagina lista los mismos articulos que tu portada, asi que "
                "compite contra ella con una version peor. Google tiene que "
                "elegir cual ensena y a veces elige la mala: la visita entra por "
                "una pagina sin producto, sin oferta y sin motivo para comprar."
            ),
            fix=(
                "Desactivar el archivo de autor entero en el SEO del CMS. No es "
                "ponerlo en noindex: es que deje de existir como URL. Son dos "
                "clics y no se toca ni un articulo."
            ),
            priority=1,
            samples=[a.url for a in authors],
            evidence=[a.verification for a in authors],
        ))

    thin = [a for a in pending if a.action == ACTION_NOINDEX]
    if thin:
        worst = min(thin, key=lambda a: (a.words, a.posts))
        found.append(Finding(
            code=CODE_THIN,
            figure=f"{_count(len(thin), 'listado')} de {worst.words} palabras",
            headline=(
                f"Tienes {_count(len(thin), 'pagina')} de listado compitiendo "
                f"contra tus propios articulos, y "
                f"{_verb(len(thin), 'tiene', 'la peor tiene')} {worst.words} "
                f"palabras y {_count(worst.posts, 'articulo')}"
            ),
            why=(
                "Son paginas que no aportan nada que no este en el articulo que "
                "enlazan, y aun asi se presentan a la misma busqueda. El trafico "
                "que deberia llegar a la pagina buena se reparte, y el "
                "presupuesto de rastreo de Google se gasta en lo que no vende."
            ),
            fix=(
                "Sacarlas del indice (noindex) y del sitemap. Siguen navegables "
                "para quien llegue desde el menu: no se pierde ninguna visita, "
                "solo se deja de competir contra uno mismo."
            ),
            priority=2,
            samples=[a.url for a in thin],
            evidence=[a.verification for a in thin],
        ))

    recat = [a for a in pending if a.action == ACTION_RECATEGORIZE]
    if recat:
        total = sum(len(a.recategorization_candidates) for a in recat)
        found.append(Finding(
            code=CODE_RECATEGORIZE,
            figure=(f"{_count(total, 'articulo')} mal "
                    f"{_verb(total, 'colocado', 'colocados')}"),
            headline=(
                f"Hay {_count(total, 'articulo')} {_verb(total, 'colocado', 'colocados')} "
                f"en la categoria equivocada, y eso deja "
                f"{_count(len(recat), 'listado')} medio "
                f"{_verb(len(recat), 'vacio', 'vacios')}"
            ),
            why=(
                "Esto no es un problema que haya que esconder: es dinero ya "
                "escrito y mal colocado. Una categoria con seis articulos buenos "
                "rankea por el tema entero; la misma con uno no rankea por nada, "
                "y el contenido que falta ya lo tienes pagado y publicado."
            ),
            fix=(
                "Reasignar esos articulos a la categoria que les toca. Es trabajo "
                "de editor, no de programador, y se hace desde el propio panel."
            ),
            priority=1,
            samples=[
                f"{a.url} — puede recibir "
                f"{_count(len(a.recategorization_candidates), 'articulo')} que ya "
                f"{_verb(len(a.recategorization_candidates), 'tienes publicado', 'tienes publicados')}"
                for a in recat
            ],
            evidence=[a.verification for a in recat],
        ))

    confirmed = [c for c in audit.cannibalization if c.confirmed]
    if confirmed:
        worst = max(confirmed, key=lambda c: c.archive_impressions)
        found.append(Finding(
            code=CODE_CANNIBAL,
            figure=f"{worst.archive_impressions} impresiones mal dirigidas",
            headline=(
                f"En {_count(len(confirmed), 'caso')} medido con tus propios "
                "datos de Search Console, el listado se lleva mas impresiones "
                f"que el articulo: {worst.archive_impressions} frente a "
                f"{worst.article_impressions}"
            ),
            why=(
                "Es la version confirmada del problema anterior, ya no una "
                "hipotesis: Google esta ensenando el listado en lugar de la "
                "pagina que convierte. Cada una de esas impresiones es una "
                "busqueda que llego a la puerta equivocada."
            ),
            fix=(
                "Dar prioridad a esas URL concretas al sacar listados del indice: "
                "son las que devuelven resultado el primer mes."
            ),
            priority=1,
            samples=[c.describe() for c in confirmed],
        ))

    if audit.robots and audit.robots.present and not audit.robots.declares_sitemap:
        found.append(Finding(
            code=CODE_SITEMAP,
            figure="sitemap sin declarar",
            headline="Tu robots.txt no declara el sitemap",
            why=(
                "Google acaba encontrando el sitemap casi siempre, pero "
                "\"casi siempre\" no es una politica: cuando publicas, tardas mas "
                "en aparecer, y en temporada alta esos dias son ventas."
            ),
            fix=(
                "Anadir una linea 'Sitemap:' con la URL absoluta en robots.txt. "
                "Es un minuto y no hay ningun riesgo."
            ),
            priority=3,
            evidence=[audit.robots.verification],
        ))

    risk = audit.intent_distribution.get("informational", 0.0)
    if risk >= INTENT_RISK_PCT and audit.intent_at_risk_urls:
        found.append(Finding(
            code=CODE_INTENT,
            figure=f"{_pct(risk)}% del contenido",
            headline=(
                f"El {_pct(risk)}% de tus articulos ({len(audit.intent_at_risk_urls)} de "
                f"{audit.post_count}) responde preguntas que la IA de Google ya "
                "contesta en el propio resultado"
            ),
            why=(
                "Ese contenido puede estar primero y no recibir la visita: la "
                "respuesta se lee sin entrar. Es trafico que figura en los "
                "informes como posicion ganada y no aparece en la caja."
            ),
            fix=(
                "Reequilibrar el calendario hacia articulos de comparacion, "
                "precio y decision de compra, que son los que la IA no cierra "
                "sola porque el usuario quiere ver el producto."
            ),
            priority=3,
            samples=audit.intent_at_risk_urls[:5],
        ))

    return sorted(found, key=lambda f: f.priority)


def unmeasured_for(audit: Audit) -> list[str]:
    """Lo que no se ha medido se declara. Es media pagina del informe y vende."""
    pending: list[str] = []
    if nothing_measured(audit):
        pending.append(
            "Nada del sitio, y es lo primero de la lista: no se leyo un sitemap "
            "con articulos ni con listados, asi que ni un listado y ni un "
            "articulo tienen veredicto. No se concluye que esten bien."
        )
    if not audit.impressions_loaded:
        pending.append(
            "Canibalizacion con cifras reales: hace falta una exportacion de "
            "Search Console, que solo tu puedes dar. Sin ese dato no se afirma "
            "nada; aqui no hay estimaciones."
        )
    if not audit.intent_distribution:
        pending.append(
            "Reparto de intencion de los articulos: no se encontraron articulos "
            "declarados en el sitemap para clasificarlos."
        )
    # Las notas del auditor estan escritas para un SEO y repiten lo de arriba
    # con otras palabras. En un informe que se manda a una marca, decir dos
    # veces lo mismo se lee como relleno.
    ya_dicho = " ".join(pending).lower()
    for note in audit.notes:
        if "search console" in note.lower() and "search console" in ya_dicho:
            continue
        pending.append(note)
    return pending


# -- las tres lineas del mensaje -------------------------------------------

def summarize(audit: Audit, findings: list[Finding], brand: str = "") -> list[str]:
    """Exactamente tres lineas: gancho con cifra, alcance y peticion.

    Si no hay hallazgos no se maquilla ninguno: se dice que esta limpio, que es
    lo unico que mantiene creible el resto del envio.
    """
    brand = brand or brand_for(audit.site)
    measured = len(audit.archives)
    when = (audit.finished_at or audit.started_at or "").split("T")[0]

    if not findings and nothing_measured(audit):
        return [
            f"{brand}: he intentado medir {_host(audit.site)} desde fuera y no "
            "he podido leer un sitemap con articulos ni con listados, asi que "
            "no tengo ni una pagina medida. No te digo que este limpio, porque "
            "no lo se.",
            "Eso ya es un dato: puede ser que el sitemap no se genere, que este "
            "en otra ruta o que no lo declare tu robots.txt. No afirmo cual de "
            "las tres es, solo que desde fuera no se ve, y lo que Google no "
            "encuentra tarda mas en aparecer cuando publicas.",
            f"Te adjunto lo unico que si he comprobado, con el codigo HTTP y la "
            f"hora de consulta ({when}); si me dices donde esta el sitemap, "
            "repito la medicion completa y te mando el informe entero.",
        ]

    if not findings:
        return [
            f"{brand}: he auditado {_count(measured, 'pagina')} de listado de "
            f"{_host(audit.site)} y no he encontrado ni un archivo fino ni un "
            "duplicado indexado, asi que no te voy a inventar un problema.",
            "Lo tecnico esta limpio, y eso cambia la conversacion: tu techo no "
            "esta en arreglar errores sino en que falta contenido que capture "
            "busquedas de compra, que es trabajo de calendario y no de parches.",
            f"Te adjunto la auditoria igual, con el codigo HTTP y la hora de "
            f"consulta de cada comprobacion ({when}), por si te sirve como punto "
            "de partida medido.",
        ]

    top = findings[0]
    rest = findings[1:]
    if rest:
        otros = ", ".join(f.figure for f in rest[:2] if f.figure)
        second = (
            f"{_first_sentence(top.why)} Y no es lo unico: en la misma pasada "
            f"salieron {otros}."
        ) if otros else _first_sentence(top.why)
    else:
        second = _first_sentence(top.why)

    return [
        f"{brand}: {top.headline}.",
        second,
        f"Te adjunto el informe de {_count(len(findings), 'hallazgo')} con el "
        f"codigo HTTP y la hora de consulta de cada uno ({when}); si quieres, "
        "te digo en una llamada de quince minutos cual arreglaria primero.",
    ]


# -- el informe -------------------------------------------------------------

def to_markdown(audit: Audit, findings: list[Finding], brand: str = "",
                summary_lines: list[str] | None = None,
                unmeasured: list[str] | None = None) -> str:
    """Informe para un responsable de e-commerce, no para un SEO."""
    brand = brand or brand_for(audit.site)
    lines: list[str] = []
    add = lines.append

    add(f"# Auditoria tecnica de {brand}")
    add("")
    add(f"Sitio medido: {audit.site}")
    add("")
    add(f"Esto no es una plantilla. Se midio en vivo entre {audit.started_at} y "
        f"{audit.finished_at} con {audit.requests_made} peticiones espaciadas, "
        "respetando tu robots.txt. Cada afirmacion de este informe lleva debajo "
        "el codigo HTTP y la hora exacta en que se comprobo.")
    add("")

    if summary_lines:
        add("## En tres lineas")
        add("")
        for position, line in enumerate(summary_lines):
            if position:
                add(">")
            add(f"> {line}")
        add("")

    # --- Hallazgos -------------------------------------------------------
    add("## Lo que encontre")
    add("")
    if not findings and nothing_measured(audit):
        add("**No he medido nada, y eso no es lo mismo que decir que esta "
            "limpio.** No se pudo leer un sitemap con articulos ni con "
            "listados, asi que no hay ni una pagina sobre la que dar un "
            "veredicto. Lo que sigue es solo lo que si se comprobo.")
        add("")
        add("Puede ser que el sitemap no se genere, que este en otra ruta o que "
            "robots.txt no lo declare. No se afirma cual: eso se sabe con un "
            "dato que desde fuera no se tiene.")
        add("")
    elif not findings:
        add("Nada que arreglar en lo que se puede medir desde fuera. Se "
            f"{_verb(len(audit.archives), 'reviso', 'revisaron')} "
            f"{_count(len(audit.archives), 'pagina')} de listado (categorias, "
            f"etiquetas y autores) y {_count(audit.post_count, 'articulo')} "
            f"{_verb(audit.post_count, 'declarado', 'declarados')} en el sitemap, "
            "y ninguno es un duplicado indexado ni un listado fino compitiendo "
            "con su propio contenido.")
        add("")
        add("Se dice tal cual porque lo contrario seria inventar un problema "
            "para tener algo que vender.")
        add("")
    else:
        for index, finding in enumerate(findings, start=1):
            add(f"### {index}. {finding.headline}")
            add("")
            add(f"**Por que importa.** {finding.why}")
            add("")
            add(f"**Que hay que hacer.** {finding.fix}")
            add("")
            if finding.samples:
                add("Donde pasa:")
                add("")
                for sample in finding.samples[:8]:
                    add(f"- {sample}")
                if len(finding.samples) > 8:
                    add(f"- ...y {len(finding.samples) - 8} mas en el anexo.")
                add("")
            for item in finding.evidence:
                add(f"Verificacion: `{item}`")
                add("")

    # --- Lo que no se ha medido -----------------------------------------
    pending = unmeasured_for(audit) if unmeasured is None else unmeasured
    if pending:
        add("## Lo que NO he medido")
        add("")
        add("Va aqui porque un informe que no distingue entre lo medido y lo "
            "supuesto no sirve para decidir:")
        add("")
        for item in pending:
            add(f"- {item}")
        add("")

    # --- Verificaciones --------------------------------------------------
    add("## Como lo he comprobado")
    add("")
    if audit.robots:
        add(f"- robots.txt: `{audit.robots.verification}`")
    for sitemap in audit.sitemaps:
        if sitemap.exists:
            add(f"- sitemap ({sitemap.kind}): `{sitemap.verification}`")
    add("")
    add("Peticiones espaciadas y con identificacion propia, respetando las "
        "reglas de tu robots.txt. No se toco nada de tu sitio: solo se leyo lo "
        "que ya sirves en abierto.")
    add("")

    return "\n".join(lines)


def build(audit: Audit, brand: str = "") -> Outreach:
    """De una auditoria a un envio: informe largo y tres lineas de mensaje."""
    brand = brand or brand_for(audit.site)
    findings = findings_for(audit)
    summary_lines = summarize(audit, findings, brand=brand)
    unmeasured = unmeasured_for(audit)
    return Outreach(
        site=audit.site,
        brand=brand,
        consulted_at=audit.finished_at or audit.started_at,
        findings=findings,
        markdown=to_markdown(audit, findings, brand=brand,
                             summary_lines=summary_lines,
                             unmeasured=unmeasured),
        summary_lines=summary_lines,
        unmeasured=unmeasured,
    )


def _count(count: int, singular: str) -> str:
    """Evita el '1 articulos' que delata una plantilla sin cuidado."""
    return f"{count} {singular}" if count == 1 else f"{count} {singular}s"


def _verb(count: int, singular: str, plural: str) -> str:
    """Concordancia del verbo o del adjetivo que acompana a la cifra.

    Existe por el mismo motivo que `_count`: este texto lo lee un cliente
    potencial que no nos conoce, y un "1 articulo que estan mal colocados" le
    dice que detras no hay nadie mirando.
    """
    return singular if count == 1 else plural


def _pct(value: float) -> str:
    """Porcentaje sin el '.0' de mas: en prosa de venta se lee '40%', no '40.0%'."""
    return str(int(value)) if float(value).is_integer() else str(value)


def _first_sentence(text: str) -> str:
    """La primera frase del 'por que', que es lo que cabe en el mensaje."""
    head = text.split(". ", 1)[0].rstrip(".")
    return f"{head}."
