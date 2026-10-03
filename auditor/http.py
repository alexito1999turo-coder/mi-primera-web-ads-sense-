"""Cliente HTTP educado con verificacion dura.

Cada peticion devuelve codigo de estado, cabeceras, cuerpo y la hora de
consulta en UTC. Nada se afirma sin una de estas respuestas detras.
"""

from __future__ import annotations

import gzip
import time
import urllib.error
import urllib.request
import zlib
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

USER_AGENT = (
    "M1Auditor/0.1 (+auditoria tecnica de archivos finos; "
    "peticiones espaciadas; contacto en el informe)"
)

DEFAULT_MIN_INTERVAL = 1.5
DEFAULT_TIMEOUT = 20
MAX_BYTES = 3_000_000


@dataclass
class Response:
    """Respuesta medida. `consulted_at` es la prueba de cuando se midio."""

    url: str
    final_url: str
    status: int
    headers: dict[str, str] = field(default_factory=dict)
    body: str = ""
    elapsed_ms: int = 0
    consulted_at: str = ""
    error: Optional[str] = None

    @property
    def ok(self) -> bool:
        return 200 <= self.status < 300

    @property
    def content_type(self) -> str:
        return self.headers.get("content-type", "")

    @property
    def redirected(self) -> bool:
        return self.final_url.rstrip("/") != self.url.rstrip("/")

    def summary(self) -> str:
        """Linea de verificacion dura para el informe."""
        if self.error:
            return f"{self.url} -> ERROR {self.error} ({self.consulted_at})"
        extra = f" -> {self.final_url}" if self.redirected else ""
        return (
            f"{self.url} -> HTTP {self.status}{extra} "
            f"[{self.content_type}] {self.elapsed_ms}ms ({self.consulted_at})"
        )


def _decode(raw: bytes, headers: dict[str, str]) -> str:
    encoding = headers.get("content-encoding", "").lower()
    if "gzip" in encoding:
        try:
            raw = gzip.decompress(raw)
        except OSError:
            pass
    elif "deflate" in encoding:
        try:
            raw = zlib.decompress(raw)
        except zlib.error:
            try:
                raw = zlib.decompress(raw, -zlib.MAX_WBITS)
            except zlib.error:
                pass

    charset = "utf-8"
    ctype = headers.get("content-type", "")
    if "charset=" in ctype:
        charset = ctype.split("charset=", 1)[1].split(";")[0].strip().strip('"')
    try:
        return raw.decode(charset, errors="replace")
    except LookupError:
        return raw.decode("utf-8", errors="replace")


class Client:
    """Cliente con intervalo minimo entre peticiones.

    El espaciado no es cortesia opcional: una rafaga contra el sitio de un
    cliente es una forma de romperselo.
    """

    def __init__(
        self,
        min_interval: float = DEFAULT_MIN_INTERVAL,
        timeout: int = DEFAULT_TIMEOUT,
        user_agent: str = USER_AGENT,
    ) -> None:
        self.min_interval = min_interval
        self.timeout = timeout
        self.user_agent = user_agent
        self._last_request_at = 0.0
        self.request_count = 0

    def _wait(self) -> None:
        delta = time.monotonic() - self._last_request_at
        if self._last_request_at and delta < self.min_interval:
            time.sleep(self.min_interval - delta)

    def get(self, url: str) -> Response:
        self._wait()
        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        started = time.monotonic()
        request = urllib.request.Request(
            url,
            headers={
                "User-Agent": self.user_agent,
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Encoding": "gzip, deflate",
            },
            method="GET",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as handle:
                headers = {k.lower(): v for k, v in handle.headers.items()}
                raw = handle.read(MAX_BYTES)
                response = Response(
                    url=url,
                    final_url=handle.geturl(),
                    status=handle.status,
                    headers=headers,
                    body=_decode(raw, headers),
                    elapsed_ms=int((time.monotonic() - started) * 1000),
                    consulted_at=now,
                )
        except urllib.error.HTTPError as exc:
            headers = {k.lower(): v for k, v in (exc.headers or {}).items()}
            raw = b""
            try:
                raw = exc.read(MAX_BYTES)
            except Exception:  # noqa: BLE001 - el cuerpo del error es opcional
                pass
            response = Response(
                url=url,
                final_url=exc.geturl() if hasattr(exc, "geturl") else url,
                status=exc.code,
                headers=headers,
                body=_decode(raw, headers),
                elapsed_ms=int((time.monotonic() - started) * 1000),
                consulted_at=now,
            )
        except Exception as exc:  # noqa: BLE001 - red, DNS, TLS, timeout
            response = Response(
                url=url,
                final_url=url,
                status=0,
                elapsed_ms=int((time.monotonic() - started) * 1000),
                consulted_at=now,
                error=f"{type(exc).__name__}: {exc}",
            )
        finally:
            self._last_request_at = time.monotonic()
            self.request_count += 1
        return response
