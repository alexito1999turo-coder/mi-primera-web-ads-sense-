"""M11 — Prospeccion: la auditoria gratuita convertida en captacion.

El motor ya sabe auditar un dominio. Lo que no sabia hacer es convertir esa
auditoria en algo que se le pueda mandar a un desconocido: un informe de M1 es
una tabla de veredictos para quien ya sabe lo que es un archivo indexable, y la
persona que firma la factura en una marca de e-commerce no lo sabe ni tiene por
que saberlo.

Esa distancia es la razon de este paquete. La auditoria gratuita es la unica
ventaja de captacion que el producto ya tiene construida y pagada: mide en vivo,
con codigo HTTP y hora de consulta detras de cada afirmacion, y eso es
exactamente lo que un correo frio no puede falsificar. Sin esta pieza se queda
sin usar, porque nadie va a enviar a mano cuarenta auditorias un lunes por la
manana.

Las dos reglas que no se tocan:

  Un dominio que falla no tumba el lote. Se registra el fallo con su motivo y
  se sigue con el siguiente, porque un lote de cuarenta marcas que muere en la
  tercera no sirve para captar a nadie.

  Si no hay hallazgos, no se inventa uno. El resumen lo dice en voz alta y lo
  convierte en argumento. Mandar un problema falso a una marca que no lo tiene
  quema el unico activo de esta pieza, que es ser creible.
"""

__version__ = "0.1.0"
