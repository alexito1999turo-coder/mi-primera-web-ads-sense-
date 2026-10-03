import unittest

from calibration.calibrator import (
    ACTION_CREATE,
    ACTION_DOWNGRADE,
    ACTION_KEEP,
    ACTION_PROMOTE,
    ACTION_RETIRE,
    ACTION_SHADOW,
    VERDICT_APPROVED,
    VERDICT_REJECTED,
    Observation,
    calibrate,
    to_markdown,
)
from calibration.metrics import GateMetrics, wilson_lower

SEVERIDADES = {
    "densidad_anomala": "bloqueante",
    "afirmacion_sin_respaldo": "aviso",
    "citabilidad_pobre": "aviso",
    "longitud_insuficiente": "bloqueante",
}


def acciones(calibration, code: str) -> list[str]:
    return [r.action for r in calibration.recommendations if r.code == code]


class TestWilson(unittest.TestCase):
    def test_tres_de_tres_no_es_certeza(self):
        # Es el punto del estadistico: 100% sobre 3 casos no significa nada.
        self.assertLess(wilson_lower(3, 3), 0.5)

    def test_cincuenta_de_cincuenta_si_lo_es(self):
        self.assertGreater(wilson_lower(50, 50), 0.9)

    def test_crece_con_la_muestra_a_igual_proporcion(self):
        self.assertLess(wilson_lower(6, 12), wilson_lower(30, 60))

    def test_sin_datos_es_cero(self):
        self.assertEqual(wilson_lower(0, 0), 0.0)


class TestMetricas(unittest.TestCase):
    def test_sin_activaciones_no_hay_precision(self):
        metrics = GateMetrics(code="x", pages_seen=30)
        self.assertIsNone(metrics.precision)
        self.assertIn("no se activo ni una vez en 30", metrics.describe())

    def test_las_revisiones_gastadas_son_los_falsos_positivos(self):
        metrics = GateMetrics(code="x", fired_and_rejected=3, fired_and_approved=7)
        self.assertEqual(metrics.wasted_reviews, 7)
        self.assertAlmostEqual(metrics.precision, 0.3)

    def test_la_cobertura_mira_lo_que_se_le_escapo(self):
        metrics = GateMetrics(code="x", fired_and_rejected=8, silent_and_rejected=2)
        self.assertAlmostEqual(metrics.recall, 0.8)


class TestCalibracion(unittest.TestCase):
    def test_sin_observaciones_no_recomienda_nada(self):
        result = calibrate([], SEVERIDADES)
        self.assertEqual(result.recommendations, [])

    def test_baja_la_bloqueante_ruidosa(self):
        observations = [
            Observation(slug=f"a{i}", fired={"densidad_anomala"},
                        verdict=VERDICT_APPROVED, reviewed_despite_block=True,
                        minutes=25)
            for i in range(14)
        ] + [
            Observation(slug=f"r{i}", fired={"densidad_anomala"},
                        verdict=VERDICT_REJECTED, reasons=["densidad_anomala"],
                        reviewed_despite_block=True)
            for i in range(4)
        ]
        result = calibrate(observations, SEVERIDADES)
        self.assertIn(ACTION_DOWNGRADE, acciones(result, "densidad_anomala"))

    def test_cuantifica_los_minutos_tirados(self):
        observations = [
            Observation(slug=f"a{i}", fired={"densidad_anomala"},
                        verdict=VERDICT_APPROVED, reviewed_despite_block=True,
                        minutes=25)
            for i in range(14)
        ]
        self.assertEqual(calibrate(observations, SEVERIDADES).wasted_minutes, 350)

    def test_sube_el_aviso_que_siempre_acierta(self):
        observations = [
            Observation(slug=f"a{i}", fired={"afirmacion_sin_respaldo"},
                        verdict=VERDICT_REJECTED, reasons=["afirmacion_sin_respaldo"])
            for i in range(40)
        ]
        result = calibrate(observations, SEVERIDADES)
        self.assertIn(ACTION_PROMOTE, acciones(result, "afirmacion_sin_respaldo"))

    def test_una_bloqueante_sin_muestreo_en_sombra_es_inmedible(self):
        # Es el problema metodologico que nadie menciona: si bloquea, la pagina
        # no llega al revisor y no hay con que medirla.
        observations = [
            Observation(slug=f"l{i}", fired={"longitud_insuficiente"},
                        verdict=VERDICT_REJECTED, reasons=["longitud_insuficiente"])
            for i in range(20)
        ]
        result = calibrate(observations, SEVERIDADES)
        self.assertIn(ACTION_SHADOW, acciones(result, "longitud_insuficiente"))
        self.assertIn("longitud_insuficiente", result.unmeasurable)

    def test_no_toca_lo_que_no_puede_medir(self):
        observations = [
            Observation(slug=f"a{i}", fired={"afirmacion_sin_respaldo"},
                        verdict=VERDICT_REJECTED, reasons=["afirmacion_sin_respaldo"])
            for i in range(4)
        ]
        result = calibrate(observations, SEVERIDADES)
        self.assertEqual(acciones(result, "afirmacion_sin_respaldo"), [ACTION_KEEP])

    def test_propone_crear_la_compuerta_que_falta(self):
        observations = [
            Observation(slug=f"t{i}", fired=set(), verdict=VERDICT_REJECTED,
                        reasons=["tono_no_es_de_marca"])
            for i in range(4)
        ]
        result = calibrate(observations, SEVERIDADES)
        self.assertIn(ACTION_CREATE, acciones(result, "tono_no_es_de_marca"))

    def test_un_motivo_aislado_no_justifica_una_compuerta(self):
        observations = [
            Observation(slug="t0", fired=set(), verdict=VERDICT_REJECTED,
                        reasons=["algo_raro_que_paso_una_vez"])
        ]
        result = calibrate(observations, SEVERIDADES)
        self.assertNotIn(ACTION_CREATE, acciones(result, "algo_raro_que_paso_una_vez"))

    def test_retira_la_que_nunca_se_activa(self):
        observations = [
            Observation(slug=f"p{i}", fired={"afirmacion_sin_respaldo"},
                        verdict=VERDICT_APPROVED)
            for i in range(30)
        ]
        result = calibrate(observations, SEVERIDADES)
        self.assertIn(ACTION_RETIRE, acciones(result, "citabilidad_pobre"))

    def test_un_rechazo_por_otro_motivo_no_cuenta_contra_la_compuerta(self):
        # Si marco densidad y el revisor rechazo por el tono, esta compuerta no
        # acerto ni fallo: contarlo seria falsear su precision.
        observations = [
            Observation(slug="x", fired={"densidad_anomala"},
                        verdict=VERDICT_REJECTED, reasons=["tono_no_es_de_marca"],
                        reviewed_despite_block=True)
        ]
        metrics = calibrate(observations, SEVERIDADES).metrics["densidad_anomala"]
        self.assertEqual(metrics.fired_and_rejected, 0)
        self.assertEqual(metrics.fired_and_approved, 0)

    def test_el_informe_dice_lo_que_no_se_puede_medir(self):
        observations = [
            Observation(slug=f"l{i}", fired={"longitud_insuficiente"},
                        verdict=VERDICT_REJECTED, reasons=["longitud_insuficiente"])
            for i in range(20)
        ]
        markdown = to_markdown(calibrate(observations, SEVERIDADES))
        self.assertIn("INMEDIBLE", markdown)

    def test_el_informe_admite_cuando_no_hay_nada_que_cambiar(self):
        observations = [
            Observation(slug=f"a{i}", fired={"afirmacion_sin_respaldo"},
                        verdict=VERDICT_REJECTED, reasons=["afirmacion_sin_respaldo"])
            for i in range(4)
        ]
        markdown = to_markdown(calibrate(observations, {"afirmacion_sin_respaldo": "aviso"}))
        self.assertIn("Ninguna", markdown)


if __name__ == "__main__":
    unittest.main()
