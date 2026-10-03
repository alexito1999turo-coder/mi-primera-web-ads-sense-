import unittest

from clusters.graph import build as build_graph
from clusters.keywords import Keyword
from generator.gates import Draft, GateResult, SEVERITY_BLOCK, SEVERITY_WARN
from publisher.links import inject, targets_for
from publisher.schema import (
    Publisher,
    SchemaContext,
    build,
    faq_page,
    how_to,
    to_script,
)
from publisher.wordpress import (
    STATUS_DRAFT,
    STATUS_PUBLISH,
    AppPassword,
    WordPress,
)

CTX = SchemaContext(
    site_url="https://ejemplo.test",
    author_name="Alex",
    publisher=Publisher(name="Ejemplo", url="https://ejemplo.test"),
)

CUERPO = """# Coste

## Cuanto cuesta la instalacion?

El coste medio es de 14.200 $, media de 40 presupuestos de 2026.

## Como se revisa el sistema

1. Abre la tapa de inspeccion y comprueba el nivel del agua
2. Revisa que el difusor de aire burbujee de forma constante
3. Confirma que el led verde de la alarma esta encendido
"""


class TestSchema(unittest.TestCase):
    def test_article_siempre_presente(self):
        blocks = build("t", CUERPO, "s", CTX)
        self.assertEqual(blocks[0]["@type"], "Article")

    def test_faq_solo_con_preguntas_contestadas(self):
        self.assertIsNone(faq_page("## Titulo\n\nProsa sin preguntas."))
        self.assertIsNone(faq_page("## Hay pregunta?\n\n"))  # sin respuesta
        faq = faq_page(CUERPO)
        self.assertEqual(len(faq["mainEntity"]), 1)

    def test_howto_solo_con_pasos_de_verdad(self):
        self.assertIsNone(how_to("t", "Solo prosa corrida."))
        self.assertIsNone(how_to("t", "1. corto\n2. otro\n3. ya"))  # pasos triviales
        self.assertEqual(len(how_to("t", CUERPO)["step"]), 3)

    def test_la_pagina_comercial_no_lleva_howto(self):
        tipos = [b["@type"] for b in build("t", CUERPO, "s", CTX, intent="commercial")]
        self.assertNotIn("HowTo", tipos)

    def test_las_fuentes_van_en_citation(self):
        blocks = build("t", CUERPO, "s", CTX, sources=["https://www.epa.gov/septic"])
        self.assertEqual(blocks[0]["citation"][0]["url"], "https://www.epa.gov/septic")

    def test_el_script_es_json_valido(self):
        import json
        import re
        script = to_script(build("t", CUERPO, "s", CTX))
        for payload in re.findall(r">(\{.*?\})</script>", script):
            json.loads(payload)  # revienta si no es valido


class TestEnlazado(unittest.TestCase):
    def setUp(self):
        self.graph = build_graph([
            Keyword("mejor bomba de aire septica", volume=700, cpc=9),
            Keyword("bomba de aire septica opiniones", volume=300, cpc=8),
        ])
        self.satellite = self.graph.pages[1]

    def test_los_destinos_son_del_mismo_cluster(self):
        destinos = targets_for(self.graph, self.satellite.slug, "https://ejemplo.test")
        self.assertTrue(destinos)
        self.assertNotIn(self.satellite.slug, [d.slug for d in destinos])

    def test_enlaza_donde_el_texto_nombra_el_destino(self):
        destinos = targets_for(self.graph, self.satellite.slug, "https://ejemplo.test")
        body = "## Analisis\n\nLa mejor bomba de aire septica se elige por caudal."
        nuevo, perdidos = inject(body, destinos)
        self.assertIn("](https://ejemplo.test/mejor-bomba-de-aire-septica/)", nuevo)
        self.assertEqual(perdidos, [])

    def test_no_enlaza_si_el_texto_no_lo_nombra(self):
        destinos = targets_for(self.graph, self.satellite.slug, "https://ejemplo.test")
        nuevo, perdidos = inject("## Otra cosa\n\nTexto que no lo menciona.", destinos)
        self.assertNotIn("](", nuevo)
        self.assertEqual(len(perdidos), 1)

    def test_no_enlaza_dentro_de_un_encabezado(self):
        destinos = targets_for(self.graph, self.satellite.slug, "https://ejemplo.test")
        nuevo, _ = inject("## mejor bomba de aire septica\n\nProsa.", destinos)
        self.assertNotIn("](", nuevo)

    def test_no_duplica_un_enlace_que_ya_puso_el_redactor(self):
        destinos = targets_for(self.graph, self.satellite.slug, "https://ejemplo.test")
        body = ("Ver [mejor bomba de aire septica]"
                "(https://ejemplo.test/mejor-bomba-de-aire-septica/) aqui. "
                "La mejor bomba de aire septica manda.")
        nuevo, _ = inject(body, destinos)
        self.assertEqual(nuevo.count("](https://ejemplo.test/mejor-bomba"), 1)

    def test_respeta_el_maximo_de_enlaces(self):
        destinos = targets_for(self.graph, self.satellite.slug, "https://ejemplo.test")
        _, perdidos = inject("La mejor bomba de aire septica.", destinos, max_links=0)
        self.assertEqual(len(perdidos), 1)


class TestWordPress(unittest.TestCase):
    def setUp(self):
        self.calls: list[tuple[str, str, dict]] = []
        self.existing: dict | None = None

        def transport(method, url, headers, body):
            import json as _json
            payload = _json.loads(body) if body else {}
            self.calls.append((method, url, payload))
            if method == "GET":
                return 200, ([self.existing] if self.existing else [])
            return 201, {"id": 7, "status": payload.get("status", "draft")}

        self.wp = WordPress("https://ejemplo.test", AppPassword("u", "p"), transport)
        self.draft = Draft(slug="coste", title="Coste", body=CUERPO)

    def test_el_defecto_es_borrador(self):
        outcome = self.wp.publish(self.draft, GateResult(), CTX)
        self.assertEqual(outcome.status, STATUS_DRAFT)
        self.assertTrue(outcome.ok)

    def test_publicar_es_explicito(self):
        outcome = self.wp.publish(self.draft, GateResult(), CTX, status=STATUS_PUBLISH)
        self.assertEqual(outcome.status, STATUS_PUBLISH)

    def test_se_niega_con_compuerta_bloqueante_y_sin_tocar_la_red(self):
        result = GateResult()
        result.add("longitud_insuficiente", SEVERITY_BLOCK, "corto")
        outcome = self.wp.publish(self.draft, result, CTX)
        self.assertFalse(outcome.ok)
        self.assertIn("longitud_insuficiente", outcome.refused_reason)
        self.assertEqual(self.calls, [])

    def test_un_aviso_no_impide_publicar(self):
        result = GateResult()
        result.add("solape_no_comprobado", SEVERITY_WARN, "sin corpus")
        self.assertTrue(self.wp.publish(self.draft, result, CTX).ok)

    def test_se_puede_forzar_pero_hay_que_pedirlo(self):
        result = GateResult()
        result.add("longitud_insuficiente", SEVERITY_BLOCK, "corto")
        outcome = self.wp.publish(self.draft, result, CTX, allow_failed_gates=True)
        self.assertTrue(outcome.ok)

    def test_estado_invalido_se_rechaza(self):
        outcome = self.wp.publish(self.draft, GateResult(), CTX, status="cualquiera")
        self.assertFalse(outcome.ok)
        self.assertIn("no valido", outcome.refused_reason)

    def test_actualiza_en_vez_de_duplicar(self):
        self.existing = {"id": 42}
        outcome = self.wp.publish(self.draft, GateResult(), CTX)
        self.assertFalse(outcome.created)
        self.assertIn("posts/42", self.calls[-1][1])

    def test_el_cuerpo_lleva_el_json_ld(self):
        self.wp.publish(self.draft, GateResult(), CTX)
        contenido = self.calls[-1][2]["content"]
        self.assertIn('<script type="application/ld+json">', contenido)

    def test_un_error_de_wordpress_se_reporta_con_su_mensaje(self):
        def failing(method, url, headers, body):
            if method == "GET":
                return 200, []
            return 401, {"message": "Credenciales no validas"}

        wp = WordPress("https://ejemplo.test", AppPassword("u", "p"), failing)
        outcome = wp.publish(self.draft, GateResult(), CTX)
        self.assertFalse(outcome.ok)
        self.assertIn("401", outcome.refused_reason)
        self.assertIn("Credenciales", outcome.refused_reason)

    def test_la_contrasena_no_viaja_en_claro(self):
        header = AppPassword("usuario", "secreto").header()
        self.assertTrue(header.startswith("Basic "))
        self.assertNotIn("secreto", header)


if __name__ == "__main__":
    unittest.main()
