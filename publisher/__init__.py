"""M5 — Publicador multi-CMS: WordPress y Shopify.

El plugin de WordPress es la pieza de friccion que le gana clientes a la
competencia: el cliente conecta y se olvida. Se copia.

Lo que no se copia es el autopiloto por defecto. Aqui todo se publica en
BORRADOR salvo que alguien active explicitamente lo contrario, porque publicar
sin revision es el patron que Google penaliza.

`shopify.py` habla el mismo contrato que `wordpress.py` a proposito:
misma firma de `publish`, mismo `PublishOutcome` y el mismo modo de
fallar, que es devolver el motivo y no lanzar excepciones. Cambiar de
CMS no deberia obligar a reescribir el codigo que llama.
"""

__version__ = "0.1.0"
