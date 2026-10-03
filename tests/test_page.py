import unittest

from auditor.page import parse


class TestPage(unittest.TestCase):
    def test_lee_meta_robots_servido(self):
        html = '<html><head><meta name="robots" content="noindex, follow"></head><body></body></html>'
        page = parse(html, "https://x.test/a/")
        self.assertTrue(page.noindex)
        self.assertFalse(page.indexable)

    def test_canonical_autorreferencial(self):
        html = '<html><head><link rel="canonical" href="https://x.test/a/"></head><body></body></html>'
        self.assertTrue(parse(html, "https://x.test/a").self_canonical)
        self.assertTrue(parse(html, "https://x.test/a/").self_canonical)

    def test_canonical_a_otra_pagina_no_es_autorreferencial(self):
        html = '<html><head><link rel="canonical" href="https://x.test/b/"></head><body></body></html>'
        self.assertFalse(parse(html, "https://x.test/a/").self_canonical)

    def test_no_cuenta_palabras_de_nav_header_footer(self):
        ruido = " ".join(["ruido"] * 80)
        html = (
            f"<html><body><nav>{ruido}</nav><header>{ruido}</header>"
            "<main><p>" + " ".join(["real"] * 40) + "</p></main>"
            f"<footer>{ruido}</footer></body></html>"
        )
        page = parse(html, "https://x.test/a/")
        self.assertEqual(page.word_count, 40)
        self.assertEqual(page.content_source, "main")

    def test_enlaces_de_navegacion_no_son_articulos(self):
        html = (
            "<html><body><nav><a href='/sobre-mi/'>Sobre mi</a></nav>"
            "<main><a href='/articulo-real/'>Articulo</a>"
            "<p>" + " ".join(["x"] * 30) + "</p></main>"
            "<footer><a href='/privacidad/'>Privacidad</a></footer></body></html>"
        )
        enlaces = [l.href for l in parse(html, "https://x.test/c/").internal_article_links()]
        self.assertEqual(enlaces, ["https://x.test/articulo-real/"])

    def test_descarta_enlaces_externos_y_de_archivo(self):
        html = (
            "<html><body><main>"
            "<a href='https://otro.test/x/'>Externo</a>"
            "<a href='/category/otra/'>Categoria</a>"
            "<a href='/page/2/'>Pagina 2</a>"
            "<a href='/bueno/'>Bueno</a>"
            "<p>" + " ".join(["x"] * 30) + "</p></main></body></html>"
        )
        enlaces = [l.href for l in parse(html, "https://x.test/c/").internal_article_links()]
        self.assertEqual(enlaces, ["https://x.test/bueno/"])

    def test_html_roto_no_tumba_el_analisis(self):
        page = parse("<html><head><title>Roto", "https://x.test/a/")
        self.assertIn("Roto", page.title)


if __name__ == "__main__":
    unittest.main()
