"""Cliente de la API REST de WordPress.

Dos reglas que no se tocan:

1. `status` es "draft" salvo que el llamante pida publicar explicitamente. El
   autopiloto es una decision del cliente, no el defecto del sistema.
2. Un borrador que no paso las compuertas no se publica. El publicador es el
   ultimo sitio donde se puede frenar, asi que frena.

El transporte es inyectable: las pruebas no tocan la red ni necesitan un
WordPress levantado.
"""

from __future__ import annotations

import base64
import json
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from typing import Callable, Protocol

from generator.gates import Draft, GateResult

from .schema import SchemaContext, build as build_schema, to_script

STATUS_DRAFT = "draft"
STATUS_PUBLISH = "publish"

# (metodo, url, cabeceras, cuerpo) -> (codigo, json)
Transport = Callable[[str, str, dict, bytes | None], tuple[int, dict]]


class Credentials(Protocol):
    def header(self) -> str: ...


def _same_slug(returned: object, asked: str) -> bool:
    """Lo devuelto por el CMS es lo que se pidio.

    Sin tildes ni normalizaciones raras: se compara en minusculas porque los dos
    CMS guardan el slug en minusculas y el llamante puede pasarlo como sea.
    """
    return isinstance(returned, str) and returned.lower() == asked.lower()


@dataclass
class AppPassword:
    """Contrasena de aplicacion de WordPress. Nunca la contrasena de la cuenta."""

    user: str
    password: str

    def header(self) -> str:
        raw = f"{self.user}:{self.password}".encode()
        return "Basic " + base64.b64encode(raw).decode()


def urllib_transport(timeout: int = 30) -> Transport:
    def send(method: str, url: str, headers: dict, body: bytes | None):
        request = urllib.request.Request(url, data=body, headers=headers, method=method)
        try:
            with urllib.request.urlopen(request, timeout=timeout) as handle:
                payload = handle.read()
                return handle.status, (json.loads(payload) if payload else {})
        except urllib.error.HTTPError as exc:
            payload = b""
            try:
                payload = exc.read()
            except Exception:  # noqa: BLE001
                pass
            detail: dict = {}
            try:
                detail = json.loads(payload) if payload else {}
            except json.JSONDecodeError:
                detail = {"raw": payload.decode("utf-8", errors="replace")[:500]}
            return exc.code, detail

    return send


@dataclass
class PublishOutcome:
    slug: str
    status: str = ""
    post_id: int | None = None
    edit_url: str = ""
    created: bool = False
    refused_reason: str = ""
    http_status: int = 0
    detail: dict = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return self.post_id is not None and not self.refused_reason


class WordPress:
    def __init__(
        self,
        site_url: str,
        credentials: Credentials,
        transport: Transport | None = None,
    ) -> None:
        self.site_url = site_url.rstrip("/")
        self.credentials = credentials
        self.transport = transport or urllib_transport()

    # -- infraestructura --------------------------------------------------
    def _call(self, method: str, path: str, payload: dict | None = None):
        url = f"{self.site_url}/wp-json/wp/v2/{path.lstrip('/')}"
        headers = {
            "Authorization": self.credentials.header(),
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        body = json.dumps(payload, ensure_ascii=False).encode() if payload else None
        return self.transport(method, url, headers, body)

    def find_by_slug(self, slug: str) -> dict | None:
        """Buscar antes de crear: evita duplicar la pagina en cada ejecucion.

        La query va codificada: un slug con `&` partia la URL y colaba un
        parametro mas, y uno con espacios la rompia. Interpolar a mano en una
        URL es inyeccion, aunque el valor venga de casa.

        Y se confirma que lo devuelto es lo pedido. Si la API ignorase el filtro
        y contestara con otro post, `publish` tomaria la rama de actualizacion y
        sobreescribiria una pagina ajena. Preferible crear un duplicado, que se
        ve y se borra, a pisar algo que no es nuestro.
        """
        query = urllib.parse.urlencode({"slug": slug, "status": "any"})
        status, data = self._call("GET", f"posts?{query}")
        if not 200 <= status < 300 or not isinstance(data, list) or not data:
            return None
        first = data[0]
        if not isinstance(first, dict):
            return None
        return first if _same_slug(first.get("slug"), slug) else None

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

        payload: dict = {
            "title": draft.title,
            "slug": draft.slug,
            "content": draft.body + "\n\n" + to_script(schema),
            "status": status,
        }
        if excerpt:
            payload["excerpt"] = excerpt
        if categories:
            payload["categories"] = categories

        existing = self.find_by_slug(draft.slug)
        if existing and existing.get("id"):
            http_status, data = self._call("POST", f"posts/{existing['id']}", payload)
        else:
            http_status, data = self._call("POST", "posts", payload)
            outcome.created = True

        outcome.http_status = http_status
        outcome.detail = data if isinstance(data, dict) else {}

        if not 200 <= http_status < 300:
            message = outcome.detail.get("message", "sin detalle")
            outcome.refused_reason = f"WordPress respondio {http_status}: {message}"
            outcome.created = False
            return outcome

        outcome.post_id = outcome.detail.get("id")
        outcome.status = outcome.detail.get("status", status)
        if outcome.post_id:
            outcome.edit_url = f"{self.site_url}/wp-admin/post.php?post={outcome.post_id}&action=edit"
        return outcome
