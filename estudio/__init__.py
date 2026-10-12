"""Estudio: la clase que faltaba para el canal.

El resto del repositorio fabrica paginas. Esto fabrica publicaciones de video
con la misma regla de la casa: compuertas que bloquean, dato propio obligatorio,
y nada que se afirme sin algo detras.

Seis piezas:

* `agentes`    — los once oficios, cada uno con la compuerta que posee.
* `compuertas` — lo que impide que salga algo porque toca.
* `plan`       — la semana canonica: siete publicaciones de una investigacion.
* `carrera`    — los minutos vistos que pide la puerta, y cuando sube.
* `jueces`     — tres rubricas con pesos, un veto y un fallo aritmetico.
* `sala`       — quien hace que a esta hora, y quien esta parado por culpa de quien.
* `herramientas` — que se paga, que quita horas medidas y que no.
"""

from . import agentes, carrera, compuertas, herramientas, jueces, plan, sala

__all__ = ["agentes", "carrera", "compuertas", "herramientas", "jueces", "plan", "sala"]
