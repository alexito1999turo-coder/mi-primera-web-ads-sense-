import tempfile
import unittest
from pathlib import Path

from clusters.keywords import Keyword, _number, load, normalize_modifiers


class TestKeyword(unittest.TestCase):
    def test_la_comercial_pequena_gana_a_la_informacional_grande(self):
        # Es el proposito de la formula: AI Overviews se come la informacional.
        comercial = Keyword("cuanto cuesta un sistema septico", volume=2000, cpc=12)
        informacional = Keyword("que es un sistema septico", volume=10000)
        self.assertGreater(comercial.priority, informacional.priority)

    def test_el_cpc_alto_sube_la_prioridad(self):
        sin_cpc = Keyword("mejor bomba septica", volume=1000)
        con_cpc = Keyword("mejor bomba septica", volume=1000, cpc=20)
        self.assertGreater(con_cpc.priority, sin_cpc.priority)

    def test_normaliza_sinonimos_de_precio(self):
        a = Keyword("cuanto cuesta un sistema septico")
        b = Keyword("precio sistema septico")
        self.assertIn("§precio", a.tokens)
        self.assertIn("§precio", b.tokens)

    def test_normaliza_frases_antes_que_palabras(self):
        self.assertEqual(normalize_modifiers("cuanto cuesta esto"), "§precio esto")
        self.assertIn("§cerca", Keyword("instalador cerca de mi").tokens)

    def test_el_plural_no_crea_token_distinto(self):
        self.assertEqual(Keyword("bombas septicas").tokens,
                         Keyword("bomba septica").tokens)

    def test_slug(self):
        self.assertEqual(Keyword("¿Cuánto cuesta? un sistema").slug, "cu-nto-cuesta-un-sistema")


class TestNumeros(unittest.TestCase):
    def test_separador_de_miles_europeo(self):
        self.assertEqual(_number("1.200"), 1200.0)

    def test_decimal_europeo(self):
        self.assertEqual(_number("8,50"), 8.5)

    def test_mixto_anglosajon(self):
        self.assertEqual(_number("1,234.56"), 1234.56)

    def test_mixto_europeo(self):
        self.assertEqual(_number("1.234,56"), 1234.56)

    def test_decimal_corto_no_es_miles(self):
        self.assertEqual(_number("0.7"), 0.7)

    def test_miles_multiples(self):
        self.assertEqual(_number("1.234.567"), 1234567.0)

    def test_vacio_es_cero(self):
        self.assertEqual(_number(""), 0.0)
        self.assertEqual(_number(None), 0.0)


class TestCarga(unittest.TestCase):
    def _csv(self, content: str) -> Path:
        path = Path(tempfile.mkdtemp()) / "kw.csv"
        path.write_text(content, encoding="utf-8")
        return path

    def test_lee_cabeceras_de_semrush(self):
        path = self._csv('Keyword,Search Volume,CPC,KD\n"bomba septica","1.200","8,50",34\n')
        keywords = load(path)
        self.assertEqual(keywords[0].volume, 1200)
        self.assertEqual(keywords[0].cpc, 8.5)
        self.assertEqual(keywords[0].difficulty, 34)

    def test_lee_cabeceras_en_espanol(self):
        path = self._csv("Palabra clave,Volumen,Dificultad\nbomba septica,900,12\n")
        self.assertEqual(load(path)[0].volume, 900)

    def test_colapsa_duplicados_de_origen(self):
        path = self._csv("Keyword,Volume\nbomba septica,900\nBOMBA SEPTICA,900\n")
        self.assertEqual(len(load(path)), 1)

    def test_sin_columna_de_keyword_falla_con_mensaje_util(self):
        path = self._csv("Volumen,CPC\n900,3\n")
        with self.assertRaises(ValueError) as ctx:
            load(path)
        self.assertIn("Cabeceras encontradas", str(ctx.exception))

    def test_funciona_sin_columnas_de_metricas(self):
        path = self._csv("Keyword\nbomba septica\n")
        self.assertEqual(load(path)[0].volume, 0)


if __name__ == "__main__":
    unittest.main()
