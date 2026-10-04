"""Prospeccion de punta a punta, sin red.

Las cuatro cosas que se vigilan aqui son las cuatro que rompen el envio del
lunes: que un dominio roto no se lleve el lote por delante, que el orden de la
lista se conserve, que el mensaje tenga exactamente tres lineas con una cifra
dentro, y que un sitio limpio no reciba un problema inventado.
"""

import tempfile
import unittest
from pathlib import Path

from prospeccion.batch import parse_domains, read_domains, run
from prospeccion.cli import INDEX_NAME, build_parser, main
from prospeccion.outreach import (
    CODE_REDIRECT,
    SUMMARY_LINES,
    brand_for,
    build,
    nothing_measured,
    sitemap_redirects,
)
from tests.fakes import SITE, FakeClient, routes

SITIO_LIMPIO = "https://limpio.test"
SITIO_MUDO = "https://mudo.test"
SITIO_REDIR = "https://redirige.test"
SITIO_AVISOS = "https://avisos.test"
HOST_ROTO = "roto.test"


def rutas_sin_sitemap() -> dict:
    """Un sitio que contesta pero del que no se puede medir nada.

    Es el caso comun fuera de WordPress, y el que destapa la unica mentira
    posible de esta pieza: hallazgos vacios por no haber medido se lee igual
    que hallazgos vacios por estar limpio.
    """
    return {
        f"{SITIO_MUDO}/robots.txt": (
            200, "text/plain",
            f"User-agent: *\nSitemap: {SITIO_MUDO}/sitemap_index.xml\n",
        ),
    }


class ClienteQueRevienta:
    """Doble que falla en un host concreto y sirve bien el resto.

    Existe porque el cliente real se come la red, el DNS y el TLS y devuelve
    Response(status=0): lo que de verdad amenaza al lote es la excepcion
    inesperada a mitad del analisis, y eso es lo que simula este doble.
    """

    def __init__(self, rutas: dict, host_roto: str = HOST_ROTO) -> None:
        self._fake = FakeClient(rutas)
        self.host_roto = host_roto

    @property
    def request_count(self) -> int:
        return self._fake.request_count

    @property
    def requested(self) -> list[str]:
        return self._fake.requested

    def get(self, url: str):
        if self.host_roto in url:
            raise RuntimeError("el servidor devolvio algo que no es HTML")
        return self._fake.get(url)


def _urlset(urls: list[str]) -> str:
    entries = "".join(f"<url><loc>{u}</loc></url>" for u in urls)
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
        f"{entries}</urlset>"
    )


def _index(urls: list[str]) -> str:
    entries = "".join(f"<sitemap><loc>{u}</loc></sitemap>" for u in urls)
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
        f"{entries}</sitemapindex>"
    )


def _listado(url: str, titulo: str, articulos: list[str], palabras: int) -> str:
    items = "".join(f'<article><h2><a href="{a}">{a}</a></h2></article>'
                    for a in articulos)
    filler = " ".join(["palabra"] * palabras)
    return (
        f"<html><head><title>{titulo}</title>"
        '<meta name="robots" content="index, follow">'
        f'<link rel="canonical" href="{url}">'
        "</head><body><nav><a href=\"/\">Inicio</a></nav>"
        f"<main><h1>{titulo}</h1>{items}<p>{filler}</p></main>"
        "</body></html>"
    )


def rutas_limpias() -> dict:
    """Un sitio sin nada que arreglar: hub legitimo e intencion de compra.

    Hace falta construirlo a mano porque el escenario de fakes.py esta disenado
    justo al contrario: alli todo tiene un hallazgo.
    """
    xml = "application/xml"
    html = "text/html; charset=UTF-8"
    posts = [
        f"{SITIO_LIMPIO}/comprar-mesa-de-roble/",
        f"{SITIO_LIMPIO}/precio-de-sillas-tapizadas/",
        f"{SITIO_LIMPIO}/mejor-sofa-comparativa/",
        f"{SITIO_LIMPIO}/instalador-cerca-de-mi/",
        f"{SITIO_LIMPIO}/presupuesto-de-montaje/",
    ]
    hub = f"{SITIO_LIMPIO}/category/salon/"
    return {
        f"{SITIO_LIMPIO}/robots.txt": (200, "text/plain",
                                       "User-agent: *\nDisallow: /wp-admin/\n\n"
                                       f"Sitemap: {SITIO_LIMPIO}/sitemap_index.xml\n"),
        f"{SITIO_LIMPIO}/sitemap_index.xml": (200, xml, _index([
            f"{SITIO_LIMPIO}/post-sitemap.xml",
            f"{SITIO_LIMPIO}/category-sitemap.xml",
        ])),
        f"{SITIO_LIMPIO}/post-sitemap.xml": (200, xml, _urlset(posts)),
        f"{SITIO_LIMPIO}/category-sitemap.xml": (200, xml, _urlset([hub])),
        hub: (200, html, _listado(hub, "Salon", posts, 900)),
    }


class TestLoteDeDominios(unittest.TestCase):
    def setUp(self):
        self.client = ClienteQueRevienta(routes())
        self.domains = ["10.0.0.5", "ejemplo.test", HOST_ROTO, "localhost"]
        self.batch = run(self.domains, client=self.client)

    def test_el_lote_respeta_el_orden_de_entrada(self):
        # El fichero de dominios y la carpeta de informes se leen en paralelo:
        # si el lote reordena, el indice deja de cuadrar con la lista.
        self.assertEqual([r.raw for r in self.batch.results], self.domains)

    def test_un_dominio_que_falla_no_tumba_el_lote(self):
        self.assertEqual(len(self.batch.results), 4)
        self.assertEqual([r.raw for r in self.batch.audited], ["ejemplo.test"])
        self.assertEqual(len(self.batch.failed), 3)

    def test_el_fallo_se_registra_con_su_motivo(self):
        roto = next(r for r in self.batch.results if r.raw == HOST_ROTO)
        self.assertFalse(roto.ok)
        self.assertIn("RuntimeError", roto.error)
        self.assertIn("no es HTML", roto.error)

    def test_una_direccion_privada_se_rechaza_sin_pedirla(self):
        # La guarda esta en webapp.api.normalize_site y se pide, no se copia.
        privada = next(r for r in self.batch.results if r.raw == "10.0.0.5")
        self.assertFalse(privada.ok)
        self.assertIn("direccion interna", privada.error)
        self.assertEqual(privada.requests_made, 0)
        self.assertFalse([u for u in self.client.requested if "10.0.0.5" in u])

    def test_cada_resultado_lleva_su_hora_de_consulta(self):
        for result in self.batch.results:
            self.assertTrue(result.consulted_at.endswith("+00:00"), result.raw)

    def test_el_espaciado_es_de_un_solo_cliente_para_todo_el_lote(self):
        # Cuarenta auditorias con un cliente cada una serian cuarenta rafagas.
        por_dominio = sum(r.requests_made for r in self.batch.results)
        self.assertEqual(self.batch.requests_made, self.client.request_count)
        self.assertEqual(por_dominio, self.client.request_count)

    def test_el_motivo_de_cada_fallo_queda_en_las_notas(self):
        texto = " ".join(self.batch.notes)
        for result in self.batch.failed:
            self.assertIn(result.raw, texto)

    def test_una_lista_vacia_lo_dice_en_vez_de_fingir_un_lote(self):
        vacio = run([], client=FakeClient({}))
        self.assertEqual(vacio.results, [])
        self.assertIn("vacia", " ".join(vacio.notes))


class TestFicheroDeDominios(unittest.TestCase):
    def test_los_comentarios_y_los_huecos_no_son_dominios(self):
        texto = "# lista del lunes\n\nuno.test\ndos.test  # ya contestaron\n\n"
        self.assertEqual(parse_domains(texto), ["uno.test", "dos.test"])

    def test_los_repetidos_de_pegar_una_hoja_de_calculo_se_descartan(self):
        self.assertEqual(parse_domains("uno.test\nUNO.test/\nuno.test"),
                         ["uno.test"])

    def test_se_lee_del_fichero_respetando_el_orden(self):
        with tempfile.TemporaryDirectory() as carpeta:
            ruta = Path(carpeta) / "dominios.txt"
            ruta.write_text("b.test\na.test\n", encoding="utf-8")
            self.assertEqual(read_domains(ruta), ["b.test", "a.test"])


class TestResumenDeTresLineas(unittest.TestCase):
    def setUp(self):
        self.batch = run(["ejemplo.test"], client=FakeClient(routes()))
        self.outreach = build(self.batch.results[0].audit)

    def test_el_resumen_tiene_exactamente_tres_lineas(self):
        self.assertEqual(len(self.outreach.summary_lines), SUMMARY_LINES)
        self.assertEqual(len(self.outreach.summary.splitlines()), SUMMARY_LINES)

    def test_ninguna_linea_esta_vacia_ni_lleva_un_salto_dentro(self):
        for line in self.outreach.summary_lines:
            self.assertTrue(line.strip())
            self.assertNotIn("\n", line)

    def test_la_primera_linea_nombra_el_hallazgo_mas_concreto_con_cifra(self):
        # Es la linea que decide si se abre el informe: una generalidad la mata.
        primera = self.outreach.summary_lines[0]
        self.assertIn(self.outreach.findings[0].headline, primera)
        self.assertTrue(any(c.isdigit() for c in primera), primera)

    def test_el_resumen_se_dirige_a_la_marca_por_su_nombre(self):
        self.assertTrue(self.outreach.summary_lines[0].startswith("Ejemplo:"))
        self.assertEqual(brand_for(SITE), "Ejemplo")

    def test_la_ultima_linea_pide_algo_concreto(self):
        self.assertIn("informe", self.outreach.summary_lines[2])


class TestSinHallazgos(unittest.TestCase):
    def setUp(self):
        self.batch = run(["limpio.test"], client=FakeClient(rutas_limpias()))
        self.outreach = build(self.batch.results[0].audit)

    def test_un_sitio_limpio_se_mide_de_verdad(self):
        # Sin esto, "no hay hallazgos" podria significar "no se midio nada".
        audit = self.batch.results[0].audit
        self.assertEqual(len(audit.archives), 1)
        self.assertEqual(audit.post_count, 5)

    def test_sin_hallazgos_no_se_inventa_ninguno(self):
        self.assertEqual(self.outreach.findings, [])
        self.assertFalse(self.outreach.has_findings)

    def test_sin_hallazgos_el_resumen_lo_dice_y_lo_usa_de_argumento(self):
        resumen = self.outreach.summary
        self.assertEqual(len(self.outreach.summary_lines), SUMMARY_LINES)
        self.assertIn("no te voy a inventar un problema", resumen)
        self.assertIn("techo", resumen)

    def test_sin_hallazgos_el_informe_no_finge_una_lista(self):
        self.assertIn("Nada que arreglar", self.outreach.markdown)
        self.assertNotIn("### 1.", self.outreach.markdown)


class TestNoSeMidioNada(unittest.TestCase):
    """Cero mediciones no es un sitio limpio, y no se puede escribir igual."""

    def setUp(self):
        self.batch = run(["mudo.test"], client=FakeClient(rutas_sin_sitemap()))
        self.audit = self.batch.results[0].audit
        self.outreach = build(self.audit)

    def test_el_caso_existe_de_verdad_sin_hallazgos_y_sin_mediciones(self):
        self.assertTrue(self.batch.results[0].ok)
        self.assertEqual(len(self.audit.archives), 0)
        self.assertEqual(self.audit.post_count, 0)
        self.assertEqual(self.outreach.findings, [])
        self.assertTrue(nothing_measured(self.audit))

    def test_no_se_afirma_que_este_limpio(self):
        # Lo que el desconocido comprobaria en diez segundos. Negar la
        # afirmacion si vale ("no te digo que este limpio"); hacerla, no.
        texto = (self.outreach.summary + self.outreach.markdown).lower()
        self.assertNotIn("lo tecnico esta limpio", texto)
        self.assertNotIn("nada que arreglar", texto)
        self.assertNotIn("no te voy a inventar un problema", texto)
        self.assertNotIn("ninguno es un duplicado indexado", texto)

    def test_el_resumen_dice_que_no_lo_sabe_y_sigue_siendo_de_tres_lineas(self):
        self.assertEqual(len(self.outreach.summary_lines), SUMMARY_LINES)
        for line in self.outreach.summary_lines:
            self.assertTrue(line.strip())
            self.assertNotIn("\n", line)
        self.assertIn("no lo se", self.outreach.summary)

    def test_lo_no_medido_encabeza_la_lista_de_lo_no_medido(self):
        self.assertIn("No he medido nada", self.outreach.markdown)
        self.assertIn("no se leyo un sitemap", self.outreach.unmeasured[0])

    def test_el_indice_del_lote_lo_distingue_de_un_sitio_limpio(self):
        with tempfile.TemporaryDirectory() as carpeta:
            lista = Path(carpeta) / "dominios.txt"
            lista.write_text("mudo.test\nlimpio.test\n", encoding="utf-8")
            rutas = dict(rutas_sin_sitemap())
            rutas.update(rutas_limpias())
            salida = Path(carpeta) / "informes"
            main([str(lista), "--out", str(salida)], client=FakeClient(rutas))
            indice = (salida / INDEX_NAME).read_text(encoding="utf-8")
        self.assertIn("SIN MEDIR", indice)
        self.assertIn("ninguno (no se inventa)", indice)


class TestCifrasDelLote(unittest.TestCase):
    """Las peticiones que se declaran tienen que ser las que se hicieron."""

    def test_un_segundo_lote_con_el_mismo_cliente_no_hereda_peticiones(self):
        # El cliente se comparte a proposito para que el espaciado sobreviva al
        # cambio de dominio, y su contador es acumulado: si el lote declarase el
        # absoluto, el informe del segundo lote citaria peticiones ajenas.
        client = FakeClient(routes())
        primero = run(["ejemplo.test"], client=client)
        segundo = run(["ejemplo.test"], client=client)
        self.assertEqual(primero.requests_made,
                         sum(r.requests_made for r in primero.results))
        self.assertEqual(segundo.requests_made,
                         sum(r.requests_made for r in segundo.results))
        self.assertIn(f"{segundo.requests_made} peticiones", segundo.describe())

    def test_cada_informe_declara_las_peticiones_hechas_a_ESE_dominio(self):
        # La cifra va en la primera linea del informe que lee la marca. Con el
        # cliente compartido, el auditor le copiaba el contador absoluto y el
        # tercer dominio heredaba las peticiones de los dos anteriores.
        rutas = dict(rutas_sin_sitemap())
        rutas.update(rutas_limpias())
        rutas.update(routes())
        batch = run(["mudo.test", "limpio.test", "ejemplo.test"],
                    client=FakeClient(rutas))
        self.assertEqual(len(batch.audited), 3)
        for result in batch.results:
            self.assertEqual(result.audit.requests_made, result.requests_made,
                             result.raw)
            informe = build(result.audit).markdown
            self.assertIn(f"con {result.requests_made} peticiones espaciadas",
                          informe)
        # Y el total del lote sigue siendo la suma, no el maximo.
        self.assertEqual(batch.requests_made,
                         sum(r.requests_made for r in batch.results))

    def test_el_mismo_sitio_con_y_sin_esquema_es_un_repetido(self):
        # Dos entradas iguales serian dos auditorias al mismo desconocido y un
        # informe pisando al otro: el slug sale del host, no de la linea.
        self.assertEqual(
            parse_domains("ejemplo.test\nhttps://ejemplo.test\nhttp://ejemplo.test/"),
            ["ejemplo.test"],
        )


class TestInformeParaLaMarca(unittest.TestCase):
    def setUp(self):
        self.batch = run(["ejemplo.test"], client=FakeClient(routes()))
        self.outreach = build(self.batch.results[0].audit)

    def test_cada_hallazgo_dice_que_pasa_por_que_y_que_hacer(self):
        # Las tres piezas son el producto: un hallazgo sin "que se hace" es un
        # diagnostico, y a un desconocido no se le manda un diagnostico.
        self.assertTrue(self.outreach.findings)
        for finding in self.outreach.findings:
            self.assertTrue(finding.headline.strip(), finding.code)
            self.assertTrue(finding.why.strip(), finding.code)
            self.assertTrue(finding.fix.strip(), finding.code)
            self.assertTrue(finding.figure.strip(), finding.code)

    def test_el_informe_lleva_la_verificacion_http_de_cada_hallazgo(self):
        self.assertIn("Verificacion: `", self.outreach.markdown)
        self.assertIn("HTTP 200", self.outreach.markdown)

    def test_lo_que_no_se_ha_medido_se_declara(self):
        # Sin exportacion de Search Console la canibalizacion no se afirma.
        self.assertIn("Lo que NO he medido", self.outreach.markdown)
        self.assertIn("Search Console", " ".join(self.outreach.unmeasured))

    def test_el_informe_esta_escrito_en_dinero_y_no_en_jerga(self):
        texto = self.outreach.markdown
        self.assertIn("Por que importa.", texto)
        self.assertIn("Que hay que hacer.", texto)

    def test_el_nombre_de_fichero_sale_del_dominio(self):
        self.assertEqual(self.outreach.slug, "ejemplo-test")


class TestLineaDeComandos(unittest.TestCase):
    def test_el_lote_completo_escribe_un_informe_y_un_mensaje_por_marca(self):
        client = ClienteQueRevienta(routes())
        with tempfile.TemporaryDirectory() as carpeta:
            lista = Path(carpeta) / "dominios.txt"
            lista.write_text("# lunes\nejemplo.test\n10.0.0.5\n", encoding="utf-8")
            salida = Path(carpeta) / "informes"
            code = main([str(lista), "--out", str(salida)], client=client)

            self.assertEqual(code, 1)  # hubo un fallo, y se ve en el codigo
            self.assertTrue((salida / "ejemplo-test.md").exists())
            mensaje = (salida / "ejemplo-test-mensaje.txt").read_text(encoding="utf-8")
            self.assertEqual(len(mensaje.strip().splitlines()), SUMMARY_LINES)

            indice = (salida / INDEX_NAME).read_text(encoding="utf-8")
            self.assertIn("ejemplo.test", indice)
            self.assertIn("10.0.0.5", indice)
            self.assertIn("direccion interna", indice)
            self.assertFalse((salida / "10-0-0-5.md").exists())

    def test_una_lista_sin_dominios_no_arranca_nada(self):
        with tempfile.TemporaryDirectory() as carpeta:
            lista = Path(carpeta) / "vacia.txt"
            lista.write_text("# solo comentarios\n", encoding="utf-8")
            client = FakeClient({})
            code = main([str(lista), "--out", str(Path(carpeta) / "out")],
                        client=client)
            self.assertEqual(code, 1)
            self.assertEqual(client.request_count, 0)

    def test_la_carpeta_de_salida_tiene_un_defecto_y_el_dominio_es_obligatorio(self):
        args = build_parser().parse_args(["dominios.txt"])
        self.assertEqual(args.out, "informes")
        with self.assertRaises(SystemExit):
            build_parser().parse_args([])


class ClienteQueRedirige:
    """Doble que sirve una URL distinta de la pedida, como un 301 ya seguido.

    Hace falta porque el doble de tests/fakes.py devuelve siempre final_url
    igual a la url pedida, y la diferencia entre esas dos es exactamente la
    senal que mide este hallazgo: el cliente real deja final_url apuntando al
    destino, y de ahi sale la linea de verificacion.
    """

    def __init__(self, rutas: dict, destinos: dict[str, str]) -> None:
        self._fake = FakeClient(rutas)
        self.destinos = destinos

    @property
    def request_count(self) -> int:
        return self._fake.request_count

    @property
    def requested(self) -> list[str]:
        return self._fake.requested

    def get(self, url: str):
        response = self._fake.get(url)
        destino = self.destinos.get(url)
        if destino:
            response.final_url = destino
        return response


def _posts_de_compra(sitio: str) -> list[str]:
    """Articulos con intencion de compra, no informacionales.

    No es decoracion del escenario: con articulos informacionales saltaria
    tambien el hallazgo de intencion y el sitio dejaria de aislar lo que se
    quiere mirar.
    """
    return [
        f"{sitio}/comprar-mesa-de-roble/",
        f"{sitio}/precio-de-sillas-tapizadas/",
        f"{sitio}/mejor-sofa-comparativa/",
        f"{sitio}/instalador-cerca-de-mi/",
        f"{sitio}/presupuesto-de-montaje/",
    ]


def rutas_con_redirecciones() -> tuple[dict, dict]:
    """Un sitio sano salvo que su sitemap declara URL que ya no se sirven.

    Las tres categorias son hubs legitimos a proposito: asi el unico hallazgo
    posible es el del sitemap y la cifra que se comprueba no puede venir de
    otro sitio. De las tres redirecciones, dos van a otra ruta y la tercera
    solo anade la barra final, que es la redireccion mas comun de WordPress y
    no es un problema de nadie.
    """
    xml = "application/xml"
    html = "text/html; charset=UTF-8"
    posts = _posts_de_compra(SITIO_REDIR)
    categorias = [
        f"{SITIO_REDIR}/category/salon/",
        f"{SITIO_REDIR}/category/cocina/",
        f"{SITIO_REDIR}/category/dormitorio/",
    ]
    rutas = {
        f"{SITIO_REDIR}/robots.txt": (
            200, "text/plain",
            f"User-agent: *\nDisallow: /wp-admin/\n\n"
            f"Sitemap: {SITIO_REDIR}/sitemap_index.xml\n",
        ),
        f"{SITIO_REDIR}/sitemap_index.xml": (200, xml, _index([
            f"{SITIO_REDIR}/post-sitemap.xml",
            f"{SITIO_REDIR}/category-sitemap.xml",
        ])),
        f"{SITIO_REDIR}/post-sitemap.xml": (200, xml, _urlset(posts)),
        f"{SITIO_REDIR}/category-sitemap.xml": (200, xml, _urlset(categorias)),
    }
    for url in categorias:
        nombre = url.rstrip("/").rsplit("/", 1)[-1].capitalize()
        rutas[url] = (200, html, _listado(url, nombre, posts, 900))
    destinos = {
        categorias[0]: f"{SITIO_REDIR}/salon/",
        categorias[1]: f"{SITIO_REDIR}/muebles/cocina/",
        categorias[2]: f"{SITIO_REDIR}/category/dormitorio",
    }
    return rutas, destinos


def rutas_de_los_otros_avisos() -> dict:
    """Un sitio que dispara los avisos 1, 2, 4 y 5 y ninguna redireccion.

    Es el escenario que protege la decision de producto: robots.txt sin linea
    Sitemap (1), sitemaps de categoria y de etiqueta declarados (2), tres
    categorias finas que la regla propondria noindexar en bloque (4) y una
    etiqueta que es hub legitimo (5). Si alguien vuelve a filtrar
    `audit.warnings` por texto, aqui es donde se ve.
    """
    xml = "application/xml"
    html = "text/html; charset=UTF-8"
    posts = _posts_de_compra(SITIO_AVISOS)
    # Temas sin una sola palabra en comun con los articulos: asi no hay
    # candidatos a recategorizacion y las tres categorias acaban en noindex,
    # que es la condicion del aviso 4.
    categorias = [
        f"{SITIO_AVISOS}/category/zinc/",
        f"{SITIO_AVISOS}/category/pomelo/",
        f"{SITIO_AVISOS}/category/ukelele/",
    ]
    etiqueta = f"{SITIO_AVISOS}/tag/salon/"
    rutas = {
        f"{SITIO_AVISOS}/robots.txt": (200, "text/plain",
                                       "User-agent: *\nDisallow: /wp-admin/\n"),
        f"{SITIO_AVISOS}/sitemap_index.xml": (200, xml, _index([
            f"{SITIO_AVISOS}/post-sitemap.xml",
            f"{SITIO_AVISOS}/category-sitemap.xml",
            f"{SITIO_AVISOS}/post_tag-sitemap.xml",
        ])),
        f"{SITIO_AVISOS}/post-sitemap.xml": (200, xml, _urlset(posts)),
        f"{SITIO_AVISOS}/category-sitemap.xml": (200, xml, _urlset(categorias)),
        f"{SITIO_AVISOS}/post_tag-sitemap.xml": (200, xml, _urlset([etiqueta])),
        etiqueta: (200, html, _listado(etiqueta, "Salon", posts, 900)),
    }
    for url in categorias:
        nombre = url.rstrip("/").rsplit("/", 1)[-1].capitalize()
        suelto = f"{SITIO_AVISOS}/requisitos-{nombre.lower()}/"
        rutas[url] = (200, html, _listado(url, nombre, [suelto], 300))
    return rutas


class TestSitemapDesactualizado(unittest.TestCase):
    """El sitemap que miente: declara URL que el sitio ya no sirve."""

    def setUp(self):
        rutas, destinos = rutas_con_redirecciones()
        self.batch = run(["redirige.test"],
                         client=ClienteQueRedirige(rutas, destinos))
        self.audit = self.batch.results[0].audit
        self.outreach = build(self.audit)
        self.finding = next(f for f in self.outreach.findings
                            if f.code == CODE_REDIRECT)

    def test_el_escenario_se_midio_de_verdad(self):
        # Sin esto el hallazgo podria estar saliendo de un sitio sin medir.
        self.assertEqual(len(self.audit.archives), 3)
        self.assertEqual(self.audit.post_count, 5)

    def test_la_cifra_es_la_de_las_url_que_no_sirven_lo_que_declaran(self):
        # Tres redirecciones, pero la de la barra final no es un problema.
        self.assertEqual(len(sitemap_redirects(self.audit)), 2)
        self.assertIn("2", self.finding.figure)
        self.assertIn("2 URL", self.finding.headline)

    def test_una_redireccion_de_barra_final_no_cuenta_como_hallazgo(self):
        declaradas = [r.declared for r in sitemap_redirects(self.audit)]
        self.assertNotIn(f"{SITIO_REDIR}/category/dormitorio/", declaradas)
        self.assertEqual(sorted(declaradas), [
            f"{SITIO_REDIR}/category/cocina/",
            f"{SITIO_REDIR}/category/salon/",
        ])

    def test_el_hallazgo_trae_las_tres_piezas_y_la_cifra(self):
        self.assertTrue(self.finding.headline.strip())
        self.assertTrue(self.finding.why.strip())
        self.assertTrue(self.finding.fix.strip())
        self.assertTrue(self.finding.figure.strip())
        self.assertEqual(self.finding.priority, 2)

    def test_cada_ejemplo_nombra_la_url_declarada_y_la_servida(self):
        # Es lo que hace accionable el arreglo: sin el destino, la marca tiene
        # que ir a buscarlo a mano.
        self.assertEqual(len(self.finding.samples), 2)
        muestras = " ".join(self.finding.samples)
        self.assertIn(f"{SITIO_REDIR}/category/salon/", muestras)
        self.assertIn(f"{SITIO_REDIR}/salon/", muestras)
        self.assertIn(f"{SITIO_REDIR}/muebles/cocina/", muestras)

    def test_el_hallazgo_va_al_informe_con_su_verificacion_http(self):
        self.assertEqual(len(self.finding.evidence), 2)
        for linea in self.finding.evidence:
            self.assertIn("HTTP", linea)
            self.assertIn("otra ruta", linea)
        self.assertIn(self.finding.headline, self.outreach.markdown)
        self.assertIn("Verificacion: `", self.outreach.markdown)

    def test_el_mensaje_de_tres_lineas_lo_usa_de_gancho_con_la_cifra(self):
        # Es el unico hallazgo del sitio, asi que encabeza el mensaje.
        self.assertEqual([f.code for f in self.outreach.findings],
                         [CODE_REDIRECT])
        self.assertEqual(len(self.outreach.summary_lines), SUMMARY_LINES)
        self.assertIn("2 URL", self.outreach.summary_lines[0])


class TestSitemapSinRedirecciones(unittest.TestCase):
    """Un sitio sin redirecciones no recibe este hallazgo."""

    def test_un_sitio_limpio_no_lo_genera(self):
        batch = run(["limpio.test"], client=FakeClient(rutas_limpias()))
        audit = batch.results[0].audit
        self.assertEqual(len(audit.archives), 1)
        self.assertEqual(sitemap_redirects(audit), [])
        self.assertEqual(build(audit).findings, [])

    def test_un_sitio_con_otros_hallazgos_tampoco_lo_genera(self):
        # ejemplo.test tiene autor duplicado, finos y recategorizables, y
        # ninguna URL redirigida: el septimo codigo no se contagia.
        batch = run(["ejemplo.test"], client=FakeClient(routes()))
        audit = batch.results[0].audit
        outreach = build(audit)
        self.assertTrue(outreach.findings)
        self.assertEqual(sitemap_redirects(audit), [])
        self.assertNotIn(CODE_REDIRECT, [f.code for f in outreach.findings])


class TestLosOtrosAvisosNoSonEsteHallazgo(unittest.TestCase):
    """Los avisos 1, 2, 4 y 5 no son el sitemap desactualizado.

    La prueba que sostiene la decision de producto: cuatro de las cinco cosas
    que escriben en `audit.warnings` no se le mandan a la marca, y ninguna de
    ellas puede colarse como este hallazgo.
    """

    def setUp(self):
        self.batch = run(["avisos.test"],
                         client=FakeClient(rutas_de_los_otros_avisos()))
        self.audit = self.batch.results[0].audit
        self.outreach = build(self.audit)
        self.avisos = " ".join(self.audit.warnings)

    def test_el_escenario_dispara_los_cuatro_avisos_que_no_van(self):
        # Si este test se cae, el de abajo no prueba nada.
        self.assertIn("robots.txt no declara el sitemap", self.avisos)
        self.assertIn("Existe sitemap de category", self.avisos)
        self.assertIn("Existe sitemap de tag", self.avisos)
        self.assertIn("propone noindex en las 3 categorias", self.avisos)
        self.assertIn("son hubs legitimos", self.avisos)

    def test_ninguno_de_esos_avisos_es_una_redireccion(self):
        self.assertNotIn("redirige a", self.avisos)
        self.assertEqual(sitemap_redirects(self.audit), [])

    def test_ningun_aviso_de_los_otros_cuatro_genera_este_hallazgo(self):
        codigos = [f.code for f in self.outreach.findings]
        self.assertTrue(codigos)  # el sitio si tiene otros hallazgos
        self.assertNotIn(CODE_REDIRECT, codigos)
        self.assertNotIn("sitemap desactualizado", self.outreach.markdown.lower())



if __name__ == "__main__":
    unittest.main()
