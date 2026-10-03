"""M4 — Generador con datos propios y compuertas duras.

La razon de que el contenido de la competencia salga plano (2,1/5 medido) es
que es una reescritura del top 10. Aqui el brief exige, antes de generar, que
la pagina aporte algo que no este ya en los diez primeros resultados: un dato
medido, una cifra atribuible, un requisito citado. Lo que no lo aporta, no
pasa la compuerta.

Economia que justifica el diseno: generar con modelo caro cuesta $0.30-0.60 por
pagina; revisar a mano cuesta $6-15. Gastar diez veces mas en generacion para
bajar la edicion de 30 a 10 minutos se paga doce veces.
"""

__version__ = "0.1.0"
