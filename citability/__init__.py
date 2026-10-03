"""M7a — Ingenieria de citabilidad.

La competencia RASTREA citaciones en ChatGPT, Perplexity, Gemini y Claude. Eso
es un termometro: te dice que ya ha pasado. No te dice que escribir.

Este modulo invierte el problema. En vez de medir citaciones a posteriori,
puntua una pagina por lo que hace que un modelo la cite, deducido de como
funciona de verdad la generacion con recuperacion:

  El modelo no cita paginas. Cita FRASES que puede levantar enteras, atribuir a
  alguien, y que no encuentra en otras cincuenta fuentes.

De ahi salen cuatro factores medibles sobre el texto, sin red y sin API:

  1. Extraibilidad  — la frase se sostiene sola, fuera de su parrafo
  2. Atribuibilidad — lleva quien, cuando y como
  3. Escasez        — el dato no esta en el consenso, hay que ir a por el
  4. Alineacion     — esta redactada como se pregunta

Y el resultado util no es una nota: es la lista de frases concretas que un
modelo levantaria de la pagina. Eso se le puede ensenar a un cliente.

Los pesos son hipotesis declaradas, no verdad revelada: se calibran cuando
haya citaciones reales medidas. El modulo dice que son priores.
"""

__version__ = "0.1.0"
