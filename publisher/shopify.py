"""Cliente de la API Admin de Shopify: articulos dentro de un blog.

Por que existe: el motor publicaba solo en WordPress, y el cliente al que apunta
el plan de ingresos son marcas de Shopify. Era el unico hueco real del motor, no
una tercera forma de hacer lo mismo.

Las dos reglas de `wordpress.py` no cambian de CMS:

1. `status` es "draft" salvo que el llamante pida publicar explicitamente. En
   Shopify el borrador no es un estado con nombre: es el campo `published` del
   articulo puesto a false. La traduccion se hace aqui, para que quien llama
   siga hablando de "draft" y "publish".
2. Un borrador que no paso las compuertas no se publica. Es la prohibicion 3 del
   README, y el publicador sigue siendo el ultimo sitio donde se puede frenar.

El contrato es el de `WordPress` a proposito: mismos nombres de metodo, mismos
parametros de `publish`, mismo `PublishOutcome` (el de `wordpress.py`, importado,
no una copia) y el mismo modo de fallar, que es devolver el motivo en
`refused_reason` y no lanzar excepciones por fallo de negocio. Cambiar de CMS no
deberia obligar a reescribir el codigo que llama.

Lo que no se duplica: el JSON-LD sale de `.schema` y el transporte de urllib sale
de `.wordpress`, que no tiene nada de WordPress. El transporte es inyectable: las
pruebas no tocan la red ni necesitan una tienda levantada.
"""

from __future__ import annotations

import json
import urllib.parse
from dataclasses import dataclass

from generator.gates import Draft, GateResult

from .schema import SchemaContext, build as build_schema, to_script
from .wordpress import (
    STATUS_DRAFT,
    STATUS_PUBLISH,
    Credentials,
    PublishOutcome,
    Transport,
    urllib_transport,
)

# Version de la API Admin. Shopify la saca por trimestres y mantiene cada una un
# ano, asi que fijarla es obligatorio (sin version la peticion no vale) y
# parametrizarla tambien: el dia que esta caduque, se cambia en la llamada y no
# hay que tocar este fichero.
DEFAULT_API_VERSION = "2026-10"

# STATUS_DRAFT, STATUS_PUBLISH, Credentials, PublishOutcome, Transport y
# urllib_transport se importan de `.wordpress` y quedan disponibles tambien aqui
# a proposito: quien los importaba del publicador de WordPress los encuentra en
# este modulo con el MISMO valor y el MISMO tipo. Si fueran copias, `isinstance`
# dejaria de servir y "cambiar de CMS sin tocar nada mas" seria solo de palabra.
# De ese modulo no se importa nada que sepa de WordPress: `urllib_transport` solo
# sabe de urllib.


@dataclass
class AccessToken:
    """Token de app personalizada de la tienda. Nunca la clave de la cuenta."""

    token: str

    def header(self) -> str:
        # Shopify no usa Basic: el token viaja tal cual en su propia cabecera.
        # No hay nada que codificar, asi que no se finge que lo hay. Lo que si se
        # garantiza es que no acaba en la URL ni en el cuerpo, que es donde queda
        # registrado en los logs de todo el mundo.
        return self.token


def _error_message(detail: dict) -> str:
    """El cuerpo del error de Shopify en una linea, para poder diagnosticar.

    Shopify no responde `message` como WordPress: responde `errors`, que a veces
    es un diccionario campo -> lista de fallos y a veces una cadena. Si no se
    reconoce la forma, va el cuerpo entero: es mas util que "sin detalle".
    """
    if not isinstance(detail, dict) or not detail:
        return "sin detalle"

    errors = detail.get("errors")
    if isinstance(errors, dict) and errors:
        parts: list[str] = []
        for field_name, value in errors.items():
            texts = value if isinstance(value, list) else [value]
            parts.append(f"{field_name}: " + "; ".join(str(t) for t in texts))
        return " | ".join(parts)
    if isinstance(errors, str) and errors.strip():
        return errors.strip()

    for key in ("error_description", "error", "message", "raw"):
        value = detail.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()

    return json.dumps(detail, ensure_ascii=False)[:500]


class Shopify:
    def __init__(
        self,
        site_url: str,
        credentials: Credentials,
        blog_id: int | str,
        transport: Transport | None = None,
        api_version: str = DEFAULT_API_VERSION,
    ) -> None:
        # `blog_id` es el tercer parametro y es obligatorio porque en Shopify un
        # articulo no existe fuera de un blog: no hay defecto razonable que
        # inventar. Eso desplaza `transport` un puesto respecto a WordPress, y el
        # fallo silencioso que eso provoca es justo el que no se puede permitir:
        # pasar el doble de pruebas en tercera posicion dejaria `transport` a
        # None y la siguiente linea saldria a internet de verdad. Por eso se
        # comprueba el tipo y se revienta aqui, con la frase que dice que mirar.
        if (
            isinstance(blog_id, bool)
            or not isinstance(blog_id, (int, str))
            or not str(blog_id).strip()
        ):
            raise ValueError(
                "blog_id es obligatorio y va en el tercer parametro: en Shopify "
                "un articulo vive dentro de un blog. Si vienes del publicador de "
                "WordPress, el transporte ahora es el cuarto parametro."
            )
        self.site_url = site_url.rstrip("/")
        self.credentials = credentials
        self.blog_id = blog_id
        self.api_version = api_version
        self.transport = transport or urllib_transport()

    # -- infraestructura --------------------------------------------------
    def _call(self, method: str, path: str, payload: dict | None = None):
        url = f"{self.site_url}/admin/api/{self.api_version}/{path.lstrip('/')}"
        headers = {
            "X-Shopify-Access-Token": self.credentials.header(),
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        body = json.dumps(payload, ensure_ascii=False).encode() if payload else None
        return self.transport(method, url, headers, body)

    @property
    def _articles(self) -> str:
        return f"blogs/{self.blog_id}/articles"

    def find_by_slug(self, slug: str) -> dict | None:
        """Buscar antes de crear: evita duplicar la pagina en cada ejecucion.

        Lo que WordPress llama `slug`, Shopify lo llama `handle`. La traduccion
        se queda dentro: el llamante sigue pasando el slug del borrador.
        """
        # `published_status=any` se pide EXPLICITAMENTE, igual que `status=any` en
        # el publicador de WordPress. El modo normal de este adaptador es
        # borrador, o sea `published` false, asi que el articulo que hay que
        # encontrar casi siempre esta sin publicar. Cual sea el defecto de la API
        # Admin cuando no se pide nada no es parte de nuestro contrato: si no
        # incluyera los no publicados, esta busqueda devolveria None para un
        # borrador que ya existe, `publish` tomaria la rama de creacion y
        # duplicaria el articulo en cada ejecucion. Es justo el fallo que este
        # metodo existe para evitar.
        query = urllib.parse.urlencode({"handle": slug, "published_status": "any"})
        status, data = self._call("GET", f"{self._articles}.json?{query}")
        if not 200 <= status < 300 or not isinstance(data, dict):
            return None
        articles = data.get("articles")
        if isinstance(articles, list) and articles:
            first = articles[0]
            return first if isinstance(first, dict) else None
        return None

    # -- publicacion ------------------------------------------------------
    def publish(
        self,
        draft: Draft,
        gate_result: GateResult,
        schema_context: SchemaContext,
        intent: str = "",
        sources: list[str] | None = None,
        status: str = STATUS_DRAFT,
        categories: list[int] | None = None,
        excerpt: str = "",
        allow_failed_gates: bool = False,
    ) -> PublishOutcome:
        outcome = PublishOutcome(slug=draft.slug)

        # La ultima compuerta. Si llega aqui algo que no paso, se para aqui.
        if not gate_result.passed and not allow_failed_gates:
            codes = ", ".join(f.code for f in gate_result.blocking)
            outcome.refused_reason = (
                f"No se publica: {len(gate_result.blocking)} compuerta(s) "
                f"bloqueante(s) sin resolver ({codes})."
            )
            return outcome

        if status not in (STATUS_DRAFT, STATUS_PUBLISH):
            outcome.refused_reason = f"Estado no valido: {status!r}."
            return outcome

        schema = build_schema(
            title=draft.title,
            body=draft.body,
            slug=draft.slug,
            context=schema_context,
            intent=intent,
            sources=sources or draft.declared_sources,
        )

        # El envoltorio `{"article": {...}}` lo exige la API Admin. `published`
        # false es el borrador: no hay cadena de estado que enviar.
        article: dict = {
            "title": draft.title,
            "handle": draft.slug,
            "body_html": draft.body + "\n\n" + to_script(schema),
            "published": status == STATUS_PUBLISH,
        }
        if excerpt:
            article["summary_html"] = excerpt

        existing = self.find_by_slug(draft.slug)
        if existing and existing.get("id"):
            http_status, data = self._call(
                "PUT", f"{self._articles}/{existing['id']}.json", {"article": article}
            )
        else:
            http_status, data = self._call(
                "POST", f"{self._articles}.json", {"article": article}
            )
            outcome.created = True

        outcome.http_status = http_status
        body = data if isinstance(data, dict) else {}
        # Shopify devuelve el recurso envuelto. Se desenvuelve para que `detail`
        # sea el articulo, como en WordPress `detail` es el post. En el error no
        # hay envoltorio y va el cuerpo entero, que es lo que hace falta leer.
        created_article = body.get("article")
        # Copia, no alias: mas abajo se anota `categories_sin_traducir`, y si
        # `detail` fuera el mismo diccionario que devolvio el transporte esa
        # anotacion acabaria dentro del cuerpo de la respuesta de Shopify. En el
        # camino de error eso llegaba a `_error_message` y el motivo acababa
        # citando nuestra propia anotacion como si fuera el error de la API.
        outcome.detail = dict(created_article) if isinstance(created_article, dict) else dict(body)

        # Shopify no tiene categorias numericas en los articulos. El parametro
        # existe para que la llamada no cambie al cambiar de CMS, pero no se
        # traduce a nada: ni se tira en silencio ni se inventa una etiqueta con
        # el numero dentro. Se declara lo que no se ha podido llevar.
        if categories:
            outcome.detail["categories_sin_traducir"] = list(categories)

        if not 200 <= http_status < 300:
            outcome.refused_reason = (
                f"Shopify respondio {http_status}: {_error_message(body)}"
            )
            outcome.created = False
            return outcome

        outcome.post_id = outcome.detail.get("id")
        # El camino de vuelta de la traduccion: un articulo con fecha de
        # publicacion esta publicado; sin ella, es borrador.
        outcome.status = STATUS_PUBLISH if outcome.detail.get("published_at") else STATUS_DRAFT
        if outcome.post_id:
            outcome.edit_url = (
                f"{self.site_url}/admin/blogs/{self.blog_id}/articles/{outcome.post_id}"
            )
        return outcome
