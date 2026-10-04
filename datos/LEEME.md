# El almacén de los proyectos

Esto **sí** va al repositorio, a propósito.

El contenedor en el que corre el sistema es efímero: se recicla al cerrar la
sesión. Si el almacén no se versiona, la memoria dura lo que dure la sesión, y
entonces no hay memoria — que es justo lo que este módulo existe para arreglar.

Lo que hay aquí dentro, y lo que NO:

- **Sí:** firmas MinHash de las páginas publicadas (hashes, no texto),
  observaciones medidas con su fecha y su nota, y los rechazos del revisor con
  la instrucción que los habría evitado.
- **No:** el texto de ninguna página. Una firma de 1.500 palabras son 256
  hashes y no se puede reconstruir el original desde ellos. Tampoco hay claves
  ni credenciales: el sistema las lee del entorno y nunca las escribe.

Si algún día entra aquí un dato que no deba publicarse, el sitio para cortarlo
es este fichero y el `.gitignore`, no el código.
