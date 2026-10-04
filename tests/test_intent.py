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


class TestSenalesVistasEnDatosReales(unittest.TestCase):
    """Huecos encontrados pasando consultas reales de un sitio por el modelo.

    El 73% salia «sin determinar», que es tanto como no clasificar. Las
    senales que se anadieron son las que generalizan a cualquier nicho, no
    las de este: todo sector tiene su «X diagram» y su «X contract».
    """

    def c(self, texto):
        return classify(texto, texto).label

    def test_la_luz_de_aviso_y_el_corte_de_luz_son_averias(self):
        for q in ("red light on aerobic septic system",
                  "aerobic septic system power outage",
                  "luz roja en la depuradora",
                  "septic system wont drain"):
            with self.subTest(q=q):
                self.assertEqual(self.c(q), "problem")

    def test_contratar_un_servicio_es_comprar(self):
        for q in ("septic system service contracts",
                  "septic maintenance contract",
                  "ossf maintenance contract",
                  "contrato de mantenimiento de fosa septica"):
            with self.subTest(q=q):
                self.assertEqual(self.c(q), "commercial")

    def test_el_material_de_referencia_es_informacional(self):
        for q in ("aerobic septic system diagram",
                  "aerobic septic system layout",
                  "septic system maintenance checklist",
                  "what does an aerobic septic system look like",
                  "diagrama de una fosa septica"):
            with self.subTest(q=q):
                self.assertEqual(self.c(q), "informational")

    def test_comprar_sigue_ganando_al_material_de_referencia(self):
        """«Donde comprar» no es lo mismo que «donde poner»."""
        self.assertEqual(self.c("where to buy septic chlorine tablets"),
                         "transactional")

    def test_un_nombre_de_producto_suelto_se_queda_sin_determinar(self):
        """Y esta bien: no hay senal de intencion en el texto.

        Adivinarla seria inventar, que es justo lo que el sistema no hace.
        El limite esta documentado en vez de escondido tras una etiqueta.
        """
        for q in ("aerobic septic chlorine tablets", "aerobic chamber"):
            with self.subTest(q=q):
                self.assertEqual(self.c(q), "undetermined")
