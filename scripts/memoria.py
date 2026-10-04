"""Prueba de que el sistema recuerda: dos procesos, no uno.

Un test que escribe y lee en la misma ejecucion no demuestra persistencia:
demuestra que un diccionario funciona. Esta prueba arranca un proceso, publica,
lo mata, arranca otro y comprueba que el segundo sabe lo que hizo el primero y
que eso CAMBIA la decision.

Se ejecuta con:  python3 -m scripts.memoria
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent

FUENTE = "https://www.epa.gov/septic"
def relleno(tema: str) -> str:
    """Relleno DISTINTO por pagina.

    La primera version de esta prueba usaba el mismo relleno en las dos
    paginas, asi que la segunda se bloqueaba por solape con la primera y el
    resultado parecia un fallo del sistema cuando era de los datos de prueba.
    Dos paginas legitimas de un mismo sitio no comparten 1.200 palabras.
    """
    frases = [
        f"El {tema} depende del numero de dormitorios de la vivienda.",
        f"En {tema} la normativa del condado manda sobre la del estado.",
        f"Un {tema} mal dimensionado se nota en la factura de luz.",
        f"La inspeccion de {tema} se documenta con fecha y firma.",
    ]
    # 180 variantes: por encima del minimo de palabras de un pilar, que es lo
    # que la compuerta de longitud exige y con razon.
    return " ".join(frases[i % len(frases)] + f" Caso {tema} numero {i}."
                    for i in range(180))


def cuerpo(term: str, cifra: str, tema: str, extra: str = "") -> str:
    return (
        f"# {term}\n\n"
        f"## {term.capitalize()}?\n\n"
        f"La instalacion completa costo {cifra} de mediana en Texas en 2026, "
        "sobre una muestra propia de 40 presupuestos reales. El marco oficial "
        f"esta en [la guia de la EPA]({FUENTE}).\n\n"
        "## Cuanto anade el permiso del condado?\n\n"
        "El permiso del condado anadio 612 $ de media en 2026 en esa misma "
        f"muestra de 40 presupuestos, contrastado con [la guia de la EPA]({FUENTE}).\n\n"
        + extra + relleno(tema)
    )


# -- el trabajo de cada proceso ------------------------------------------
PROCESO = '''
import sys, json
sys.path.insert(0, {raiz!r})
from store.project import ProjectStore
from store.portfolio import PortfolioStore
from generator.brief import Brief, OwnData, Source
from generator.pipeline import produce_many
from generator.llm import ScriptedLLM
from clusters.graph import build as build_graph
from clusters.keywords import Keyword

raiz = {carpeta!r}
cuerpos = json.loads({cuerpos!r})
terminos = json.loads({terminos!r})

almacen = ProjectStore(raiz + "/sitio", client="cliente-demo")
briefs = []
for term in terminos:
    grafo = build_graph([Keyword(term, volume=2000, cpc=14)])
    briefs.append(Brief(
        page=grafo.pages[0],
        what_it_adds="Precios medidos en 40 presupuestos reales.",
        questions=["Cuanto cuesta la instalacion completa?"],
        required_sources=[Source(url="https://www.epa.gov/septic", title="EPA",
                                 consulted_at="2026-10-03")],
        own_data=[OwnData(label="Coste medio", value="14.200 $",
                          method="40 presupuestos 2026")],
    ))

llm = ScriptedLLM(routes={{t: c for t, c in zip(terminos, cuerpos)}},
                  fallback=cuerpos[0])
producciones, stats = produce_many(briefs, llm, store=almacen)

for p in producciones:
    codigos = sorted({{f.code for f in p.attempts[-1].result.findings}}) if p.attempts else []
    print(json.dumps({{"slug": p.brief.page.slug, "pasa": p.passed,
                      "codigos": codigos}}))
print(json.dumps({{"resumen": True, "paginas_en_almacen": len(almacen.pages)}}))
'''


def ejecutar(carpeta: str, terminos: list[str], cuerpos: list[str]) -> list[dict]:
    import json
    codigo = PROCESO.format(raiz=str(RAIZ), carpeta=carpeta,
                            cuerpos=json.dumps(cuerpos),
                            terminos=json.dumps(terminos))
    salida = subprocess.run([sys.executable, "-c", codigo], capture_output=True,
                            text=True, cwd=str(RAIZ))
    if salida.returncode != 0:
        print(salida.stderr)
        raise SystemExit("el proceso hijo fallo")
    return [json.loads(l) for l in salida.stdout.strip().splitlines() if l.strip()]


def main() -> int:
    import json

    with tempfile.TemporaryDirectory() as tmp:
        print("=" * 72)
        print("PROCESO 1 — publica dos paginas en un sitio vacio")
        print("=" * 72)
        t1 = ["cuanto cuesta un sistema septico aerobico",
              "mantenimiento de un sistema septico aerobico"]
        c1 = [cuerpo(t1[0], "14.200 $", tema="coste de instalacion"),
              # La misma cifra propia porque los dos briefs declaran el mismo
              # dato: con otra cifra la pagina se bloquearia por no traer el
              # dato del brief, que es correcto pero no es lo que se prueba.
              cuerpo(t1[1], "14.200 $", tema="mantenimiento anual",
                     extra="El soplante se cambia cada cinco anos. ")]
        filas = ejecutar(tmp, t1, c1)
        for fila in filas:
            print("  ", fila)

        guardadas = [f for f in filas if f.get("resumen")][0]["paginas_en_almacen"]
        print(f"\n  -> el almacen guardo {guardadas} pagina(s)")

        print()
        print("=" * 72)
        print("PROCESO 2 — proceso nuevo, intenta publicar la MISMA pagina")
        print("=" * 72)
        t2 = ["precio de un sistema septico aerobico"]
        # El mismo cuerpo del proceso 1, con otro slug: es la reescritura que
        # ninguna compuerta veia sin memoria.
        c2 = [cuerpo(t1[0], "14.200 $", tema="coste de instalacion")]
        filas2 = ejecutar(tmp, t2, c2)
        for fila in filas2:
            print("  ", fila)

        pagina = [f for f in filas2 if not f.get("resumen")][0]
        bloqueada = not pagina["pasa"]
        por_solape = "solape_con_publicado" in pagina["codigos"]
        no_comprobado = "solape_no_comprobado" in pagina["codigos"]

        print()
        print("=" * 72)
        print("VEREDICTO")
        print("=" * 72)
        print(f"  pagina repetida bloqueada:            {'SI' if bloqueada else 'NO'}")
        print(f"  el motivo es el solape con lo publicado: "
              f"{'SI' if por_solape else 'NO'}")
        print(f"  quedo algo sin comprobar:             "
              f"{'SI' if no_comprobado else 'NO'}")

        estado = Path(tmp) / "sitio" / "estado.json"
        peso = estado.stat().st_size
        datos = json.loads(estado.read_text())
        print(f"\n  estado.json: {peso} bytes, esquema {datos['schema']}, "
              f"{len(datos['pages'])} paginas")
        # Comprobacion de verdad: ninguna frase distintiva de las paginas
        # puede estar en el fichero. Un almacen que guardase el texto seria
        # mas facil, y creceria sin limite.
        crudo = estado.read_text()
        filtradas = [f for f in ("de mediana en Texas", "soplante",
                                 "numero de dormitorios", "la guia de la EPA")
                     if f in crudo]
        print(f"  frases del contenido encontradas en el fichero: "
              f"{filtradas or 'ninguna'}")

        ok = bloqueada and por_solape and not no_comprobado and not filtradas
        print()
        print("RESULTADO:", "la memoria cambia la decision, sin guardar el texto"
              if ok else "FALLO: revisa el veredicto de arriba")
        return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
