"""Pruebas sobre HTTP de verdad, contra un WordPress que levanta el banco.

Las demas pruebas usan dobles dentro del proceso. Eso verifica la logica y no
verifica nada del transporte: ni la cabecera de autenticacion, ni gzip, ni el
charset, ni los redirects, ni el comportamiento del analizador con el marcado
real de un tema, que trae nav, header, footer, aside y enlaces por todas partes.

Estas son mas lentas porque abren sockets. Son las que de verdad dicen que el
sistema funciona fuera de su propia cabeza.
"""

import unittest

from auditor.audit import run
from auditor.http import Client
from auditor.report import to_markdown
from generator.gates import SEVERITY_BLOCK, Draft, GateResult
from harness.wpsite import LocalWordPress
from publisher.schema import Publisher, SchemaContext
from publisher.wordpress import STATUS_DRAFT, AppPassword, WordPress

CUERPO = (
    "# Coste de un sistema septico aerobico\n\n"
    "## Cuanto cuesta la instalacion completa?\n\n"
    "La instalacion completa costo 14.237 $ de mediana en Texas en 2026, sobre "
    "una muestra propia de 40 presupuestos reales. El marco oficial esta en "
    "[la guia de la EPA](https://www.epa.gov/septic).\n"
)


class TestAuditorSobreHTTP(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.site = LocalWordPress().__enter__()
        cls.audit = run(cls.site.base, client=Client(min_interval=0.01))

    @classmethod
    def tearDownClass(cls):
        cls.site.__exit__(None, None, None)

    def _archivo(self, fragmento: str):
        return next(a for a in self.audit.archives if fragmento in a.url)

    def test_descubre_los_sitemaps_comprimidos(self):
        # El indice se sirve con gzip: si el cliente no descomprime, no hay nada.
        self.assertTrue(any(s.kind == "author" and s.exists for s in self.audit.sitemaps))
        self.assertTrue(any(s.kind == "category" and s.exists for s in self.audit.sitemaps))

    def test_lee_el_sitemap_declarado_en_robots(self):
        self.assertTrue(self.audit.robots.declares_sitemap)
        self.assertEqual([], [w for w in self.audit.warnings if "no declara" in w])

    def test_respeta_las_reglas_de_robots(self):
        self.assertFalse(self.audit.robots.allows(f"{self.site.base}/wp-admin/x"))
        self.assertTrue(self.audit.robots.allows(f"{self.site.base}/category/alarmas/"))

    def test_no_cuenta_los_enlaces_de_nav_aside_y_footer(self):
        # El tema pone 5 enlaces en nav, 2 en aside y 2 en footer. Un archivo
        # con un solo articulo tiene que contar exactamente uno.
        self.assertEqual(self._archivo("/category/alarmas/").posts, 1)
        self.assertEqual(self._archivo("/category/mantenimiento/").posts, 6)

    def test_las_palabras_salen_del_contenido_no_del_tema(self):
        alarmas = self._archivo("/category/alarmas/")
        hub = self._archivo("/category/mantenimiento/")
        self.assertLess(alarmas.words, 600)
        self.assertGreater(hub.words, 600)

    def test_el_archivo_de_autor_se_detecta_como_duplicado(self):
        autor = self._archivo("/author/")
        self.assertEqual(autor.verdict, "duplicado")
        self.assertEqual(autor.action, "desactivar_archivo")

    def test_el_hub_legitimo_queda_intacto(self):
        hub = self._archivo("/category/mantenimiento/")
        self.assertEqual(hub.verdict, "hub")
        self.assertNotIn(hub, self.audit.actionable)

    def test_prefiere_recategorizar_donde_hay_candidatos(self):
        alarmas = self._archivo("/category/alarmas/")
        self.assertEqual(alarmas.action, "recategorizar")
        self.assertTrue(alarmas.recategorization_candidates)

    def test_el_archivo_ya_en_noindex_no_genera_trabajo(self):
        etiqueta = self._archivo("/tag/urgencias/")
        self.assertFalse(etiqueta.indexable)
        self.assertEqual(etiqueta.action, "ninguna")

    def test_el_informe_distingue_indexable_de_no_indexable(self):
        markdown = to_markdown(self.audit)
        self.assertIn("no (noindex)", markdown)
        self.assertIn("ya estan en noindex y no compiten", markdown)

    def test_cada_verificacion_lleva_su_respuesta_http_y_su_hora(self):
        for archive in self.audit.archives:
            self.assertIn("HTTP 200", archive.verification)
            self.assertIn("T", archive.verification)  # marca de tiempo ISO

    def test_sigue_la_redireccion_canonica_y_dice_de_que_tipo(self):
        # El servidor redirige /category/alarmas -> /category/alarmas/, que es
        # la redireccion mas comun de WordPress y antes no se detectaba.
        client = Client(min_interval=0.01)
        response = client.get(f"{self.site.base}/category/alarmas")
        self.assertTrue(response.ok)
        self.assertTrue(response.redirected)
        self.assertEqual(response.redirect_kind, "barra final")
        self.assertIn("barra final", response.summary())

    def test_sin_redireccion_no_inventa_una(self):
        client = Client(min_interval=0.01)
        response = client.get(f"{self.site.base}/category/alarmas/")
        self.assertFalse(response.redirected)
        self.assertEqual(response.redirect_kind, "")

    def test_una_ruta_inexistente_da_404_y_no_rompe(self):
        client = Client(min_interval=0.01)
        self.assertEqual(client.get(f"{self.site.base}/no-existe/").status, 404)


class TestPublicadorSobreHTTP(unittest.TestCase):
    def setUp(self):
        self.site = LocalWordPress().__enter__()
        self.context = SchemaContext(
            site_url=self.site.base, author_name="Alex",
            publisher=Publisher(name="Sitio de prueba", url=self.site.base),
        )
        self.draft = Draft(
            slug="coste-nuevo", title="Coste de un sistema septico aerobico",
            body=CUERPO, declared_sources=["https://www.epa.gov/septic"],
        )
        self.wp = WordPress(
            self.site.base,
            AppPassword(self.site.state.user, self.site.state.password),
        )

    def tearDown(self):
        self.site.__exit__(None, None, None)

    def test_credenciales_malas_dan_401_de_verdad(self):
        mala = WordPress(self.site.base, AppPassword("editor", "incorrecta"))
        outcome = mala.publish(self.draft, GateResult(), self.context)
        self.assertFalse(outcome.ok)
        self.assertIn("401", outcome.refused_reason)

    def test_con_compuerta_bloqueante_no_toca_la_red(self):
        result = GateResult()
        result.add("afirmacion_sin_respaldo", SEVERITY_BLOCK, "cifra sin fuente")
        antes = len(self.site.state.requests)
        outcome = self.wp.publish(self.draft, result, self.context)
        self.assertFalse(outcome.ok)
        self.assertEqual(len(self.site.state.requests), antes)

    def test_publica_en_borrador_por_defecto(self):
        outcome = self.wp.publish(self.draft, GateResult(), self.context)
        self.assertTrue(outcome.ok, outcome.refused_reason)
        self.assertEqual(outcome.status, STATUS_DRAFT)
        self.assertTrue(outcome.created)

    def test_la_segunda_vez_actualiza_en_vez_de_duplicar(self):
        primero = self.wp.publish(self.draft, GateResult(), self.context)
        segundo = self.wp.publish(self.draft, GateResult(), self.context)
        self.assertEqual(primero.post_id, segundo.post_id)
        self.assertFalse(segundo.created)
        self.assertEqual(len(self.site.state.posts), 1)

    def test_el_cuerpo_guardado_lleva_json_ld_valido(self):
        import json
        import re

        outcome = self.wp.publish(self.draft, GateResult(), self.context)
        guardado = self.site.state.posts[outcome.post_id]["content"]
        bloques = re.findall(
            r'<script type="application/ld\+json">(.*?)</script>', guardado
        )
        self.assertTrue(bloques)
        tipos = [json.loads(b)["@type"] for b in bloques]
        self.assertIn("Article", tipos)

    def test_un_estado_invalido_lo_rechaza_el_cliente_antes_de_salir(self):
        antes = len(self.site.state.requests)
        outcome = self.wp.publish(self.draft, GateResult(), self.context,
                                  status="cualquier-cosa")
        self.assertFalse(outcome.ok)
        self.assertEqual(len(self.site.state.requests), antes)


if __name__ == "__main__":
    unittest.main()
