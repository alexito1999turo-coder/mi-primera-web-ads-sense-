"""M10 — Memoria del sistema.

Afirme que el foso de este producto es el conjunto de datos medidos, y que solo
se acumula operando. Era falso mientras nada se guardaba: cada ejecucion
empezaba de cero, los priores no veian un solo dato, el registro de rechazos
moria al cerrar el proceso y el corpus para detectar solape habia que pasarlo a
mano.

Esto es la columna que faltaba. Un almacen por sitio y uno de cartera, con
cuatro decisiones de ingenieria que no son adorno:

  - **Escritura atomica.** Se escribe a un fichero temporal y se renombra. Un
    corte a mitad deja el fichero anterior intacto en vez de uno a medias.
  - **Esquema versionado.** Los datos sobreviven a los cambios de formato, con
    migracion declarada en vez de un `KeyError` dentro de seis meses.
  - **Historico de solo anadir.** Las observaciones no se reescriben. Si una
    medicion estuvo mal, se anade la correccion; borrar el pasado es perder la
    unica evidencia de como se llego aqui.
  - **Firmas acotadas.** El corpus de solape no guarda las frases enteras de
    cada pagina: guarda una firma MinHash de tamano fijo. Con mil paginas el
    fichero sigue siendo pequeno y la estimacion de parecido se mantiene.
"""

__version__ = "0.1.0"
