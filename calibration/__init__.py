"""M8b — Calibracion de las compuertas con el criterio del revisor.

Las compuertas son heuristicas escritas por alguien. Nadie en esta categoria de
producto mide sus propias compuertas, y es un problema de dinero, no de estilo:

- Una compuerta que marca paginas que el revisor luego aprueba consume minutos
  de revision para nada y entrena al revisor a ignorarla. Precision baja.
- Lo que el revisor rechaza sin que ninguna compuerta avisara es una compuerta
  que falta. Cobertura incompleta.

Este modulo convierte el veredicto humano en la verdad de referencia, mide cada
compuerta contra el, y recomienda subirla, bajarla, crearla o retirarla.

Rigor estadistico explicito: con muestras pequenas una proporcion no significa
nada, asi que se usa el limite inferior de Wilson y por debajo del tamano minimo
el modulo dice "muestra insuficiente" en vez de inventar un numero.
"""

__version__ = "0.1.0"
