"""La pagina que explica que se vende, servida por el mismo servidor.

Esta prueba vigila tres cosas distintas y conviene separarlas, porque fallan por
motivos distintos:

  - Que la ruta existe y contesta HTML. Es la parte de infraestructura.
  - Que el precio de los tres planes esta en el documento. Una pagina de ventas
    sin precio es un folleto, y el precio es justo lo que se cae cuando alguien
    refactoriza las tarjetas y se deja un plan a medias.
  - Que la pagina no se trae nada de fuera y sigue atada a 127.0.0.1. Lo
    segundo tiene su propia prueba en tests/test_webapp.py para la herramienta;
    aqui se comprueba otra vez porque una pagina de ventas es justo la que un
    dia alguien quiere exponer al mundo.

Y una cuarta que es de la casa: la pagina tiene que declarar que todavia no hay
cliente en produccion. Si eso desaparece del HTML, el producto esta prometiendo
prueba social que no tiene.
"""

import unittest
import urllib.error
import urllib.request

from webapp.offer import (CAP_PAGES, COMPETITOR_PAGES, PLANS, PROOF, QUESTIONS,
                          STATE_UNMEASURED, _max_pages, page as offer_page)
from webapp.server import Background


def pedir_html(base: str, ruta: str):
    req = urllib.request.Request(base + ruta, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, r.read().decode("utf-8"), dict(r.headers)
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode("utf-8"), dict(exc.headers)


class TestLaRutaDeOferta(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = Background().__enter__()
        cls.status, cls.html, cls.headers = pedir_html(cls.app.base, "/oferta")

    @classmethod
    def tearDownClass(cls):
        cls.app.__exit__(None, None, None)

    def test_la_ruta_responde_200_con_html(self):
        self.assertEqual(self.status, 200)
        self.assertIn("text/html", self.headers["Content-Type"])
        self.assertTrue(self.html.startswith("<!doctype html>"))

    def test_el_html_lleva_los_tres_precios(self):
        for precio in ("490 €", "890 €", "1.490 €"):
            self.assertIn(precio, self.html, f"falta el precio {precio}")

    def test_el_html_lleva_los_tres_nombres_de_plan(self):
        for nombre in ("Esencial", "Crecimiento", "Completo"):
            self.assertIn(f"<h3>{nombre}</h3>", self.html)

    def test_el_plan_que_se_vende_va_destacado_y_es_uno_solo(self):
        # Si se destacan dos, no se destaca ninguno.
        self.assertEqual(self.html.count("plan destacado"), 1)
        self.assertEqual(self.html.count("El que se vende"), 1)

    def test_estan_respondidas_las_seis_preguntas(self):
        self.assertEqual(len(QUESTIONS), 6)
        for clave, pregunta in QUESTIONS:
            self.assertIn(f'id="{clave}"', self.html)
            self.assertIn(pregunta, self.html)

    def test_dice_que_todavia_no_hay_cliente_en_produccion(self):
        # La regla de la casa aplicada a la propia pagina de ventas: lo que no
        # se ha medido se declara como no medido, empezando por lo de uno.
        self.assertIn(STATE_UNMEASURED, self.html)
        self.assertIn("producción", self.html)

    def test_el_argumento_diferencial_esta_en_la_pagina(self):
        self.assertIn("99,9%", self.html)
        self.assertIn("74,3%", self.html)
        # "30" a secas aparece en el propio CSS (padding:30px), asi que no
        # afirma nada: se afirma la frase que sostiene el argumento.
        self.assertIn(f"{COMPETITOR_PAGES} artículos al mes", self.html)
        self.assertIn(f"{CAP_PAGES} páginas al mes", self.html)

    def test_no_se_trae_nada_de_fuera(self):
        # Sin CDN, sin fuentes externas y sin JavaScript de terceros: tiene que
        # verse igual en una maquina sin internet, como el resto de la aplicacion.
        self.assertNotIn("<script", self.html)
        self.assertNotIn("<link", self.html)
        self.assertNotIn("http://", self.html)
        self.assertNotIn("https://", self.html)

    def test_extiende_la_hoja_de_estilos_en_vez_de_duplicarla(self):
        from webapp.views import STYLE

        # STYLE declara :root dos veces, una por esquema de color. Lo que esta
        # prueba vigila es que no haya una SEGUNDA hoja: la oferta anade reglas
        # al final, no vuelve a declarar las variables.
        self.assertEqual(self.html.count(STYLE), 1)
        self.assertEqual(self.html.count(":root{"), STYLE.count(":root{"))

    def test_la_pagina_se_sigue_sirviendo_atada_a_127_0_0_1(self):
        self.assertEqual(self.app.server.server_address[0], "127.0.0.1")

    def test_una_ruta_parecida_sigue_dando_404(self):
        status, cuerpo, _ = pedir_html(self.app.base, "/ofertas")
        self.assertEqual(status, 404)
        self.assertIn("error", cuerpo)

    def test_la_herramienta_lleva_a_la_oferta(self):
        # Una pagina de ventas que no se enlaza desde la demostracion no la
        # encuentra nadie.
        _, portada, _ = pedir_html(self.app.base, "/")
        self.assertIn('href="/oferta"', portada)


class TestLosPlanesComoDato(unittest.TestCase):
    """Los planes son datos, no HTML incrustado: se pueden afirmar sin servidor."""

    def test_el_precio_lleva_separador_de_miles_espanol(self):
        completo = next(p for p in PLANS if p.name == "Completo")
        self.assertEqual(completo.price, "1.490 €")

    def test_el_tope_queda_por_encima_del_plan_mas_grande(self):
        # La pagina afirma que el tope esta POR ENCIMA del plan mas grande, o
        # sea que el limite no es comercial. Si algun plan lo alcanzara, la
        # frase pasaria a ser falsa sin que nada se rompiera: de ahi el
        # estricto, y no un <=.
        for plan in PLANS:
            self.assertLess(plan.pages_per_month, CAP_PAGES,
                            f"{plan.name} alcanza el tope y deja sin sentido "
                            "la frase del cierre de planes")
        self.assertEqual(_max_pages(), max(p.pages_per_month for p in PLANS))

    def test_cada_plan_dice_en_su_lista_las_paginas_que_trae(self):
        # pages_per_month es el dato y la vineta es texto a mano: si se cambia
        # uno y no el otro, la tarjeta miente. Esto lo vigila.
        for plan in PLANS:
            self.assertTrue(
                any(f"{plan.pages_per_month} páginas al mes" in item
                    for item in plan.includes),
                f"{plan.name} no dice {plan.pages_per_month} paginas al mes "
                "en lo que incluye",
            )

    def test_cada_plan_dice_a_quien_le_toca(self):
        for plan in PLANS:
            self.assertTrue(plan.for_whom, f"{plan.name} no dice para quien es")
            self.assertTrue(plan.includes, f"{plan.name} no lista lo que incluye")

    def test_la_pagina_se_construye_sin_servidor(self):
        # Util para iterar el texto sin levantar nada.
        self.assertIn("Menos páginas, mejores y medidas.", offer_page())


if __name__ == "__main__":
    unittest.main()


class TestElTopeNoEsUnaConstanteCopiada(unittest.TestCase):
    """El README afirma que el tope lo lee del planificador. Esto lo guarda.

    Las demas pruebas interpolan `CAP_PAGES`, asi que pasarian igual con el 24
    escrito a mano en la pagina: comprobado rompiendolo a proposito. Una
    afirmacion del README que ninguna prueba vigila deja de ser cierta sin que
    nadie se entere, y el README es el documento que no miente.
    """

    def test_el_tope_de_la_pagina_es_el_del_planificador(self):
        from clusters.validate import MONTHLY_CAP

        self.assertEqual(CAP_PAGES, MONTHLY_CAP)

    def test_el_tope_se_deriva_y_no_se_copia(self):
        """Comprobado en el origen, no en el valor.

        Comparar los valores no sirve: los dos son 24 y Python internea los
        enteros pequenos, asi que `CAP_PAGES = 24` escrito a mano pasa igual
        que `CAP_PAGES = MONTHLY_CAP`. Lo que el README afirma es de donde sale
        el numero, y eso solo se ve en la linea que lo asigna.
        """
        import inspect

        import webapp.offer as offer

        source = inspect.getsource(offer)
        self.assertIn("CAP_PAGES = MONTHLY_CAP", source)
        self.assertNotIn("CAP_PAGES = 24", source)

    def test_ningun_plan_supera_el_tope_del_planificador(self):
        from clusters.validate import MONTHLY_CAP

        for plan in PLANS:
            with self.subTest(plan=plan.name):
                self.assertLess(plan.pages_per_month, MONTHLY_CAP)


class TestLaPaginaNoSeQuedaEnWordPress(unittest.TestCase):
    """El cliente objetivo de esta pagina es una marca de Shopify.

    La copy decia solo "en tu WordPress" despues de que el publicador aprendiera
    a hablar con Shopify: le decia al comprador que publicamos en el CMS que el
    no usa. Esto lo vigila, y vigila tambien que no se prometa de mas.
    """

    @classmethod
    def setUpClass(cls):
        cls.html = offer_page()

    def test_nombra_los_dos_destinos_de_publicacion(self):
        self.assertIn("Shopify", self.html)
        self.assertIn("WordPress", self.html)

    def test_el_camino_de_shopify_se_declara_no_medido(self):
        """La pagina presume de distinguir lo medido de lo supuesto.

        El banco de pruebas simula un WordPress, no una tienda. Decirlo en la
        tabla es la misma regla que se le aplica a los informes del cliente.
        """
        shopify_claims = [c for c in PROOF if "Shopify" in c.statement]
        self.assertTrue(shopify_claims, "ninguna afirmacion habla de Shopify")
        for claim in shopify_claims:
            with self.subTest(claim=claim.statement):
                self.assertEqual(claim.state, STATE_UNMEASURED)
