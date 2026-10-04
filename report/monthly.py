"""El informe mensual del cliente, ensamblado desde lo que el sistema registro."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

MEDIDO = "medido"
ESTIMADO = "estimado"
SUPUESTO = "supuesto"

MARCA = {MEDIDO: "medido", ESTIMADO: "estimado", SUPUESTO: "SUPUESTO"}

# Por debajo de esto una cifra no se presenta como medicion aunque haya datos:
# tres observaciones no son una media, son tres observaciones.
MIN_OBSERVACIONES = 5


@dataclass
class Figure:
    """Una cifra con su procedencia pegada.

    La procedencia no es un adorno de transparencia: es lo que impide que un
    numero supuesto se cite seis meses despues como si se hubiera medido. Pasa
    siempre, y pasa porque el numero viaja sin ella.
    """

    label: str
    value: str
    provenance: str = SUPUESTO
    basis: str = ""           # de donde sale, en una linea

    @property
    def trustworthy(self) -> bool:
        return self.provenance == MEDIDO

    def line(self) -> str:
        marca = MARCA.get(self.provenance, self.provenance)
        base = f" — {self.basis}" if self.basis else ""
        return f"{self.label}: **{self.value}** ({marca}){base}"


@dataclass
class Section:
    title: str
    figures: list[Figure] = field(default_factory=list)
    lines: list[str] = field(default_factory=list)

    def markdown(self) -> str:
        out = [f"## {self.title}", ""]
        for figura in self.figures:
            out.append(f"- {figura.line()}")
        if self.figures and self.lines:
            out.append("")
        out.extend(self.lines)
        out.append("")
        return "\n".join(out)


@dataclass
class MonthlyReport:
    client: str
    period: str
    sections: list[Section] = field(default_factory=list)
    unknowns: list[str] = field(default_factory=list)
    would_change: list[str] = field(default_factory=list)
    blockers: list[str] = field(default_factory=list)
    generated_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(timespec="seconds")
    )

    # -- lo que hace que esto sea vendible --------------------------------
    @property
    def figures(self) -> list[Figure]:
        return [f for s in self.sections for f in s.figures]

    @property
    def measured_share(self) -> int:
        """Que porcentaje del informe son mediciones.

        Es la cifra que yo ensenaria primero en una propuesta, porque es la que
        el competidor no puede ensenar: para publicarla hay que haber decidido
        antes que lo supuesto se marca.
        """
        todas = self.figures
        if not todas:
            return 0
        return round(100 * len([f for f in todas if f.trustworthy]) / len(todas))

    @property
    def deliverable(self) -> bool:
        return not self.blockers

    def headline(self) -> str:
        if self.blockers:
            return (f"{len(self.blockers)} asunto(s) sin resolver: el mes no se "
                    "cierra hasta que esten.")
        return (f"Mes cerrado. {self.measured_share}% de las cifras de este "
                f"informe son mediciones; el resto se marca como tal.")

    def to_markdown(self) -> str:
        out = [
            f"# {self.client} — informe de {self.period}",
            "",
            self.headline(),
            "",
            f"_Generado el {self.generated_at[:16].replace('T', ' ')} UTC desde el "
            "registro del sistema. Ninguna cifra de este documento se teclea a "
            "mano: si no esta medida, no aparece o aparece marcada._",
            "",
        ]
        for seccion in self.sections:
            out.append(seccion.markdown())

        out.append("## Lo que todavia no sabemos")
        out.append("")
        if self.unknowns:
            out.append(
                "Esta seccion la genera el sistema. No se puede quitar sin "
                "quitar los datos que la producen."
            )
            out.append("")
            out.extend(f"- {u}" for u in self.unknowns)
        else:
            out.append("Nada pendiente de medir en el alcance contratado.")
        out.append("")

        out.append("## Que haria cambiar la recomendacion")
        out.append("")
        if self.would_change:
            out.append(
                "Un informe que solo justifica lo hecho no sirve para decidir "
                "el mes que viene. Esto es lo que nos haria cambiar de opinion:"
            )
            out.append("")
            out.extend(f"- {w}" for w in self.would_change)
        else:
            out.append("Sin datos suficientes para plantear alternativas todavia.")
        out.append("")

        if self.blockers:
            out.append("## Sin resolver")
            out.append("")
            out.extend(f"- {b}" for b in self.blockers)
            out.append("")
        return "\n".join(out)


# -- el ensamblado --------------------------------------------------------
#
# Todo lo de abajo lee del almacen y de los modulos. No hay ningun parametro
# por el que colar una cifra inventada, y eso es una decision de diseno, no una
# limitacion: la frontera entre «lo que el sistema sabe» y «lo que el comercial
# quiere poner» tiene que estar en el codigo, porque en la buena voluntad no
# aguanta tres meses.

def _plural(n: int, singular: str, plural: str) -> str:
    return f"{n} {singular if n == 1 else plural}"


def _trabajo(store, record) -> Section:
    seccion = Section(title="Lo que se ha hecho")
    publicadas = len(store.pages)
    seccion.figures.append(Figure(
        "Paginas publicadas", str(record.pages_published), MEDIDO,
        f"{publicadas} en el corpus del almacen"))
    seccion.figures.append(Figure(
        "Paginas bloqueadas por las compuertas", str(record.pages_blocked), MEDIDO,
        "no salieron: el coste esta pagado y el riesgo no se asumio"))
    if record.pages_published + record.pages_blocked:
        seccion.figures.append(Figure(
            "Publicables sin tocar", f"{record.publishable_rate}%", MEDIDO,
            "pasaron todas las compuertas a la primera"))
    seccion.figures.append(Figure(
        "Tope del mes", f"{record.pages_published} de {record.monthly_cap}",
        MEDIDO,
        "el tope es una decision de riesgo, no un limite tecnico"))
    if not record.cap_respected:
        seccion.lines.append(
            "> El tope se ha pasado. Cuatro paginas al dia en un dominio sin "
            "revision es el patron que Google penaliza como scaled content "
            "abuse: pasarlo es el riesgo que el tope evita."
        )
    return seccion


def _solape(store, portfolio, cliente: str) -> Section:
    seccion = Section(title="Que se ha comprobado antes de publicar")
    paginas = len(store.pages)
    if paginas < 2:
        seccion.figures.append(Figure(
            "Solape interno maximo", "no medido", SUPUESTO,
            f"{_plural(paginas, 'pagina', 'paginas')} en el corpus: hacen falta "
            "dos para comparar"))
    else:
        peor = 0.0
        par = ("", "")
        estimado = False
        from store.sketch import similarity
        firmas = store.corpus()
        slugs = sorted(firmas)
        for i, a in enumerate(slugs):
            for b in slugs[i + 1:]:
                valor = similarity(firmas[a], firmas[b])
                if valor > peor:
                    peor, par = valor, (a, b)
                    estimado = not (firmas[a].exact and firmas[b].exact)
        seccion.figures.append(Figure(
            "Solape interno maximo", f"{peor * 100:.0f}%",
            ESTIMADO if estimado else MEDIDO,
            f"entre '{par[0]}' y '{par[1]}', sobre "
            f"{_plural(paginas, 'pagina', 'paginas')}"))

    if portfolio is None:
        seccion.figures.append(Figure(
            "Huella cruzada de la cartera", "no medida", SUPUESTO,
            "sin almacen de cartera no se puede comprobar"))
    else:
        auditoria = portfolio.audit()
        if auditoria.sites < 2:
            seccion.figures.append(Figure(
                "Huella cruzada de la cartera", "no aplica", MEDIDO,
                f"{_plural(auditoria.sites, 'sitio', 'sitios')} en cartera"))
        else:
            peor = max((c.phrase_similarity for c in auditoria.collisions),
                       default=0.0)
            seccion.figures.append(Figure(
                "Parecido maximo con otro sitio de la cartera",
                f"{peor * 100:.1f}%", ESTIMADO,
                f"{auditoria.sites} sitios, "
                f"{_plural(len(auditoria.collisions), 'par', 'pares')}; "
                "estimado desde las firmas"))
            seccion.lines.append(f"> {auditoria.describe()}")
    return seccion


def _medido(store, prior_sets) -> Section:
    seccion = Section(title="Lo que se ha medido este mes")
    from store.project import MEDIDO as ORIGEN_MEDIDO

    metricas = store.metrics()
    if not metricas:
        seccion.lines.append(
            "Ninguna observacion registrada. Todas las cifras de planificacion "
            "siguen siendo las declaradas al empezar."
        )
        return seccion

    for nombre in sorted(metricas):
        medidas = store.observations(nombre, source=ORIGEN_MEDIDO)
        if not medidas:
            seccion.figures.append(Figure(
                nombre, "solo declarada", SUPUESTO,
                f"{metricas[nombre]} apunte(s), ninguno medido"))
            continue
        media = sum(medidas) / len(medidas)
        suficiente = len(medidas) >= MIN_OBSERVACIONES
        seccion.figures.append(Figure(
            nombre, f"{round(media, 4)}",
            MEDIDO if suficiente else ESTIMADO,
            f"{_plural(len(medidas), 'observacion', 'observaciones')}"
            + ("" if suficiente else
               f"; hacen falta {MIN_OBSERVACIONES} para llamarlo medicion")))

    for conjunto in (prior_sets or []):
        seccion.lines.append(f"> {conjunto.describe()}")
    return seccion


def _revision(store) -> Section:
    seccion = Section(title="Lo que el revisor corrigio")
    log = store.rejection_log()
    seccion.figures.append(Figure(
        "Rechazos registrados", str(len(log.rejections)), MEDIDO,
        "cada uno con el motivo y la instruccion que lo habria evitado"))
    if not log.rejections:
        seccion.lines.append(
            "Sin rechazos. Con pocas paginas esto no dice que el generador sea "
            "bueno: dice que todavia no hay muestra."
        )
        return seccion
    taxonomia = log.taxonomy()
    seccion.lines.append("Motivos por frecuencia:")
    seccion.lines.append("")
    for codigo, veces in list(taxonomia.items())[:6]:
        seccion.lines.append(f"- `{codigo}`: {veces}")
    seccion.lines.append("")
    seccion.lines.append(f"> {log.minutes_trend()}")
    adiciones = log.brief_additions()
    if adiciones:
        seccion.lines.append("")
        seccion.lines.append(
            "Lo que ya vuelve al brief automaticamente, por ser recurrente:")
        seccion.lines.append("")
        seccion.lines.extend(f"- {a}" for a in adiciones)
    return seccion


def _incognitas(store, portfolio, record, prior_sets) -> list[str]:
    """Lo que NO se sabe. Generado, no escrito.

    Es la seccion que ningun competidor incluye, y por una razon entendible:
    es la unica que puede perder un cliente. Tambien es la unica que, cuando
    el trafico no sube en el mes cuatro, demuestra que se dijo antes.
    """
    from store.project import MEDIDO as ORIGEN_MEDIDO

    fuera: list[str] = []

    if len(store.pages) < 2:
        fuera.append(
            "No sabemos si las paginas se canibalizan entre si: con menos de "
            "dos publicadas no hay con que comparar."
        )
    if portfolio is None or len(getattr(portfolio, "sites", {})) < 2:
        fuera.append(
            "No sabemos como se ve esta cartera en agregado: hace falta mas de "
            "un sitio para medir la huella cruzada, que es el patron que mata "
            "varios clientes a la vez en vez de uno."
        )

    # Una misma cifra puede estar floja por dos motivos a la vez: pocas
    # observaciones y un prior que todavia manda. Decirlo en dos lineas
    # distintas hace que la seccion parezca rellenada, y es justo la seccion
    # que no se puede permitir parecerlo. Se dice una vez, con los dos datos.
    por_metrica: dict[str, list[str]] = {}

    metricas = store.metrics()
    for nombre in sorted(metricas):
        medidas = store.observations(nombre, source=ORIGEN_MEDIDO)
        if len(medidas) < MIN_OBSERVACIONES:
            por_metrica.setdefault(nombre, []).append(
                f"{_plural(len(medidas), 'observacion medida', 'observaciones medidas')} "
                f"de las {MIN_OBSERVACIONES} que hacen falta"
            )

    for conjunto in (prior_sets or []):
        for post in conjunto.report():
            if post.trustworthy:
                continue
            por_metrica.setdefault(post.prior.name, []).append(
                f"{post.prior_share}% sigue siendo el prior declarado "
                f"({conjunto.label})"
            )

    for nombre in sorted(por_metrica):
        fuera.append(f"«{nombre}» no es todavia una medicion: "
                     + "; ".join(por_metrica[nombre]) + ".")

    if record.max_density is None:
        fuera.append(
            "No tenemos la densidad maxima del mes registrada; la compuerta la "
            "comprueba por pagina pero el dossier no la puede citar."
        )
    if not record.sources_cited:
        fuera.append(
            "No hay fuentes citadas registradas en el periodo, asi que no "
            "podemos demostrar documentalmente que se citaron."
        )

    idiomas = set(record.languages) - set(record.languages_human_reviewed)
    if idiomas:
        fuera.append(
            "Publicado en "
            + ", ".join(sorted(idiomas))
            + " sin revision nativa registrada: no podemos afirmar que no sea "
            "traduccion automatica a ojos de la politica."
        )
    return fuera


def _alternativas(store, record, oportunidad=None) -> list[str]:
    cambios: list[str] = []
    if record.pages_published and record.publishable_rate < 60:
        cambios.append(
            f"Si el {100 - record.publishable_rate:.0f}% que necesita arreglo "
            "sigue ahi el mes que viene, el problema es el brief y no el "
            "generador: tocaria rehacer los briefs del cluster antes de "
            "producir mas."
        )
    log = store.rejection_log()
    recurrentes = log.recurring_codes()
    if recurrentes:
        cambios.append(
            "Hay motivos de rechazo que se repiten ("
            + ", ".join(sorted(recurrentes))
            + "). Si siguen tras inyectar las instrucciones en el brief, el "
            "fallo esta en la compuerta, no en el texto."
        )
    if len(store.pages) >= record.monthly_cap:
        cambios.append(
            "Con el tope lleno, mas volumen solo se consigue subiendo el "
            "riesgo. La alternativa es mejorar las paginas que ya estan: "
            "cuesta menos y no toca el perfil de riesgo del dominio."
        )
    if oportunidad is not None and getattr(oportunidad, "demoted", None):
        demotidas = oportunidad.demoted()
        if demotidas:
            cambios.append(
                f"{len(demotidas)} consulta(s) pierden valor al descontar la "
                "respuesta generada. Si el reparto de intencion sigue igual el "
                "mes que viene, hay que mover el presupuesto a comercial."
            )
    if not cambios:
        cambios.append(
            "Con los datos de este mes no hay nada que recomiende cambiar el "
            "plan. Esto no es lo mismo que decir que el plan es correcto: es "
            "que todavia no hay senal."
        )
    return cambios


def build(store, record, portfolio=None, prior_sets=None,
          oportunidad=None) -> MonthlyReport:
    """Ensambla el informe desde el registro. No admite cifras de fuera."""
    from compliance.dossier import unresolved

    informe = MonthlyReport(client=record.client or store.client,
                            period=record.period)
    informe.sections = [
        _trabajo(store, record),
        _solape(store, portfolio, record.client),
        _medido(store, prior_sets),
        _revision(store),
    ]
    informe.unknowns = _incognitas(store, portfolio, record, prior_sets)
    informe.would_change = _alternativas(store, record, oportunidad)
    informe.blockers = unresolved(record)
    return informe
