"""Priores que se apagan solos, y el seguro contra calibrar con ruido."""

import unittest

from calibration.priors import (
    PESO_DEBIL,
    PESO_FUERTE,
    Prior,
    PriorSet,
    unmeasured_factors,
    weights_from_separation,
)


class TestPrior(unittest.TestCase):
    def test_sin_datos_el_posterior_es_el_prior(self):
        p = Prior(name="x", value=0.5, weight=20)
        post = p.posterior([])
        self.assertEqual(post.value, 0.5)
        self.assertEqual(post.prior_share, 100)
        self.assertFalse(post.trustworthy)

    def test_los_datos_tiran_hacia_su_media(self):
        p = Prior(name="x", value=0.0, weight=10)
        post = p.posterior([1.0] * 10)
        self.assertAlmostEqual(post.value, 0.5, places=3)
        self.assertEqual(post.prior_share, 50)

    def test_un_prior_fuerte_aguanta_mas_que_uno_debil(self):
        datos = [1.0] * 10
        fuerte = Prior(name="f", value=0.0, weight=PESO_FUERTE).posterior(datos)
        debil = Prior(name="d", value=0.0, weight=PESO_DEBIL).posterior(datos)
        self.assertGreater(fuerte.shrinkage, debil.shrinkage)
        self.assertLess(fuerte.value, debil.value)

    def test_con_muestra_grande_la_cifra_pasa_a_ser_medicion(self):
        post = Prior(name="x", value=0.0, weight=20).posterior([1.0] * 200)
        self.assertTrue(post.trustworthy)
        self.assertLess(post.prior_share, 11)

    def test_el_informe_dice_cuanto_sigue_siendo_suposicion(self):
        texto = Prior(name="x", value=1.0, weight=20, source="mercado").posterior([]).describe()
        self.assertIn("100% prior", texto)
        self.assertIn("mercado", texto)


class TestConjunto(unittest.TestCase):
    def setUp(self):
        self.ps = PriorSet(label="prueba")
        self.ps.declare("a", 1.0, PESO_DEBIL, "supuesto")
        self.ps.declare("b", 2.0, PESO_FUERTE, "mercado")

    def test_arranca_siendo_todo_suposicion(self):
        self.assertEqual(self.ps.calibration(), 1.0)
        self.assertIn("100% prior", self.ps.describe())

    def test_observar_lo_que_no_existe_falla(self):
        with self.assertRaises(KeyError):
            self.ps.observe("no-existe", 1.0)

    def test_el_conjunto_se_calibra_por_partes(self):
        for _ in range(60):
            self.ps.observe("a", 5.0)
        self.assertTrue(self.ps.posterior("a").trustworthy)
        self.assertFalse(self.ps.posterior("b").trustworthy)
        self.assertLess(self.ps.calibration(), 1.0)

    def test_value_devuelve_el_posterior_no_el_prior(self):
        for _ in range(100):
            self.ps.observe("a", 5.0)
        self.assertGreater(self.ps.value("a"), 4.0)


class TestPesosPorSeparacion(unittest.TestCase):
    PREVIOS = {"atr": 0.4, "esc": 0.4, "ali": 0.2}

    def test_sin_ejemplos_no_mueve_nada(self):
        self.assertEqual(weights_from_separation([], [], self.PREVIOS), self.PREVIOS)

    def test_pocos_ejemplos_mueven_poco(self):
        citadas = [{"atr": 90, "esc": 90, "ali": 50}] * 3
        no = [{"atr": 10, "esc": 10, "ali": 40}] * 3
        nuevos = weights_from_separation(citadas, no, self.PREVIOS)
        for k in self.PREVIOS:
            self.assertLess(abs(nuevos[k] - self.PREVIOS[k]), 0.1)

    def test_muchos_ejemplos_mandan(self):
        citadas = [{"atr": 100, "esc": 10, "ali": 50}] * 200
        no = [{"atr": 0, "esc": 8, "ali": 40}] * 200
        nuevos = weights_from_separation(citadas, no, self.PREVIOS)
        self.assertGreater(nuevos["atr"], self.PREVIOS["atr"])

    def test_un_factor_sin_varianza_no_se_toca(self):
        # El fallo real: el banco de pruebas envolvia cada frase igual, la
        # alineacion salia identica en todas, y el ajuste le bajaba el peso por
        # un artefacto del diseno en vez de por evidencia.
        citadas = [{"atr": 90, "esc": 90, "ali": 100}] * 9
        no = [{"atr": 10, "esc": 20, "ali": 100}] * 9
        nuevos = weights_from_separation(citadas, no, self.PREVIOS)
        self.assertEqual(nuevos["ali"], self.PREVIOS["ali"])

    def test_los_pesos_siguen_sumando_uno(self):
        citadas = [{"atr": 90, "esc": 70, "ali": 100}] * 9
        no = [{"atr": 10, "esc": 20, "ali": 100}] * 9
        nuevos = weights_from_separation(citadas, no, self.PREVIOS)
        self.assertAlmostEqual(sum(nuevos.values()), 1.0, places=3)

    def test_declara_que_factores_no_pudo_medir(self):
        citadas = [{"atr": 90, "esc": 90, "ali": 100}] * 5
        no = [{"atr": 10, "esc": 20, "ali": 100}] * 5
        self.assertEqual(unmeasured_factors(citadas, no, ["atr", "esc", "ali"]), ["ali"])

    def test_si_nada_separa_no_mueve_nada(self):
        iguales = [{"atr": 50, "esc": 50, "ali": 50}] * 5
        self.assertEqual(weights_from_separation(iguales, iguales, self.PREVIOS),
                         self.PREVIOS)


if __name__ == "__main__":
    unittest.main()
