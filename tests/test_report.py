"""El informe mensual: ensamblado desde el registro, no tecleado."""

import tempfile
import unittest
from pathlib import Path

from calibration.priors import PESO_MEDIO, PriorSet
from compliance.dossier import MonthRecord
from report.monthly import (
    ESTIMADO,
    MEDIDO,
    MIN_OBSERVACIONES,
    SUPUESTO,
    Figure,
    MonthlyReport,
    build,
)
from store.portfolio import PortfolioStore
from store.project import ProjectStore


def cuerpo(tema: str, n: int = 170) -> str:
    frases = [
        f"El {tema} depende del numero de dormitorios de la vivienda.",
        f"En {tema} la normativa del condado manda sobre la del estado.",
        f"Un {tema} mal dimensionado se nota en la factura de luz.",
    ]
    return " ".join(frases[i % 3] + f" Caso {tema} numero {i}." for i in range(n))


def record(**kw) -> MonthRecord:
    base = dict(client="Cliente", site="cliente.com", period="2026-10",
                pages_published=3, pages_blocked=1, publishable_as_is=3,
                monthly_cap=24, pages_with_own_data=3, pages_with_sources=3,
                sources_cited=["https://www.epa.gov/septic"],
                languages=["es"], languages_human_reviewed=["es"],
                max_internal_overlap=0.1, max_density=0.02)
    base.update(kw)
    return MonthRecord(**base)


class TestFigure(unittest.TestCase):
    def test_lo_supuesto_se_marca_en_mayusculas(self):
        self.assertIn("SUPUESTO", Figure("x", "1", SUPUESTO).line())
        self.assertNotIn("SUPUESTO", Figure("x", "1", MEDIDO).line())

    def test_solo_lo_medido_cuenta_como_medicion(self):
        self.assertTrue(Figure("x", "1", MEDIDO).trustworthy)
        self.assertFalse(Figure("x", "1", ESTIMADO).trustworthy)
        self.assertFalse(Figure("x", "1", SUPUESTO).trustworthy)


class TestInforme(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.raiz = Path(self.tmp.name)
        self.store = ProjectStore(self.raiz / "cliente", client="Cliente")
        self.cartera = PortfolioStore(self.raiz)

    def tearDown(self):
        self.tmp.cleanup()

    def llenar(self, paginas: int = 3):
        temas = ["coste de instalacion", "mantenimiento anual",
                 "permisos del condado", "bombas de aire", "alarmas"]
        for i in range(paginas):
            self.store.record_page(f"p{i}", cuerpo(temas[i % len(temas)]),
                                   role="pilar")

    def test_no_hay_manera_de_colar_una_cifra_de_fuera(self):
        """La firma de `build` no admite cifras sueltas, y es a proposito.

        Si el ensamblado aceptara un diccionario de extras, el informe dejaria
        de ser una lectura del registro para ser lo que alguien quiera poner.
        """
        import inspect

        parametros = set(inspect.signature(build).parameters)
        self.assertEqual(
            parametros, {"store", "record", "portfolio", "prior_sets",
                         "oportunidad"},
            "cualquier parametro nuevo tiene que venir de un registro, no de "
            "un formulario",
        )

    def test_con_una_sola_pagina_el_solape_se_declara_no_medido(self):
        self.llenar(1)
        informe = build(self.store, record(pages_published=1), self.cartera)
        solape = [f for f in informe.figures if "Solape interno" in f.label][0]
        self.assertEqual(solape.provenance, SUPUESTO)
        self.assertIn("no medido", solape.value)
        self.assertTrue(any("canibalizan" in u for u in informe.unknowns))

    def test_con_varias_paginas_el_solape_sale_medido_y_nombra_el_par(self):
        self.llenar(3)
        informe = build(self.store, record(), self.cartera)
        solape = [f for f in informe.figures if "Solape interno" in f.label][0]
        self.assertIn(solape.provenance, (MEDIDO, ESTIMADO))
        self.assertIn("'p0'", solape.basis)

    def test_pocas_observaciones_no_son_una_medicion(self):
        self.llenar(2)
        for _ in range(MIN_OBSERVACIONES - 1):
            self.store.observe("ctr", 0.2)
        informe = build(self.store, record(), self.cartera)
        cifra = [f for f in informe.figures if f.label == "ctr"][0]
        self.assertEqual(cifra.provenance, ESTIMADO)
        self.assertIn(f"hacen falta {MIN_OBSERVACIONES}", cifra.basis)

        for _ in range(3):
            self.store.observe("ctr", 0.2)
        otro = build(self.store, record(), self.cartera)
        self.assertEqual([f for f in otro.figures if f.label == "ctr"][0].provenance,
                         MEDIDO)

    def test_una_metrica_solo_declarada_no_se_presenta_como_dato(self):
        self.llenar(2)
        self.store.observe("cpc", 12.0, source="declarado", note="propuesta")
        informe = build(self.store, record(), self.cartera)
        cifra = [f for f in informe.figures if f.label == "cpc"][0]
        self.assertEqual(cifra.provenance, SUPUESTO)
        self.assertEqual(cifra.value, "solo declarada")

    def test_las_incognitas_no_repiten_la_misma_cifra_dos_veces(self):
        """Regresion: la misma metrica salia en dos lineas distintas.

        Decir dos veces lo mismo con otras palabras hace que la seccion
        parezca rellenada, y es justo la que no puede parecerlo.
        """
        self.llenar(2)
        self.store.observe("ctr_posicion_1", 0.21)
        priores = PriorSet(label="Curvas")
        priores.declare("ctr_posicion_1", 0.25, weight=PESO_MEDIO)
        self.store.feed(priores)
        informe = build(self.store, record(), self.cartera, prior_sets=[priores])
        menciones = [u for u in informe.unknowns if "ctr_posicion_1" in u]
        self.assertEqual(len(menciones), 1)
        self.assertIn("observacion medida", menciones[0])
        self.assertIn("prior declarado", menciones[0])

    def test_las_incognitas_se_generan_solas(self):
        informe = build(self.store, record(pages_published=0, sources_cited=[],
                                           max_density=None), self.cartera)
        self.assertTrue(informe.unknowns)
        self.assertTrue(any("densidad" in u for u in informe.unknowns))
        self.assertTrue(any("fuentes citadas" in u for u in informe.unknowns))

    def test_un_idioma_sin_revision_nativa_sale_como_incognita(self):
        self.llenar(2)
        informe = build(self.store,
                        record(languages=["es", "de"],
                               languages_human_reviewed=["es"]),
                        self.cartera)
        self.assertTrue(any("de" in u and "traduccion automatica" in u
                            for u in informe.unknowns))

    def test_pasarse_del_tope_sale_en_el_informe(self):
        self.llenar(3)
        informe = build(self.store, record(pages_published=40, monthly_cap=24),
                        self.cartera)
        trabajo = informe.sections[0]
        self.assertTrue(any("scaled content abuse" in l for l in trabajo.lines))

    def test_el_porcentaje_medido_cuenta_solo_lo_medido(self):
        self.llenar(3)
        informe = build(self.store, record(), self.cartera)
        total = len(informe.figures)
        medidas = len([f for f in informe.figures if f.trustworthy])
        self.assertEqual(informe.measured_share, round(100 * medidas / total))
        self.assertLess(informe.measured_share, 100,
                        "un informe al 100% medido en el mes uno seria mentira")

    def test_un_bloqueante_de_cumplimiento_impide_cerrar_el_mes(self):
        self.llenar(2)
        informe = build(self.store,
                        record(reciprocal_link_exchange=True), self.cartera)
        self.assertFalse(informe.deliverable)
        self.assertIn("sin resolver", informe.headline())
        self.assertIn("## Sin resolver", informe.to_markdown())

    def test_el_markdown_lleva_las_cuatro_secciones_obligatorias(self):
        self.llenar(3)
        texto = build(self.store, record(), self.cartera).to_markdown()
        for titulo in ("Lo que se ha hecho", "Que se ha comprobado antes de publicar",
                       "Lo que todavia no sabemos",
                       "Que haria cambiar la recomendacion"):
            self.assertIn(titulo, texto)

    def test_sin_senal_lo_dice_en_vez_de_inventar_una_recomendacion(self):
        self.llenar(1)
        informe = build(self.store, record(pages_published=1, pages_blocked=0,
                                           publishable_as_is=1), self.cartera)
        self.assertTrue(any("todavia no hay senal" in w
                            for w in informe.would_change))

    def test_sin_cartera_se_declara_en_vez_de_darlo_por_limpio(self):
        self.llenar(2)
        informe = build(self.store, record(), portfolio=None)
        huella = [f for f in informe.figures if "cartera" in f.label.lower()][0]
        self.assertEqual(huella.provenance, SUPUESTO)
        self.assertIn("no medida", huella.value)


    def test_una_metrica_medida_que_aun_no_manda_no_parece_contradiccion(self):
        """Regresion: el informe decia «medido» arriba y «no es medicion» abajo.

        Las dos frases eran ciertas — la media observada frente al valor que
        el sistema usa para planificar — pero juntas se leen como que el
        informe se contradice, que es lo que no se puede permitir.
        """
        self.llenar(2)
        for _ in range(MIN_OBSERVACIONES + 1):
            self.store.observe("ctr_posicion_1", 0.2)
        priores = PriorSet(label="Curvas")
        priores.declare("ctr_posicion_1", 0.25, weight=PESO_MEDIO)
        self.store.feed(priores)
        informe = build(self.store, record(), self.cartera, prior_sets=[priores])

        cifra = [f for f in informe.figures if f.label == "ctr_posicion_1"][0]
        self.assertEqual(cifra.provenance, MEDIDO)

        menciones = [u for u in informe.unknowns if "ctr_posicion_1" in u]
        self.assertEqual(len(menciones), 1)
        self.assertIn("ya esta medida", menciones[0])
        self.assertIn("para planificar", menciones[0])
        self.assertNotIn("no es todavia una medicion", menciones[0])

    def test_dice_cuantas_observaciones_faltan_para_que_mande_el_dato(self):
        """«Sigue siendo suposicion» no es accionable; un numero si."""
        self.llenar(2)
        for _ in range(MIN_OBSERVACIONES + 1):
            self.store.observe("ctr_posicion_1", 0.2)
        priores = PriorSet(label="Curvas")
        priores.declare("ctr_posicion_1", 0.25, weight=PESO_MEDIO)
        self.store.feed(priores)
        informe = build(self.store, record(), self.cartera, prior_sets=[priores])
        mencion = [u for u in informe.unknowns if "ctr_posicion_1" in u][0]
        import re

        numeros = re.findall(r"unas (\d+) observaciones mas", mencion)
        self.assertTrue(numeros, f"no dice cuantas faltan: {mencion}")
        self.assertGreater(int(numeros[0]), 0)

    def test_los_codigos_de_idioma_van_entrecomillados(self):
        """«Publicado en en» se lee como una errata, no como un idioma."""
        self.llenar(2)
        informe = build(self.store,
                        record(languages=["es", "en"],
                               languages_human_reviewed=["es"]),
                        self.cartera)
        mencion = [u for u in informe.unknowns if "traduccion automatica" in u][0]
        self.assertIn("«en»", mencion)
        self.assertNotIn("en en ", mencion)


class TestCabecera(unittest.TestCase):
    def test_informe_vacio_no_divide_por_cero(self):
        vacio = MonthlyReport(client="x", period="2026-10")
        self.assertEqual(vacio.measured_share, 0)
        self.assertIn("Mes cerrado", vacio.headline())
