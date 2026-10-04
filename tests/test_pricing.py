"""Economia unitaria: que cuesta una pagina y que se come el margen."""

import unittest

from generator.llm import Usage
from pricing.plans import (
    MARGEN_MINIMO,
    NO_CONTADO,
    Plan,
    curva_de_cartera,
    evaluar,
    paginas_maximas,
    precio_minimo,
    punto_muerto,
    sensibilidad,
    tarifa,
)
from pricing.unit import (
    DESCUENTO_LOTES,
    MEDIDO,
    SUPUESTO,
    TARIFAS,
    coste_modelo,
    por_pagina,
)

USO = Usage(input_tokens=4000, output_tokens=6000, cache_write_tokens=3000,
            cache_read_tokens=24000, calls=1)
BASE = dict(usage=USO, reparaciones=0.6, coste_hora=45.0,
            herramientas_mes=120.0, lotes=True)


class TestUsage(unittest.TestCase):
    def test_lee_el_uso_del_sdk(self):
        class Uso:
            input_tokens = 10
            output_tokens = 20
            cache_creation_input_tokens = 5
            cache_read_input_tokens = 100

        class Mensaje:
            usage = Uso()

        u = Usage.from_message(Mensaje())
        self.assertEqual((u.input_tokens, u.output_tokens), (10, 20))
        self.assertEqual((u.cache_write_tokens, u.cache_read_tokens), (5, 100))
        self.assertEqual(u.total_input, 115)

    def test_un_sdk_sin_campos_de_cache_no_revienta(self):
        class Mensaje:
            class usage:
                input_tokens = 7
                output_tokens = 3

        u = Usage.from_message(Mensaje())
        self.assertEqual(u.cache_read_tokens, 0)
        self.assertEqual(u.calls, 1)

    def test_una_respuesta_sin_uso_cuenta_la_llamada(self):
        u = Usage.from_message(object())
        self.assertEqual(u.calls, 1)
        self.assertEqual(u.total_input, 0)

    def test_se_acumula(self):
        total = Usage()
        total.add(USO)
        total.add(USO)
        self.assertEqual(total.calls, 2)
        self.assertEqual(total.output_tokens, 12000)


class TestCosteModelo(unittest.TestCase):
    def test_el_cache_se_cobra_distinto_que_la_entrada(self):
        caro = coste_modelo(Usage(input_tokens=10000, calls=1))
        barato = coste_modelo(Usage(cache_read_tokens=10000, calls=1))
        self.assertGreater(caro, barato * 5,
                           "leer de cache tiene que ser mucho mas barato")

    def test_lotes_cuesta_la_mitad(self):
        entero = coste_modelo(USO)
        mitad = coste_modelo(USO, lotes=True)
        self.assertAlmostEqual(mitad, entero * DESCUENTO_LOTES, places=6)

    def test_un_modelo_sin_tarifa_falla_en_vez_de_estimar(self):
        with self.assertRaises(KeyError):
            coste_modelo(USO, modelo="modelo-inventado")

    def test_todas_las_tarifas_tienen_las_cuatro_lineas(self):
        for modelo, tarifa_ in TARIFAS.items():
            self.assertEqual(set(tarifa_), {"in", "out", "cache_write",
                                            "cache_read"}, modelo)
            self.assertLess(tarifa_["cache_read"], tarifa_["in"], modelo)


class TestPorPagina(unittest.TestCase):
    def test_sin_uso_medido_el_coste_de_modelo_no_se_inventa(self):
        coste = por_pagina(usage=None, minutos_revision=12, coste_hora=45)
        self.assertEqual(coste.modelo, 0.0)
        entrada = [e for e in coste.entradas if "tokens" in e.nombre][0]
        self.assertEqual(entrada.origen, SUPUESTO)
        self.assertIn("no se ha medido", entrada.nota)

    def test_las_reparaciones_multiplican_el_modelo_no_la_revision(self):
        sin = por_pagina(**dict(BASE, reparaciones=0.0))
        con = por_pagina(**dict(BASE, reparaciones=1.0))
        self.assertAlmostEqual(con.modelo, sin.modelo * 2, places=3)
        self.assertEqual(con.revision, sin.revision)

    def test_la_revision_manda_sobre_el_modelo(self):
        """Es la conclusion del modulo, y conviene que un test la sostenga."""
        coste = por_pagina(**BASE)
        self.assertGreater(coste.reparto["revision"], coste.reparto["modelo"] * 5)

    def test_los_minutos_cronometrados_cuentan_como_medidos(self):
        supuesto = por_pagina(**BASE)
        medido = por_pagina(**dict(BASE, minutos_medidos=True))
        self.assertGreater(medido.medido, supuesto.medido)
        self.assertEqual(medido.total, supuesto.total,
                         "marcar algo como medido no cambia el numero")

    def test_el_reparto_de_un_coste_cero_no_divide_por_cero(self):
        vacio = por_pagina(usage=None, minutos_revision=0, coste_hora=0)
        self.assertEqual(vacio.reparto, {"modelo": 0, "revision": 0,
                                         "herramientas": 0})


class TestPlanes(unittest.TestCase):
    def planes(self):
        return [Plan("Inicio", 490, 8, minutos_revision=14),
                Plan("Crecimiento", 1290, 24),
                Plan("Cartera", 2900, 60, minutos_revision=9)]

    def test_un_plan_que_pierde_dinero_se_declara(self):
        malo = Plan("Regalado", 50, 24)
        resultado = evaluar(malo, **BASE)
        self.assertLess(resultado.margen_mes, 0)
        self.assertFalse(resultado.sano)
        self.assertIn("AJUSTADO", resultado.describe())

    def test_la_sensibilidad_mueve_una_palanca_cada_vez(self):
        casos = sensibilidad(self.planes()[1], BASE)
        self.assertEqual(len(casos), 3)
        self.assertEqual(
            {c.palanca for c in casos},
            {"Minutos de revision por pagina", "Reparaciones por pagina",
             "Precio negociado"})

    def test_la_revision_mueve_el_margen_mas_que_las_reparaciones(self):
        casos = {c.palanca: c for c in sensibilidad(self.planes()[1], BASE)}
        self.assertGreater(casos["Minutos de revision por pagina"].caida,
                           casos["Reparaciones por pagina"].caida)

    def test_un_plan_sin_punto_muerto_lo_dice(self):
        dato = punto_muerto(Plan("Regalado", 50, 24), 4000, **BASE)
        self.assertIsNone(dato["clientes"])
        self.assertIn("agujero que crece", dato["lectura"])

    def test_el_punto_muerto_dice_las_horas_de_revision(self):
        dato = punto_muerto(self.planes()[1], 4000, **BASE)
        self.assertGreater(dato["clientes"], 0)
        self.assertGreater(dato["horas_revision_mes"], 0)
        self.assertIn("horas de revision", dato["lectura"])

    def test_la_tarifa_declara_lo_que_no_cuenta(self):
        texto = tarifa(self.planes(), fijos_mes=4000, **BASE).to_markdown()
        self.assertIn("Lo que este calculo NO cuenta", texto)
        for nombre, _ in NO_CONTADO:
            self.assertIn(nombre, texto)

    def test_la_tarifa_marca_los_planes_fragiles(self):
        frágil = Plan("Al limite", 420, 24)
        resultado = tarifa([frágil], **BASE)
        self.assertTrue(
            resultado.planes_fragiles,
            f"con margen {resultado.resultados[0].margen_pct}% y una palanca "
            f"movida deberia caer por debajo del {MARGEN_MINIMO * 100:.0f}%")

    def test_la_tarifa_dice_cuanto_de_si_misma_es_suposicion(self):
        resultado = tarifa(self.planes(), **BASE)
        self.assertLess(resultado.medido, 100)
        self.assertIn("mediciones", resultado.to_markdown())


class TestRepartoDeHerramientas(unittest.TestCase):
    """Regresion del error que cambiaba la conclusion del modulo.

    Dividir las herramientas entre las paginas DE UN PLAN supone que cada
    cliente paga su propia caja entera. Con ese reparto, un plan pequeno
    salia inviable por un artefacto del calculo y no por su economia: yo
    mismo llegue a decir que el plan Core de la web era una trampa, y era
    mio el error.
    """

    def test_el_mismo_coste_de_herramientas_no_puede_salir_distinto_por_plan(self):
        pequeno = por_pagina(**dict(BASE, paginas_mes=8, paginas_cartera=300))
        grande = por_pagina(**dict(BASE, paginas_mes=60, paginas_cartera=300))
        self.assertEqual(pequeno.herramientas, grande.herramientas)

    def test_sin_cartera_declarada_supone_un_solo_cliente_y_lo_dice(self):
        coste = por_pagina(**dict(BASE, paginas_mes=8))
        entrada = [e for e in coste.entradas if "herramientas" in e.nombre][0]
        self.assertIn("un solo cliente", entrada.nota)

    def test_con_cartera_declarada_lo_dice_tambien(self):
        coste = por_pagina(**dict(BASE, paginas_mes=8, paginas_cartera=300))
        entrada = [e for e in coste.entradas if "herramientas" in e.nombre][0]
        self.assertIn("toda la cartera", entrada.nota)
        self.assertLess(coste.herramientas,
                        por_pagina(**dict(BASE, paginas_mes=8)).herramientas)


class TestSolver(unittest.TestCase):
    def test_el_precio_robusto_es_mayor_que_el_del_caso_bueno(self):
        plan = Plan("Core", 299, 12)
        flojo = precio_minimo(plan, robusto=False, **BASE)["precio"]
        duro = precio_minimo(plan, robusto=True, **BASE)["precio"]
        self.assertGreaterEqual(duro, flojo)

    def test_el_precio_propuesto_alcanza_el_margen(self):
        plan = Plan("Core", 299, 12)
        dato = precio_minimo(plan, robusto=False, **BASE)
        self.assertGreaterEqual(dato["margen_resultante"],
                                MARGEN_MINIMO * 100 - 2)

    def test_un_margen_objetivo_imposible_se_rechaza(self):
        with self.assertRaises(ValueError):
            precio_minimo(Plan("x", 100, 1), margen_objetivo=1.0, **BASE)

    def test_las_paginas_maximas_dejan_el_margen_pedido(self):
        plan = Plan("Core", 299, 12)
        dato = paginas_maximas(plan, **BASE)
        ajustado = Plan("Core", 299, max(dato["paginas"], 1))
        self.assertGreaterEqual(evaluar(ajustado, **BASE).margen_pct,
                                MARGEN_MINIMO * 100 - 1)

    def test_subir_el_precio_y_bajar_paginas_son_las_dos_salidas(self):
        plan = Plan("Core", 299, 12)
        self.assertGreater(precio_minimo(plan, **BASE)["precio"], 299)
        self.assertLess(paginas_maximas(plan, **BASE)["paginas"], 12)


class TestCurvaDeCartera(unittest.TestCase):
    def test_el_margen_sube_con_el_tamano_de_la_cartera(self):
        curva = curva_de_cartera(Plan("Core", 299, 12), **BASE)
        margenes = [p["margen_pct"] for p in curva["puntos"]]
        self.assertEqual(margenes, sorted(margenes),
                         "mas clientes reparten el coste fijo, nunca al reves")

    def test_dice_a_partir_de_cuantos_clientes_aguanta(self):
        curva = curva_de_cartera(Plan("Core", 299, 12), **BASE)
        self.assertEqual(curva["umbral_clientes"], 2)
        self.assertIn("no aguanta con pocos clientes", curva["lectura"])

    def test_un_plan_rentable_desde_el_primer_cliente_lo_dice(self):
        curva = curva_de_cartera(Plan("Scale", 699, 24), **BASE)
        self.assertEqual(curva["umbral_clientes"], 1)
        self.assertIn("primer cliente", curva["lectura"])

    def test_un_plan_que_no_escala_no_culpa_a_la_escala(self):
        curva = curva_de_cartera(Plan("Regalado", 60, 24), **BASE)
        self.assertIsNone(curva["umbral_clientes"])
        self.assertIn("no es la escala", curva["lectura"])
