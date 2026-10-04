"""El experimento controlado sobre las compuertas."""

import unittest

from clusters.graph import build
from clusters.keywords import Keyword
from generator.brief import Brief, OwnData, Source
from generator.gates import Draft, unsupported_claims
from rubric.criteria import DEFECTS, RUBRIC, Specimen
from rubric.experiment import run, to_observations
from rubric.specimens import despersonalizar, quitar_fuentes, recortar, variantes

FUENTE = "https://www.epa.gov/septic"
CUERPO = (
    "# Coste\n\n"
    "## ¿Cuánto cuesta la instalación?\n\n"
    "La instalación completa costó 15.498,50 $ de mediana en Texas en 2026, "
    "sobre una muestra propia de 30 presupuestos reales.\n\n"
    "## ¿Y el permiso?\n\n"
    f"El permiso añadió 612 $ de media en 2026, según [la guía de la EPA]({FUENTE}).\n\n"
    + " ".join(["El dimensionado del tanque depende de los dormitorios."] * 180)
)


def brief_de(rol: str = "satellite") -> Brief:
    page = build([Keyword("cuanto cuesta un sistema septico", volume=2000, cpc=14)]).pages[0]
    page.role = rol
    return Brief(
        page=page, what_it_adds="Precios medidos.",
        questions=["¿Cuánto cuesta la instalación?"],
        required_sources=[Source(url=FUENTE, title="EPA", consulted_at="2026-10-04")],
        own_data=[OwnData(label="Coste", value="15.498,50 $",
                          method="mediana de 30 presupuestos")],
    )


class TestRubrica(unittest.TestCase):
    def test_los_criterios_son_binarios(self):
        self.assertTrue(all(isinstance(c.expected, bool) for c in RUBRIC))

    def test_cada_defecto_apunta_a_una_familia_de_compuertas(self):
        for clave, (_texto, familia) in DEFECTS.items():
            self.assertIsInstance(familia, tuple, clave)
            self.assertTrue(familia, clave)

    def test_un_especimen_sin_defectos_es_limpio(self):
        self.assertTrue(Specimen(slug="x", body="y").clean)


class TestInyeccion(unittest.TestCase):
    def test_quitar_fuentes_deja_el_ancla_sin_enlace(self):
        salida = quitar_fuentes(CUERPO)
        self.assertNotIn("](http", salida)
        self.assertIn("la guía de la EPA", salida)

    def test_recortar_deja_el_articulo_corto(self):
        self.assertLess(len(recortar(CUERPO, 200).split()), 210)

    def test_despersonalizar_rompe_la_atribucion(self):
        salida = despersonalizar(CUERPO)
        self.assertNotIn("en 2026", salida)

    def test_produce_el_limpio_y_cinco_variantes(self):
        specs = variantes("slug", CUERPO, "keyword", "15.498,50 $")
        self.assertEqual(len(specs), 6)
        self.assertEqual(len([s for s in specs if s.clean]), 1)


class TestExperimento(unittest.TestCase):
    def setUp(self):
        self.brief = brief_de()
        self.specs = variantes("coste", CUERPO, "cuanto cuesta un sistema septico",
                               "15.498,50 $")
        self.exp = run([(s, self.brief) for s in self.specs])

    def test_caza_los_defectos_inyectados(self):
        self.assertGreaterEqual(self.exp.detection_rate, 80.0)

    def test_el_corpus_no_se_acumula_entre_variantes(self):
        # Son alternativas del mismo articulo, no una secuencia de
        # publicaciones: acumularlas hacia saltar el solape en todas.
        for outcome in self.exp.outcomes:
            self.assertNotIn("solape_con_publicado", outcome.fired)

    def test_el_corpus_de_entrada_si_detecta_solape(self):
        draft = Draft(slug="otra", title="t", body=CUERPO)
        exp = run([(self.specs[0], self.brief)], corpus={"ya-publicada": draft.shingles()})
        self.assertIn("solape_con_publicado", exp.outcomes[0].fired)

    def test_las_familias_evitan_exigir_compuertas_excluyentes(self):
        # Si se quitan TODOS los enlaces salta sin_fuentes_enlazadas y nunca
        # fuente_obligatoria_ausente: exigir las dos marcaba un fallo inexistente.
        sin_fuentes = next(o for o in self.exp.outcomes
                           if o.specimen.slug.endswith("-sin-fuentes"))
        self.assertIn("fuente_no_citada", sin_fuentes.caught)

    def test_convierte_a_observaciones_para_el_calibrador(self):
        observaciones = to_observations(self.exp)
        self.assertEqual(len(observaciones), len(self.exp.outcomes))
        self.assertTrue(all(o.reviewed_despite_block for o in observaciones))


class TestRespaldoDeAfirmaciones(unittest.TestCase):
    """La correccion que salio de medir la compuerta contra prosa real."""

    def test_el_metodo_propio_cuenta_como_respaldo(self):
        frase = ("El coste fue de 15.498,50 $ en 2026, sobre una muestra propia "
                 "de 30 presupuestos reales.")
        self.assertEqual(unsupported_claims(Draft(slug="x", title="t", body=frase)), [])

    def test_sin_metodo_ni_enlace_si_se_marca(self):
        frase = "El coste fue de 15.498,50 $ en 2026."
        self.assertTrue(unsupported_claims(Draft(slug="x", title="t", body=frase)))

    def test_la_ventana_es_el_parrafo_no_la_frase_siguiente(self):
        # La fuente dos frases despues es como escribe la gente.
        parrafo = (f"El coste fue de 612 $. Conviene revisarlo con calma. "
                   f"La referencia esta en [la EPA]({FUENTE}).")
        self.assertEqual(unsupported_claims(Draft(slug="x", title="t", body=parrafo)), [])

    def test_un_enlace_en_otro_parrafo_no_respalda(self):
        texto = f"[la EPA]({FUENTE}) dice cosas.\n\nEl coste fue de 612 $ en 2026."
        self.assertTrue(unsupported_claims(Draft(slug="x", title="t", body=texto)))


if __name__ == "__main__":
    unittest.main()
