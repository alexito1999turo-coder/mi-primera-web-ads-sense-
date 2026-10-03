import unittest

from auditor.rules import (
    ACTION_DISABLE,
    ACTION_NOINDEX,
    ACTION_NONE,
    ACTION_RECATEGORIZE,
    VERDICT_HUB,
    Archive,
    find_cannibalization,
    judge,
    network_guard,
)


def archivo(**kwargs) -> Archive:
    base = dict(url="https://x.test/category/a/", kind="category", status=200)
    base.update(kwargs)
    return Archive(**base)


class TestVeredictos(unittest.TestCase):
    def test_hub_legitimo_no_se_toca(self):
        a = judge(archivo(words=1017, posts=10))
        self.assertEqual(a.verdict, VERDICT_HUB)
        self.assertEqual(a.action, ACTION_NONE)

    def test_fino_sin_salida_va_a_noindex(self):
        a = judge(archivo(words=400, posts=1))
        self.assertEqual(a.action, ACTION_NOINDEX)

    def test_fino_con_candidatos_prefiere_recategorizar(self):
        a = judge(archivo(words=415, posts=1,
                          recategorization_candidates=["u1", "u2", "u3"]))
        self.assertEqual(a.action, ACTION_RECATEGORIZE)
        self.assertIn("hub real", a.reason)

    def test_candidatos_insuficientes_lo_dice_sin_maquillar(self):
        # Tres candidatos no alcanzan el umbral de seis: el informe no debe
        # prometer un hub que no se consigue solo reasignando.
        a = judge(archivo(words=415, posts=1,
                          recategorization_candidates=["u1", "u2", "u3"]))
        self.assertIn("sigue siendo fino", a.reason)
        self.assertIn("pide 5", a.reason)

    def test_candidatos_suficientes_prometen_el_hub(self):
        a = judge(archivo(words=415, posts=1,
                          recategorization_candidates=[f"u{i}" for i in range(6)]))
        self.assertIn("pasa a hub real", a.reason)
        self.assertNotIn("sigue siendo fino", a.reason)

    def test_archivo_de_autor_se_desactiva_entero(self):
        a = judge(archivo(url="https://x.test/author/alex/", kind="author",
                          words=1035, posts=17))
        self.assertEqual(a.action, ACTION_DISABLE)

    def test_ya_en_noindex_no_es_accion_pendiente(self):
        a = judge(archivo(words=400, posts=1, indexable=False))
        self.assertEqual(a.action, ACTION_NONE)

    def test_archivo_que_no_se_sirve_no_genera_accion(self):
        a = judge(archivo(status=404, words=0, posts=0))
        self.assertEqual(a.action, ACTION_NONE)

    def test_pocos_posts_es_fino_aunque_tenga_palabras(self):
        # Tres articulos con mucho texto de plantilla sigue siendo un archivo
        # fino: lo que importa es que no aporta sobre los articulos.
        a = judge(archivo(words=1200, posts=2))
        self.assertIn(a.action, (ACTION_NOINDEX, ACTION_RECATEGORIZE))

    def test_umbral_configurable(self):
        a = judge(archivo(words=700, posts=8), thin_words=900)
        self.assertEqual(a.action, ACTION_NOINDEX)
        b = judge(archivo(words=700, posts=8), thin_words=600)
        self.assertEqual(b.action, ACTION_NONE)


class TestGuardaDeRed(unittest.TestCase):
    def test_avisa_si_se_ocultan_todas_las_categorias(self):
        archivos = [
            judge(archivo(url=f"https://x.test/category/c{i}/", words=200, posts=1))
            for i in range(4)
        ]
        avisos = network_guard(archivos)
        self.assertTrue(any("AVISO" in a for a in avisos))

    def test_no_avisa_si_queda_algun_hub(self):
        archivos = [
            judge(archivo(url="https://x.test/category/c1/", words=200, posts=1)),
            judge(archivo(url="https://x.test/category/c2/", words=1500, posts=12)),
        ]
        avisos = network_guard(archivos)
        self.assertFalse(any("AVISO" in a for a in avisos))
        self.assertTrue(any("hubs legitimos" in a for a in avisos))


class TestCanibalizacion(unittest.TestCase):
    def test_confirmada_cuando_el_archivo_gana(self):
        a = archivo(url="https://x.test/category/alarma/")
        pares = find_cannibalization(
            a, ["https://x.test/articulo/"],
            {"x.test/category/alarma": 14, "x.test/articulo": 5},
        )
        self.assertEqual(len(pares), 1)
        self.assertTrue(pares[0].confirmed)

    def test_no_confirmada_cuando_el_articulo_gana(self):
        a = archivo(url="https://x.test/category/alarma/")
        pares = find_cannibalization(
            a, ["https://x.test/articulo/"],
            {"x.test/category/alarma": 3, "x.test/articulo": 40},
        )
        self.assertFalse(pares[0].confirmed)

    def test_sin_datos_no_se_inventa_nada(self):
        a = archivo(url="https://x.test/category/alarma/")
        self.assertEqual(find_cannibalization(a, ["https://x.test/articulo/"], {}), [])


if __name__ == "__main__":
    unittest.main()
