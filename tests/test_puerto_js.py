"""El puerto JS de la economia, comprobado contra el motor Python.

El banco de pruebas lleva una copia en JavaScript del modulo `pricing`, para
que se pueda usar desde el navegador sin instalar nada. Una copia es una
promesa de que los dos dan lo mismo, y una promesa sin comprobar se rompe en
la primera correccion que solo se aplica a uno de los dos.

Esto corre los dos sobre los mismos casos — incluidos los extremos: sin
revision, sin herramientas, un solo cliente, un plan en perdidas — y falla si
difieren. Si no hay `node`, se salta: el motor de verdad es el de Python y no
tiene que depender de que haya Node instalado.
"""

import json
import shutil
import subprocess
import unittest
from pathlib import Path

from generator.llm import Usage
from pricing.plans import (
    Plan,
    curva_de_cartera,
    evaluar,
    paginas_maximas,
    precio_minimo,
    punto_muerto,
    sensibilidad,
)

AQUI = Path(__file__).parent / "puerto"
# El motor JS canonico vive con los artefactos, no con los tests: es codigo
# que se publica, no andamiaje de pruebas.
MOTOR = Path(__file__).parent.parent / "artefactos" / "economia.js"
USO = Usage(input_tokens=4000, output_tokens=6000, cache_write_tokens=3000,
            cache_read_tokens=24000, calls=1)

PUENTE = """
const { readFileSync } = require('fs');
const e = require(process.env.MOTOR_JS);
const U = {input:4000, output:6000, cacheWrite:3000, cacheRead:24000, calls:1};
const casos = JSON.parse(readFileSync(process.env.CASOS, 'utf8'));
console.log(JSON.stringify(casos.map(c => {
  const kw = {usage:U, reparaciones:c.rep, costeHora:c.hora,
              herramientasMes:c.herr, lotes:c.lotes, minutosRevision:c.mins};
  if (c.cartera) kw.paginasCartera = c.cartera;
  const p = {nombre:c.nombre, precioMes:c.precio, paginas:c.paginas,
             minutosRevision:c.mins};
  const r = e.evaluar(p, kw);
  const pm = e.puntoMuerto(p, c.fijos, kw);
  const kwSin = Object.assign({}, kw); delete kwSin.paginasCartera;
  return {nombre:c.nombre, coste_pagina:r.costePagina, margen_pct:r.margenPct,
    reparto:r.reparto, sano:r.sano,
    sens: e.sensibilidad(p, kw).map(s => [s.palanca, s.despues, s.rompe]),
    clientes: pm.clientes,
    horas: pm.horasRevisionMes === undefined ? null : pm.horasRevisionMes,
    umbral: e.curvaDeCartera(p, kwSin).umbralClientes,
    pag_max: e.paginasMaximas(p, kw).paginas,
    precio_min: e.precioMinimo(p, kw).precio};
})));
"""


def _python(casos: list[dict]) -> list[dict]:
    salida = []
    for c in casos:
        kw = dict(usage=USO, reparaciones=c["rep"], coste_hora=c["hora"],
                  herramientas_mes=c["herr"], lotes=c["lotes"],
                  minutos_revision=c["mins"])
        if c["cartera"]:
            kw["paginas_cartera"] = c["cartera"]
        p = Plan(c["nombre"], c["precio"], c["paginas"], c["mins"])
        r = evaluar(p, **kw)
        pm = punto_muerto(p, c["fijos"], **kw)
        sin = {k: v for k, v in kw.items() if k != "paginas_cartera"}
        salida.append({
            "nombre": c["nombre"], "coste_pagina": r.coste_pagina,
            "margen_pct": r.margen_pct, "reparto": r.reparto, "sano": r.sano,
            "sens": [[s.palanca, s.margen_despues, s.rompe]
                     for s in sensibilidad(p, kw)],
            "clientes": pm["clientes"], "horas": pm.get("horas_revision_mes"),
            "umbral": curva_de_cartera(p, **sin)["umbral_clientes"],
            "pag_max": paginas_maximas(p, **kw)["paginas"],
            "precio_min": precio_minimo(p, **kw)["precio"],
        })
    return salida


class TestPuerteJS(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if shutil.which("node") is None:
            raise unittest.SkipTest(
                "sin node: el motor de verdad es Python y no depende de el")
        cls.casos = json.loads((AQUI / "casos.json").read_text(encoding="utf-8"))
        import os

        # Por variables de entorno y no por argumentos: con `node -e` los
        # indices de `process.argv` dependen de como node parsea la linea, y
        # eso ya me costo un rato.
        entorno = dict(os.environ,
                       MOTOR_JS=str(MOTOR.resolve()),
                       CASOS=str((AQUI / "casos.json").resolve()))
        salida = subprocess.run(["node", "-e", PUENTE], env=entorno,
                                capture_output=True, text=True, timeout=60)
        if salida.returncode != 0:
            raise AssertionError("el puerto JS no corre:\n" + salida.stderr)
        cls.js = json.loads(salida.stdout)
        cls.py = _python(cls.casos)

    def test_los_casos_cubren_los_extremos(self):
        nombres = {c["nombre"] for c in self.casos}
        for imprescindible in ("Regalado", "SinHerr", "SinRevision", "Core-solo"):
            self.assertIn(imprescindible, nombres,
                          "sin los extremos, coincidir no significa nada")

    def test_los_dos_motores_dan_lo_mismo(self):
        diferencias = []
        for a, b in zip(self.py, self.js):
            for clave, va in a.items():
                vb = b.get(clave)
                if clave == "sens":
                    for sa, sb in zip(va, vb):
                        if abs(sa[1] - sb[1]) > 0.11 or sa[2] != sb[2]:
                            diferencias.append((a["nombre"], sa[0], sa, sb))
                elif isinstance(va, (int, float)) and isinstance(vb, (int, float)):
                    if abs(va - vb) > 0.011:
                        diferencias.append((a["nombre"], clave, va, vb))
                elif va != vb:
                    diferencias.append((a["nombre"], clave, va, vb))
        self.assertEqual(diferencias, [], "el puerto JS se ha desviado del motor")

    def test_el_puerto_lleva_la_misma_tarifa_y_la_misma_fecha(self):
        from pricing.unit import TARIFAS, TARIFAS_REVISADAS

        fuente = MOTOR.read_text(encoding="utf-8")
        for modelo in TARIFAS:
            self.assertIn(modelo, fuente, f"falta {modelo} en el puerto")
        self.assertIn(TARIFAS_REVISADAS, fuente,
                      "la fecha de revision de tarifas tiene que ir en los dos")


class TestArtefacto(unittest.TestCase):
    """El banco lleva el motor JS incrustado. Una copia mas que puede desviarse.

    Comprobar solo el fichero canonico no sirve de nada si lo que el usuario
    abre es otra copia: la correccion se aplicaria al que se mide y no al que
    se usa.
    """

    BANCO = Path(__file__).parent.parent / "artefactos" / "banco.html"

    def test_el_banco_lleva_el_motor_tal_cual(self):
        motor = MOTOR.read_text(encoding="utf-8").split("if (typeof module")[0]
        banco = self.BANCO.read_text(encoding="utf-8")
        faltan = []
        for linea in motor.splitlines():
            limpia = linea.strip()
            # Solo las lineas con sustancia: el ruido de formato no prueba nada.
            if len(limpia) < 25 or limpia.startswith(("*", "//", "/*")):
                continue
            if limpia not in banco:
                faltan.append(limpia)
        self.assertEqual(
            faltan[:5], [],
            f"{len(faltan)} linea(s) del motor no estan en el artefacto: la "
            "copia incrustada se ha desviado. Regenerala con "
            "artefactos/construir_banco.py")

    def test_el_banco_tiene_la_pestana_de_economia(self):
        banco = self.BANCO.read_text(encoding="utf-8")
        self.assertIn('data-panel="economia"', banco)
        self.assertIn('data-tab="economia"', banco)
        self.assertIn("calcularEconomia", banco)
