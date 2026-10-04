"""Datos propios con procedencia.

Este modulo existe porque habia un agujero en el diseno: el generador bloquea
cualquier pagina sin dato propio y nada producia uno. Las pruebas verifican que
el circulo se cierra, incluido que la frase que escribe este modulo pasa el
motor de citabilidad.
"""

import tempfile
import unittest
from pathlib import Path

from citability.score import analyse
from dataset.aggregate import Figure, compute, publishable, to_own_data
from dataset.asset import build
from dataset.records import Provenance, Record, load

CABECERA = "valor,unidad,fuente,fecha,metodo,condado\n"


def csv_con(filas: list[str]) -> Path:
    path = Path(tempfile.mkdtemp()) / "d.csv"
    path.write_text(CABECERA + "".join(filas), encoding="utf-8")
    return path


def muestra(n: int = 12, condado: str = "Travis", base: int = 14000) -> Path:
    return csv_con([
        f"{base + i * 137},$,Empresa {i},2026-0{(i % 6) + 1}-1{i % 9},"
        f"presupuesto pedido por telefono,{condado}\n"
        for i in range(n)
    ])


class TestProcedencia(unittest.TestCase):
    def test_sin_fuente_no_vale(self):
        self.assertFalse(Provenance(source="", collected_at="2026-01-01",
                                    method="presupuesto").valid)

    def test_sin_metodo_no_vale(self):
        self.assertFalse(Provenance(source="X", collected_at="2026-01-01",
                                    method="").valid)

    def test_fecha_mal_formada_no_vale(self):
        p = Provenance(source="X", collected_at="enero 2026", method="presupuesto")
        self.assertFalse(p.valid)
        self.assertTrue(any("fecha" in x for x in p.problems()))

    def test_completa_vale(self):
        self.assertTrue(Provenance(source="X", collected_at="2026-01-01",
                                   method="presupuesto").valid)

    def test_un_registro_sin_procedencia_no_es_usable(self):
        self.assertFalse(Record(value=1.0, unit="$").usable)


class TestCarga(unittest.TestCase):
    def test_descarta_y_dice_por_que(self):
        path = csv_con([
            "14000,$,Empresa A,2026-01-05,presupuesto,Travis\n",
            "15000,$,,2026-01-06,presupuesto,Travis\n",
            "16000,$,Empresa C,,presupuesto,Travis\n",
            "no-numero,$,Empresa D,2026-01-08,presupuesto,Travis\n",
        ])
        data = load(path, name="Coste", unit="$")
        self.assertEqual(data.size, 1)
        self.assertEqual(len(data.rejected), 3)
        motivos = " ".join(m for _f, ms in data.rejected for m in ms)
        self.assertIn("sin fuente", motivos)
        self.assertIn("fecha", motivos)
        self.assertIn("numero", motivos)

    def test_las_columnas_libres_son_dimensiones(self):
        data = load(muestra(), name="Coste")
        self.assertIn("condado", data.dimensions())

    def test_el_periodo_es_el_real_no_uno_mas_amplio(self):
        path = csv_con(["14000,$,A,2026-03-01,presupuesto,Travis\n",
                        "15000,$,B,2026-03-20,presupuesto,Travis\n"])
        self.assertEqual(load(path).period, "2026")

    def test_sin_columna_de_valor_falla_con_mensaje_util(self):
        path = Path(tempfile.mkdtemp()) / "x.csv"
        path.write_text("fuente,fecha\nA,2026-01-01\n", encoding="utf-8")
        with self.assertRaises(ValueError) as ctx:
            load(path)
        self.assertIn("Cabeceras", str(ctx.exception))


class TestAgregacion(unittest.TestCase):
    def test_muestra_pequena_no_es_publicable(self):
        data = load(muestra(n=3), name="Coste")
        figura = compute(data, "mediana")[0]
        self.assertFalse(figura.publishable)
        self.assertIn("anecdota", figura.why_not)

    def test_muestra_suficiente_si_lo_es(self):
        figura = compute(load(muestra(n=12), name="Coste"), "mediana")[0]
        self.assertTrue(figura.publishable)

    def test_un_percentil_exige_mas_muestra_que_una_mediana(self):
        data = load(muestra(n=12), name="Coste")
        self.assertTrue(compute(data, "mediana")[0].publishable)
        self.assertFalse(compute(data, "p75")[0].publishable)

    def test_agrupa_por_dimension(self):
        path = csv_con(
            [f"{14000 + i},$,E{i},2026-01-0{(i % 9) + 1},presupuesto,Travis\n" for i in range(10)]
            + [f"{16000 + i},$,F{i},2026-02-0{(i % 9) + 1},presupuesto,Bexar\n" for i in range(9)]
            + ["21000,$,Z,2026-03-01,presupuesto,Harris\n"]
        )
        figuras = compute(load(path, name="Coste"), "mediana", group_by=["condado"])
        self.assertEqual(len(figuras), 3)
        buenas = publishable(figuras)
        self.assertEqual({f.where for f in buenas}, {"Travis", "Bexar"})

    def test_devuelve_tambien_las_no_publicables(self):
        # Esconderlas ocultaria que existen; el informe debe poder decir por que
        # una no vale.
        data = load(muestra(n=2), name="Coste")
        self.assertEqual(len(compute(data, "mediana")), 1)

    def test_no_redondea_la_cifra_a_un_numero_bonito(self):
        path = csv_con([f"1423{i},$,E{i},2026-01-0{i + 1},presupuesto,Travis\n"
                        for i in range(9)])
        figura = compute(load(path, name="Coste"), "mediana")[0]
        self.assertIn("14.23", figura.formatted)

    def test_marca_la_cifra_redonda_por_casualidad(self):
        figura = Figure(label="x", statistic="mediana", value=14000, unit="$", n=20)
        self.assertTrue(figura.round_by_chance)
        otra = Figure(label="x", statistic="mediana", value=14237, unit="$", n=20)
        self.assertFalse(otra.round_by_chance)


class TestCierreDelCirculo(unittest.TestCase):
    """Lo que mide este modulo es lo que la compuerta del generador exigia."""

    def test_la_cifra_se_convierte_en_dato_propio_del_brief(self):
        figura = compute(load(muestra(n=12), name="Coste de instalacion"), "mediana")[0]
        propio = to_own_data(figura, "Coste medio")
        self.assertTrue(propio.usable)
        self.assertEqual(propio.marker, figura.formatted)

    def test_una_cifra_no_publicable_no_puede_ser_dato_propio(self):
        figura = compute(load(muestra(n=3), name="Coste"), "mediana")[0]
        with self.assertRaises(ValueError):
            to_own_data(figura)

    def test_la_frase_que_escribe_pasa_el_motor_de_citabilidad(self):
        # Es la prueba que une dos modulos: lo que produce el de datos tiene que
        # ser citable segun el de citabilidad, sin retocarlo a mano.
        figura = compute(load(muestra(n=20), name="Coste de instalacion"), "mediana")[0]
        frase = figura.sentence("El coste de instalacion de un sistema septico aerobico")
        informe = analyse("## ¿Cuánto cuesta?\n\n" + frase)
        self.assertTrue(informe.liftable, "la frase del modulo de datos debe ser citable")
        self.assertGreaterEqual(informe.liftable[0].total, 70)

    def test_la_frase_nombra_el_sujeto_la_cifra_el_ano_y_el_metodo(self):
        figura = compute(load(muestra(n=20), name="Coste"), "mediana")[0]
        frase = figura.sentence("El coste de instalacion")
        self.assertIn("El coste de instalacion", frase)
        self.assertIn("2026", frase)
        self.assertIn("muestra propia", frase)


class TestActivoEnlazable(unittest.TestCase):
    def setUp(self):
        path = csv_con(
            [f"{14000 + i * 53},$,E{i},2026-0{(i % 6) + 1}-1{i % 9},"
             f"presupuesto pedido por telefono,Travis\n" for i in range(10)]
            + [f"{16000 + i * 61},$,F{i},2026-0{(i % 6) + 1}-1{i % 9},"
               f"presupuesto pedido por telefono,Bexar\n" for i in range(9)]
            + ["21000,$,Z,2026-03-01,presupuesto pedido por telefono,Harris\n"]
        )
        self.page = build(
            load(path, name="Coste de instalacion", unit="$"),
            title="Cuanto cuesta instalar un sistema septico aerobico en Texas",
            subject="El coste de instalacion de un sistema septico aerobico",
            group_by=["condado"], author="el equipo",
        )

    def test_publica_las_buenas_y_retiene_las_pequenas(self):
        self.assertTrue(self.page.figures)
        self.assertEqual([f.where for f in self.page.withheld], ["Harris"])

    def test_dice_lo_que_no_publica_y_por_que(self):
        self.assertIn("Lo que no publicamos", self.page.markdown)
        self.assertIn("Harris", self.page.markdown)

    def test_no_repite_el_lugar_dos_veces_en_la_misma_frase(self):
        # "en Bexar ... en Bexar" era el resultado de poner el lugar en el
        # sujeto y dejar que la frase lo anadiera otra vez.
        for frase in self.page.markdown.split("\n"):
            if "Travis" in frase and frase.startswith("El coste"):
                self.assertEqual(frase.count("Travis"), 1, frase)

    def test_la_pregunta_esta_bien_escrita(self):
        self.assertNotIn("cuesta instalacion de", self.page.markdown.lower())
        self.assertIn("?", self.page.markdown)

    def test_declara_el_metodo_y_las_descartadas(self):
        self.assertIn("## Metodo", self.page.markdown)
        self.assertIn("presupuesto pedido por telefono", self.page.markdown)

    def test_la_pagina_entera_es_citable(self):
        informe = analyse(self.page.markdown)
        self.assertGreaterEqual(len(informe.liftable), 2)
        self.assertGreater(informe.score, 55)


if __name__ == "__main__":
    unittest.main()
