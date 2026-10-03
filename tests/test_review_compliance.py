import tempfile
import unittest
from pathlib import Path

from clusters.graph import build as build_graph
from clusters.keywords import Keyword
from compliance.dossier import MonthRecord, to_markdown, unresolved
from compliance.fingerprint import SitePrint, audit, outline, shingles
from generator.brief import Brief
from generator.gates import Draft, GateResult, SEVERITY_BLOCK, SEVERITY_WARN
from generator.pipeline import Attempt, Production
from review.log import RejectionLog
from review.triage import LEVEL_AUTO, LEVEL_FULL, LEVEL_SPOT, assign, build_queue

PAGE = build_graph([Keyword("tema de prueba largo", volume=10)]).pages[0]


def production(slug: str, findings: list[tuple[str, str]], repairs: int = 0,
               aborted: str = "") -> Production:
    prod = Production(brief=Brief(page=PAGE), aborted_reason=aborted)
    if aborted:
        return prod
    result = GateResult()
    for code, severity in findings:
        result.add(code, severity, f"mensaje de {code}")
    for index in range(repairs + 1):
        prod.attempts.append(
            Attempt(number=index + 1,
                    draft=Draft(slug=slug, title="t", body="cuerpo"),
                    result=result)
        )
    return prod


class TestTriaje(unittest.TestCase):
    def test_limpio_a_la_primera_no_consume_revisor(self):
        a = assign(production("limpio", []))
        self.assertEqual(a.level, LEVEL_AUTO)
        self.assertEqual(a.minutes, 0)

    def test_bloqueado_va_a_revision_completa(self):
        a = assign(production("x", [("longitud_insuficiente", SEVERITY_BLOCK)]))
        self.assertEqual(a.level, LEVEL_FULL)

    def test_lo_que_toca_veracidad_siempre_lleva_ojo_humano(self):
        a = assign(production("x", [("afirmacion_sin_respaldo", SEVERITY_WARN)]))
        self.assertEqual(a.level, LEVEL_FULL)

    def test_un_aviso_inocuo_solo_lleva_muestreo(self):
        a = assign(production("x", [("solape_no_comprobado", SEVERITY_WARN)]))
        self.assertEqual(a.level, LEVEL_SPOT)

    def test_una_reparacion_baja_la_confianza(self):
        a = assign(production("x", [], repairs=1))
        self.assertEqual(a.level, LEVEL_SPOT)

    def test_brief_incompleto_lo_arregla_una_persona(self):
        a = assign(production("x", [], aborted="Brief incompleto: falta dato propio"))
        self.assertEqual(a.level, LEVEL_FULL)

    def test_el_historial_sube_el_nivel(self):
        log = RejectionLog()
        log.add("a", "secundaria_ausente", "falto", "instruccion")
        log.add("b", "secundaria_ausente", "otra vez", "instruccion")
        sin = assign(production("x", [("secundaria_ausente", SEVERITY_WARN)]))
        con = assign(production("x", [("secundaria_ausente", SEVERITY_WARN)]), log)
        self.assertEqual(sin.level, LEVEL_SPOT)
        self.assertEqual(con.level, LEVEL_FULL)

    def test_la_cola_pone_lo_arriesgado_primero(self):
        queue = build_queue([
            production("limpio", []),
            production("bloqueado", [("longitud_insuficiente", SEVERITY_BLOCK)]),
            production("aviso", [("solape_no_comprobado", SEVERITY_WARN)]),
        ])
        self.assertEqual([a.level for a in queue.assignments],
                         [LEVEL_FULL, LEVEL_SPOT, LEVEL_AUTO])

    def test_el_coste_del_lote_es_calculable(self):
        queue = build_queue([production("x", [("longitud_insuficiente", SEVERITY_BLOCK)])])
        self.assertEqual(queue.total_minutes, 25)
        self.assertAlmostEqual(queue.cost(hourly_rate=24.0), 10.0, places=2)


class TestRegistro(unittest.TestCase):
    def setUp(self):
        self.log = RejectionLog(client="demo")
        self.log.add("a", "afirmacion_sin_respaldo", "cifra sin fuente",
                     "Toda cifra de coste cita su presupuesto.")
        self.log.add("b", "afirmacion_sin_respaldo", "otra vez",
                     "Toda cifra de coste cita su presupuesto.")
        self.log.add("c", "secundaria_ausente", "falto", "Mencionarla antes del tercio.")

    def test_la_taxonomia_ordena_por_frecuencia(self):
        self.assertEqual(list(self.log.taxonomy())[0], "afirmacion_sin_respaldo")

    def test_solo_lo_recurrente_llega_al_brief(self):
        additions = self.log.brief_additions()
        self.assertEqual(len(additions), 1)
        self.assertIn("presupuesto", additions[0])

    def test_no_repite_la_misma_instruccion(self):
        self.log.add("d", "afirmacion_sin_respaldo", "y otra",
                     "Toda cifra de coste cita su presupuesto.")
        self.assertEqual(len(self.log.brief_additions()), 1)

    def test_un_rechazo_sin_instruccion_no_ensena_nada(self):
        log = RejectionLog()
        log.add("a", "codigo", "motivo")
        log.add("b", "codigo", "motivo")
        self.assertEqual(log.brief_additions(), [])

    def test_la_tendencia_admite_no_tener_datos(self):
        self.assertIn("Aun no hay datos", self.log.minutes_trend())

    def test_la_tendencia_avisa_si_empeora(self):
        log = RejectionLog()
        for i in range(10):
            log.add(f"p{i}", "siempre_el_mismo", "x")
        for i in range(10):
            log.add(f"q{i}", f"distinto_{i}", "x")
        self.assertIn("SUBIENDO", log.minutes_trend())

    def test_ida_y_vuelta_a_disco(self):
        path = Path(tempfile.mkdtemp()) / "log.json"
        self.log.save(path)
        recargado = RejectionLog.load(path)
        self.assertEqual(recargado.client, "demo")
        self.assertEqual(recargado.taxonomy(), self.log.taxonomy())

    def test_cargar_un_fichero_que_no_existe_da_registro_vacio(self):
        self.assertEqual(RejectionLog.load("/tmp/no-existe-jamas.json").rejections, [])


class TestHuellaDeCartera(unittest.TestCase):
    PLANTILLA = ("## Que es y como funciona\n\nEste sistema funciona mediante un "
                 "proceso de tres fases que conviene conocer.\n\n## Cuanto cuesta\n\n"
                 "El precio depende de varios factores que detallamos aqui.\n")

    def test_la_misma_plantilla_en_dos_sitios_bloquea(self):
        a = SitePrint(site="a.com"); a.add_page(self.PLANTILLA)
        b = SitePrint(site="b.com"); b.add_page(self.PLANTILLA.replace("sistema", "equipo"))
        result = audit([a, b])
        self.assertFalse(result.passed)
        self.assertIn("granja de contenido", result.describe())

    def test_sitios_de_verdad_distintos_pasan(self):
        a = SitePrint(site="a.com")
        a.add_page("## Requisitos en Texas\n\nLa norma exige inspeccion anual del tanque.")
        b = SitePrint(site="b.com")
        b.add_page("## Precio de la bomba\n\nEl caudal manda sobre el coste final.")
        self.assertTrue(audit([a, b]).passed)

    def test_un_solo_sitio_no_tiene_huella_cruzada(self):
        a = SitePrint(site="a.com"); a.add_page(self.PLANTILLA)
        result = audit([a])
        self.assertTrue(result.passed)
        self.assertIn("no hay huella cruzada", result.describe())

    def test_el_esqueleto_delata_aunque_cambien_las_palabras(self):
        a = SitePrint(site="a.com"); a.add_page(self.PLANTILLA)
        b = SitePrint(site="b.com")
        b.add_page("## Que es y como funciona\n\nTexto completamente diferente sin "
                   "ninguna palabra compartida.\n\n## Cuanto cuesta\n\nOtro parrafo "
                   "distinto por completo de aquel.\n")
        colision = audit([a, b]).collisions[0]
        self.assertEqual(colision.outline_similarity, 1.0)
        self.assertTrue(colision.blocking)

    def test_outline_normaliza(self):
        self.assertEqual(outline("## ¿Cuánto Cuesta?\n"), ["cuánto cuesta"])

    def test_shingles_de_texto_corto_no_revienta(self):
        self.assertEqual(shingles("dos palabras"), {"dos palabras"})
        self.assertEqual(shingles(""), set())


class TestDossier(unittest.TestCase):
    def _record(self, **extra) -> MonthRecord:
        base = dict(
            client="Cliente A", site="a.com", period="2026-10",
            pages_published=12, pages_blocked=2, publishable_as_is=9,
            pages_with_own_data=12, pages_with_sources=12,
            sources_cited=["https://www.epa.gov/septic"],
            languages=["es"], languages_human_reviewed=["es"],
            max_internal_overlap=0.12, max_density=0.011,
        )
        base.update(extra)
        return MonthRecord(**base)

    def test_un_mes_limpio_se_puede_firmar(self):
        self.assertEqual(unresolved(self._record()), [])

    def test_superar_el_tope_incumple_el_patron_a(self):
        record = self._record(pages_published=30, monthly_cap=24,
                              pages_with_own_data=30, pages_with_sources=30)
        problemas = unresolved(record)
        self.assertTrue(any("Patron A" in p for p in problemas))

    def test_un_idioma_sin_revision_nativa_incumple_el_patron_b(self):
        record = self._record(languages=["es", "en"], languages_human_reviewed=["es"])
        self.assertTrue(any("Patron B" in p for p in unresolved(record)))

    def test_lo_no_medido_no_se_declara_como_cumple(self):
        markdown = to_markdown(self._record(max_internal_overlap=None))
        self.assertIn("_no medido_", markdown)
        self.assertIn("no se comprobo", markdown)

    def test_no_medido_no_bloquea_la_firma(self):
        # No medir no es incumplir: es no saberlo, y el documento lo dice.
        self.assertEqual(unresolved(self._record(max_density=None)), [])

    def test_alojar_contenido_de_terceros_impide_firmar(self):
        record = self._record(hosts_third_party_content=True)
        self.assertTrue(any("terceros" in p for p in unresolved(record)))

    def test_el_intercambio_de_enlaces_impide_firmar(self):
        record = self._record(reciprocal_link_exchange=True)
        self.assertTrue(any("reciproco" in p for p in unresolved(record)))

    def test_el_porcentaje_se_compara_con_la_linea_base(self):
        markdown = to_markdown(self._record())
        self.assertIn("52,4%", markdown)
        self.assertIn("64.3%", markdown)

    def test_sin_paginas_el_patron_a_no_se_evalua(self):
        record = self._record(pages_published=0, pages_blocked=0,
                              publishable_as_is=0, pages_with_own_data=0,
                              pages_with_sources=0)
        self.assertEqual(unresolved(record), [])
        self.assertIn("no se publico nada", to_markdown(record))

    def test_el_dossier_nombra_las_dos_politicas(self):
        markdown = to_markdown(self._record())
        self.assertIn("28 de agosto de 2026", markdown)
        self.assertIn("site reputation", markdown)


if __name__ == "__main__":
    unittest.main()
