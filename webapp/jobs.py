"""Trabajos en segundo plano con progreso.

Una auditoria educada tarda segundos: con intervalo de 1,5 s entre peticiones,
un sitio con veinte archivos son treinta segundos. Bloquear la peticion HTTP
todo ese rato da una pagina colgada y un navegador que agota el tiempo.

Asi que la auditoria corre en un hilo, devuelve un identificador, y la pagina
pregunta por el progreso. Es la diferencia entre una demo y algo usable.
"""

from __future__ import annotations

import threading
import time
import traceback
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable

# Un trabajo terminado se guarda un rato para que la pagina lo recoja, y luego
# se tira: esto es un servidor local, no una base de datos.
RETENTION_SECONDS = 900
MAX_JOBS = 50

STATE_RUNNING = "corriendo"
STATE_DONE = "hecho"
STATE_FAILED = "fallo"


@dataclass
class Job:
    id: str
    state: str = STATE_RUNNING
    step: str = ""
    done: int = 0
    total: int = 0
    result: Any = None
    error: str = ""
    started_at: float = field(default_factory=time.time)
    finished_at: float = 0.0

    @property
    def elapsed(self) -> float:
        end = self.finished_at or time.time()
        return round(end - self.started_at, 1)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "state": self.state,
            "step": self.step,
            "done": self.done,
            "total": self.total,
            "elapsed": self.elapsed,
            "error": self.error,
        }


class Progress:
    """Lo que el trabajo usa para contar por donde va."""

    def __init__(self, job: Job) -> None:
        self._job = job

    def set_total(self, total: int) -> None:
        self._job.total = total

    def step(self, text: str, advance: int = 1) -> None:
        self._job.step = text
        self._job.done += advance


class Registry:
    def __init__(self) -> None:
        self._jobs: dict[str, Job] = {}
        self._lock = threading.Lock()

    def submit(self, work: Callable[[Progress], Any]) -> Job:
        self._evict()
        job = Job(id=uuid.uuid4().hex[:12])
        with self._lock:
            self._jobs[job.id] = job

        def runner() -> None:
            try:
                job.result = work(Progress(job))
                job.state = STATE_DONE
            except Exception as exc:  # noqa: BLE001 - el fallo viaja al cliente
                job.state = STATE_FAILED
                job.error = f"{type(exc).__name__}: {exc}"
                job.result = None
                # La traza al log del servidor, no a la pagina.
                traceback.print_exc()
            finally:
                job.finished_at = time.time()

        threading.Thread(target=runner, daemon=True).start()
        return job

    def get(self, job_id: str) -> Job | None:
        with self._lock:
            return self._jobs.get(job_id)

    def _evict(self) -> None:
        now = time.time()
        with self._lock:
            caducados = [
                key for key, job in self._jobs.items()
                if job.finished_at and now - job.finished_at > RETENTION_SECONDS
            ]
            for key in caducados:
                del self._jobs[key]
            if len(self._jobs) > MAX_JOBS:
                por_antiguedad = sorted(self._jobs.values(), key=lambda j: j.started_at)
                for job in por_antiguedad[: len(self._jobs) - MAX_JOBS]:
                    self._jobs.pop(job.id, None)
