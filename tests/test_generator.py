import unittest

from clusters.graph import build as build_graph
from clusters.keywords import Keyword
from generator.brief import Brief, OwnData, Source
from generator.gates import Draft, check, unsupported_claims
from generator.llm import ScriptedLLM, batch_requests
from generator.pipeline import BatchStats, produce, produce_many, repair_prompt

FUENTE = "https://www.epa.gov/septic"
RELLENO = " ".join(
    ["El dimensionado del tanque depende del numero de dormitorios de la vivienda."] * 170
)


def pagina(term="cuanto cuesta un sistema septico aerobico", **kw):
    graph = build_graph([Keyword(term, volume=2000, cpc=14), *kw.get("extra", [])])
    return graph.pages[0]


def brief_completo(page=None, **extra) -> Brief:
    return Brief(
        page=page or pagina(),
        what_it_adds="Precios medidos en 40 presupuestos reales.",
        questions=["Cuanto cuesta la instalacion completa?"],
        required_sources=[Source(url=FUENTE, title="EPA", consulted_at="2026-10-03")],
        own_data=[OwnData(label="Coste medio", value="14.200 $",
                          method="40 presupuestos 2026")],
        **extra,
    )


def cuerpo_bueno() -> str:
    # Dos frases citables, no una: cifra exacta, ano y metodo en la misma frase,
    # debajo de un encabezado en forma de pregunta y en primera posicion. Es lo
    # que pide la compuerta de citabilidad, y es como se escribe de verdad una
    # pagina que un modelo pueda citar.
    return (
        "# Coste de un sistema septico aerobico\n\n"
        "## Cuanto cuesta la instalacion completa?\n\n"
        "La instalacion completa costo 14.200 $ de mediana en Texas en 2026, "
        "sobre una muestra propia de 40 presupuestos reales. El marco oficial "
        f"esta en [la guia de la EPA]({FUENTE}).\n\n"
        "## Cuanto anade el permiso del condado?\n\n"
        "El permiso del condado anadio 612 $ de media en 2026 en esa misma "
        f"muestra de 40 presupuestos, contrastado con [la guia de la EPA]({FUENTE}).\n\n"
        + RELLENO
    )


class TestBrief(unittest.TestCase):
    def test_brief_vacio_es_incompleto_y_lo_explica(self):
        brief = Brief(page=pagina())
        self.assertFalse(brief.complete)
        self.assertEqual(len(brief.missing()), 4)

    def test_fuente_sin_fecha_no_es_verificable(self):
        self.assertFalse(Source(url=FUENTE).verifiable)
        self.assertTrue(Source(url=FUENTE, consulted_at="2026-10-03").verifiable)

    def test_fuente_sin_url_no_es_verificable(self):
        self.assertFalse(Source(url="EPA", consulted_at="2026-10-03").verifiable)

    def test_dato_propio_sin_metodo_no_sirve(self):
        self.assertFalse(OwnData(label="Coste", value="14.200 $").usable)
        self.assertTrue(OwnData(label="Coste", value="14.200 $", method="medicion").usable)

    def test_el_marcador_del_dato_es_el_valor_por_defecto(self):
        self.assertEqual(OwnData(label="x", value="14.200 $", method="m").marker, "14.200 $")

    def test_el_prompt_lleva_lo_que_aporta_y_las_fuentes(self):
        prompt = brief_completo().to_prompt()
        self.assertIn("Que aporta esta pagina", prompt)
        self.assertIn(FUENTE, prompt)
        self.assertIn("14.200 $", prompt)
        self.assertIn("1800 palabras", prompt)


class TestCompuertas(unittest.TestCase):
    def test_un_borrador_bueno_pasa_limpio(self):
        result = check(Draft(slug="coste", title="t", body=cuerpo_bueno()),
                       brief_completo(), corpus={"otra": {"nada que ver"}})
        self.assertTrue(result.passed)
        self.assertTrue(result.publishable_as_is)

    def test_bloquea_por_longitud(self):
        result = check(Draft(slug="x", title="t", body=f"Corto [EPA]({FUENTE}) 14.200 $"),
                       brief_completo())
        self.assertIn("longitud_insuficiente", [f.code for f in result.blocking])

    def test_bloquea_si_no_enlaza_ninguna_fuente(self):
        result = check(Draft(slug="x", title="t", body="14.200 $ " + RELLENO),
                       brief_completo())
        self.assertIn("sin_fuentes_enlazadas", [f.code for f in result.blocking])

    def test_bloquea_si_falta_la_fuente_obligatoria(self):
        body = f"14.200 $ segun [otra cosa](https://otro.test/x). " + RELLENO
        result = check(Draft(slug="x", title="t", body=body), brief_completo())
        self.assertIn("fuente_obligatoria_ausente", [f.code for f in result.blocking])

    def test_bloquea_si_el_dato_propio_no_aparece(self):
        body = f"Cuesta bastante segun [la EPA]({FUENTE}). " + RELLENO
        result = check(Draft(slug="x", title="t", body=body), brief_completo())
        self.assertIn("dato_propio_ausente", [f.code for f in result.blocking])

    def test_bloquea_si_el_brief_no_trae_dato_propio(self):
        brief = Brief(
            page=pagina(), what_it_adds="algo", questions=["q"],
            required_sources=[Source(url=FUENTE, consulted_at="2026-10-03")],
        )
        result = check(Draft(slug="x", title="t", body=cuerpo_bueno()), brief)
        self.assertIn("brief_sin_dato_propio", [f.code for f in result.blocking])

    def test_bloquea_afirmaciones_sin_respaldo(self):
        body = (f"El coste medio es de 14.200 $ segun [la EPA]({FUENTE}).\n\n"
                "Este equipo es el mejor del mercado y nunca falla.\n\n" + RELLENO)
        result = check(Draft(slug="x", title="t", body=body), brief_completo())
        self.assertIn("afirmacion_sin_respaldo", [f.code for f in result.blocking])

    def test_la_fuente_en_la_frase_siguiente_vale(self):
        texto = ("El coste medio es de 14.200 $. "
                 f"La cifra viene de [la guia de la EPA]({FUENTE}).")
        self.assertEqual(unsupported_claims(Draft(slug="x", title="t", body=texto)), [])

    def test_bloquea_densidad_anomala(self):
        term = "cuanto cuesta un sistema septico aerobico"
        body = (f"14.200 $ segun [la EPA]({FUENTE}). " + f"{term}. " * 40 + RELLENO)
        result = check(Draft(slug="x", title="t", body=body), brief_completo())
        self.assertIn("densidad_anomala", [f.code for f in result.blocking])

    def test_bloquea_solape_con_publicado(self):
        draft = Draft(slug="nueva", title="t", body=cuerpo_bueno())
        corpus = {"ya-publicada": draft.shingles()}
        result = check(draft, brief_completo(), corpus=corpus)
        self.assertIn("solape_con_publicado", [f.code for f in result.blocking])

    def test_sin_corpus_lo_declara_en_vez_de_afirmarlo(self):
        result = check(Draft(slug="x", title="t", body=cuerpo_bueno()), brief_completo())
        self.assertIn("solape_no_comprobado", [f.code for f in result.findings])
        self.assertTrue(result.passed)  # es aviso, no bloqueante

    def test_avisa_de_secundaria_ausente(self):
        graph = build_graph([
            Keyword("cuanto cuesta un sistema septico aerobico", volume=2000, cpc=14),
            Keyword("precio sistema septico aerobico", volume=1500, cpc=13),
        ])
        brief = brief_completo(page=graph.pages[0])
        self.assertTrue(brief.page.secondary, "el caso exige una secundaria")
        result = check(Draft(slug="x", title="t", body=cuerpo_bueno()), brief)
        self.assertIn("secundaria_ausente", [f.code for f in result.findings])

    def test_no_cuenta_la_url_como_palabras(self):
        # El texto del ancla cuenta como palabra; la URL no. Sin esto, un
        # articulo con muchos enlaces superaria el minimo de longitud a base
        # de direcciones web.
        corto = Draft(slug="x", title="t", body=f"Hola [EPA]({FUENTE}) adios")
        self.assertEqual(corto.word_count, 3, "Hola + EPA + adios")
        self.assertNotIn("epa.gov", " ".join(corto.words))


class TestPipeline(unittest.TestCase):
    def test_el_bucle_de_reparacion_converge(self):
        llm = ScriptedLLM(responses=["# Malo\n\nCuesta 14.000 $.", cuerpo_bueno()])
        production = produce(brief_completo(), llm)
        self.assertTrue(production.passed)
        self.assertEqual(production.repairs, 1)

    def test_la_reparacion_cita_los_hallazgos(self):
        llm = ScriptedLLM(responses=["# Malo\n\nCuesta 14.000 $.", cuerpo_bueno()])
        produce(brief_completo(), llm)
        instruccion = llm.calls[1].prompt
        self.assertIn("OBLIGATORIO", instruccion)
        self.assertIn("longitud_insuficiente".split("_")[0], instruccion.lower())

    def test_brief_incompleto_no_gasta_una_sola_llamada(self):
        llm = ScriptedLLM(responses=["jamas se usa"])
        production = produce(Brief(page=pagina()), llm)
        self.assertEqual(len(llm.calls), 0)
        self.assertIn("Brief incompleto", production.aborted_reason)
        self.assertFalse(production.passed)

    def test_se_rinde_tras_el_maximo_de_reparaciones(self):
        llm = ScriptedLLM(fallback="# Siempre malo\n\nCuesta 14.000 $.")
        production = produce(brief_completo(), llm, max_repairs=2)
        self.assertFalse(production.passed)
        self.assertEqual(len(llm.calls), 3)  # 1 intento + 2 reparaciones

    def test_el_titulo_sale_del_cuerpo(self):
        llm = ScriptedLLM(responses=[cuerpo_bueno()])
        production = produce(brief_completo(), llm)
        self.assertEqual(production.draft.title, "Coste de un sistema septico aerobico")

    def test_la_voz_de_marca_llega_al_system(self):
        llm = ScriptedLLM(responses=[cuerpo_bueno()])
        produce(brief_completo(brand_voice="Seco y directo"), llm)
        self.assertIn("Seco y directo", llm.calls[0].system)
        self.assertIn("No inventas fuentes", llm.calls[0].system)

    def test_el_lote_no_se_canibaliza_a_si_mismo(self):
        # Dos paginas distintas con el mismo cuerpo: la segunda debe bloquearse.
        graph = build_graph([
            Keyword("cuanto cuesta un sistema septico aerobico", volume=2000, cpc=14),
            Keyword("instalador septico cerca de mi", volume=1100, cpc=18),
        ])
        briefs = [brief_completo(page=p) for p in graph.pages]
        llm = ScriptedLLM(fallback=cuerpo_bueno())
        productions, stats = produce_many(briefs, llm, max_repairs=0)
        self.assertEqual(stats.passed, 1)
        self.assertIn("solape_con_publicado",
                      [f.code for f in productions[1].result.blocking])

    def test_las_estadisticas_dan_el_porcentaje_vendible(self):
        stats = BatchStats(total=4, passed=3, publishable_as_is=2)
        self.assertEqual(stats.pass_rate, 75.0)
        self.assertEqual(stats.publishable_rate, 50.0)
        self.assertIn("52,4%", stats.describe())

    def test_estadisticas_vacias_no_dividen_por_cero(self):
        self.assertEqual(BatchStats().publishable_rate, 0.0)


class TestLote(unittest.TestCase):
    def test_la_peticion_de_lote_cachea_el_system(self):
        requests = batch_requests([("p1", "voz", "escribe")])
        system = requests[0]["params"]["system"][0]
        self.assertEqual(system["cache_control"], {"type": "ephemeral"})

    def test_la_peticion_de_lote_usa_el_modelo_y_esfuerzo_correctos(self):
        params = batch_requests([("p1", "voz", "escribe")])[0]["params"]
        self.assertEqual(params["model"], "claude-opus-5-5")
        self.assertEqual(params["output_config"]["effort"], "high")
        self.assertEqual(params["thinking"], {"type": "adaptive"})

    def test_cada_trabajo_conserva_su_custom_id(self):
        requests = batch_requests([("p1", "v", "a"), ("p2", "v", "b")])
        self.assertEqual([r["custom_id"] for r in requests], ["p1", "p2"])


if __name__ == "__main__":
    unittest.main()
