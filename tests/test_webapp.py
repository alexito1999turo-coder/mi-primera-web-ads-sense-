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


class TestMemoriaHTTP(unittest.TestCase):
    """La memoria por HTTP, con el almacen en un directorio temporal."""

    @classmethod
    def setUpClass(cls):
        import os
        import tempfile

        cls.tmp = tempfile.TemporaryDirectory()
        cls.antes = os.environ.get("BANCO_DATOS")
        os.environ["BANCO_DATOS"] = cls.tmp.name
        cls.app = Background().__enter__()

    @classmethod
    def tearDownClass(cls):
        import os

        cls.app.__exit__(None, None, None)
        if cls.antes is None:
            os.environ.pop("BANCO_DATOS", None)
        else:
            os.environ["BANCO_DATOS"] = cls.antes
        cls.tmp.cleanup()

    def cuerpo(self, tema: str, n: int = 160) -> str:
        frases = [
            f"El {tema} depende del numero de dormitorios de la vivienda.",
            f"En {tema} la normativa del condado manda sobre la del estado.",
            f"Un {tema} mal dimensionado se nota en la factura de luz.",
        ]
        return " ".join(frases[i % 3] + f" Caso {tema} numero {i}."
                        for i in range(n))

    def test_la_pestana_de_memoria_existe_en_la_pagina(self):
        estado, _ = pedir(self.app.base, "/salud")
        self.assertEqual(estado, 200)
        req = urllib.request.Request(self.app.base + "/")
        with urllib.request.urlopen(req, timeout=10) as r:
            html = r.read().decode()
        self.assertIn('data-panel="memoria"', html)
        self.assertIn("/api/memoria", html)

    def test_cliente_vacio_o_con_ruta_se_rechaza(self):
        for malo in ("", "../etc", "a/b", ".oculto"):
            estado, data = pedir(
                self.app.base, "/api/memoria?cliente=" + malo.replace("/", "%2F"))
            self.assertEqual(estado, 400, f"{malo!r} deberia dar 400")
            self.assertIn("error", data)

    def test_ciclo_completo_guardar_comprobar_y_consultar(self):
        cuerpo = self.cuerpo("coste de instalacion")

        estado, vacio = pedir(self.app.base, "/api/memoria?cliente=ciclo")
        self.assertEqual(estado, 200)
        self.assertEqual(vacio["paginas"], [])

        estado, guardada = pedir(self.app.base, "/api/memoria/pagina", {
            "cliente": "ciclo", "slug": "coste-instalacion", "text": cuerpo,
            "url": "/coste-instalacion", "role": "pilar"}, "POST")
        self.assertEqual(estado, 200)
        self.assertFalse(guardada["solape_previo"]["medido"],
                         "la primera pagina no tenia con que compararse")

        # La misma pagina con otro slug: el solape se ve por HTTP.
        estado, check = pedir(self.app.base, "/api/memoria/comprobar",
                              {"cliente": "ciclo", "text": cuerpo}, "POST")
        self.assertEqual(estado, 200)
        self.assertTrue(check["sitio"]["medido"])
        self.assertGreater(check["sitio"]["valor"], 0.9)
        self.assertEqual(check["sitio"]["contra"], "coste-instalacion")

        # Una distinta, no.
        estado, limpia = pedir(self.app.base, "/api/memoria/comprobar",
                               {"cliente": "ciclo",
                                "text": self.cuerpo("permisos municipales")},
                               "POST")
        self.assertLess(limpia["sitio"]["valor"], 0.1)

        estado, consulta = pedir(self.app.base, "/api/memoria?cliente=ciclo")
        self.assertEqual(len(consulta["paginas"]), 1)
        self.assertEqual(consulta["paginas"][0]["rol"], "pilar")

    def test_lo_declarado_se_guarda_pero_se_avisa(self):
        estado, medida = pedir(self.app.base, "/api/memoria/observacion", {
            "cliente": "obs", "metrica": "cpc", "valor": 1.4,
            "fuente": "medido", "nota": "panel de Ads"}, "POST")
        self.assertEqual(estado, 200)
        self.assertEqual(medida["aviso"], "")

        estado, declarada = pedir(self.app.base, "/api/memoria/observacion", {
            "cliente": "obs", "metrica": "cpc", "valor": 9.9,
            "fuente": "declarado", "nota": "estimacion de la propuesta"}, "POST")
        self.assertEqual(estado, 200)
        self.assertIn("NO alimenta", declarada["aviso"])
        self.assertEqual(declarada["vigentes"], 2)
        self.assertEqual(declarada["medidas"], 1)

    def test_entradas_malas_dan_400_y_no_una_traza(self):
        casos = [
            ("/api/memoria/observacion", {"cliente": "x", "metrica": "cpc",
                                          "valor": "no un numero"}),
            ("/api/memoria/observacion", {"cliente": "x", "metrica": "CPC MAL",
                                          "valor": 1}),
            ("/api/memoria/observacion", {"cliente": "x", "metrica": "cpc",
                                          "valor": 1, "fuente": "inventada"}),
            ("/api/memoria/observacion", {"cliente": "x", "metrica": "cpc",
                                          "valor": float("1e400")}),
            ("/api/memoria/pagina", {"cliente": "x", "slug": "../fuera",
                                     "text": "algo"}),
            ("/api/memoria/pagina", {"cliente": "x", "slug": "ok", "text": ""}),
            ("/api/memoria/comprobar", {"cliente": "x", "text": "  "}),
        ]
        for ruta, cuerpo in casos:
            estado, data = pedir(self.app.base, ruta, cuerpo, "POST")
            self.assertEqual(estado, 400, f"{ruta} {cuerpo} deberia dar 400")
            self.assertIn("error", data)
            self.assertNotIn("Traceback", json.dumps(data))

    def test_la_cartera_avisa_del_mismo_contenido_en_otro_sitio(self):
        cuerpo = ("## Que es\n" + self.cuerpo("sistema aerobico") +
                  "\n## Cuanto cuesta\n" + self.cuerpo("coste del sistema"))
        pedir(self.app.base, "/api/memoria/pagina",
              {"cliente": "sitio-a", "slug": "guia", "text": cuerpo}, "POST")
        estado, check = pedir(self.app.base, "/api/memoria/comprobar",
                              {"cliente": "sitio-b", "text": cuerpo}, "POST")
        self.assertEqual(estado, 200)
        self.assertTrue(check["bloquea"],
                        "el mismo contenido en dos sitios de la cartera bloquea")
        self.assertTrue(any(c["otro"] == "sitio-a" for c in check["cartera"]))

    def test_la_media_de_una_metrica_no_mezcla_lo_declarado(self):
        """Regresion: el panel titulaba «lo que el sistema ha medido» y

        promediaba tambien lo declarado. Es la mezcla que todo el resto del
        sistema evita, y se colo en la unica pieza que la ensena.
        """
        for valor, fuente in ((0.20, "medido"), (0.20, "medido"),
                              (9.00, "declarado")):
            pedir(self.app.base, "/api/memoria/observacion",
                  {"cliente": "mezcla", "metrica": "ctr", "valor": valor,
                   "fuente": fuente, "nota": "n"}, "POST")
        _, estado = pedir(self.app.base, "/api/memoria?cliente=mezcla")
        fila = [m for m in estado["metricas"] if m["nombre"] == "ctr"][0]
        self.assertEqual(fila["observaciones"], 3)
        self.assertEqual(fila["medidas"], 2)
        self.assertEqual(fila["declaradas"], 1)
        self.assertEqual(fila["media"], 0.2, "la media es solo de lo medido")

    def test_una_metrica_solo_declarada_no_tiene_media(self):
        pedir(self.app.base, "/api/memoria/observacion",
              {"cliente": "solodecl", "metrica": "cpc", "valor": 5,
               "fuente": "declarado", "nota": "propuesta"}, "POST")
        _, estado = pedir(self.app.base, "/api/memoria?cliente=solodecl")
        fila = [m for m in estado["metricas"] if m["nombre"] == "cpc"][0]
        self.assertIsNone(fila["media"])
        self.assertEqual(fila["medidas"], 0)


class TestNegocioHTTP(unittest.TestCase):
    """Tarifa e informe por HTTP."""

    @classmethod
    def setUpClass(cls):
        import os
        import tempfile

        cls.tmp = tempfile.TemporaryDirectory()
        cls.antes = os.environ.get("BANCO_DATOS")
        os.environ["BANCO_DATOS"] = cls.tmp.name
        cls.app = Background().__enter__()

    @classmethod
    def tearDownClass(cls):
        import os

        cls.app.__exit__(None, None, None)
        if cls.antes is None:
            os.environ.pop("BANCO_DATOS", None)
        else:
            os.environ["BANCO_DATOS"] = cls.antes
        cls.tmp.cleanup()

    def test_la_tarifa_por_defecto_calcula_y_declara_lo_supuesto(self):
        estado, r = pedir(self.app.base, "/api/tarifa", {}, "POST")
        self.assertEqual(estado, 200)
        self.assertEqual(len(r["planes"]), 3)
        self.assertLess(r["medido"], 100)
        self.assertIn("Lo que este calculo NO cuenta", r["markdown"])

    def test_la_revision_pesa_mas_que_el_modelo_en_todos_los_planes(self):
        _, r = pedir(self.app.base, "/api/tarifa", {}, "POST")
        for plan in r["planes"]:
            self.assertGreater(plan["reparto"]["revision"],
                               plan["reparto"]["modelo"], plan["nombre"])

    def test_una_lista_de_planes_vacia_no_devuelve_los_de_por_defecto(self):
        estado, r = pedir(self.app.base, "/api/tarifa", {"planes": []}, "POST")
        self.assertEqual(estado, 400)
        self.assertIn("al menos un plan", r["error"])

    def test_entradas_malas_de_tarifa_dan_400(self):
        casos = [
            {"modelo": "gpt-inventado"},
            {"coste_hora": "ocho"},
            {"reparaciones": -1},
            {"planes": "tres"},
            {"planes": [{"nombre": "", "precio_mes": 1, "paginas": 1}]},
            {"planes": [{"nombre": "x", "paginas": 0}]},
        ]
        for cuerpo in casos:
            estado, data = pedir(self.app.base, "/api/tarifa", cuerpo, "POST")
            self.assertEqual(estado, 400, f"{cuerpo} deberia dar 400")
            self.assertNotIn("Traceback", json.dumps(data))

    def test_el_informe_sale_del_almacen_de_ese_cliente(self):
        cuerpo = " ".join(f"Frase {i % 3} del coste. Caso numero {i}."
                          for i in range(170))
        pedir(self.app.base, "/api/memoria/pagina",
              {"cliente": "informe", "slug": "una", "text": cuerpo}, "POST")
        pedir(self.app.base, "/api/memoria/observacion",
              {"cliente": "informe", "metrica": "ctr_posicion_1",
               "valor": 0.2, "fuente": "medido", "nota": "GSC"}, "POST")

        estado, r = pedir(self.app.base, "/api/informe",
                          {"cliente": "informe", "periodo": "2026-10"}, "POST")
        self.assertEqual(estado, 200)
        self.assertEqual(r["cliente"], "informe")
        self.assertLess(r["medido"], 100)
        self.assertTrue(r["incognitas"])
        self.assertIn("Lo que todavia no sabemos", r["markdown"])
        # La pagina guardada se cuenta sola: no se teclea.
        hechas = [c for s in r["secciones"] for c in s["cifras"]
                  if c["label"] == "Paginas publicadas"][0]
        self.assertEqual(hechas["valor"], "1")

    def test_un_cliente_sin_nada_no_inventa_un_informe(self):
        estado, r = pedir(self.app.base, "/api/informe",
                          {"cliente": "vacio", "periodo": "2026-10"}, "POST")
        self.assertEqual(estado, 200)
        self.assertTrue(any("canibalizan" in u for u in r["incognitas"]))
        supuestas = [c for s in r["secciones"] for c in s["cifras"]
                     if c["origen"] == "supuesto"]
        self.assertTrue(supuestas, "sin datos, las cifras tienen que ir marcadas")
