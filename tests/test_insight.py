import tempfile
import unittest
from pathlib import Path

from clusters.graph import build as build_graph
from clusters.keywords import Keyword
from insight.curves import click_retention, click_value, ctr_at
from insight.gsc import Report, Row, load
from insight.opportunity import (
    BAND_FAR,
    BAND_NEAR,
    BAND_STRIKING,
    BAND_TOP,
    BAND_UNKNOWN,
    analyse,
    band_of,
    evaluate,
)
from insight.reallocate import (
    DECISION_INVEST,
    DECISION_RETIRE,
    DECISION_UNKNOWN,
    reallocate,
)

SITIO = "https://ejemplo.test"


class TestCurvas(unittest.TestCase):
    def test_el_ctr_cae_con_la_posicion(self):
        self.assertGreater(ctr_at(1), ctr_at(3))
        self.assertGreater(ctr_at(3), ctr_at(12))

    def test_interpola_entre_posiciones(self):
        self.assertTrue(ctr_at(13) > ctr_at(12.5) > ctr_at(12) or
                        ctr_at(12) > ctr_at(12.5) > ctr_at(13))

    def test_mas_alla_de_la_curva_hay_un_suelo(self):
        self.assertGreater(ctr_at(80), 0)

    def test_la_informacional_retiene_menos_clic(self):
        self.assertLess(click_retention("informational"),
                        click_retention("transactional"))

    def test_el_clic_transaccional_vale_mas(self):
        self.assertGreater(click_value("transactional"), click_value("informational"))


class TestBandas(unittest.TestCase):
    def test_bandas(self):
        self.assertEqual(band_of(2), BAND_TOP)
        self.assertEqual(band_of(8), BAND_NEAR)
        self.assertEqual(band_of(15), BAND_STRIKING)
        self.assertEqual(band_of(40), BAND_FAR)
        self.assertEqual(band_of(0), BAND_UNKNOWN)

    def test_sin_posicion_no_se_mide(self):
        self.assertFalse(evaluate(Row(query="x", impressions=500)).measurable)


class TestOportunidad(unittest.TestCase):
    def setUp(self):
        self.filas = [
            Row(query="que es un sistema septico aerobico",
                impressions=10000, clicks=160, position=12.0),
            Row(query="cuanto cuesta un sistema septico aerobico",
                impressions=2200, clicks=40, position=13.0),
            Row(query="instalador septico cerca de mi",
                impressions=900, clicks=12, position=11.5),
            Row(query="como funciona la nitrificacion",
                impressions=4000, clicks=50, position=14.0),
        ]
        self.report = analyse(Report(rows=self.filas))

    def test_el_valor_da_la_vuelta_al_orden(self):
        # Es el resultado que justifica el modulo: por clics gana la
        # informacional de 10.000 impresiones; por valor, la transaccional de 900.
        por_clics = self.report.ranked_by_clicks[0].subject
        por_valor = self.report.ranked[0].subject
        self.assertIn("que es", por_clics)
        self.assertIn("instalador", por_valor)

    def test_el_descuento_por_aio_solo_no_bastaba(self):
        # Comprobado con numeros: ordenar por clics ajustados seguia poniendo
        # primera la informacional. Sin esta prueba la afirmacion del modulo
        # seria falsa.
        por_clics_ajustados = sorted(
            self.report.measurable_items, key=lambda o: -o.adjusted_gain
        )
        self.assertIn("que es", por_clics_ajustados[0].subject)

    def test_declara_lo_que_se_queda_la_respuesta_generada(self):
        informacional = next(o for o in self.report.ranked if "que es" in o.subject)
        self.assertGreater(informacional.lost_to_aio, 0)

    def test_las_filas_que_bajan_son_las_informacionales(self):
        bajan = [sujeto for sujeto, _a, _d in self.report.demoted()]
        self.assertTrue(any("que es" in s for s in bajan))

    def test_las_que_suben_son_las_de_intencion_alta(self):
        suben = [sujeto for sujeto, _a, _d in self.report.promoted()]
        self.assertTrue(any("instalador" in s for s in suben))

    def test_descarta_el_ruido_de_volumen_bajo(self):
        report = analyse(Report(rows=[Row(query="x", impressions=5, position=40)]))
        self.assertEqual(report.skipped_low_volume, 1)
        self.assertEqual(report.ranked, [])

    def test_declara_que_los_pesos_son_priores(self):
        self.assertIn("priores", self.report.describe())


class TestCarga(unittest.TestCase):
    def _csv(self, content: str) -> Path:
        path = Path(tempfile.mkdtemp()) / "gsc.csv"
        path.write_text(content, encoding="utf-8")
        return path

    def test_lee_la_exportacion_en_ingles(self):
        path = self._csv("Query,Clicks,Impressions,Position\nbomba,12,900,11.5\n")
        report = load(path)
        self.assertEqual(report.rows[0].impressions, 900)
        self.assertAlmostEqual(report.rows[0].position, 11.5)

    def test_lee_la_exportacion_en_espanol(self):
        path = self._csv("Consulta,Clics,Impresiones,Posición\nbomba,12,900,11,5\n")
        self.assertEqual(load(path).rows[0].clicks, 12)

    def test_sin_posicion_lo_dice_en_vez_de_inventarla(self):
        path = self._csv("Query,Clicks,Impressions\nbomba,12,900\n")
        report = load(path)
        self.assertFalse(report.has_positions)
        self.assertTrue(any("posicion" in n for n in report.notes))

    def test_sin_impresiones_no_puede_estimar(self):
        path = self._csv("Query,Clicks\nbomba,12\n")
        report = load(path)
        self.assertEqual(report.rows, [])
        self.assertTrue(report.notes)


class TestReasignacion(unittest.TestCase):
    def setUp(self):
        self.graph = build_graph([
            Keyword(t, volume=v, cpc=c) for t, v, c in [
                ("cuanto cuesta un sistema septico aerobico", 2000, 14.0),
                ("que es nitrificacion", 12000, 0.5),
                ("mejor bomba de aire septica", 700, 9.0),
            ]
        ])

        def url(slug: str) -> str:
            return f"{SITIO}/{slug}/"

        self.antes = Report(rows=[
            Row(page=url("cuanto-cuesta-un-sistema-septico-aerobico"),
                impressions=400, clicks=8, position=18),
            Row(page=url("que-es-nitrificacion"),
                impressions=2000, clicks=30, position=12),
            Row(page=url("mejor-bomba-de-aire-septica"),
                impressions=40, clicks=0, position=25),
        ])
        self.ahora = Report(rows=[
            Row(page=url("cuanto-cuesta-un-sistema-septico-aerobico"),
                impressions=900, clicks=22, position=12),
            Row(page=url("que-es-nitrificacion"),
                impressions=1200, clicks=14, position=15),
            Row(page=url("mejor-bomba-de-aire-septica"),
                impressions=45, clicks=1, position=22),
        ])
        self.result = reallocate(self.graph, self.antes, self.ahora,
                                 analyse(self.ahora))

    def test_invierte_en_lo_que_sube(self):
        invertir = self.result.by_decision(DECISION_INVEST)
        self.assertTrue(invertir)
        self.assertIn("aerobico", invertir[0].cluster_id)

    def test_retira_lo_que_cae(self):
        retirar = self.result.by_decision(DECISION_RETIRE)
        self.assertTrue(retirar)
        self.assertIn("nitrificacion", retirar[0].cluster_id)

    def test_admite_no_saber_con_poco_volumen(self):
        # Una subida del 12% sobre 85 impresiones no es una tendencia.
        sin_datos = self.result.by_decision(DECISION_UNKNOWN)
        self.assertTrue(sin_datos)
        self.assertIn("todavia no se sabe", sin_datos[0].rationale.lower())

    def test_el_presupuesto_va_a_quien_lo_merece(self):
        allocation = self.result.budget(12)
        self.assertEqual(sum(allocation.values()), 12)
        for cluster_id in allocation:
            self.assertNotIn("nitrificacion", cluster_id)

    def test_sin_nada_que_merezca_esfuerzo_no_reparte(self):
        vacio = Report(rows=[])
        result = reallocate(self.graph, vacio, vacio)
        self.assertEqual(result.budget(12), {})
        self.assertIn("mas datos", result.describe(pages=12))


if __name__ == "__main__":
    unittest.main()
