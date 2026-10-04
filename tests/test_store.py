"""La memoria del sistema: firmas, historico, migracion y escritura atomica."""

import json
import os
import tempfile
import unittest
from pathlib import Path

from store.archivo import Esquema, append_line, read_lines, write_atomic, write_json
from store.portfolio import PortfolioStore
from store.project import MEDIDO, DECLARADO, ProjectStore
from store.sketch import Sketch, merge, shingles, similarity


def texto(semilla: int, n: int = 400) -> str:
    """Texto reproducible y sin parecido entre semillas distintas."""
    return " ".join(f"w{semilla}_{i % 97}_{i}" for i in range(n))


class TestSketch(unittest.TestCase):
    def test_identico_da_uno(self):
        a = Sketch.of(texto(1))
        self.assertEqual(similarity(a, Sketch.of(texto(1))), 1.0)

    def test_sin_relacion_da_cero(self):
        self.assertEqual(similarity(Sketch.of(texto(1)), Sketch.of(texto(2))), 0.0)

    def test_tamano_acotado(self):
        grande = Sketch.of(texto(3, 5000))
        self.assertEqual(len(grande.hashes), grande.k)
        self.assertFalse(grande.exact)

    def test_texto_corto_es_exacto(self):
        corto = Sketch.of("una frase de prueba con pocas palabras")
        self.assertTrue(corto.exact)

    def test_una_pagina_copiada_dentro_de_otra_larga_se_ve(self):
        copiada = texto(4, 300)
        larga = copiada + " " + texto(5, 3000)
        valor = similarity(Sketch.of(copiada), Sketch.of(larga))
        self.assertGreater(valor, 0.8, "el minimo como denominador es lo que hace esto")

    def test_estimacion_cerca_de_la_verdad(self):
        a, b = texto(6, 2000), texto(6, 1000) + " " + texto(7, 1000)
        sa, sb = set(shingles(a)), set(shingles(b))
        exacto = len(sa & sb) / min(len(sa), len(sb))
        estimado = similarity(Sketch.of(a), Sketch.of(b))
        self.assertLess(abs(exacto - estimado), 0.12)

    def test_union_se_calcula_sin_los_textos(self):
        paginas = [texto(10 + i, 400) for i in range(6)]
        acumulada = Sketch()
        for p in paginas:
            acumulada = merge(acumulada, Sketch.of(p))
        # Una pagina del sitio contra la huella del sitio: esta dentro.
        self.assertGreater(similarity(Sketch.of(paginas[2]), acumulada), 0.9)
        # Una ajena, no.
        self.assertLess(similarity(Sketch.of(texto(999, 400)), acumulada), 0.1)

    def test_merge_vacio_no_revienta(self):
        self.assertEqual(merge().hashes, [])
        self.assertEqual(merge(Sketch(), Sketch()).hashes, [])

    def test_cardinalidad_estimada_con_error_bajo(self):
        paginas = [texto(20 + i, 600) for i in range(10)]
        reales = set()
        for p in paginas:
            reales |= set(shingles(p))
        acumulada = Sketch()
        for p in paginas:
            acumulada = merge(acumulada, Sketch.of(p))
        error = abs(acumulada.size - len(reales)) / len(reales)
        self.assertLess(error, 0.20)
        self.assertFalse(acumulada.exact, "truncada: su tamano es estimacion")


class TestEscrituraAtomica(unittest.TestCase):
    def test_el_fichero_anterior_sobrevive_a_un_fallo(self):
        with tempfile.TemporaryDirectory() as tmp:
            destino = Path(tmp) / "estado.json"
            write_json(destino, {"bueno": True})

            class Explota(str):
                def __str__(self):  # pragma: no cover - lo usa json
                    raise RuntimeError("corte a mitad")

            with self.assertRaises(Exception):
                write_atomic(destino, None)  # type: ignore[arg-type]
            self.assertEqual(json.loads(destino.read_text())["bueno"], True)

    def test_no_deja_temporales_tras_un_fallo(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(Exception):
                write_atomic(Path(tmp) / "x.json", None)  # type: ignore[arg-type]
            self.assertEqual(
                [p for p in os.listdir(tmp) if p.startswith(".tmp-")], []
            )

    def test_historico_salta_la_linea_corrupta(self):
        with tempfile.TemporaryDirectory() as tmp:
            fichero = Path(tmp) / "h.jsonl"
            append_line(fichero, {"a": 1})
            with open(fichero, "a", encoding="utf-8") as fh:
                fh.write('{"a": 2, "rot')
            append_line(fichero, {"a": 3})
            self.assertEqual([r["a"] for r in read_lines(fichero)], [1, 3])


class TestEsquema(unittest.TestCase):
    def test_migra_en_cadena(self):
        esquema = Esquema(version=3, migraciones={
            1: lambda d: {**d, "b": d["a"] + 1},
            2: lambda d: {**d, "c": d["b"] + 1},
        })
        data, pasos = esquema.upgrade({"schema": 1, "a": 1})
        self.assertEqual((data["b"], data["c"], data["schema"]), (2, 3, 3))
        self.assertEqual(len(pasos), 2)

    def test_se_niega_a_abrir_un_fichero_del_futuro(self):
        with self.assertRaises(ValueError):
            Esquema(version=1, migraciones={}).upgrade({"schema": 9})

    def test_falta_de_migracion_se_declara(self):
        with self.assertRaises(ValueError):
            Esquema(version=2, migraciones={}).upgrade({"schema": 1})


class TestProjectStore(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name) / "sitio"

    def tearDown(self):
        self.tmp.cleanup()

    def test_sobrevive_al_cierre_del_proceso(self):
        almacen = ProjectStore(self.root, client="cliente")
        almacen.record_page("guia-bombas", texto(1, 900), url="/guia-bombas")
        almacen.observe("ctr_posicion_1", 0.21)
        almacen.record_rejection("guia-bombas", "dato_debil",
                                 "la cifra no tiene metodo",
                                 instruction="Declara n y fecha.")
        del almacen

        otra = ProjectStore(self.root)
        self.assertEqual(otra.client, "cliente")
        self.assertIn("guia-bombas", otra.pages)
        self.assertEqual(otra.observations("ctr_posicion_1"), [0.21])
        self.assertEqual(len(otra.rejection_log().rejections), 1)

    def test_solape_contra_lo_publicado(self):
        almacen = ProjectStore(self.root)
        almacen.record_page("a", texto(1, 900))
        almacen.record_page("b", texto(2, 900))

        propio = almacen.overlap_of(texto(1, 900))
        self.assertEqual(propio.slug, "a")
        self.assertGreater(propio.value, 0.9)

        nuevo = almacen.overlap_of(texto(3, 900))
        self.assertLess(nuevo.value, 0.1)
        self.assertTrue(nuevo.measured)

    def test_solape_sin_corpus_se_declara_no_medido(self):
        vacio = ProjectStore(self.root).overlap_of(texto(1))
        self.assertFalse(vacio.measured)
        self.assertIn("no medido", vacio.describe())

    def test_pagina_despublicada_sale_del_corpus(self):
        almacen = ProjectStore(self.root)
        almacen.record_page("a", texto(1, 900))
        self.assertTrue(almacen.forget_page("a"))
        self.assertFalse(almacen.forget_page("a"))
        self.assertEqual(ProjectStore(self.root).pages, {})

    def test_el_historico_no_se_reescribe(self):
        almacen = ProjectStore(self.root)
        mala = almacen.observe("cpc", 4.0, note="leido mal del panel")
        almacen.correct(mala.seq, 1.4, note="era 1,40 no 4,00")

        self.assertEqual(almacen.observations("cpc"), [1.4],
                         "al leer vale la correccion")
        crudo = (self.root / "observaciones.jsonl").read_text()
        self.assertIn("4.0", crudo, "el error original sigue en el fichero")
        self.assertEqual(len(almacen.history()), 2)

    def test_una_correccion_sin_motivo_no_se_guarda(self):
        almacen = ProjectStore(self.root)
        obs = almacen.observe("cpc", 4.0)
        with self.assertRaises(ValueError):
            almacen.correct(obs.seq, 1.4, note="   ")
        with self.assertRaises(KeyError):
            almacen.correct(999, 1.0, note="no existe")

    def test_los_priores_se_diluyen_con_el_historico(self):
        from calibration.priors import PESO_MEDIO, PriorSet

        almacen = ProjectStore(self.root)
        conjunto = PriorSet(label="prueba")
        conjunto.declare("cpc", 3.0, weight=PESO_MEDIO, source="declarado")

        almacen.feed(conjunto)
        self.assertEqual(conjunto.posterior("cpc").prior_share, 100)

        for _ in range(PESO_MEDIO * 4):
            almacen.observe("cpc", 1.0)
        fresco = PriorSet(label="prueba")
        fresco.declare("cpc", 3.0, weight=PESO_MEDIO, source="declarado")
        almacen.feed(fresco)
        post = fresco.posterior("cpc")
        self.assertEqual(post.n, PESO_MEDIO * 4)
        self.assertTrue(post.trustworthy)
        self.assertLess(post.value, 1.5)

    def test_lo_declarado_no_alimenta_un_prior(self):
        from calibration.priors import PriorSet

        almacen = ProjectStore(self.root)
        almacen.observe("cpc", 9.9, source=DECLARADO, note="estimacion de la propuesta")
        almacen.observe("cpc", 1.2, source=MEDIDO)
        conjunto = PriorSet(label="x")
        conjunto.declare("cpc", 3.0)
        almacen.feed(conjunto)
        self.assertEqual(conjunto.posterior("cpc").n, 1)
        self.assertEqual(almacen.observations("cpc"), [9.9, 1.2])

    def test_mapeo_de_nombres(self):
        from calibration.priors import PriorSet

        almacen = ProjectStore(self.root)
        almacen.observe("ctr@1", 0.3)
        conjunto = PriorSet(label="x")
        conjunto.declare("ctr_posicion_1", 0.25)
        almacen.feed(conjunto, mapping={"ctr_posicion_1": "ctr@1"})
        self.assertEqual(conjunto.posterior("ctr_posicion_1").n, 1)

    def test_migracion_de_v1_conserva_los_datos(self):
        cuerpo = texto(1, 900)
        self.root.mkdir(parents=True, exist_ok=True)
        write_json(self.root / "estado.json", {
            "schema": 1, "client": "viejo",
            "pages": {"a": {"shingles": sorted(set(shingles(cuerpo)))[:300],
                            "words": 900}},
        })
        almacen = ProjectStore(self.root)
        self.assertEqual(almacen.migrations, ["esquema 1 -> 2"])
        self.assertIn("a", almacen.pages)
        self.assertEqual(almacen.pages["a"].migrado_de, "v1:shingles")
        # La firma migrada sigue reconociendo su propia pagina.
        self.assertGreater(almacen.overlap_of(cuerpo).value, 0.5)
        # Y queda escrita en v2, sin los fragmentos.
        crudo = json.loads((self.root / "estado.json").read_text())
        self.assertEqual(crudo["schema"], 2)
        self.assertNotIn("shingles", crudo["pages"]["a"])

    def test_instrucciones_recurrentes_vuelven_al_brief(self):
        almacen = ProjectStore(self.root)
        for slug in ("a", "b"):
            almacen.record_rejection(slug, "dato_debil", "sin metodo",
                                     instruction="Declara n y fecha.")
        almacen.record_rejection("c", "otro", "caso raro",
                                 instruction="No repetir esto.")
        adiciones = ProjectStore(self.root).brief_additions()
        self.assertEqual(adiciones, ["Declara n y fecha."])

    def test_describe_no_afirma_lo_que_no_tiene(self):
        texto_vacio = ProjectStore(self.root).describe()
        self.assertIn("0 pagina(s)", texto_vacio)
        self.assertIn("0 observacion(es)", texto_vacio)


class TestPortfolioStore(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_dos_sitios_con_la_misma_plantilla_colisionan(self):
        plantilla = ("## Que es\n" + texto(1, 300) +
                     "\n## Cuanto cuesta\n" + texto(2, 300) +
                     "\n## Como se mantiene\n" + texto(3, 300))
        cartera = PortfolioStore(self.root)
        cartera.add_page("sitio-a.com", plantilla)
        cartera.add_page("sitio-b.com", plantilla)
        auditoria = cartera.audit()
        self.assertTrue(auditoria.blocking)
        self.assertIn("granja de contenido", auditoria.describe())

    def test_dos_sitios_distintos_pasan(self):
        cartera = PortfolioStore(self.root)
        cartera.add_page("a.com", "## Bombas de aire\n" + texto(1, 500))
        cartera.add_page("b.com", "## Permisos municipales\n" + texto(2, 500))
        self.assertTrue(cartera.audit().passed)

    def test_avisa_antes_de_publicar_no_despues(self):
        cuerpo = "## Que es\n" + texto(1, 600)
        cartera = PortfolioStore(self.root)
        cartera.add_page("a.com", cuerpo)
        riesgos = cartera.would_collide("b.com", cuerpo)
        self.assertTrue(riesgos and riesgos[0].blocking)
        self.assertTrue(cartera.audit().passed,
                        "el borrador no entra en la cartera por comprobarlo")

    def test_el_fichero_no_crece_con_las_paginas(self):
        cartera = PortfolioStore(self.root)
        for i in range(5):
            cartera.add_page("a.com", texto(100 + i, 1500))
        pequeno = (self.root / "cartera.json").stat().st_size
        for i in range(45):
            cartera.add_page("a.com", texto(200 + i, 1500))
        grande = (self.root / "cartera.json").stat().st_size
        self.assertEqual(cartera.sites["a.com"].pages, 50)
        self.assertLess(grande, pequeno * 2,
                        "diez veces mas paginas no es diez veces mas fichero")

    def test_sobrevive_al_cierre_y_el_cliente_que_se_va_sale(self):
        cartera = PortfolioStore(self.root)
        cartera.add_page("a.com", texto(1, 400))
        cartera.add_page("b.com", texto(2, 400))
        otra = PortfolioStore(self.root)
        self.assertEqual(set(otra.sites), {"a.com", "b.com"})
        self.assertTrue(otra.drop_site("a.com"))
        self.assertFalse(otra.drop_site("a.com"))
        self.assertEqual(set(PortfolioStore(self.root).sites), {"b.com"})

    def test_cartera_vacia_no_inventa_auditoria(self):
        self.assertIn("Cartera vacia", PortfolioStore(self.root).describe())
