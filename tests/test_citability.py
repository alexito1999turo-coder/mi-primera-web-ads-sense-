import unittest

from citability.score import LIFTABLE_THRESHOLD, Quote, analyse
from citability.signals import ANAPHORA_START, is_precise, sentences_of

FUENTE = "https://tceq.texas.gov/permisos"

CITABLE = (
    "# Costes\n\n"
    "## Cuanto cuesta instalar un sistema aerobico en Texas?\n\n"
    "La instalacion completa costo 14.237 $ de mediana en Texas en 2026, sobre "
    "una muestra propia de 40 presupuestos reales.\n"
)

NO_CITABLE = (
    "# Costes\n\n"
    "## Introduccion\n\n"
    "Un sistema aerobico trata el agua. Este cuesta unos 14.000 $ de media.\n"
)


class TestSenales(unittest.TestCase):
    def test_cifra_exacta_es_medicion(self):
        self.assertTrue(is_precise("Costo 14.237 $ en 2026."))

    def test_cifra_redonda_es_consenso(self):
        self.assertFalse(is_precise("Cuesta unos 14.000 $."))

    def test_entre_con_cifras_es_horquilla(self):
        self.assertFalse(is_precise("Entre 300 y 900 dolares."))

    def test_entre_con_meses_es_rango_exacto(self):
        # Era un falso positivo que hundia la frase mejor atribuida del texto.
        self.assertTrue(is_precise("Recogidos entre enero y junio, la mediana fue 14.237 $."))

    def test_el_aproximador_solo_afecta_a_su_cifra(self):
        self.assertTrue(is_precise("Unos 30 dias de espera y un coste de 14.237 $."))

    def test_la_frase_no_se_corta_en_el_salto_de_linea(self):
        texto = "La instalacion costo 14.237 $ de mediana\nen Texas en 2026."
        self.assertEqual(len(sentences_of(texto)), 1)

    def test_el_encabezado_es_su_propia_frase(self):
        self.assertEqual(sentences_of("## Titulo\n\nTexto."), ["## Titulo", "Texto."])

    def test_demostrativo_es_anafora(self):
        self.assertTrue(ANAPHORA_START.match("Este cuesta 14.237 $."))

    def test_el_articulo_no_es_anafora(self):
        # "La instalacion" penalizada como pronombre era un falso positivo.
        self.assertIsNone(ANAPHORA_START.match("La instalacion costo 14.237 $."))

    def test_el_posesivo_si_es_anafora(self):
        self.assertTrue(ANAPHORA_START.match("Su coste es de 14.237 $."))


class TestPuntuacion(unittest.TestCase):
    def test_discrimina_citable_de_no_citable(self):
        self.assertGreater(analyse(CITABLE).score, analyse(NO_CITABLE).score + 30)

    def test_la_frase_buena_es_citable(self):
        report = analyse(CITABLE)
        self.assertEqual(len(report.liftable), 1)
        self.assertGreaterEqual(report.liftable[0].total, LIFTABLE_THRESHOLD)

    def test_la_frase_mala_no_lo_es(self):
        self.assertEqual(analyse(NO_CITABLE).liftable, [])

    def test_una_pagina_mala_si_da_lista_de_arreglos(self):
        # Es justo cuando mas hace falta: dejarla vacia seria inutil.
        self.assertTrue(analyse(NO_CITABLE).top_fixes())

    def test_los_arreglos_se_ordenan_por_cuantas_frases_afectan(self):
        texto = ("## Intro\n\nEste sistema basico cuesta exactamente 14.237 $ "
                 "en Texas en 2026 segun nuestra muestra propia de 40 casos.\n\n"
                 "Este sistema medio cuesta exactamente 15.311 $ en Texas en 2026 "
                 "segun nuestra muestra propia de 40 casos.\n\n"
                 "Este sistema grande cuesta exactamente 16.422 $ en Texas en 2026 "
                 "segun nuestra muestra propia de 40 casos.\n")
        report = analyse(texto)
        self.assertEqual(len(report.quotes), 3)
        fixes = report.top_fixes()
        self.assertTrue(fixes, "una pagina con fallos repetidos debe dar arreglos")
        # Las tres empiezan por demostrativo: el arreglo afecta a las tres.
        self.assertGreaterEqual(fixes[0][1], 2)

    def test_sin_cifras_no_hay_nada_que_citar(self):
        report = analyse("## Opinion\n\nEs una buena idea y conviene hacerlo.\n")
        self.assertEqual(report.quotes, [])
        self.assertEqual(report.score, 0)

    def test_cuenta_los_encabezados_en_forma_de_pregunta(self):
        self.assertEqual(analyse(CITABLE).question_headings, 1)
        self.assertEqual(analyse(NO_CITABLE).question_headings, 0)

    def test_la_nota_pesa_el_techo_no_el_promedio(self):
        # Al modelo le basta una frase buena: tres excelentes valen mas que
        # treinta mediocres.
        pocas_buenas = CITABLE
        muchas_malas = "## Intro\n\n" + " ".join(
            [f"Este cuesta {n}.000 $." for n in range(1, 30)]
        )
        self.assertGreater(analyse(pocas_buenas).score, analyse(muchas_malas).score)

    def test_la_respuesta_enterrada_puntua_peor_que_la_primera(self):
        primera = ("## Cuanto cuesta?\n\nCosto 14.237 $ de mediana en Texas en 2026 "
                   "sobre una muestra propia de 40 casos.\n")
        enterrada = ("## Cuanto cuesta?\n\nHay varios factores. Conviene valorarlos. "
                     "Depende del terreno. Costo 14.237 $ de mediana en Texas en 2026 "
                     "sobre una muestra propia de 40 casos.\n")
        self.assertGreater(
            analyse(primera).quotes[0].alignment,
            analyse(enterrada).quotes[0].alignment,
        )

    def test_los_pesos_se_declaran_sin_calibrar(self):
        self.assertIn("sin calibrar", analyse(CITABLE).describe())


class TestQuote(unittest.TestCase):
    def test_el_total_es_la_media_ponderada(self):
        quote = Quote(text="x", extractability=100, attributability=100,
                      scarcity=100, alignment=100)
        self.assertEqual(quote.total, 100)

    def test_una_frase_perfecta_pero_no_extraible_no_llega(self):
        quote = Quote(text="x", extractability=0, attributability=100,
                      scarcity=100, alignment=100)
        self.assertFalse(quote.liftable)


if __name__ == "__main__":
    unittest.main()
