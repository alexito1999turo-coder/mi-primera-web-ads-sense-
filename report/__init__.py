"""M11 — El informe mensual, que es el producto que el cliente ve.

El competidor entrega un numero: «hemos publicado 30 articulos». Es facil de
producir y no responde a la unica pregunta que el cliente se hace en el mes
cuatro, cuando el trafico no sube: *y esto que me ha dado*.

Este informe se construye con tres reglas que lo hacen distinto:

  - **Se ensambla desde el almacen, no se escribe.** Una cifra que nadie midio
    no puede aparecer, porque no hay donde teclearla.
  - **Cada cifra lleva su procedencia.** Medida, estimada o supuesta. Las tres
    se pueden entregar; confundirlas, no.
  - **Hay una seccion obligatoria de lo que NO se sabe,** y se genera sola. No
    se puede borrar sin borrar los datos que la producen, que es lo que la
    hace creible.

La cuarta regla es la que lo convierte en un documento de decision en vez de
un parte de trabajo: dice **que haria cambiar la recomendacion**. Un informe
que solo justifica lo hecho no sirve para decidir el mes siguiente.
"""

__version__ = "0.1.0"
