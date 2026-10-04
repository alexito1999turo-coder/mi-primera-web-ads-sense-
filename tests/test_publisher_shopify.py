"""El adaptador de Shopify, verificado sin red.

El motor publicaba solo en WordPress y el cliente objetivo son marcas de
Shopify, asi que este fichero vigila las dos cosas que de verdad importan: que
las reglas editoriales no se relajan al cambiar de CMS, y que el contrato de
`publish` es el mismo (misma firma, mismo tipo de retorno, mismo modo de fallar)
para que cambiar de publicador no obligue a reescribir a quien llama.
"""

import inspect
import unittest
import urllib.parse

from generator.gates import Draft, GateResult, SEVERITY_BLOCK, SEVERITY_WARN
from publisher.schema import Publisher, SchemaContext
from publisher.shopify import (
    DEFAULT_API_VERSION,
    STATUS_DRAFT,
    STATUS_PUBLISH,
    AccessToken,
    Shopify,
)
from publisher.wordpress import PublishOutcome, WordPress

CTX = SchemaContext(
    site_url="https://mi-tienda.myshopify.com",
    author_name="Alex",
    publisher=Publisher(name="Mi Tienda", url="https://mi-tienda.myshopify.com"),
)

CUERPO = """# Coste

## Cuanto cuesta la instalacion?

El coste medio es de 14.200 $, media de 40 presupuestos de 2026.

## Como se revisa el sistema

1. Abre la tapa de inspeccion y comprueba el nivel del agua
2. Revisa que el difusor de aire burbujee de forma constante
3. Confirma que el led verde de la alarma esta encendido
"""

TOKEN = "shpat_token_de_prueba"
TIENDA = "https://mi-tienda.myshopify.com"
BLOG = 55


class TestShopify(unittest.TestCase):
    def setUp(self):
        # El doble del publicador de WordPress no guarda las cabeceras. Aqui si:
        # el token de Shopify viaja en una cabecera propia y hay que poder
        # afirmar sobre ella, y sobre que no aparece en ningun otro sitio.
        self.calls: list[tuple[str, str, dict, dict]] = []
        self.existing: dict | None = None

        def transport(method, url, headers, body):
            import json as _json
            payload = _json.loads(body) if body else {}
            self.calls.append((method, url, payload, headers))
            if method == "GET":
                return 200, {"articles": [self.existing] if self.existing else []}
            article = payload.get("article", {})
            return 201, {
                "article": {
                    "id": 7,
                    "handle": article.get("handle", ""),
                    # Shopify no devuelve un estado con nombre: devuelve la fecha
                    # de publicacion, o null si es borrador.
                    "published_at": (
                        "2026-10-04T10:00:00-04:00" if article.get("published") else None
                    ),
                }
            }

        self.shop = Shopify(TIENDA, AccessToken(TOKEN), BLOG, transport)
        self.draft = Draft(slug="coste", title="Coste", body=CUERPO)

    # -- las reglas que no cambian de CMS ---------------------------------
    def test_el_defecto_es_borrador(self):
        outcome = self.shop.publish(self.draft, GateResult(), CTX)
        self.assertTrue(outcome.ok)
        self.assertEqual(outcome.status, STATUS_DRAFT)
        self.assertFalse(self.calls[-1][2]["article"]["published"])

    def test_publicar_en_vivo_es_explicito(self):
        outcome = self.shop.publish(self.draft, GateResult(), CTX, status=STATUS_PUBLISH)
        self.assertTrue(self.calls[-1][2]["article"]["published"])
        self.assertEqual(outcome.status, STATUS_PUBLISH)

    def test_se_niega_con_compuerta_bloqueante_y_sin_tocar_la_red(self):
        result = GateResult()
        result.add("longitud_insuficiente", SEVERITY_BLOCK, "corto")
        outcome = self.shop.publish(self.draft, result, CTX)
        self.assertFalse(outcome.ok)
        self.assertIn("longitud_insuficiente", outcome.refused_reason)
        self.assertEqual(self.calls, [])

    def test_un_aviso_no_impide_publicar(self):
        result = GateResult()
        result.add("solape_no_comprobado", SEVERITY_WARN, "sin corpus")
        self.assertTrue(self.shop.publish(self.draft, result, CTX).ok)

    def test_se_puede_forzar_pero_hay_que_pedirlo(self):
        result = GateResult()
        result.add("longitud_insuficiente", SEVERITY_BLOCK, "corto")
        outcome = self.shop.publish(self.draft, result, CTX, allow_failed_gates=True)
        self.assertTrue(outcome.ok)

    def test_estado_invalido_se_rechaza(self):
        outcome = self.shop.publish(self.draft, GateResult(), CTX, status="cualquiera")
        self.assertFalse(outcome.ok)
        self.assertIn("no valido", outcome.refused_reason)
        self.assertEqual(self.calls, [])

    # -- la API Admin ------------------------------------------------------
    def test_la_url_de_creacion_es_la_de_la_api_admin(self):
        self.shop.publish(self.draft, GateResult(), CTX)
        method, url, _, _ = self.calls[-1]
        self.assertEqual(method, "POST")
        self.assertEqual(
            url,
            f"{TIENDA}/admin/api/{DEFAULT_API_VERSION}/blogs/{BLOG}/articles.json",
        )

    def test_busca_por_handle_y_pide_los_no_publicados(self):
        # La busqueda existe para no duplicar el articulo en cada ejecucion, y el
        # modo normal de este adaptador es borrador. Si se deja de pedir
        # `published_status=any` y el defecto de la API no incluyera los no
        # publicados, un borrador existente no se encontraria y se crearia otro
        # cada vez. Por eso la prueba mira la URL que recibe el transporte doble:
        # quitar el parametro tiene que caerse aqui.
        self.shop.publish(self.draft, GateResult(), CTX)
        method, url, _, _ = self.calls[0]
        self.assertEqual(method, "GET")
        base, _, query = url.partition("?")
        self.assertEqual(
            base,
            f"{TIENDA}/admin/api/{DEFAULT_API_VERSION}/blogs/{BLOG}/articles.json",
        )
        # parse_qs y no comparacion de cadena: el orden de los parametros no es
        # parte del contrato, pero que esten los dos si lo es.
        self.assertEqual(
            urllib.parse.parse_qs(query),
            {"handle": ["coste"], "published_status": ["any"]},
        )

    def test_el_handle_de_la_busqueda_va_codificado(self):
        # Un slug con espacios o con `&` no puede romper la query ni colar un
        # tercer parametro: los dos valores van codificados.
        self.shop.find_by_slug("coste & plazos/2026")
        _, url, _, _ = self.calls[0]
        query = url.partition("?")[2]
        self.assertNotIn(" ", url)
        self.assertEqual(
            urllib.parse.parse_qs(query),
            {"handle": ["coste & plazos/2026"], "published_status": ["any"]},
        )

    def test_la_version_de_api_es_parametrizable(self):
        otra = Shopify(
            TIENDA, AccessToken(TOKEN), BLOG, self.shop.transport, api_version="2025-07"
        )
        otra.publish(self.draft, GateResult(), CTX)
        self.assertIn("/admin/api/2025-07/", self.calls[-1][1])

    def test_actualiza_en_vez_de_duplicar(self):
        self.existing = {"id": 42, "handle": "coste"}
        outcome = self.shop.publish(self.draft, GateResult(), CTX)
        self.assertFalse(outcome.created)
        method, url, _, _ = self.calls[-1]
        self.assertEqual(method, "PUT")
        self.assertTrue(url.endswith(f"/blogs/{BLOG}/articles/42.json"))

    def test_un_articulo_con_otro_handle_no_se_sobreescribe(self):
        """Mismo criterio que el publicador de WordPress, y por lo mismo.

        Si la API ignorase el filtro de handle, el PUT caeria sobre el articulo
        de otro. Un duplicado se ve y se borra; lo machacado, no.
        """
        self.existing = {"id": 42, "handle": "otra-cosa"}
        outcome = self.shop.publish(self.draft, GateResult(), CTX)
        self.assertTrue(outcome.created)
        method, url, _, _ = self.calls[-1]
        self.assertEqual(method, "POST")
        self.assertNotIn("/articles/42.json", url)

    def test_el_cuerpo_lleva_el_json_ld(self):
        self.shop.publish(self.draft, GateResult(), CTX)
        contenido = self.calls[-1][2]["article"]["body_html"]
        self.assertIn('<script type="application/ld+json">', contenido)

    def test_el_excerpt_va_en_summary_html(self):
        self.shop.publish(self.draft, GateResult(), CTX, excerpt="Resumen corto.")
        self.assertEqual(self.calls[-1][2]["article"]["summary_html"], "Resumen corto.")

    def test_el_token_va_en_su_cabecera_y_no_en_la_url(self):
        import json as _json
        self.shop.publish(self.draft, GateResult(), CTX)
        for _, url, payload, headers in self.calls:
            self.assertEqual(headers["X-Shopify-Access-Token"], TOKEN)
            self.assertNotIn(TOKEN, url)
            self.assertNotIn(TOKEN, _json.dumps(payload))
            self.assertNotIn("Authorization", headers)

    # -- los errores de la API --------------------------------------------
    def test_un_error_de_la_api_se_reporta_con_el_cuerpo(self):
        # Shopify no responde `message` como WordPress: responde `errors`, y si
        # ese cuerpo no llega al motivo no hay nada que diagnosticar.
        def failing(method, url, headers, body):
            if method == "GET":
                return 200, {"articles": []}
            return 422, {"errors": {"title": ["no puede estar vacio"]}}

        shop = Shopify(TIENDA, AccessToken(TOKEN), BLOG, failing)
        outcome = shop.publish(self.draft, GateResult(), CTX)
        self.assertFalse(outcome.ok)
        self.assertFalse(outcome.created)
        self.assertIn("422", outcome.refused_reason)
        self.assertIn("title", outcome.refused_reason)
        self.assertIn("no puede estar vacio", outcome.refused_reason)
        self.assertEqual(outcome.detail, {"errors": {"title": ["no puede estar vacio"]}})

    def test_un_error_con_errores_en_texto_tambien_se_lee(self):
        def failing(method, url, headers, body):
            if method == "GET":
                return 200, {"articles": []}
            return 404, {"errors": "Not Found"}

        shop = Shopify(TIENDA, AccessToken(TOKEN), BLOG, failing)
        outcome = shop.publish(self.draft, GateResult(), CTX)
        self.assertIn("404", outcome.refused_reason)
        self.assertIn("Not Found", outcome.refused_reason)

    def test_un_error_sin_cuerpo_lo_dice_sin_maquillar(self):
        def failing(method, url, headers, body):
            if method == "GET":
                return 200, {"articles": []}
            return 500, {}

        shop = Shopify(TIENDA, AccessToken(TOKEN), BLOG, failing)
        outcome = shop.publish(self.draft, GateResult(), CTX)
        self.assertIn("sin detalle", outcome.refused_reason)

    # -- compatibilidad con el publicador de WordPress --------------------
    def test_la_firma_de_publicar_es_la_misma_que_la_de_wordpress(self):
        # Esta es la prueba que sostiene la promesa del encargo: cambiar de CMS
        # no obliga a tocar la llamada. Si alguien anade un parametro a uno de
        # los dos publicadores y no al otro, esto se cae aqui y no en produccion.
        self.assertEqual(
            inspect.signature(Shopify.publish),
            inspect.signature(WordPress.publish),
        )

    def test_el_resultado_es_el_mismo_tipo_que_el_de_wordpress(self):
        outcome = self.shop.publish(self.draft, GateResult(), CTX)
        self.assertIsInstance(outcome, PublishOutcome)
        self.assertEqual(outcome.post_id, 7)
        self.assertTrue(outcome.created)
        self.assertIn("/admin/blogs/55/articles/7", outcome.edit_url)

    def test_las_categorias_de_wordpress_se_declaran_sin_traducir(self):
        # Shopify no tiene categorias numericas. Ni se tiran en silencio ni se
        # inventa una etiqueta con el numero: se dice que no se pudieron llevar.
        outcome = self.shop.publish(self.draft, GateResult(), CTX, categories=[12, 30])
        self.assertNotIn("categories", self.calls[-1][2]["article"])
        self.assertEqual(outcome.detail["categories_sin_traducir"], [12, 30])

    def test_el_cuerpo_del_error_no_se_contamina_con_la_anotacion(self):
        # Regresion: `categories_sin_traducir` se escribia en el mismo
        # diccionario que devolvio el transporte y antes de leer el error, asi
        # que un 500 sin cuerpo acababa reportando nuestra propia anotacion
        # como si fuera el mensaje de Shopify.
        def failing(method, url, headers, body):
            if method == "GET":
                return 200, {"articles": []}
            return 500, {}

        shop = Shopify(TIENDA, AccessToken(TOKEN), BLOG, failing)
        outcome = shop.publish(self.draft, GateResult(), CTX, categories=[12, 30])
        self.assertIn("sin detalle", outcome.refused_reason)
        self.assertNotIn("categories_sin_traducir", outcome.refused_reason)

    def test_no_se_escribe_dentro_de_la_respuesta_del_transporte(self):
        # `detail` es una copia: anotar lo que no se pudo traducir no puede
        # modificar el cuerpo que devolvio el transporte.
        respuesta = {"article": {"id": 7}}

        def transport(method, url, headers, body):
            if method == "GET":
                return 200, {"articles": []}
            return 201, respuesta

        shop = Shopify(TIENDA, AccessToken(TOKEN), BLOG, transport)
        outcome = shop.publish(self.draft, GateResult(), CTX, categories=[9])
        self.assertEqual(outcome.detail["categories_sin_traducir"], [9])
        self.assertEqual(respuesta, {"article": {"id": 7}})

    def test_sin_blog_id_no_se_construye(self):
        # En Shopify un articulo no existe fuera de un blog, asi que no hay
        # defecto que inventar. Y el error que de verdad hay que cazar es el del
        # que viene de WordPress y pasa el transporte en tercera posicion: si
        # pasara, `transport` quedaria a None y la prueba saldria a internet.
        with self.assertRaises(ValueError):
            Shopify(TIENDA, AccessToken(TOKEN), "")
        with self.assertRaises(ValueError):
            Shopify(TIENDA, AccessToken(TOKEN), self.shop.transport)
        # `True` es un int en Python y colaba, dejando la ruta
        # /blogs/True/articles.json.
        with self.assertRaises(ValueError):
            Shopify(TIENDA, AccessToken(TOKEN), True)


if __name__ == "__main__":
    unittest.main()
