"""El formato compartido. Son tonterias que juntas restan credibilidad."""

import unittest

from textos import cifra, lista, plural, porcentaje


class TestPlural(unittest.TestCase):
    def test_uno_va_en_singular(self):
        self.assertEqual(plural(1, "par", "pares"), "1 par")
        self.assertEqual(plural(1, "pagina"), "1 pagina")

    def test_cero_y_varios_van_en_plural(self):
        self.assertEqual(plural(0, "par", "pares"), "0 pares")
        self.assertEqual(plural(2, "pagina"), "2 paginas")

    def test_sin_plural_explicito_lo_deduce(self):
        self.assertEqual(plural(2, "articulo"), "2 articulos")
        self.assertEqual(plural(2, "sitio"), "2 sitios")
        self.assertEqual(plural(2, "razon"), "2 razones")

    def test_no_adivina_el_plural_de_lo_acabado_en_ese(self):
        """«mes» hace «meses» y «crisis» no cambia: la regla es del acento.

        Un deductor que adivine ahi escribe «2 mess» en el informe de un
        cliente. Falla aqui, con la palabra en el codigo, en vez de alli.
        """
        with self.assertRaises(ValueError):
            plural(2, "mes")
        self.assertEqual(plural(2, "mes", "meses"), "2 meses")
        self.assertEqual(plural(2, "crisis", "crisis"), "2 crisis")

    def test_el_deductor_falla_con_los_prestamos_y_esta_documentado(self):
        """No es un fallo oculto: es un limite escrito en el docstring.

        «clic» hace «clics», no «clices». La frontera entre prestamo y
        palabra asentada no esta en la ortografia, asi que no hay regla: para
        esos, el plural explicito.
        """
        self.assertEqual(plural(2, "clic"), "2 clices")  # limite conocido
        self.assertEqual(plural(2, "clic", "clics"), "2 clics")
        self.assertIn("clic", plural.__doc__)

    def test_lleva_separador_de_miles(self):
        self.assertEqual(plural(1200, "pagina"), "1.200 paginas")


class TestCifra(unittest.TestCase):
    def test_separador_espanol(self):
        self.assertEqual(cifra(1234567), "1.234.567")
        self.assertEqual(cifra(1234.5678, 2), "1.234,57")

    def test_redondea_hacia_arriba_no_al_par(self):
        """`round` de Python da 0 para 0,5 y 2 para 1,5.

        Es correcto estadisticamente y en un informe parece un fallo: dos
        cifras equivalentes salen distintas.
        """
        self.assertEqual(cifra(0.5), "1")
        self.assertEqual(cifra(1.5), "2")
        self.assertEqual(cifra(2.5), "3")

    def test_no_depende_del_locale_de_la_maquina(self):
        import locale

        try:
            locale.setlocale(locale.LC_ALL, "C")
        except locale.Error:  # pragma: no cover
            self.skipTest("sin locale C")
        self.assertEqual(cifra(1234567), "1.234.567")


class TestLista(unittest.TestCase):
    def test_sin_coma_antes_de_la_y(self):
        self.assertEqual(lista(["a", "b", "c"]), "a, b y c")

    def test_casos_de_borde(self):
        self.assertEqual(lista([]), "")
        self.assertEqual(lista(["a"]), "a")
        self.assertEqual(lista(["a", "b"]), "a y b")
        self.assertEqual(lista(["a", "", "b"]), "a y b")


class TestPorcentaje(unittest.TestCase):
    def test_de_proporcion_a_porcentaje(self):
        self.assertEqual(porcentaje(0.4237, 1), "42,4%")
        self.assertEqual(porcentaje(1.0), "100%")
        self.assertEqual(porcentaje(0), "0%")
