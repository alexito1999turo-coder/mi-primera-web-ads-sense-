"""Formato de texto compartido. Un sitio, no quince.

Nace de un fallo pequeno y repetido: «1 pares comparados», «1 paginas», «1
articulos». Cada uno por separado es una tonteria. Juntos, en el documento que
se le manda a un cliente que esta pagando por rigor, son la clase de detalle
que hace dudar del resto de las cifras.

Estaba escrito a mano en quince sitios, asi que arreglar uno no arreglaba
ninguno. Esto es el sitio.
"""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

MILES = "."
DECIMAL = ","


VOCALES = "aeiouáéíóú"


def plural(n: int | float, singular: str, plural_: str | None = None) -> str:
    """«1 pagina» / «2 paginas».

    Sin el segundo argumento lo deduce, pero solo donde la regla es segura:
    vocal anade «s», consonante anade «es». Las palabras acabadas en «s» NO
    se deducen, porque la regla depende del acento — «mes» hace «meses» y
    «crisis» no cambia — y un deductor que adivina ahi acaba escribiendo
    «2 mess» en el informe de un cliente. Lo descubrio su propio test.

    Falla en vez de adivinar. Es un error de programacion, con la palabra
    escrita en el codigo: salta la primera vez que se ejecuta, no en
    produccion ante un cliente.

    Lo que SIGUE sin cubrir, y conviene saberlo: los prestamos acabados en
    consonante hacen el plural en «s», no en «es» — «clic» hace «clics», y
    este deductor diria «clices». Para esos, el plural explicito. No se
    arregla con una regla porque la frontera entre prestamo y palabra
    asentada no esta en la ortografia.
    """
    if plural_ is None:
        if singular.endswith("s"):
            raise ValueError(
                f"El plural de «{singular}» depende del acento y no se deduce. "
                "Pasalo explicito: plural(n, \"mes\", \"meses\")."
            )
        plural_ = singular + ("s" if singular[-1:].lower() in VOCALES else "es")
    return f"{cifra(n)} {singular if n == 1 else plural_}"


def cifra(n: int | float, decimales: int = 0) -> str:
    """Numero con separador de miles espanol, sin depender del `locale`.

    `locale` depende de lo que tenga instalado la maquina del cliente, y un
    informe que se ve distinto segun el servidor que lo genere no sirve para
    comparar dos meses.
    """
    if decimales:
        entero, _, resto = f"{_redondear(n, decimales):,.{decimales}f}".partition(".")
        return entero.replace(",", MILES) + DECIMAL + resto
    # `round` de Python redondea al par: round(0,5) da 0 y round(1,5) da 2.
    # Es correcto estadisticamente y en un informe parece un fallo, porque
    # dos cifras equivalentes salen distintas. Para ENSENAR numeros se
    # redondea hacia arriba, que es lo que espera quien lo lee.
    return f"{int(_redondear(n, 0)):,}".replace(",", MILES)


def _redondear(n: int | float, decimales: int) -> float:
    cuantia = Decimal(1).scaleb(-decimales)
    return float(Decimal(str(n)).quantize(cuantia, rounding=ROUND_HALF_UP))


def lista(items: list[str], union: str = "y") -> str:
    """«a», «a y b», «a, b y c». Una coma antes de «y» no se usa en espanol."""
    limpio = [i for i in items if i]
    if not limpio:
        return ""
    if len(limpio) == 1:
        return limpio[0]
    return f"{', '.join(limpio[:-1])} {union} {limpio[-1]}"


def porcentaje(valor: float, decimales: int = 0) -> str:
    """De 0-1 a «42%». El error de meter aqui un 42 ya escalado se ve solo."""
    return f"{cifra(valor * 100, decimales)}%"


def porcentajes(conteos: dict[str, int], decimales: int = 1) -> dict[str, float]:
    """Reparto porcentual que suma 100 exactamente.

    Redondear cada parte por su cuenta no suma 100: con cinco clases de
    intencion el reparto salia 99,9%, y en un informe de cliente eso se lee
    como descuido en el resto de las cifras. Lo destapo anadir una clase
    nueva, no un test escrito a proposito.

    Se usa el metodo del resto mayor, que es el de los repartos de escanos:
    se dan las partes enteras y lo que sobra va a quien tenga el resto mas
    grande. Es la unica forma de que cuadre sin falsear ninguna parte mas de
    lo que el redondeo ya obliga.
    """
    total = sum(conteos.values())
    if not total:
        return {}

    escala = 10 ** decimales
    objetivo = 100 * escala
    exactos = {k: 100 * v * escala / total for k, v in conteos.items()}
    suelo = {k: int(v) for k, v in exactos.items()}
    sobran = objetivo - sum(suelo.values())

    # A quien mas resto tenga. Con empate, por nombre, para que dos
    # ejecuciones con los mismos datos den el mismo reparto.
    orden = sorted(exactos, key=lambda k: (-(exactos[k] - suelo[k]), k))
    for k in orden[:sobran]:
        suelo[k] += 1
    return {k: suelo[k] / escala for k in sorted(suelo)}
