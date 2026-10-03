"""Banco de pruebas: un WordPress de verdad, servido por HTTP de verdad.

Por que existe: hasta ahora el sistema estaba verificado con dobles dentro del
proceso. Eso prueba la logica y no prueba nada del transporte — ni la cabecera
de autenticacion, ni gzip, ni el charset, ni los redirects, ni como se comporta
el analizador con el marcado real de un tema de WordPress, que trae nav, header,
footer, aside, comentarios de Yoast y enlaces por todas partes.

Este modulo levanta un servidor HTTP que habla el contrato real de WordPress
(paginas, sitemaps, robots.txt y la API REST con sus codigos de estado y sus
formas de error) para poder pasar el sistema entero por la red sin depender de
que nadie me preste un sitio.
"""

__version__ = "0.1.0"
