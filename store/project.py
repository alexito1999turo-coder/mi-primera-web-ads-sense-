"""El almacen de un sitio: lo que el sistema recuerda de el.

Tres cosas se guardan, y cada una porque sin ella una pieza del sistema estaba
mintiendo:

  - **Las paginas publicadas**, como firma MinHash. La compuerta de solape
    avisaba «sin corpus: el solape no se ha comprobado» en cada ejecucion,
    porque el corpus habia que pasarlo a mano y nadie lo pasaba.
  - **Las observaciones**, en historico de solo anadir. Los priores se
    diluyen con los datos, pero no llegaba ninguno: cada ejecucion los
    presentaba al 100% de suposicion.
  - **Los rechazos del revisor**, con la instruccion que los habria evitado.
    Es lo que vuelve al brief, y moria al cerrar el proceso.

La diferencia entre esto y una base de datos no es el tamano: es que aqui el
fichero se puede abrir y leer. Un almacen que el cliente no puede auditar no
sirve para vender honestidad.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from review.log import Rejection, RejectionLog

from .archivo import Esquema, append_line, read_json, read_lines, write_json
from .sketch import Sketch, merge, similarity

ESTADO = "estado.json"
HISTORICO = "observaciones.jsonl"
RECHAZOS = "rechazos.json"

MEDIDO = "medido"
DECLARADO = "declarado"


def _ahora() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _migrar_1_a_2(data: dict) -> dict:
    """v1 guardaba los fragmentos enteros de cada pagina; v2 guarda la firma.

    Esta migracion es la razon de que el esquema este versionado y no es un
    ejemplo inventado: la primera version del almacen guardaba `shingles` como
    lista, y con doscientas paginas el fichero pasaba de los diez megas. Los
    datos viejos no se tiran: de la lista de fragmentos sale la firma exacta.
    """
    paginas = data.get("pages") or {}
    for slug, row in paginas.items():
        if "sketch" in row:
            continue
        fragmentos = row.pop("shingles", None)
        if fragmentos is None:
            continue
        unicos = sorted(set(int(h) if str(h).lstrip("-").isdigit()
                            else _hash_texto(h) for h in fragmentos))
        row["sketch"] = Sketch(hashes=unicos[:256], size=len(unicos),
                               k=256).to_dict()
        row["migrado_de"] = "v1:shingles"
    data["pages"] = paginas
    return data


def _hash_texto(fragmento: str) -> int:
    from .sketch import _hash
    return _hash(fragmento)


ESQUEMA = Esquema(version=2, migraciones={1: _migrar_1_a_2})


@dataclass
class PublishedPage:
    slug: str
    sketch: Sketch
    words: int = 0
    at: str = ""
    url: str = ""
    role: str = ""
    migrado_de: str = ""

    def to_dict(self) -> dict:
        row = {"sketch": self.sketch.to_dict(), "words": self.words,
               "at": self.at, "url": self.url, "role": self.role}
        if self.migrado_de:
            row["migrado_de"] = self.migrado_de
        return row

    @classmethod
    def from_dict(cls, slug: str, row: dict) -> "PublishedPage":
        return cls(slug=slug, sketch=Sketch.from_dict(row.get("sketch") or {}),
                   words=int(row.get("words", 0)), at=row.get("at", ""),
                   url=row.get("url", ""), role=row.get("role", ""),
                   migrado_de=row.get("migrado_de", ""))


@dataclass
class Overlap:
    """El parecido mas alto de un texto con lo ya publicado."""

    slug: str = ""
    value: float = 0.0
    estimated: bool = True
    compared: int = 0

    @property
    def measured(self) -> bool:
        """Falso cuando no habia nada con lo que comparar."""
        return self.compared > 0

    def describe(self) -> str:
        if not self.measured:
            return "Solape no medido: el almacen no tiene ninguna pagina todavia."
        modo = "estimado" if self.estimated else "exacto"
        return (f"Solape maximo {self.value * 100:.0f}% ({modo}) contra "
                f"'{self.slug}', sobre {self.compared} pagina(s) publicada(s).")


@dataclass
class Observation:
    """Una observacion del historico.

    `source` separa lo medido de lo declarado. Sin esa columna un almacen
    convierte una estimacion en un dato con solo guardarla.
    """

    seq: int
    metric: str
    value: float
    source: str = MEDIDO
    note: str = ""
    at: str = ""
    corrects: int | None = None

    def to_dict(self) -> dict:
        row = {"seq": self.seq, "metric": self.metric, "value": self.value,
               "source": self.source, "note": self.note, "at": self.at}
        if self.corrects is not None:
            row["corrects"] = self.corrects
        return row


class ProjectStore:
    """Un directorio por sitio. Abrirlo dos veces da el mismo estado."""

    def __init__(self, root: str | Path, client: str = ""):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.migrations: list[str] = []
        data = read_json(self.root / ESTADO, default=None)
        if data is None:
            data = {"schema": ESQUEMA.version, "client": client,
                    "created": _ahora(), "pages": {}}
        else:
            data, self.migrations = ESQUEMA.upgrade(data)
            if self.migrations:
                write_json(self.root / ESTADO, data)
        self.client = client or data.get("client", "")
        self._created = data.get("created", _ahora())
        self.pages: dict[str, PublishedPage] = {
            slug: PublishedPage.from_dict(slug, row)
            for slug, row in (data.get("pages") or {}).items()
        }
        # Abrir el almacen lo crea en disco. Si solo existiera a partir de la
        # primera pagina guardada, un sitio sin publicar nada no se
        # distinguiria de un sitio que nunca se abrio, y lo primero es
        # informacion util: hay cliente y todavia no hay contenido.
        if not (self.root / ESTADO).exists():
            self._flush()

    # -- paginas publicadas -----------------------------------------------
    def record_page(self, slug: str, body: str, words: int = 0, url: str = "",
                    role: str = "") -> PublishedPage:
        """Guarda la firma de una pagina publicada. Idempotente por slug."""
        pagina = PublishedPage(
            slug=slug, sketch=Sketch.of(body),
            words=words or len(re.findall(r"\S+", body)),
            at=_ahora(), url=url, role=role,
        )
        self.pages[slug] = pagina
        self._flush()
        return pagina

    def forget_page(self, slug: str) -> bool:
        """Una pagina despublicada deja de contar para el solape."""
        if slug not in self.pages:
            return False
        del self.pages[slug]
        self._flush()
        return True

    def corpus(self) -> dict[str, Sketch]:
        return {slug: p.sketch for slug, p in self.pages.items()}

    def overlap_of(self, body: str, skip: str = "") -> Overlap:
        """Parecido maximo de un texto con el corpus guardado."""
        mia = Sketch.of(body)
        candidatas = {s: p for s, p in self.pages.items() if s != skip}
        peor = Overlap(compared=len(candidatas))
        for slug, pagina in candidatas.items():
            valor = similarity(mia, pagina.sketch)
            if valor >= peor.value:
                peor.slug = slug
                peor.value = round(valor, 4)
                peor.estimated = not (mia.exact and pagina.sketch.exact)
        return peor

    def fingerprint(self) -> Sketch:
        """Huella del sitio entero, acumulada desde las firmas."""
        return merge(*[p.sketch for p in self.pages.values()])

    # -- observaciones ----------------------------------------------------
    def observe(self, metric: str, value: float, source: str = MEDIDO,
                note: str = "", corrects: int | None = None) -> Observation:
        seq = self._next_seq()
        obs = Observation(seq=seq, metric=metric, value=float(value),
                          source=source, note=note, at=_ahora(),
                          corrects=corrects)
        append_line(self.root / HISTORICO, obs.to_dict())
        return obs

    def correct(self, seq: int, value: float, note: str) -> Observation:
        """Corrige una observacion anterior sin borrarla.

        Exige nota: una correccion sin motivo es indistinguible de maquillar
        los numeros, que es exactamente lo que el historico tiene que impedir.
        """
        if not note.strip():
            raise ValueError("Una correccion sin motivo escrito no se guarda.")
        original = self._by_seq().get(seq)
        if original is None:
            raise KeyError(f"No hay observacion con seq={seq}.")
        return self.observe(original.metric, value, source=original.source,
                            note=note, corrects=seq)

    def history(self) -> list[Observation]:
        """Todo lo escrito, correcciones incluidas, en orden."""
        salida: list[Observation] = []
        for row in read_lines(self.root / HISTORICO):
            try:
                salida.append(Observation(
                    seq=int(row["seq"]), metric=str(row["metric"]),
                    value=float(row["value"]), source=row.get("source", MEDIDO),
                    note=row.get("note", ""), at=row.get("at", ""),
                    corrects=(int(row["corrects"]) if row.get("corrects") is not None
                              else None),
                ))
            except (KeyError, TypeError, ValueError):
                continue
        return salida

    def observations(self, metric: str, source: str | None = None) -> list[float]:
        """Valores vigentes de una metrica, con las correcciones aplicadas.

        El historico no se toca: la correccion sustituye el valor al leer, y el
        original sigue en el fichero para quien audite.
        """
        todas = self.history()
        reemplazo: dict[int, float] = {}
        anulados: set[int] = set()
        for obs in todas:
            if obs.corrects is not None:
                reemplazo[obs.corrects] = obs.value
                anulados.add(obs.seq)
        salida: list[float] = []
        for obs in todas:
            if obs.metric != metric or obs.seq in anulados:
                continue
            if source is not None and obs.source != source:
                continue
            salida.append(reemplazo.get(obs.seq, obs.value))
        return salida

    def metrics(self) -> dict[str, int]:
        """Cuantas observaciones vigentes hay de cada metrica."""
        nombres = {o.metric for o in self.history()}
        return {n: len(self.observations(n)) for n in sorted(nombres)}

    def feed(self, prior_set, mapping: dict[str, str] | None = None) -> None:
        """Mete el historico en un `PriorSet` para que los priores se diluyan.

        Solo entran observaciones marcadas como medidas. Alimentar un prior con
        valores declarados le haria creer que ya hay evidencia y apagaria la
        unica senal honesta que tiene el sistema.
        """
        for nombre in list(prior_set.priors):
            metrica = (mapping or {}).get(nombre, nombre)
            for valor in self.observations(metrica, source=MEDIDO):
                prior_set.observe(nombre, valor)

    # -- rechazos ---------------------------------------------------------
    def rejection_log(self) -> RejectionLog:
        log = RejectionLog.load(self.root / RECHAZOS)
        if not log.client:
            log.client = self.client
        return log

    def record_rejection(self, slug: str, code: str, reason: str,
                         instruction: str = "", reviewer: str = "") -> Rejection:
        log = self.rejection_log()
        rechazo = log.add(slug, code, reason, instruction, reviewer)
        log.save(self.root / RECHAZOS)
        return rechazo

    def brief_additions(self) -> list[str]:
        return self.rejection_log().brief_additions()

    # -- estado -----------------------------------------------------------
    def _flush(self) -> None:
        write_json(self.root / ESTADO, {
            "schema": ESQUEMA.version,
            "client": self.client,
            "created": self._created,
            "updated": _ahora(),
            "pages": {slug: p.to_dict() for slug, p in self.pages.items()},
        })

    def _by_seq(self) -> dict[int, Observation]:
        return {o.seq: o for o in self.history()}

    def _next_seq(self) -> int:
        vistos = self._by_seq()
        return (max(vistos) + 1) if vistos else 1

    def describe(self) -> str:
        huella = self.fingerprint()
        metricas = self.metrics()
        rechazos = len(self.rejection_log().rejections)
        lineas = [
            f"Almacen de {self.client or self.root.name}:",
            f"  {len(self.pages)} pagina(s) publicada(s) en el corpus de solape",
            f"  huella del sitio: {len(huella.hashes)} hashes sobre "
            f"{huella.size} fragmentos"
            f"{'' if huella.exact else ' (estimado)'}",
            f"  {sum(metricas.values())} observacion(es) vigentes en "
            f"{len(metricas)} metrica(s)",
            f"  {rechazos} rechazo(s) registrados, "
            f"{len(self.brief_additions())} instruccion(es) de vuelta al brief",
        ]
        if self.migrations:
            lineas.append(f"  migrado al abrir: {', '.join(self.migrations)}")
        return "\n".join(lineas)
