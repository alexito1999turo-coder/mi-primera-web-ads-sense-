import unittest

from auditor.intent import classify, distribution


class TestIntencion(unittest.TestCase):
    def test_transaccional_gana_a_lo_demas(self):
        self.assertEqual(classify("https://x.test/instalador-cerca-de-mi/").label,
                         "transactional")

    def test_comercial_por_coste(self):
        i = classify("https://x.test/cuanto-cuesta-instalar-septico/")
        self.assertEqual(i.label, "commercial")
        self.assertGreater(i.click_survival, 50)

    def test_comparativa_es_comercial(self):
        self.assertEqual(classify("https://x.test/mejor-equipo-comparativa/").label,
                         "commercial")

    def test_informacional_en_riesgo(self):
        i = classify("https://x.test/que-es-un-sistema-aerobico/")
        self.assertEqual(i.label, "informational")
        self.assertTrue(i.at_risk)

    def test_como_hacer_es_informacional(self):
        self.assertTrue(classify("https://x.test/como-mantener-el-sistema/").at_risk)

    def test_sin_senal_queda_indeterminado(self):
        i = classify("https://x.test/xyz-abc-123/")
        self.assertEqual(i.label, "undetermined")
        self.assertFalse(i.at_risk)

    def test_el_titulo_tambien_cuenta(self):
        i = classify("https://x.test/p/1/", title="Cuanto cuesta un sistema")
        self.assertEqual(i.label, "commercial")

    def test_distribucion_suma_cien(self):
        items = [classify(u) for u in [
            "https://x.test/que-es-a/", "https://x.test/cuanto-cuesta-b/",
            "https://x.test/como-c/", "https://x.test/mejor-d-comparativa/",
        ]]
        dist = distribution(items)
        self.assertAlmostEqual(sum(dist.values()), 100.0, places=1)


if __name__ == "__main__":
    unittest.main()
