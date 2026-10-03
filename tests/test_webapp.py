"""La aplicacion entera, por HTTP, contra el WordPress del banco.

Esta es la prueba que dice si existe un producto y no solo un motor: va del
cliente HTTP al servidor, al trabajo en segundo plano, al auditor, y de ahi por
la red a un WordPress de verdad.
"""

import json
import unittest
import urllib.error
import urllib.request

from harness.wpsite import LocalWordPress
from webapp.server import Background


def pedir(base: str, ruta: str, cuerpo=None, metodo="GET"):
    datos = json.dumps(cuerpo).encode() if cuerpo is not None else None
    req = urllib.request.Request(
        base + ruta, data=datos, method=metodo,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            payload = r.read()
            return r.status, (json.loads(payload) if payload else {})
    except urllib.error.HTTPError as exc:
        payload = exc.read()
        return exc.code, (json.loads(payload) if payload else {})


class TestServidor(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = Background().__enter__()

    @classmethod
    def tearDownClass(cls):
        cls.app.__exit__(None, None, None)

    def test_sirve_la_pagina(self):
        with urllib.request.urlopen(self.app.base + "/") as r:
            html = r.read().decode()
        self.assertEqual(r.status, 200)
        self.assertIn("Banco de pruebas SEO-GEO", html)
        self.assertIn("aud-go", html)

    def test_salud(self):
        status, body = pedir(self.app.base, "/salud")
        self.assertEqual(status, 200)
        self.assertTrue(body["ok"])

    def test_ruta_inexistente_da_404_json(self):
        status, body = pedir(self.app.base, "/api/nada")
        self.assertEqual(status, 404)
        self.assertIn("error", body)

    def test_cuerpo_no_json_da_400_con_mensaje(self):
        req = urllib.request.Request(
            self.app.base + "/api/citabilidad", data=b"no soy json",
            method="POST", headers={"Content-Type": "application/json"},
        )
        try:
            urllib.request.urlopen(req, timeout=10)
            self.fail("deberia rechazarlo")
        except urllib.error.HTTPError as exc:
            self.assertEqual(exc.code, 400)
            self.assertIn("JSON", json.loads(exc.read())["error"])

    def test_un_error_interno_se_contesta_no_cuelga_la_conexion(self):
        # Esta prueba existe porque paso: do_GET no tenia manejo de errores y
        # un NameError cerraba la conexion sin contestar. El cliente veia
        # «el servidor cerro sin responder», que no dice donde esta el fallo.
        import webapp.server as server

        original = server.Handler._get

        def explota(self):
            raise RuntimeError("fallo a proposito")

        server.Handler._get = explota
        try:
            status, body = pedir(self.app.base, "/salud")
            self.assertEqual(status, 500)
            self.assertIn("fallo a proposito", body["error"])
        finally:
            server.Handler._get = original

    def test_el_servidor_no_se_ata_a_la_red(self):
        # 127.0.0.1 y nada mas: una herramienta local no se abre al mundo.
        self.assertEqual(self.app.server.server_address[0], "127.0.0.1")


class TestCitabilidadPorHTTP(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = Background().__enter__()

    @classmethod
    def tearDownClass(cls):
        cls.app.__exit__(None, None, None)

    def test_un_texto_citable_puntua_alto(self):
        texto = ("# Costes\n\n## Cuanto cuesta en Texas?\n\n"
                 "La instalacion completa costo 14.237 $ de mediana en Texas en "
                 "2026, sobre una muestra propia de 40 presupuestos reales.\n")
        status, body = pedir(self.app.base, "/api/citabilidad", {"text": texto}, "POST")
        self.assertEqual(status, 200)
        self.assertGreater(body["score"], 55)
        self.assertEqual(len(body["liftable"]), 1)

    def test_un_texto_flojo_puntua_bajo_y_da_arreglos(self):
        texto = ("# Costes\n\n## Intro\n\nUn sistema trata el agua. "
                 "Este cuesta unos 14.000 $ de media.\n")
        status, body = pedir(self.app.base, "/api/citabilidad", {"text": texto}, "POST")
        self.assertEqual(status, 200)
        self.assertLess(body["score"], 30)
        self.assertEqual(body["liftable"], [])
        self.assertTrue(body["fixes"])

    def test_texto_vacio_da_400(self):
        status, body = pedir(self.app.base, "/api/citabilidad", {"text": "  "}, "POST")
        self.assertEqual(status, 400)
        self.assertIn("Pega un texto", body["error"])


class TestOportunidadPorHTTP(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = Background().__enter__()

    @classmethod
    def tearDownClass(cls):
        cls.app.__exit__(None, None, None)

    CSV = ("Consulta,Clics,Impresiones,Posicion\n"
           "que es un sistema septico aerobico,160,10000,12\n"
           "cuanto cuesta un sistema septico aerobico,40,2200,13\n"
           "instalador septico cerca de mi,12,900,11.5\n")

    def test_ordena_por_valor_y_no_por_clics(self):
        status, body = pedir(self.app.base, "/api/oportunidad", {"csv": self.CSV}, "POST")
        self.assertEqual(status, 200)
        self.assertIn("que es", body["by_clicks"][0]["subject"])
        self.assertIn("instalador", body["by_value"][0]["subject"])

    def test_declara_lo_que_se_queda_la_respuesta_generada(self):
        _, body = pedir(self.app.base, "/api/oportunidad", {"csv": self.CSV}, "POST")
        self.assertGreater(body["totals"]["lost"], 0)

    def test_sin_impresiones_da_400_util(self):
        status, body = pedir(self.app.base, "/api/oportunidad",
                             {"csv": "Consulta,Clics\nalgo,5\n"}, "POST")
        self.assertEqual(status, 400)
        self.assertIn("impresiones", body["error"])

    def test_sin_posicion_lo_dice(self):
        status, body = pedir(self.app.base, "/api/oportunidad",
                             {"csv": "Consulta,Impresiones\nalgo,500\n"}, "POST")
        self.assertEqual(status, 400)
        self.assertIn("posicion", body["error"])


class TestClustersPorHTTP(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = Background().__enter__()

    @classmethod
    def tearDownClass(cls):
        cls.app.__exit__(None, None, None)

    CSV = ("Keyword,Search Volume,CPC\n"
           "cuanto cuesta un sistema septico aerobico,2000,14\n"
           "precio sistema septico aerobico,1500,13\n"
           "alarma septica pitando,900,3\n"
           "instalador septico cerca de mi,1100,18\n"
           "que es nitrificacion,12000,0.5\n")

    def test_devuelve_plan_con_solape_cero(self):
        status, body = pedir(self.app.base, "/api/clusters",
                             {"csv": self.CSV, "cap": 24}, "POST")
        self.assertEqual(status, 200)
        self.assertTrue(body["validation"]["passed"])
        terminos = [p["term"] for m in body["months"] for p in m["pages"]]
        self.assertEqual(len(terminos), len(set(terminos)))

    def test_respeta_el_tope_mensual(self):
        _, body = pedir(self.app.base, "/api/clusters",
                        {"csv": self.CSV, "cap": 2}, "POST")
        for mes in body["months"]:
            self.assertLessEqual(len(mes["pages"]), 2)

    def test_sin_columna_de_keyword_da_400_que_nombra_las_cabeceras(self):
        status, body = pedir(self.app.base, "/api/clusters",
                             {"csv": "Volumen,CPC\n900,3\n"}, "POST")
        self.assertEqual(status, 400)
        self.assertIn("Cabeceras encontradas", body["error"])


class TestAuditoriaDePuntaAPunta(unittest.TestCase):
    """El stack completo: HTTP -> servidor -> hilo -> auditor -> HTTP -> WordPress."""

    def test_auditoria_real_a_traves_de_la_aplicacion(self):
        import time

        with LocalWordPress() as sitio, Background(allow_private=True) as app:
            status, trabajo = pedir(
                app.base, "/api/auditoria",
                {"site": sitio.base, "interval": 0.01, "max_archives": 20}, "POST",
            )
            self.assertEqual(status, 202)
            self.assertEqual(trabajo["state"], "corriendo")

            # Esperar como lo hace la pagina: preguntando por el progreso.
            vio_progreso = False
            for _ in range(200):
                _, estado = pedir(app.base, f"/api/job/{trabajo['id']}")
                if estado["step"]:
                    vio_progreso = True
                if estado["state"] != "corriendo":
                    break
                time.sleep(0.05)
            self.assertEqual(estado["state"], "hecho", estado.get("error"))
            self.assertTrue(vio_progreso, "el progreso debe poder consultarse")

            status, payload = pedir(app.base, f"/api/job/{trabajo['id']}/resultado")
            self.assertEqual(status, 200)
            resultado = payload["result"]

            # Lo que tiene que haber encontrado en ese WordPress.
            self.assertEqual(resultado["summary"]["archives"], 6)
            self.assertEqual(resultado["summary"]["indexable"], 5)
            acciones = {a["action"] for a in resultado["archives"]}
            self.assertIn("desactivar_archivo", acciones)
            self.assertIn("recategorizar", acciones)

            hub = next(a for a in resultado["archives"] if "mantenimiento" in a["url"])
            self.assertEqual(hub["verdict"], "hub")
            self.assertEqual(hub["action"], "ninguna")

            # Cada fila lleva su verificacion con respuesta HTTP.
            for archivo in resultado["archives"]:
                self.assertIn("HTTP 200", archivo["verification"])

    def test_un_trabajo_que_no_existe_da_404(self):
        with Background() as app:
            status, _ = pedir(app.base, "/api/job/noexiste")
            self.assertEqual(status, 404)

    def test_no_audita_direcciones_internas_por_defecto(self):
        # Sin --allow-private, apuntar a la red local se rechaza: si no, la
        # herramienta seria un escaner de la red de quien la levanta.
        with Background(allow_private=False) as app:
            status, body = pedir(app.base, "/api/auditoria",
                                 {"site": "http://192.168.1.1"}, "POST")
            self.assertEqual(status, 400)
            self.assertIn("interna", body["error"])

    def test_un_dominio_invalido_da_400_antes_de_arrancar_nada(self):
        with Background() as app:
            status, body = pedir(app.base, "/api/auditoria", {"site": "no-dominio"}, "POST")
            self.assertEqual(status, 400)
            self.assertIn("no parece un dominio", body["error"])


if __name__ == "__main__":
    unittest.main()
