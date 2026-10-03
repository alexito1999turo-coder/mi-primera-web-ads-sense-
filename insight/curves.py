"""Curvas y descuentos. Son PRIORES declarados, no mediciones propias.

Van en su propio modulo precisamente para que se vean: el dia que haya datos
propios suficientes, se sustituyen aqui y todo lo demas sigue igual.
"""

from __future__ import annotations

# CTR por posicion. Prior de mercado, no medicion de este sitio.
#
# Se usa para estimar cuanto clic hay que ganar al subir, no para prometer
# nada. Cuando el sitio tenga ocho semanas de datos propios, esta curva se
# calcula con ellos y deja de ser un prior.
CTR_BY_POSITION: dict[int, float] = {
    1: 0.279, 2: 0.157, 3: 0.110, 4: 0.080, 5: 0.061,
    6: 0.049, 7: 0.040, 8: 0.033, 9: 0.028, 10: 0.025,
    11: 0.018, 12: 0.016, 13: 0.014, 14: 0.013, 15: 0.012,
    16: 0.011, 17: 0.010, 18: 0.009, 19: 0.009, 20: 0.008,
}
CTR_FLOOR = 0.004

# Exposicion a AI Overviews por intencion.
#
# De la cobertura medida: las consultas informacionales tienen 99,9% de
# cobertura de AIO y 74,3% de busquedas sin clic. Las transaccionales apenas
# se resuelven con una respuesta generada, porque el usuario necesita ir a
# algun sitio.
AIO_EXPOSURE: dict[str, float] = {
    "informational": 0.90,
    "undetermined": 0.60,
    "commercial": 0.45,
    "transactional": 0.20,
}
DEFAULT_EXPOSURE = 0.60

# De la parte expuesta, cuanto clic se pierde de verdad.
AIO_SUPPRESSION = 0.58


def ctr_at(position: float) -> float:
    """CTR esperable en una posicion. Interpola entre enteros."""
    if position < 1:
        position = 1.0
    low = int(position)
    high = low + 1
    ctr_low = CTR_BY_POSITION.get(low, CTR_FLOOR)
    ctr_high = CTR_BY_POSITION.get(high, CTR_FLOOR)
    fraction = position - low
    return ctr_low + (ctr_high - ctr_low) * fraction


def click_retention(intent: str) -> float:
    """Fraccion del clic que sobrevive a la respuesta generada.

    Es el factor que corrige el reflejo de "posicion 11-30 es oportunidad":
    en informacional la oportunidad esta casi toda comida.
    """
    exposure = AIO_EXPOSURE.get(intent, DEFAULT_EXPOSURE)
    return round(1 - exposure * AIO_SUPPRESSION, 4)


# Valor relativo de un clic por intencion.
#
# Esta aqui porque sin esto el modulo se contradice. Comprobado con numeros: el
# descuento por AI Overviews SOLO casi nunca da la vuelta al orden — una
# consulta informacional de 10.000 impresiones en posicion 12 sigue ganando a
# una comercial de 2.200 aunque le quites la mitad del clic. Priorizar clics es
# priorizar volumen con otro nombre.
#
# Lo que si cambia el orden es que un clic no vale lo que otro. El que busca
# "instalador cerca de mi" esta a un paso de pagar; el que busca "que es la
# nitrificacion" esta a ninguno. Estos pesos son priores de nicho de servicios
# y se sustituyen por los datos de conversion del cliente en cuanto existan.
CLICK_VALUE: dict[str, float] = {
    "informational": 0.15,
    "undetermined": 0.40,
    "commercial": 1.00,
    "transactional": 2.50,
}
DEFAULT_CLICK_VALUE = 0.40


def click_value(intent: str) -> float:
    """Valor relativo de un clic de esta intencion. 1,0 = clic comercial."""
    return CLICK_VALUE.get(intent, DEFAULT_CLICK_VALUE)
