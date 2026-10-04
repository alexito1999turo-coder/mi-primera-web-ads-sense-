"""Ejecuta el experimento controlado sobre los articulos de specimens/.

    python3 -m scripts.experimento
"""
from __future__ import annotations

import pathlib

from calibration.calibrator import calibrate
from clusters.graph import build
from clusters.keywords import Keyword
from generator.brief import Brief, OwnData, Source
from rubric.experiment import run, to_observations
from rubric.specimens import variantes

SEVERIDADES = {
    "afirmacion_sin_respaldo": "bloqueante", "dato_propio_ausente": "bloqueante",
    "sin_fuentes_enlazadas": "bloqueante", "fuente_obligatoria_ausente": "bloqueante",
    "densidad_anomala": "bloqueante", "longitud_insuficiente": "bloqueante",
    "solape_con_publicado": "bloqueante", "sin_frase_citable": "bloqueante",
    "citabilidad_pobre": "aviso", "secundaria_ausente": "aviso",
    "pregunta_sin_contestar": "aviso", "solape_no_comprobado": "nota",
}


def brief_de(keyword: str) -> Brief:
    page = build([Keyword(keyword, volume=2000, cpc=14)]).pages[0]
    page.role = "satellite"
    return Brief(
        page=page,
        what_it_adds="Precios medidos en 30 presupuestos reales, no rangos copiados.",
        questions=["Cuanto cuesta la instalacion completa?",
                   "Cuanto anade el permiso del condado?"],
        required_sources=[
            Source(url="https://www.epa.gov/septic", title="EPA", consulted_at="2026-10-04"),
            Source(url="https://www.tceq.texas.gov/permitting/ossf", title="TCEQ",
                   consulted_at="2026-10-04"),
        ],
        own_data=[OwnData(label="Coste mediano de instalacion", value="15.498,50 $",
                          method="mediana de 30 presupuestos reales de 2026")],
        brand_voice="Directo, cifras antes que adjetivos",
    )


def main() -> int:
    cuerpo = pathlib.Path("specimens/01-coste-instalacion-texas.md").read_text()
    keyword = "cuanto cuesta un sistema septico aerobico"
    brief = brief_de(keyword)
    specs = variantes("coste-instalacion-texas", cuerpo, keyword, "15.498,50 $")
    experimento = run([(s, brief) for s in specs])

    print(experimento.describe(), "\n")
    for outcome in experimento.outcomes:
        marca = "LIMPIO " if outcome.specimen.clean else "DEFECTO"
        print(f"  [{marca}] {outcome.specimen.slug}")
        if outcome.specimen.injected:
            print(f"            inyectado: {sorted(outcome.specimen.injected)}")
            print(f"            cazado:    {sorted(outcome.caught) or '— NO SE CAZO'}")
        print(f"            bloquean:  {sorted(outcome.fired_blocking) or 'ninguna'}")

    print("\nPor compuerta:")
    for codigo in sorted(experimento.gates):
        marcador = experimento.gates[codigo]
        if marcador.caught + marcador.missed or marcador.fired_without_injection:
            print("  " + marcador.describe())

    print("\n" + calibrate(to_observations(experimento), SEVERIDADES).describe())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
