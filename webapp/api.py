"""Los cuatro servicios, envolviendo los modulos del motor.

Cada funcion recibe datos del formulario y devuelve algo serializable. Nada de
logica de negocio aqui: la logica esta en los modulos y probada aparte. Lo que
si hay aqui es la validacion de lo que llega de fuera, que es trabajo de la
frontera y no se delega.
"""

from __future__ import annotations

import csv
import io
import os
import re
from dataclasses import asdict
from datetime import date
from pathlib import Path
from urllib.parse import urlparse

from auditor.audit import run as run_audit
from auditor.http import Client
from auditor.report import to_markdown as audit_markdown
from citability.score import analyse as analyse_citability
from clusters.graph import build as build_graph
from clusters.keywords import Keyword
from clusters.plan import build as build_plan
from clusters.validate import validate as validate_graph
from estudio import herramientas as estudio_herramientas
from estudio import jueces as estudio_jueces
from estudio import plan as estudio_plan
from estudio.agentes import PLANTILLA
from estudio.carrera import Carrera, comparar_rutas
from estudio.sala import Sala
from insight.gsc import Report, Row
from insight.opportunity import analyse as analyse_opportunity

from .jobs import Progress

MAX_UPLOAD = 4_000_000
MAX_TEXT = 400_000
MAX_KEYWORDS = 2000
MAX_GSC_ROWS = 20000

# Un servidor local no debe convertirse en un escaner de la red interna de quien
# lo levante. Se rechazan destinos que no son internet publico.
PRIVATE_HOSTS = re.compile(
    r"^(?:localhost|127\.|10\.|192\.168\.|169\.254\.|172\.(?:1[6-9]|2\d|3[01])\.|"
    r"0\.|\[?::1\]?|metadata\.)",
    re.I,
)


class BadRequest(ValueError):
    """Lo que llega de fuera esta mal. Se contesta con 400, no con una traza."""


def normalize_site(raw: str, allow_private: bool = False) -> str:
    site = (raw or "").strip()
    if not site:
        raise BadRequest("Falta el dominio.")
    if len(site) > 300:
        raise BadRequest("El dominio es absurdamente largo.")
    if "://" not in site:
        site = "https://" + site
    parsed = urlparse(site)
    if parsed.scheme not in ("http", "https"):
        raise BadRequest("Solo http y https.")
    if not parsed.netloc or "." not in parsed.netloc.split(":")[0]:
        raise BadRequest(f"«{raw}» no parece un dominio.")
    if not allow_private and PRIVATE_HOSTS.match(parsed.netloc):
        raise BadRequest(
            "Ese destino es una direccion interna. Esta herramienta audita sitios "
            "publicos; apuntarla a la red local la convertiria en un escaner."
        )
    return f"{parsed.scheme}://{parsed.netloc}"


# --- 1. Auditoria ----------------------------------------------------------

def audit(site: str, thin_words: int, interval: float, max_archives: int,
          allow_private: bool = False):
    root = normalize_site(site, allow_private=allow_private)
    thin_words = max(100, min(5000, int(thin_words)))
    interval = max(0.05, min(5.0, float(interval)))
    max_archives = max(1, min(200, int(max_archives)))

    def work(progress: Progress):
        progress.set_total(max_archives + 6)
        progress.step(f"Pidiendo robots.txt de {root}", advance=0)
        client = _ReportingClient(Client(min_interval=interval), progress)
        result = run_audit(root, client=client, thin_words=thin_words,
                           max_archives=max_archives)
        progress.step("Informe listo", advance=0)
        return {
            "site": result.site,
            "markdown": audit_markdown(result),
            "summary": {
                "archives": len(result.archives),
                "indexable": len([a for a in result.archives if a.indexable]),
                "actions": len(result.actionable),
                "posts": result.post_count,
                "requests": result.requests_made,
                "intent": result.intent_distribution,
            },
            "archives": [
                {
                    "url": a.url, "kind": a.kind, "status": a.status,
                    "indexable": a.indexable, "posts": a.posts, "words": a.words,
                    "verdict": a.verdict, "action": a.action, "reason": a.reason,
                    "candidates": a.recategorization_candidates[:10],
                    "verification": a.verification,
                }
                for a in sorted(result.archives, key=lambda x: (x.priority or 9, -x.words))
            ],
            "warnings": result.warnings,
            "notes": result.notes,
        }

    return work


class _ReportingClient:
    """Envuelve el cliente para contar el progreso sin tocar el auditor."""

    def __init__(self, client: Client, progress: Progress) -> None:
        self._client = client
        self._progress = progress

    def get(self, url: str):
        corto = urlparse(url).path or "/"
        self._progress.step(f"Midiendo {corto}")
        return self._client.get(url)

    @property
    def request_count(self) -> int:
        return self._client.request_count


# --- 2. Citabilidad --------------------------------------------------------

def citability(text: str) -> dict:
    if not (text or "").strip():
        raise BadRequest("Pega un texto para medirlo.")
    if len(text) > MAX_TEXT:
        raise BadRequest("El texto pasa del limite de 400.000 caracteres.")
    report = analyse_citability(text)
    return {
        "score": report.score,
        "question_headings": report.question_headings,
        "answer_first": report.answer_first_sections,
        "candidates": len(report.quotes),
        "liftable": [
            {"text": q.text, "total": q.total, "ext": q.extractability,
             "atr": q.attributability, "esc": q.scarcity, "ali": q.alignment}
            for q in report.liftable
        ],
        "worst": [
            {"text": q.text, "total": q.total, "ext": q.extractability,
             "atr": q.attributability, "esc": q.scarcity, "ali": q.alignment,
             "blockers": q.blockers}
            for q in sorted(report.quotes, key=lambda q: q.total)[:5]
            if not q.liftable
        ],
        "fixes": [{"fix": fix, "count": count} for fix, count in report.top_fixes(8)],
        "describe": report.describe(),
    }


# --- 3. Oportunidad --------------------------------------------------------

def opportunity(csv_text: str) -> dict:
    rows = _parse_gsc(csv_text)
    if not rows:
        raise BadRequest(
            "No se encontraron filas utilizables. Hace falta una columna de "
            "consulta o pagina y otra de impresiones."
        )
    report = analyse_opportunity(Report(rows=rows))
    if not report.ranked:
        # El mensaje tiene que decir el motivo DE VERDAD. El de antes mandaba
        # a exportar con la columna de posicion aunque la posicion estuviera
        # ahi y el problema fuera el volumen: mandar a hacer algo que no
        # arregla nada es peor que no decir nada.
        from insight.opportunity import MIN_IMPRESSIONS

        if report.unmeasurable and not report.skipped_low_volume:
            raise BadRequest(
                f"Las {report.unmeasurable} fila(s) no traen posicion media, "
                "que es lo que hace falta para estimar cuanto clic se gana al "
                "subir. En Search Console, exporta desde Rendimiento con la "
                "columna «Posicion» activada."
            )
        if report.skipped_low_volume:
            techo = max((r.impressions for r in rows), default=0)
            raise BadRequest(
                f"Ninguna de las {len(rows)} consulta(s) llega a "
                f"{MIN_IMPRESSIONS} impresiones; la que mas tiene se queda en "
                f"{techo}. Con ese volumen cualquier orden que saliera seria "
                "ruido con aspecto de dato, asi que no se calcula. Es un sitio "
                "demasiado nuevo o un periodo demasiado corto: amplia el rango "
                "de fechas, y si aun asi no llega, lo que toca todavia no es "
                "priorizar sino publicar y arreglar lo estructural."
            )
        raise BadRequest(
            "No hay ninguna fila con posicion y volumen suficientes para "
            "estimar oportunidad."
        )

    def pack(items):
        return [
            {"subject": o.subject, "impressions": o.row.impressions,
             "position": round(o.row.position, 1), "intent": o.intent,
             "band": o.band, "raw": round(o.raw_gain), "adjusted": round(o.adjusted_gain),
             "value": round(o.value), "lost": round(o.lost_to_aio)}
            for o in items
        ]

    return {
        "describe": report.describe(),
        "by_value": pack(report.ranked[:40]),
        "by_clicks": pack(report.ranked_by_clicks[:40]),
        "demoted": [{"subject": s, "before": b, "after": a}
                    for s, b, a in report.demoted()],
        "promoted": [{"subject": s, "before": b, "after": a}
                     for s, b, a in report.promoted()],
        "totals": {"adjusted": report.total_adjusted,
                   "lost": report.total_lost_to_aio,
                   "skipped": report.skipped_low_volume,
                   "unmeasurable": report.unmeasurable},
    }


def _parse_gsc(csv_text: str) -> list[Row]:
    if not (csv_text or "").strip():
        raise BadRequest("Pega o sube la exportacion de Search Console.")
    if len(csv_text) > MAX_UPLOAD:
        raise BadRequest("El fichero es demasiado grande.")
    reader = csv.DictReader(io.StringIO(csv_text))
    if not reader.fieldnames:
        raise BadRequest("El CSV no tiene cabecera.")
    from insight.gsc import _number, _pick

    fields = list(reader.fieldnames)
    query_field = _pick(fields, ("query", "consulta", "consultas", "keyword"))
    page_field = _pick(fields, ("page", "pagina", "página", "url", "address"))
    clicks_field = _pick(fields, ("clicks", "clics"))
    impressions_field = _pick(fields, ("impressions", "impresiones"))
    position_field = _pick(fields, ("position", "posicion", "posición"))
    if not impressions_field:
        raise BadRequest("Falta la columna de impresiones.")
    if not (query_field or page_field):
        raise BadRequest("Falta la columna de consulta o de pagina.")

    rows: list[Row] = []
    for raw in reader:
        if len(rows) >= MAX_GSC_ROWS:
            break
        row = Row(
            query=(raw.get(query_field) or "").strip() if query_field else "",
            page=(raw.get(page_field) or "").strip() if page_field else "",
            clicks=int(_number(raw.get(clicks_field) if clicks_field else None)),
            impressions=int(_number(raw.get(impressions_field))),
            position=_number(raw.get(position_field) if position_field else None),
        )
        if row.impressions or row.clicks:
            rows.append(row)
    return rows


# --- 4. Clusters -----------------------------------------------------------

def clusters(csv_text: str, cap: int) -> dict:
    if not (csv_text or "").strip():
        raise BadRequest("Pega o sube el CSV de keywords.")
    if len(csv_text) > MAX_UPLOAD:
        raise BadRequest("El fichero es demasiado grande.")
    cap = max(1, min(120, int(cap)))

    from clusters.keywords import _number, _pick

    reader = csv.DictReader(io.StringIO(csv_text))
    if not reader.fieldnames:
        raise BadRequest("El CSV no tiene cabecera.")
    fields = list(reader.fieldnames)
    term_field = _pick(fields, ("keyword", "palabra", "query", "term", "consulta"))
    if not term_field:
        raise BadRequest(
            "No hay columna de keyword. Cabeceras encontradas: " + ", ".join(fields)
        )
    volume_field = _pick(fields, ("search volume", "volume", "volumen", "searches"))
    difficulty_field = _pick(fields, ("difficulty", "dificultad", "kd", "competition"))
    cpc_field = _pick(fields, ("cpc", "coste por clic"))

    keywords: list[Keyword] = []
    seen: set[str] = set()
    for raw in reader:
        if len(keywords) >= MAX_KEYWORDS:
            break
        term = (raw.get(term_field) or "").strip()
        if not term:
            continue
        key = " ".join(term.lower().split())
        if key in seen:
            continue
        seen.add(key)
        keywords.append(Keyword(
            term=term,
            volume=int(_number(raw.get(volume_field) if volume_field else None)),
            difficulty=int(_number(raw.get(difficulty_field) if difficulty_field else None)),
            cpc=_number(raw.get(cpc_field) if cpc_field else None),
        ))
    if not keywords:
        raise BadRequest("El CSV no contiene keywords.")

    graph = build_graph(keywords)
    validation = validate_graph(graph, monthly_cap=cap)
    plan = build_plan(graph, cap=cap)

    return {
        "summary": {
            "keywords": len(keywords), "clusters": len(graph.clusters),
            "pages": len(graph.pages), "merged": graph.merged,
            "covered": graph.keyword_count, "months": plan.horizon,
            "links": len(graph.internal_links()),
        },
        "intent_mix": plan.intent_mix(),
        "validation": {
            "passed": validation.passed,
            "findings": [
                {"code": f.code, "severity": f.severity, "message": f.message,
                 "blocking": f.blocking}
                for f in sorted(validation.findings, key=lambda f: not f.blocking)
            ],
        },
        "months": [
            {
                "month": month,
                "pages": [
                    {"term": item.page.primary.term, "role": item.page.role,
                     "cluster": item.page.cluster_id, "intent": item.page.intent,
                     "min_words": item.page.min_words,
                     "priority": round(item.page.priority),
                     "secondary": [k.term for k in item.page.secondary]}
                    for item in plan.month(month)
                ],
            }
            for month in sorted(plan.months)
        ],
    }


# -- memoria ---------------------------------------------------------------
#
# El almacen vive en un directorio por cliente, y el nombre del cliente llega
# del formulario. Eso convierte un campo de texto en un nombre de ruta, que es
# el agujero clasico: `../../.ssh` como nombre de cliente escribiria fuera. Se
# valida con lista blanca, no filtrando lo malo: filtrar lo malo deja siempre
# una codificacion que no se penso.
CLIENTE_VALIDO = re.compile(r"^[a-z0-9][a-z0-9._-]{0,62}$")
METRICA_VALIDA = re.compile(r"^[a-z0-9][a-z0-9_@.-]{0,62}$")
MAX_OBSERVACION = 1e12


def datos_root() -> Path:
    """Donde vive el almacen. Se puede mover con BANCO_DATOS."""
    return Path(os.environ.get("BANCO_DATOS", "datos")).resolve()


def normalize_client(raw: str) -> str:
    cliente = (raw or "").strip().lower()
    if not cliente:
        raise BadRequest("Falta el cliente.")
    if not CLIENTE_VALIDO.match(cliente):
        raise BadRequest(
            "El cliente solo puede llevar minusculas, numeros, punto, guion y "
            "guion bajo, y empezar por letra o numero."
        )
    if cliente in (".", "..") or cliente.startswith("."):
        raise BadRequest("Ese nombre de cliente no es valido.")
    return cliente


def _store(cliente: str):
    from store.project import ProjectStore
    raiz = datos_root()
    destino = (raiz / cliente).resolve()
    # Cinturon y tirantes: aunque la lista blanca ya lo impide, se comprueba
    # que la ruta final sigue dentro. Una defensa de frontera que depende de
    # una sola comprobacion es una defensa que se rompe al refactorizar.
    if raiz not in destino.parents and destino != raiz:
        raise BadRequest("Ruta de cliente fuera del almacen.")
    return ProjectStore(destino, client=cliente)


def _portfolio():
    from store.portfolio import PortfolioStore
    return PortfolioStore(datos_root())


def memory_state(cliente: str) -> dict:
    """Que sabe el sistema de este cliente, y que sigue siendo suposicion."""
    from store.project import MEDIDO as MEDIDO_

    almacen = _store(cliente)
    metricas = almacen.metrics()
    huella = almacen.fingerprint()
    log = almacen.rejection_log()
    return {
        "cliente": cliente,
        "resumen": almacen.describe(),
        "paginas": [
            {"slug": p.slug, "palabras": p.words, "rol": p.role,
             "url": p.url, "guardada": p.at,
             "fragmentos": p.sketch.size, "exacta": p.sketch.exact}
            for p in sorted(almacen.pages.values(), key=lambda x: x.slug)
        ],
        "huella": {"hashes": len(huella.hashes), "fragmentos": huella.size,
                   "estimada": not huella.exact},
        # La media se calcula SOLO sobre lo medido. El panel se titulaba «lo
        # que el sistema ha medido» y promediaba tambien lo declarado, que es
        # exactamente la mezcla que el resto del sistema evita. Se vio al
        # mirar la pagina renderizada, no en ningun test.
        "metricas": [
            {"nombre": n, "observaciones": c,
             "medidas": len(almacen.observations(n, source=MEDIDO_)),
             "declaradas": c - len(almacen.observations(n, source=MEDIDO_)),
             "media": (round(sum(almacen.observations(n, source=MEDIDO_))
                             / len(almacen.observations(n, source=MEDIDO_)), 4)
                       if almacen.observations(n, source=MEDIDO_) else None)}
            for n, c in metricas.items()
        ],
        "rechazos": {
            "total": len(log.rejections),
            "taxonomia": log.taxonomy(),
            "al_brief": log.brief_additions(),
            "tendencia": log.minutes_trend(),
        },
        "migraciones": almacen.migrations,
    }


def memory_check(cliente: str, text: str) -> dict:
    """Comprueba un borrador contra el sitio y contra la cartera.

    Se comprueba ANTES de publicar a proposito. Auditar la cartera despues
    encuentra el problema cuando ya esta indexado.
    """
    cuerpo = (text or "").strip()
    if not cuerpo:
        raise BadRequest("No hay texto que comprobar.")
    if len(cuerpo) > MAX_TEXT:
        raise BadRequest("El texto es demasiado largo.")

    almacen = _store(cliente)
    solape = almacen.overlap_of(cuerpo)
    riesgos = _portfolio().would_collide(cliente, cuerpo)
    return {
        "cliente": cliente,
        "sitio": {
            "medido": solape.measured,
            "comparadas": solape.compared,
            "valor": solape.value,
            "contra": solape.slug,
            "estimado": solape.estimated,
            "lectura": solape.describe(),
        },
        "cartera": [
            {"otro": c.site_b, "frases": c.phrase_similarity,
             "esqueleto": c.outline_similarity, "bloquea": c.blocking,
             "lectura": c.describe()}
            for c in riesgos[:5]
        ],
        "bloquea": any(c.blocking for c in riesgos),
    }


def memory_record(cliente: str, slug: str, text: str, url: str = "",
                  role: str = "") -> dict:
    """Guarda una pagina publicada. Devuelve el solape QUE TENIA antes."""
    cuerpo = (text or "").strip()
    if not cuerpo:
        raise BadRequest("No hay texto que guardar.")
    if len(cuerpo) > MAX_TEXT:
        raise BadRequest("El texto es demasiado largo.")
    limpio = (slug or "").strip().lower()
    if not CLIENTE_VALIDO.match(limpio):
        raise BadRequest("El slug solo puede llevar minusculas, numeros, "
                         "punto, guion y guion bajo.")

    almacen = _store(cliente)
    antes = almacen.overlap_of(cuerpo, skip=limpio)
    pagina = almacen.record_page(limpio, cuerpo, url=url.strip()[:300],
                                 role=role.strip()[:40])
    cartera = _portfolio()
    cartera.add_page(cliente, cuerpo)
    return {
        "guardada": {"slug": pagina.slug, "palabras": pagina.words,
                     "fragmentos": pagina.sketch.size},
        "solape_previo": {"valor": antes.value, "contra": antes.slug,
                          "medido": antes.measured, "lectura": antes.describe()},
        "paginas": len(almacen.pages),
        "cartera": cartera.describe(),
    }


def memory_observe(cliente: str, metrica: str, valor, fuente: str = "medido",
                   nota: str = "") -> dict:
    """Anade una observacion al historico. Es lo que apaga los priores."""
    from store.project import DECLARADO, MEDIDO

    nombre = (metrica or "").strip().lower()
    if not METRICA_VALIDA.match(nombre):
        raise BadRequest("Nombre de metrica no valido.")
    try:
        numero = float(valor)
    except (TypeError, ValueError):
        raise BadRequest("El valor de la observacion tiene que ser un numero.") from None
    if numero != numero or abs(numero) in (float("inf"),) or abs(numero) > MAX_OBSERVACION:
        raise BadRequest("Ese valor no es un numero utilizable.")
    origen = (fuente or MEDIDO).strip().lower()
    if origen not in (MEDIDO, DECLARADO):
        raise BadRequest(f"La fuente solo puede ser «{MEDIDO}» o «{DECLARADO}».")

    almacen = _store(cliente)
    obs = almacen.observe(nombre, numero, source=origen, note=nota.strip()[:400])
    vigentes = almacen.observations(nombre)
    medidas = almacen.observations(nombre, source=MEDIDO)
    return {
        "guardada": obs.to_dict(),
        "vigentes": len(vigentes),
        "medidas": len(medidas),
        "aviso": ("" if origen == MEDIDO else
                  "Marcada como declarada: NO alimenta los priores. Solo lo "
                  "medido puede apagar una suposicion."),
    }


# -- negocio ---------------------------------------------------------------
PLANES_POR_DEFECTO = (
    # No son una recomendacion: son el punto de partida para que el calculo
    # tenga algo que evaluar. Lo que vale del modulo es lo que pasa al
    # moverlos, no estos tres numeros.
    {"nombre": "Inicio", "precio_mes": 490, "paginas": 8, "minutos_revision": 14},
    {"nombre": "Crecimiento", "precio_mes": 1290, "paginas": 24,
     "minutos_revision": 12},
    {"nombre": "Cartera", "precio_mes": 2900, "paginas": 60,
     "minutos_revision": 9},
)

MAX_PLANES = 8


def _numero(data: dict, clave: str, defecto: float, minimo: float,
            maximo: float) -> float:
    crudo = data.get(clave, defecto)
    try:
        valor = float(crudo)
    except (TypeError, ValueError):
        raise BadRequest(f"«{clave}» tiene que ser un numero.") from None
    if valor != valor or valor in (float("inf"), float("-inf")):
        raise BadRequest(f"«{clave}» no es un numero utilizable.")
    if not (minimo <= valor <= maximo):
        raise BadRequest(f"«{clave}» tiene que estar entre {minimo} y {maximo}.")
    return valor


def tarifa(data: dict) -> dict:
    """Evalua la tarifa con los supuestos que llegan del formulario.

    Los supuestos SI vienen de fuera aqui, al reves que en el informe mensual,
    y es correcto: un coste por hora o un precio de plan son decisiones del
    negocio, no mediciones del sistema. Lo que no se admite de fuera es el
    resultado; eso lo calcula el modulo y marca que parte sigue supuesta.
    """
    from generator.llm import Usage
    from pricing.plans import Plan, tarifa as evaluar_tarifa

    # «Sin la clave» y «la clave con una lista vacia» no son lo mismo: lo
    # primero es no haber elegido y lo segundo es haber elegido ninguno.
    # Devolver los tres planes por defecto a quien pidio cero es contestar a
    # otra pregunta.
    if "planes" not in data:
        entrada = list(PLANES_POR_DEFECTO)
    else:
        entrada = data["planes"]
    if not isinstance(entrada, list):
        raise BadRequest("«planes» tiene que ser una lista.")
    if not entrada:
        raise BadRequest("Hace falta al menos un plan que evaluar.")
    if len(entrada) > MAX_PLANES:
        raise BadRequest(f"Como mucho {MAX_PLANES} planes.")

    planes = []
    for fila in entrada:
        if not isinstance(fila, dict):
            raise BadRequest("Cada plan tiene que ser un objeto.")
        nombre = str(fila.get("nombre", "")).strip()[:40]
        if not nombre:
            raise BadRequest("Cada plan necesita un nombre.")
        planes.append(Plan(
            nombre=nombre,
            precio_mes=_numero(fila, "precio_mes", 0, 0, 1_000_000),
            paginas=int(_numero(fila, "paginas", 1, 1, 1000)),
            minutos_revision=_numero(fila, "minutos_revision", 12, 0, 600),
        ))

    uso = Usage(
        input_tokens=int(_numero(data, "input_tokens", 4000, 0, 10_000_000)),
        output_tokens=int(_numero(data, "output_tokens", 6000, 0, 10_000_000)),
        cache_write_tokens=int(_numero(data, "cache_write_tokens", 3000, 0,
                                       10_000_000)),
        cache_read_tokens=int(_numero(data, "cache_read_tokens", 24000, 0,
                                      50_000_000)),
        calls=1,
    ) if data.get("usage_medido", True) else None

    kw = dict(
        usage=uso,
        modelo=str(data.get("modelo", "claude-opus-5-5"))[:60],
        lotes=bool(data.get("lotes", True)),
        coste_hora=_numero(data, "coste_hora", 45, 0, 1000),
        herramientas_mes=_numero(data, "herramientas_mes", 120, 0, 100_000),
        reparaciones=_numero(data, "reparaciones", 0.6, 0, 20),
        minutos_medidos=bool(data.get("minutos_medidos", False)),
    )
    from pricing.unit import TARIFAS

    if kw["modelo"] not in TARIFAS:
        raise BadRequest(
            f"No hay tarifa declarada para «{kw['modelo']}». Los modelos con "
            "precio declarado son: " + ", ".join(sorted(TARIFAS)) + "."
        )

    fijos = _numero(data, "fijos_mes", 4000, 0, 1_000_000)
    resultado = evaluar_tarifa(planes, fijos_mes=fijos, **kw)
    return {
        "medido": resultado.medido,
        "fragiles": resultado.planes_fragiles,
        "planes": [
            {"nombre": r.plan.nombre, "precio_mes": r.plan.precio_mes,
             "paginas": r.plan.paginas, "precio_pagina": r.precio_pagina,
             "coste_pagina": r.coste_pagina, "coste_mes": r.coste_mes,
             "margen_mes": r.margen_mes, "margen_pct": r.margen_pct,
             "reparto": r.reparto, "sano": r.sano}
            for r in resultado.resultados
        ],
        "sensibilidad": {
            nombre: [{"palanca": c.palanca, "desde": c.desde, "hasta": c.hasta,
                      "antes": c.margen_antes, "despues": c.margen_despues,
                      "caida": c.caida, "rompe": c.rompe}
                     for c in casos]
            for nombre, casos in resultado.sensibilidades.items()
        },
        "punto_muerto": resultado.puntos_muertos,
        "markdown": resultado.to_markdown(),
    }


def informe_mensual(cliente: str, data: dict) -> dict:
    """El informe del mes, ensamblado desde el almacen de ese cliente."""
    from calibration.priors import PESO_MEDIO, PriorSet
    from compliance.dossier import MonthRecord
    from report.monthly import build

    almacen = _store(cliente)
    periodo = str(data.get("periodo", "")).strip()[:10] or "sin periodo"

    record = MonthRecord(
        client=cliente, site=str(data.get("site", ""))[:200], period=periodo,
        pages_published=int(_numero(data, "pages_published",
                                    len(almacen.pages), 0, 10_000)),
        pages_blocked=int(_numero(data, "pages_blocked", 0, 0, 10_000)),
        publishable_as_is=int(_numero(data, "publishable_as_is", 0, 0, 10_000)),
        monthly_cap=int(_numero(data, "monthly_cap", 24, 1, 1000)),
        pages_with_own_data=int(_numero(data, "pages_with_own_data",
                                        len(almacen.pages), 0, 10_000)),
        pages_with_sources=int(_numero(data, "pages_with_sources",
                                       len(almacen.pages), 0, 10_000)),
        sources_cited=[str(s)[:300] for s in (data.get("sources_cited") or [])][:50],
        languages=[str(s)[:12] for s in (data.get("languages") or [])][:20],
        languages_human_reviewed=[
            str(s)[:12] for s in (data.get("languages_human_reviewed") or [])][:20],
        max_density=data.get("max_density"),
    )

    # Los priores declarados del sistema, alimentados con lo que el almacen
    # haya medido. Si no hay nada medido, el informe lo dira solo.
    priores = PriorSet(label="Curvas de clic y valor")
    priores.declare("ctr_posicion_1", 0.25, weight=PESO_MEDIO,
                    source="curva de CTR de mercado")
    priores.declare("valor_clic_comercial", 3.4, weight=PESO_MEDIO,
                    source="declarado en la propuesta")
    almacen.feed(priores)

    informe = build(almacen, record, portfolio=_portfolio(),
                    prior_sets=[priores])
    return {
        "cliente": cliente,
        "periodo": periodo,
        "titular": informe.headline(),
        "medido": informe.measured_share,
        "entregable": informe.deliverable,
        "secciones": [
            {"titulo": s.title,
             "cifras": [{"label": f.label, "valor": f.value,
                         "origen": f.provenance, "base": f.basis}
                        for f in s.figures],
             "lineas": s.lines}
            for s in informe.sections
        ],
        "incognitas": informe.unknowns,
        "alternativas": informe.would_change,
        "bloqueantes": informe.blockers,
        "markdown": informe.to_markdown(),
    }


# --- el estudio del canal ------------------------------------------------

MAX_PRESUPUESTO = 2000.0
MAX_VISTAS = 5_000_000.0


def estudio(presupuesto: float, vistas: float, hoy: str = "") -> dict:
    """El fallo del tribunal, el plan, la carrera y la pila de herramientas.

    No hay nada que decidir aqui: las cuatro cosas salen del paquete `estudio`
    y esta funcion solo valida lo que llega del formulario. El unico cuidado es
    con `vistas`, que es una hipotesis de quien la escribe y no una medicion —
    el veredicto lo dice con esas palabras.
    """
    presupuesto = _numero({"presupuesto": presupuesto}, "presupuesto", 0.0, 0.0,
                           MAX_PRESUPUESTO)
    vistas = _numero({"vistas": vistas}, "vistas", 0.0, 0.0, MAX_VISTAS)

    if hoy.strip():
        try:
            dia = date.fromisoformat(hoy.strip()[:10])
        except ValueError:
            raise BadRequest("La fecha tiene que ser AAAA-MM-DD.") from None
    else:
        dia = date.today()

    carrera = Carrera(hoy=dia)
    fallo = estudio_jueces.fallo()

    return {
        "hoy": dia.isoformat(),
        "agentes": [a.to_dict() for a in PLANTILLA],
        "fallo": fallo.to_dict(),
        "tabla": estudio_jueces.tabla(),
        "jueces": [
            {"clave": j.clave, "nombre": j.nombre, "oficio": j.oficio,
             "mira": j.mira, "veto": j.veto_por_debajo_de,
             "criterios": [{"clave": c.clave, "pregunta": c.pregunta,
                            "peso": c.peso, "enmienda": c.enmienda}
                           for c in j.criterios]}
            for j in estudio_jueces.JUECES
        ],
        "plan": {
            "resumen": estudio_plan.describe(),
            "horas_semana": estudio_plan.horas_semana(),
            "minutos_semana": estudio_plan.minutos_semana(),
            "carga": estudio_plan.carga_por_agente(),
            "dias": [d.to_dict() for d in estudio_plan.SEMANA],
            "cadencia": [v.to_dict() for v in estudio_plan.veredicto_cadencia()],
        },
        "calendario": [e.to_dict() for e in estudio_plan.calendario(dia, semanas=4)],
        "carrera": carrera.to_dict(vistas_por_largo=vistas),
        "rutas": comparar_rutas(carrera),
        "herramientas": estudio_herramientas.pila(presupuesto),
        "riesgos": estudio_herramientas.riesgos(),
    }


def estudio_pelicula(dia: int, paso: int) -> dict:
    """La jornada entera de un dia. Una peticion por dia, no una por fotograma."""
    dia = int(_numero({"dia": dia}, "dia", 1, 1, len(estudio_plan.SEMANA)))
    paso = int(_numero({"paso": paso}, "paso", 5, 1, 60))
    return Sala.del_dia(dia).pelicula(paso)
