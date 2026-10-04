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


class TestIntencionDeProblema(unittest.TestCase):
    """La clase que faltaba, encontrada con datos reales de un nicho.

    «aerobic septic alarm going off» salia como «sin determinar», que es
    tanto como no clasificarla, y es la consulta mas valiosa del nicho: quien
    tiene la alarma sonando no esta leyendo.
    """

    def clasificar(self, texto):
        return classify(texto, texto)

    def test_una_averia_se_reconoce_en_los_dos_idiomas(self):
        for consulta in ("aerobic septic alarm going off",
                         "septic air pump not working",
                         "septic tank backing up",
                         "la alarma septica no para de pitar",
                         "mi fosa septica desborda",
                         "la bomba no funciona"):
            with self.subTest(consulta=consulta):
                self.assertEqual(self.clasificar(consulta).label, "problem")

    def test_comprar_manda_sobre_averia(self):
        """Quien busca el repuesto ya esta comprando, no diagnosticando."""
        self.assertEqual(
            self.clasificar("best replacement septic air pump").label, "commercial")
        self.assertEqual(
            self.clasificar("buy septic alarm replacement").label, "transactional")

    def test_averia_manda_sobre_informacional(self):
        """«Como arreglar X» con una averia detras no es curiosidad."""
        self.assertEqual(self.clasificar("how to fix septic alarm").label, "problem")

    def test_sobrevive_mas_clic_que_lo_informacional_y_menos_que_lo_comercial(self):
        problema = self.clasificar("septic alarm going off").click_survival
        info = self.clasificar("what is an aerobic septic system").click_survival
        comercial = self.clasificar("aerobic septic system cost").click_survival
        self.assertLess(info, problema)
        self.assertLess(problema, comercial)

    def test_tiene_curva_y_valor_declarados(self):
        """Sin esto cae en el defecto y el valor sale mal sin avisar."""
        from insight.curves import AIO_EXPOSURE, CLICK_VALUE, click_value

        self.assertIn("problem", AIO_EXPOSURE)
        self.assertIn("problem", CLICK_VALUE)
        self.assertGreater(click_value("problem"), click_value("informational"))

    def test_una_averia_no_cuenta_como_informacional_en_riesgo(self):
        self.assertFalse(self.clasificar("septic alarm going off").at_risk)
