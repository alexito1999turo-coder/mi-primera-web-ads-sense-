"""Servidor de la aplicacion. Libreria estandar, sin dependencias.

Se ata a 127.0.0.1 a proposito: es una herramienta que uno levanta en su
maquina, y abrirla a la red sin autenticacion convertiria el auditor en un
servicio que cualquiera puede usar para pedir paginas en tu nombre.
"""

from __future__ import annotations

import json
import socket
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

from . import api
from .jobs import STATE_FAILED, STATE_RUNNING, Registry
from .offer import page as offer_page
from .views import page

MAX_BODY = 8_000_000


class Handler(BaseHTTPRequestHandler):
    registry: Registry
    allow_private: bool = False
    server_version = "BancoSEO/0.1"

    def log_message(self, fmt: str, *args) -> None:
        # Una linea por peticion, sin la parrafada por defecto.
        print(f"  {self.command} {self.path.split('?')[0]} {args[1] if len(args) > 1 else ''}")

    # -- utilidades -------------------------------------------------------
    def _send(self, status: int, body: bytes, content_type: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def _json(self, status: int, payload: dict) -> None:
        self._send(status, json.dumps(payload, ensure_ascii=False).encode(),
                   "application/json; charset=utf-8")

    def _body(self) -> dict:
        length = int(self.headers.get("Content-Length") or 0)
        if length > MAX_BODY:
            raise api.BadRequest("El cuerpo de la peticion es demasiado grande.")
        if not length:
            return {}
        raw = self.rfile.read(length)
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            raise api.BadRequest("El cuerpo no es JSON valido.") from None
        if not isinstance(data, dict):
            raise api.BadRequest("Se esperaba un objeto JSON.")
        return data

    # -- rutas ------------------------------------------------------------
    def do_GET(self) -> None:  # noqa: N802
        self._dispatch(self._get)

    def do_POST(self) -> None:  # noqa: N802
        self._dispatch(self._post)

    def _dispatch(self, handler) -> None:
        try:
            handler()
        except api.BadRequest as exc:
            # Lo que llega mal de fuera: 400 con una frase util, no una traza.
            self._json(400, {"error": str(exc)})
        except Exception as exc:  # noqa: BLE001
            import traceback
            traceback.print_exc()
            self._json(500, {"error": f"{type(exc).__name__}: {exc}"})

    def _get(self) -> None:
        path = urlparse(self.path).path
        if path in ("/", "/index.html"):
            self._send(200, page().encode("utf-8"), "text/html; charset=utf-8")
            return
        if path == "/oferta":
            self._send(200, offer_page().encode("utf-8"), "text/html; charset=utf-8")
            return
        if path == "/salud":
            self._json(200, {"ok": True, "version": "0.1.0"})
            return
        if path.startswith("/api/job/"):
            resto = path[len("/api/job/"):].strip("/")
            quiere_resultado = resto.endswith("/resultado")
            job_id = resto[: -len("/resultado")] if quiere_resultado else resto
            job = self.registry.get(job_id)
            if job is None:
                self._json(404, {"error": "Ese trabajo ya no existe."})
                return
            if not quiere_resultado:
                self._json(200, job.to_dict())
                return
            if job.state == STATE_RUNNING:
                self._json(409, {"error": "Todavia esta corriendo."})
                return
            if job.state == STATE_FAILED:
                self._json(500, {"error": job.error})
                return
            self._json(200, {"job": job.to_dict(), "result": job.result})
            return
        self._json(404, {"error": "No hay nada en esa ruta."})

    def _post(self) -> None:
        path = urlparse(self.path).path
        data = self._body()

        if path == "/api/auditoria":
            work = api.audit(
                site=data.get("site", ""),
                thin_words=data.get("thin_words", 600),
                interval=data.get("interval", 1.0),
                max_archives=data.get("max_archives", 40),
                allow_private=self.allow_private,
            )
            job = self.registry.submit(work)
            self._json(202, job.to_dict())
            return
        if path == "/api/citabilidad":
            self._json(200, api.citability(data.get("text", "")))
            return
        if path == "/api/oportunidad":
            self._json(200, api.opportunity(data.get("csv", "")))
            return
        if path == "/api/clusters":
            self._json(200, api.clusters(data.get("csv", ""),
                                         data.get("cap", 24)))
            return
        self._json(404, {"error": "No hay nada en esa ruta."})


def build(port: int = 8000, allow_private: bool = False) -> ThreadingHTTPServer:
    registro = Registry()
    bound = type("Bound", (Handler,),
                 {"registry": registro, "allow_private": allow_private})
    return ThreadingHTTPServer(("127.0.0.1", port), bound)


def serve(port: int = 8000, allow_private: bool = False) -> None:
    servidor = build(port=port, allow_private=allow_private)
    direccion = f"http://127.0.0.1:{servidor.server_address[1]}"
    print(f"\n  Banco de pruebas SEO-GEO en {direccion}")
    print("  Auditoria, citabilidad, oportunidad y clusters. Ctrl-C para parar.")
    print(f"  Que se vende y cuanto cuesta: {direccion}/oferta\n")
    try:
        servidor.serve_forever()
    except KeyboardInterrupt:
        print("\n  Parado.")
    finally:
        servidor.server_close()


class Background:
    """El servidor en un hilo, para las pruebas."""

    def __init__(self, allow_private: bool = True) -> None:
        self.server = build(port=0, allow_private=allow_private)
        self.base = f"http://127.0.0.1:{self.server.server_address[1]}"
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)

    def __enter__(self) -> "Background":
        self.thread.start()
        return self

    def __exit__(self, *exc) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)
