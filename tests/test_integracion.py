"""De keywords a dossier, sin red y sin clave.

Esta prueba es la que dice si el sistema existe como sistema o solo como cinco
paquetes que compilan por separado.
"""

import unittest

from clusters.graph import build as build_graph
from clusters.keywords import Keyword
from clusters.plan import build as build_plan
from clusters.validate import validate
from compliance.dossier import MonthRecord, unresolved
from compliance.fingerprint import SitePrint, audit
from generator.brief import Brief, OwnData, Source
from generator.gates import GateResult
from generator.llm import ScriptedLLM
from generator.pipeline import produce_many
from publisher.links import inject, targets_for
from publisher.schema import Publisher, SchemaContext
from publisher.wordpress import AppPassword, WordPress
from review.log import RejectionLog
from review.triage import build_queue

FUENTE = "https://www.epa.gov/septic"
SITIO = "https://ejemplo.test"

KEYWORDS = [
    ("cuanto cuesta un sistema septico aerobico", 2000, 14.0),
    ("precio sistema septico aerobico", 1500, 13.0),
    ("instalador septico cerca de mi", 1100, 18.0),
    ("mejor bomba de aire septica", 700, 9.0),
]


# Cuerpos de prueba que no se parecen entre si.
#
# Hizo falta variar tambien la ESTRUCTURA de la frase, no solo el vocabulario:
# con un unico andamio ("conviene revisar el X antes de decidir sobre Y") los
# shingles caen sobre el andamio compartido y la compuerta de solape bloquea con
# razon. Que costara tres intentos acertar el fixture es la mejor prueba de que
# la compuerta sirve.
PLANTILLAS = (
    (
        ("tanque", "dormitorio", "vivienda", "capacidad", "litro", "familia"),
        "El {a} de la casa condiciona el {b}, y eso cambia la {c} que hay que "
        "contratar desde el primer dia.",
    ),
    (
        ("condado", "permiso", "inspector", "distancia", "pozo", "normativa"),
        "Sin {a} tramitado no hay {b} valido: el {c} lo comprueba en la visita "
        "y levanta acta en el momento.",
    ),
    (
        ("difusor", "caudal", "compresor", "burbuja", "membrana", "oxigeno"),
        "Un {a} sucio reduce el {b} disponible, con lo que el {c} trabaja mas "
        "horas para el mismo resultado.",
    ),
    (
        ("garantia", "fabricante", "recambio", "averia", "taller", "factura"),
        "Guarda la {a} junto al albaran del {b}: sin ese papel ningun {c} "
        "cubre la pieza aunque este en plazo.",
    ),
)


def cuerpo(brief, indice: int, minimo: int = 1300) -> str:
    """Un cuerpo que cumple el brief y no se parece a sus hermanos.

    Cumplir el brief incluye contestar sus preguntas y nombrar las keywords
    secundarias: si no, las compuertas avisan, y con razon.
    """
    titulo = brief.primary_term
    dato = brief.own_data[0].value
    palabras, plantilla = PLANTILLAS[indice % len(PLANTILLAS)]
    frases: list[str] = []
    contador = 0
    numero = 0
    while contador < minimo:
        numero += 1
        frase = plantilla.format(
            a=palabras[numero % len(palabras)],
            b=palabras[(numero * 3 + 1) % len(palabras)],
            c=palabras[(numero * 5 + 2) % len(palabras)],
        )
        frases.append(f"{frase} Caso {numero}.")
        contador += len(frase.split()) + 2
    secciones = [
        f"# {titulo}",
        "",
        f"## {palabras[0].capitalize()} y lo que de verdad importa",
        "",
        f"Nuestra medicion propia da {dato} para el {palabras[1]}, sobre una "
        f"muestra de 2026. El marco oficial esta en "
        f"[la guia de la EPA]({FUENTE}).",
        "",
    ]
    # Contestar cada pregunta del brief, con sus propios terminos.
    for pregunta in brief.questions:
        secciones += [
            f"## {pregunta}",
            "",
            f"Respuesta directa: {dato} segun nuestra muestra, y el {palabras[2]} "
            f"es el factor que mas lo mueve. La referencia oficial sigue siendo "
            f"[la guia de la EPA]({FUENTE}).",
            "",
        ]
    # Nombrar las secundarias: el brief las pide cubiertas.
    for keyword in brief.page.secondary:
        secciones += [
            f"Sobre {keyword.term}, la respuesta es la misma cifra con otro "
            f"nombre: {dato}, contrastada con "
            f"[la guia de la EPA]({FUENTE}).",
            "",
        ]
    secciones.append(" ".join(frases))
    return "\n".join(secciones)


class TestDePuntaAPunta(unittest.TestCase):
    def setUp(self):
        # --- M2: keywords -> grafo -> validacion -> plan -----------------
        self.keywords = [Keyword(t, volume=v, cpc=c) for t, v, c in KEYWORDS]
        self.graph = build_graph(self.keywords)
        self.validation = validate(self.graph)
        self.plan = build_plan(self.graph, cap=24)

        # --- M4: un brief completo por pagina ---------------------------
        self.briefs = []
        for index, page in enumerate(self.graph.pages):
            self.briefs.append(
                Brief(
                    page=page,
                    what_it_adds=f"Dato propio {index} que no esta en el top 10.",
                    questions=["Que necesita saber el propietario?"],
                    required_sources=[
                        Source(url=FUENTE, title="EPA", consulted_at="2026-10-03")
                    ],
                    own_data=[
                        OwnData(label=f"Medicion {index}", value=f"{index}.400 $",
                                method="muestra propia 2026")
                    ],
                    brand_voice="Directo, cifras antes que adjetivos",
                )
            )

        # Enrutado por termino primario, no por orden: una reparacion en
        # cualquier pagina desalinearia un guion por orden global.
        rutas = {
            b.primary_term: cuerpo(b, i, minimo=b.min_words + 200)
            for i, b in enumerate(self.briefs)
        }
        self.llm = ScriptedLLM(routes=rutas)
        self.productions, self.stats = produce_many(self.briefs, self.llm)

    # -- M2 ---------------------------------------------------------------
    def test_el_plan_pasa_la_validacion_de_solape_cero(self):
        self.assertTrue(self.validation.passed)
        self.assertEqual(self.plan.total, len(self.graph.pages))

    # -- M4 ---------------------------------------------------------------
    def test_todas_las_paginas_pasan_las_compuertas(self):
        self.assertEqual(self.stats.passed, len(self.briefs))
        self.assertEqual(self.stats.aborted, 0)

    def test_ninguna_pagina_se_canibaliza_con_otra_del_lote(self):
        for production in self.productions:
            codes = [f.code for f in production.result.findings]
            self.assertNotIn("solape_con_publicado", codes)

    # -- M5 ---------------------------------------------------------------
    def test_se_publica_en_borrador_con_json_ld_y_enlazado(self):
        enviados: list[dict] = []

        def transport(method, url, headers, body):
            import json
            payload = json.loads(body) if body else {}
            if method == "GET":
                return 200, []
            enviados.append(payload)
            return 201, {"id": len(enviados), "status": payload["status"]}

        wp = WordPress(SITIO, AppPassword("u", "p"), transport)
        context = SchemaContext(site_url=SITIO, author_name="Alex",
                                publisher=Publisher(name="Ejemplo"))

        for production in self.productions:
            draft = production.draft
            destinos = targets_for(self.graph, draft.slug, SITIO)
            draft.body, _ = inject(draft.body, destinos)
            outcome = wp.publish(draft, production.result, context,
                                 intent=production.brief.page.intent)
            self.assertTrue(outcome.ok, outcome.refused_reason)
            self.assertEqual(outcome.status, "draft")

        self.assertEqual(len(enviados), len(self.productions))
        for payload in enviados:
            self.assertIn("application/ld+json", payload["content"])

    def test_el_publicador_frena_lo_que_no_paso(self):
        def transport(method, url, headers, body):
            raise AssertionError("no deberia llegar a la red")

        wp = WordPress(SITIO, AppPassword("u", "p"), transport)
        context = SchemaContext(site_url=SITIO, author_name="Alex",
                                publisher=Publisher(name="Ejemplo"))
        from generator.gates import SEVERITY_BLOCK
        fallo = GateResult()
        fallo.add("afirmacion_sin_respaldo", SEVERITY_BLOCK, "cifra sin fuente")
        outcome = wp.publish(self.productions[0].draft, fallo, context)
        self.assertFalse(outcome.ok)

    # -- M8 ---------------------------------------------------------------
    def test_el_triaje_reparte_los_minutos_del_revisor(self):
        log = RejectionLog(client="Cliente A")
        queue = build_queue(self.productions, log)
        self.assertEqual(len(queue.assignments), len(self.productions))
        # Un lote limpio no debe consumir 25 minutos por pagina.
        self.assertLess(queue.total_minutes, 25 * len(self.productions))

    def test_lo_que_aprende_el_revisor_vuelve_al_brief(self):
        log = RejectionLog(client="Cliente A")
        for slug in ("a", "b"):
            log.add(slug, "afirmacion_sin_respaldo", "cifra sin fuente",
                    "Toda cifra de coste cita el presupuesto exacto.")
        self.assertEqual(len(log.brief_additions()), 1)

    # -- M9 ---------------------------------------------------------------
    def test_el_dossier_del_mes_se_puede_firmar(self):
        publicadas = len([p for p in self.productions if p.passed])
        huella = SitePrint(site="ejemplo.test")
        for production in self.productions:
            huella.add_page(production.draft.body)
        otra = SitePrint(site="otro-cliente.test")
        otra.add_page("## Normativa de Oklahoma\n\nTexto propio sin relacion alguna.")

        record = MonthRecord(
            client="Cliente A", site="ejemplo.test", period="2026-10",
            pages_published=publicadas,
            pages_blocked=len(self.productions) - publicadas,
            publishable_as_is=self.stats.publishable_as_is,
            repairs=self.stats.repairs,
            review_minutes=build_queue(self.productions).total_minutes,
            pages_with_own_data=publicadas,
            pages_with_sources=publicadas,
            sources_cited=[FUENTE],
            languages=["es"], languages_human_reviewed=["es"],
            max_internal_overlap=0.10, max_density=0.010,
            portfolio=audit([huella, otra]),
        )
        self.assertEqual(unresolved(record), [])
        self.assertGreater(record.publishable_rate, 0)

    def test_la_huella_de_cartera_detecta_la_plantilla_compartida(self):
        # Si dos clientes reciben el mismo cuerpo, la cartera es una granja en
        # agregado aunque cada sitio parezca limpio.
        a = SitePrint(site="a.test")
        b = SitePrint(site="b.test")
        mismo = self.productions[0].draft.body
        a.add_page(mismo)
        b.add_page(mismo)
        self.assertFalse(audit([a, b]).passed)

    # -- coste ------------------------------------------------------------
    def test_una_llamada_al_modelo_por_pagina_cuando_sale_limpia(self):
        self.assertEqual(len(self.llm.calls), len(self.briefs))
        self.assertEqual(self.stats.repairs, 0)


if __name__ == "__main__":
    unittest.main()
