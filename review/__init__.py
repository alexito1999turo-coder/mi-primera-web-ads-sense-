"""M8 — Compuerta editorial que aprende.

Es el cuello de botella del negocio, no un detalle de calidad: diez clientes a
12 paginas son 120 revisiones al mes. A 30 minutos cada una son 60 horas; a 10
son 20. La diferencia entre esas dos cifras es si el negocio escala.

Dos mecanismos:

1. Triaje: revision completa solo para lo que el sistema marca dudoso.
2. Registro: cada rechazo se guarda con su motivo, se agrupa en taxonomia, y
   vuelve al brief. Sin esto se paga el aprendizaje y se tira.
"""

__version__ = "0.1.0"
