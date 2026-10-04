"""Auditoria completa de punta a punta, sin red."""

import tempfile
import unittest
from pathlib import Path

from auditor.audit import run
from auditor.report import to_json, to_markdown
from auditor.rules import ACTION_DISABLE, ACTION_NOINDEX, ACTION_RECATEGORIZE
from tests.fakes import (
    AUTHOR_URL,
    CAT_ALARMAS,
    CAT_FLORIDA,
    CAT_HUB,
    ROBOTS_SIN_SITEMAP,
    SITE,
    FakeClient,
    routes,
)


class TestAuditoriaCompleta(unittest.TestCase):
    def setUp(self):
        self.client = FakeClient(routes())
        self.audit = run(SITE, client=self.client)

    def _por_url(self, url):
        return next(a for a in self.audit.archives if a.url == url)

    def test_descubre_los_cuatro_archivos(self):
        self.assertEqual(len(self.audit.archives), 4)

    def test_el_hub_queda_intacto(self):
        hub = self._por_url(CAT_HUB)
        self.assertEqual(hub.verdict, "hub")
        self.assertNotIn(hub, self.audit.actionable)

    def test_el_autor_se_desactiva(self):
        self.assertEqual(self._por_url(AUTHOR_URL).action, ACTION_DISABLE)

    def test_categoria_con_candidatos_se_recategoriza(self):
        alarmas = self._por_url(CAT_ALARMAS)
        self.assertEqual(alarmas.action, ACTION_RECATEGORIZE)
        # 'alarma' aparece en dos articulos mas que no estan listados ahi.
        self.assertTrue(any("aspersor-atascado-alarma" in c
                            for c in alarmas.recategorization_candidates))

    def test_categoria_sin_salida_va_a_noindex(self):
        self.assertEqual(self._por_url(CAT_FLORIDA).action, ACTION_NOINDEX)

    def test_prioriza_recategorizar_y_desactivar_antes_que_noindex(self):
        acciones = [a.action for a in self.audit.actionable]
        self.assertEqual(acciones[-1], ACTION_NOINDEX)

    def test_avisa_de_los_sitemaps_de_archivo(self):
        texto = " ".join(self.audit.warnings)
        self.assertIn("sitemap de author", texto)
        self.assertIn("sitemap de category", texto)

    def test_mide_la_distribucion_de_intencion(self):
        dist = self.audit.intent_distribution
        self.assertIn("informational", dist)
        self.assertIn("commercial", dist)
        self.assertAlmostEqual(sum(dist.values()), 100.0, places=1)
        self.assertTrue(self.audit.intent_at_risk_urls)

    def test_sin_search_console_no_afirma_canibalizacion(self):
        self.assertEqual(self.audit.cannibalization, [])
        self.assertTrue(any("Sin exportacion de Search Console" in n
                            for n in self.audit.notes))

    def test_con_search_console_confirma_canibalizacion(self):
        carpeta = Path(tempfile.mkdtemp())
        csv_path = carpeta / "gsc.csv"
        csv_path.write_text(
            "Página,Impresiones\n"
            f"{CAT_ALARMAS},14\n"
            f"{SITE}/alarma-septica-pitando/,5\n",
            encoding="utf-8",
        )
        audit = run(SITE, client=FakeClient(routes()), impressions_csv=csv_path)
        confirmadas = [c for c in audit.cannibalization if c.confirmed]
        self.assertEqual(len(confirmadas), 1)
        self.assertIn("CONFIRMADA", confirmadas[0].describe())

    def test_detecta_sitemap_no_declarado_en_robots(self):
        audit = run(SITE, client=FakeClient(routes(ROBOTS_SIN_SITEMAP)))
        self.assertTrue(any("no declara el sitemap" in w for w in audit.warnings))

    def test_informe_markdown_lleva_verificacion_con_hora(self):
        markdown = to_markdown(self.audit)
        self.assertIn("# Auditoria M1", markdown)
        self.assertIn("HTTP 200", markdown)
        self.assertIn("robots.txt:", markdown)
        self.assertIn("Verificaciones duras", markdown)

    def test_informe_json_es_valido(self):
        import json
        datos = json.loads(to_json(self.audit))
        self.assertEqual(datos["site"], SITE)
        self.assertEqual(len(datos["archives"]), 4)

    def test_respeta_el_limite_de_archivos(self):
        audit = run(SITE, client=FakeClient(routes()), max_archives=2)
        self.assertEqual(len(audit.archives), 2)
        self.assertTrue(any("limite por cortesia" in n for n in audit.notes))

    def test_registra_las_peticiones_hechas(self):
        self.assertGreater(self.audit.requests_made, 5)
        self.assertEqual(self.audit.requests_made, self.client.request_count)


class TestSitioQueNoResponde(unittest.TestCase):
    def test_sitio_vacio_no_rompe_la_auditoria(self):
        audit = run("https://vacio.test", client=FakeClient({}))
        self.assertEqual(audit.archives, [])
        markdown = to_markdown(audit)
        self.assertIn("No se encontraron archivos", markdown)


if __name__ == "__main__":
    unittest.main()


class TestContadorDePeticiones(unittest.TestCase):
    """El contador que se publica es el de ESTA auditoria, no el del cliente.

    `prospeccion` comparte un cliente entre todos los dominios de un lote para
    espaciar las peticiones de verdad. Si la auditoria copiase el contador
    absoluto, el segundo dominio declararia en la primera linea de su informe
    las peticiones del primero. Esa cifra se la lee la marca auditada.
    """

    def test_una_auditoria_sola_cuenta_sus_peticiones(self):
        client = FakeClient(routes())
        audit = run(SITE, client=client)
        self.assertEqual(audit.requests_made, client.request_count)
        self.assertGreater(audit.requests_made, 0)

    def test_con_cliente_compartido_cada_auditoria_cuenta_la_suya(self):
        client = FakeClient(routes())
        primera = run(SITE, client=client)
        segunda = run(SITE, client=client)

        self.assertEqual(segunda.requests_made, primera.requests_made)
        self.assertEqual(
            client.request_count,
            primera.requests_made + segunda.requests_made,
        )
