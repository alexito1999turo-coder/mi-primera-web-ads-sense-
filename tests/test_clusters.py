import unittest

from clusters.graph import ROLE_PILLAR, build, generic_tokens, jaccard
from clusters.keywords import Keyword
from clusters.plan import build as build_plan
from clusters.validate import (
    SEVERITY_BLOCK,
    SEVERITY_WARN,
    validate,
)

NICHO = [
    ("sistema septico aerobico", 5000, 6.0),
    ("cuanto cuesta un sistema septico aerobico", 2000, 14.0),
    ("precio sistema septico aerobico", 1500, 13.0),
    ("alarma septica pitando", 900, 3.0),
    ("alarma septica no para de pitar", 400, 3.0),
    ("mejor bomba de aire septica", 700, 9.0),
    ("bomba de aire septica opiniones", 300, 8.0),
    ("que es nitrificacion", 12000, 0.5),
    ("instalador septico cerca de mi", 1100, 18.0),
    ("mantenimiento septico aerobico", 800, 7.0),
]


def nicho() -> list[Keyword]:
    return [Keyword(t, volume=v, cpc=c) for t, v, c in NICHO]


class TestGrafo(unittest.TestCase):
    def setUp(self):
        self.keywords = nicho()
        self.graph = build(self.keywords)

    def test_ninguna_keyword_se_pierde(self):
        self.assertEqual(self.graph.keyword_count, len(self.keywords))

    def test_solape_cero_por_construccion(self):
        primarias = [page.primary.term for page in self.graph.pages]
        self.assertEqual(len(primarias), len(set(primarias)))

    def test_fusiona_sinonimos_de_precio_en_una_pagina(self):
        terminos = [p.all_terms for p in self.graph.pages]
        juntas = [
            t for t in terminos
            if any("cuanto cuesta" in x for x in t) and any("precio" in x for x in t)
        ]
        self.assertTrue(juntas, "precio y cuanto cuesta deben ser la misma pagina")

    def test_el_token_del_nicho_no_agrupa_todo(self):
        genericos = generic_tokens(self.keywords)
        self.assertIn("septico", genericos)
        # Las alarmas no deben caer en el cluster de bombas.
        alarmas = self.graph.cluster_of("alarma-septica-pitando")
        self.assertIsNotNone(alarmas)
        terminos = " ".join(t for p in alarmas.pages for t in p.all_terms)
        self.assertNotIn("bomba", terminos)

    def test_cada_cluster_tiene_un_pilar(self):
        for cluster in self.graph.clusters:
            self.assertEqual(cluster.pillar.role, ROLE_PILLAR)
            self.assertEqual(
                sum(1 for p in cluster.pages if p.role == ROLE_PILLAR), 1
            )

    def test_el_pilar_pide_mas_palabras_que_el_satelite(self):
        cluster = next(c for c in self.graph.clusters if c.satellites)
        self.assertGreater(cluster.pillar.min_words, cluster.satellites[0].min_words)

    def test_enlazado_es_bidireccional(self):
        enlaces = set(self.graph.internal_links())
        for origen, destino in list(enlaces):
            self.assertIn((destino, origen), enlaces)

    def test_grafo_vacio_no_rompe(self):
        self.assertEqual(build([]).clusters, [])

    def test_una_sola_keyword_da_un_pilar(self):
        graph = build([Keyword("bomba septica", volume=100)])
        self.assertEqual(len(graph.pages), 1)
        self.assertEqual(graph.pages[0].role, ROLE_PILLAR)

    def test_el_solape_de_serp_manda_sobre_los_tokens(self):
        a = Keyword("tema uno distinto", volume=100)
        b = Keyword("asunto dos diferente", volume=90)
        sin_serp = build([a, b])
        self.assertEqual(len(sin_serp.clusters), 2)
        con_serp = build([a, b], serp_overlap={(a.term, b.term): 0.8})
        self.assertEqual(len(con_serp.clusters), 1)

    def test_jaccard(self):
        self.assertEqual(jaccard({"a", "b"}, {"a", "b"}), 1.0)
        self.assertEqual(jaccard({"a"}, {"b"}), 0.0)
        self.assertEqual(jaccard(set(), {"a"}), 0.0)


class TestValidacion(unittest.TestCase):
    def test_el_nicho_real_pasa(self):
        self.assertTrue(validate(build(nicho())).passed)

    def test_detecta_primaria_duplicada(self):
        graph = build(nicho())
        # Duplicar a mano una primaria: es lo que nunca debe salir del grafo.
        graph.clusters[0].satellites.append(graph.clusters[0].pillar)
        result = validate(graph)
        self.assertFalse(result.passed)
        self.assertTrue(any(f.code == "primaria_duplicada" for f in result.blocking))

    def test_misma_intencion_y_texto_parecido_bloquea(self):
        # Similitud 0.75 y las dos comerciales. Con el umbral de fusion subido
        # salen como dos paginas, y entonces el validador debe bloquearlas.
        keywords = [
            Keyword("mejor bomba de aire septica", volume=900, cpc=9),
            Keyword("mejor bomba de aire", volume=800, cpc=9),
        ]
        graph = build(keywords, merge_threshold=0.99)
        self.assertEqual(len(graph.pages), 2, "el caso de prueba exige dos paginas")
        result = validate(graph)
        self.assertFalse(result.passed)
        self.assertTrue(any(f.code == "primarias_en_conflicto" for f in result.blocking))

    def test_sinonimos_identicos_se_fusionan_pese_al_umbral(self):
        # "de aire" y "del aire" normalizan igual: son la misma pagina y el
        # umbral no deberia poder separarlas.
        graph = build([
            Keyword("mejor bomba de aire", volume=900, cpc=9),
            Keyword("mejor bomba del aire", volume=800, cpc=9),
        ], merge_threshold=0.99)
        self.assertEqual(len(graph.pages), 1)

    def test_intencion_distinta_solo_avisa(self):
        # La regla del validador es la misma que usa el constructor al fusionar:
        # el sistema no se contradice consigo mismo.
        result = validate(build(nicho()))
        codigos = [f.code for f in result.findings]
        self.assertIn("primarias_parecidas_intencion_distinta", codigos)
        self.assertTrue(result.passed)

    def test_avisa_si_el_plan_es_mayoritariamente_informacional(self):
        keywords = [
            Keyword("que es a", volume=100), Keyword("que es b", volume=100),
            Keyword("como hacer c", volume=100), Keyword("guia de d", volume=100),
        ]
        result = validate(build(keywords))
        self.assertTrue(any(f.code == "mezcla_informacional" for f in result.findings))

    def test_avisa_al_superar_el_tope(self):
        # Temas realmente distintos: un numero no sirve como tema porque los
        # tokens de una sola cifra se descartan.
        temas = [
            "aireacion", "clarificador", "desinfeccion", "efluente", "filtro",
            "lodos", "membrana", "nitrato", "ozono", "percolacion", "quimico",
            "residual", "sedimento", "tanque", "ultravioleta", "valvula",
            "aspersor", "bomba", "cloro", "decantador", "electrodo", "fosa",
            "gravedad", "humedal", "inyector", "lecho",
        ]
        keywords = [Keyword(f"{t} industrial grande", volume=100) for t in temas]
        graph = build(keywords)
        self.assertGreater(len(graph.pages), 24)
        result = validate(graph, monthly_cap=24)
        self.assertTrue(any(f.code == "tope_superado" for f in result.findings))

    def test_entrada_degenerada_no_rompe(self):
        # Si todas las keywords comparten todos sus tokens no hay temas que
        # separar: colapsan en una pagina en vez de petar.
        keywords = [Keyword(f"tema numero {i} distinto", volume=100) for i in range(30)]
        graph = build(keywords)
        self.assertEqual(len(graph.pages), 1)
        self.assertEqual(graph.keyword_count, 30)

    def test_grafo_vacio_es_bloqueante(self):
        self.assertFalse(validate(build([])).passed)


class TestPlan(unittest.TestCase):
    def test_respeta_el_tope_mensual(self):
        plan = build_plan(build(nicho()), cap=4)
        for month in plan.months:
            self.assertLessEqual(len(plan.month(month)), 4)

    def test_no_pierde_paginas(self):
        graph = build(nicho())
        self.assertEqual(build_plan(graph, cap=3).total, len(graph.pages))

    def test_el_pilar_va_antes_que_sus_satelites(self):
        graph = build(nicho())
        plan = build_plan(graph, cap=100)
        orden = [item.slug for item in plan.month(1)]
        for cluster in graph.clusters:
            for satellite in cluster.satellites:
                self.assertLess(
                    orden.index(cluster.pillar.slug),
                    orden.index(satellite.slug),
                    "un enlace a una pagina que no existe no vale nada",
                )

    def test_mezcla_de_intencion_suma_cien(self):
        plan = build_plan(build(nicho()))
        self.assertAlmostEqual(sum(plan.intent_mix().values()), 100.0, places=1)

    def test_el_mes_uno_lleva_lo_mas_prioritario(self):
        graph = build(nicho())
        plan = build_plan(graph, cap=3)
        primero = plan.month(1)[0].page
        self.assertEqual(primero.cluster_id, graph.clusters[0].id)


if __name__ == "__main__":
    unittest.main()
