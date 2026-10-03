"""Registro de rechazos y lo que vuelve al brief.

Cada correccion del revisor es informacion que se ha pagado. Si no se guarda
con su motivo, se paga otra vez el mes que viene.
"""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

# A partir de cuantas veces un motivo deja de ser anecdota y pasa a ser patron.
RECURRING_THRESHOLD = 2


@dataclass
class Rejection:
    """Un rechazo. `instruction` es lo unico que mejora el sistema."""

    slug: str
    code: str
    reason: str
    # La instruccion que habria evitado el fallo. Es lo que se inyecta al brief.
    instruction: str = ""
    reviewer: str = ""
    at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat(timespec="seconds"))


@dataclass
class RejectionLog:
    client: str = ""
    rejections: list[Rejection] = field(default_factory=list)

    def add(self, slug: str, code: str, reason: str, instruction: str = "",
            reviewer: str = "") -> Rejection:
        rejection = Rejection(slug=slug, code=code, reason=reason,
                              instruction=instruction, reviewer=reviewer)
        self.rejections.append(rejection)
        return rejection

    def taxonomy(self) -> dict[str, int]:
        """Motivos por frecuencia. Es el diagnostico del generador."""
        return dict(Counter(r.code for r in self.rejections).most_common())

    def recurring_codes(self, threshold: int = RECURRING_THRESHOLD) -> set[str]:
        return {code for code, count in self.taxonomy().items() if count >= threshold}

    def brief_additions(self, threshold: int = RECURRING_THRESHOLD) -> list[str]:
        """Instrucciones a inyectar en los briefs siguientes.

        Solo las de motivos recurrentes: una correccion suelta puede ser un
        caso raro, y llenar el brief de excepciones lo degrada.
        """
        recurring = self.recurring_codes(threshold)
        seen: set[str] = set()
        out: list[str] = []
        for rejection in self.rejections:
            if rejection.code not in recurring or not rejection.instruction:
                continue
            key = rejection.instruction.strip().lower()
            if key in seen:
                continue
            seen.add(key)
            out.append(rejection.instruction.strip())
        return out

    def minutes_trend(self, window: int = 10) -> str:
        """Lectura honesta: si el registro no baja, el sistema no aprende."""
        if len(self.rejections) < window * 2:
            return (
                f"Aun no hay datos para una tendencia ({len(self.rejections)} "
                f"rechazos, hacen falta {window * 2})."
            )
        older = self.rejections[-window * 2 : -window]
        recent = self.rejections[-window:]
        older_codes = len({r.code for r in older})
        recent_codes = len({r.code for r in recent})
        if recent_codes < older_codes:
            return f"Variedad de fallos bajando: {older_codes} -> {recent_codes}."
        if recent_codes > older_codes:
            return (
                f"Variedad de fallos SUBIENDO: {older_codes} -> {recent_codes}. "
                "El generador esta empeorando o el nicho cambio."
            )
        return f"Variedad de fallos estable en {recent_codes}."

    # -- persistencia -----------------------------------------------------
    def save(self, path: str | Path) -> None:
        payload = {
            "client": self.client,
            "rejections": [asdict(r) for r in self.rejections],
        }
        Path(path).write_text(
            json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8"
        )

    @classmethod
    def load(cls, path: str | Path) -> "RejectionLog":
        file = Path(path)
        if not file.exists():
            return cls()
        data = json.loads(file.read_text(encoding="utf-8"))
        log = cls(client=data.get("client", ""))
        for row in data.get("rejections", []):
            log.rejections.append(Rejection(**row))
        return log
