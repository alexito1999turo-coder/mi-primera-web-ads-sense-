"""Informe. Cada comprobacion lleva su respuesta HTTP y su hora de consulta."""

from __future__ import annotations

import json
from dataclasses import asdict

from .audit import Audit
from .rules import ACTION_DISABLE, ACTION_NOINDEX, ACTION_RECATEGORIZE

ACTION_LABEL = {
    ACTION_DISABLE: "Desactivar el archivo completo",
    ACTION_RECATEGORIZE: "Recategorizar (preferido)",
    ACTION_NOINDEX: "Poner en noindex",
}


def to_markdown(audit: Audit) -> str:
    lines: list[str] = []
    add = lines.append

    add(f"# Auditoria M1 — {audit.site}")
    add("")
    add(f"Medido en vivo entre {audit.started_at} y {audit.finished_at}. "
        f"{audit.requests_made} peticiones espaciadas. Nada de memoria.")
    add("")

    # --- Resumen ---------------------------------------------------------
    pending = audit.actionable
    add("## Resumen")
    add("")
    add(f"- Archivos indexables medidos: **{len(audit.archives)}**")
    add(f"- Archivos con accion pendiente: **{len(pending)}**")
    add(f"- Articulos declarados en sitemap: **{audit.post_count}**")
    if audit.intent_distribution:
        risk = audit.intent_distribution.get("informational", 0.0)
        add(f"- Contenido informacional puro: **{risk}%** "
            "(99,9% de cobertura de AI Overviews, 74,3% sin clic)")
    if audit.impressions_loaded:
        confirmed = [c for c in audit.cannibalization if c.confirmed]
        add(f"- Canibalizacion confirmada: **{len(confirmed)}** de "
            f"{len(audit.cannibalization)} pares comparados")
    add("")

    # --- Archivos --------------------------------------------------------
    add("## Archivos indexables")
    add("")
    if audit.archives:
        add("| Archivo | Tipo | HTTP | Posts | Palabras | Veredicto | Accion |")
        add("|---|---|---|---|---|---|---|")
        for a in sorted(audit.archives, key=lambda x: (x.priority or 9, -x.words)):
            add(f"| {a.url} | {a.kind} | {a.status} | {a.posts} | {a.words} "
                f"| {a.verdict} | {ACTION_LABEL.get(a.action, '—')} |")
        add("")
    else:
        add("No se encontraron archivos de autor, categoria o etiqueta en los "
            "sitemaps declarados.")
        add("")

    # --- Acciones --------------------------------------------------------
    if pending:
        add("## Acciones, por prioridad")
        add("")
        for index, a in enumerate(pending, start=1):
            add(f"### {index}. {ACTION_LABEL.get(a.action, a.action)} — `{a.url}`")
            add("")
            add(a.reason)
            add("")
            if a.action == ACTION_RECATEGORIZE and a.recategorization_candidates:
                add("Articulos reasignables detectados:")
                add("")
                for candidate in a.recategorization_candidates:
                    add(f"- {candidate}")
                add("")
            add(f"Verificacion: `{a.verification}`")
            add("")

    # --- Canibalizacion --------------------------------------------------
    add("## Canibalizacion archivo-vs-articulo")
    add("")
    if not audit.impressions_loaded:
        add("No medida: falta la exportacion de Search Console. "
            "Pasar `--impressions ruta.csv` para medirla.")
    elif not audit.cannibalization:
        add("Ningun par archivo/articulo tenia datos en la exportacion aportada.")
    else:
        for item in sorted(audit.cannibalization, key=lambda c: not c.confirmed):
            mark = "**" if item.confirmed else ""
            add(f"- {mark}{item.describe()}{mark}")
    add("")

    # --- Intencion -------------------------------------------------------
    if audit.intent_distribution:
        add("## Distribucion de intencion")
        add("")
        add("| Intencion | % de articulos |")
        add("|---|---|")
        for label, pct in audit.intent_distribution.items():
            add(f"| {label} | {pct}% |")
        add("")
        if audit.intent_at_risk_urls:
            add(f"{len(audit.intent_at_risk_urls)} articulos son informacionales "
                "puros: rankean pero el clic lo absorbe la respuesta generada. "
                "La mezcla necesita intencion comercial y transaccional.")
            add("")

    # --- Avisos y verificaciones ----------------------------------------
    if audit.warnings:
        add("## Avisos")
        add("")
        for warning in audit.warnings:
            add(f"- {warning}")
        add("")

    add("## Verificaciones duras")
    add("")
    if audit.robots:
        add(f"- robots.txt: `{audit.robots.verification}`")
        add(f"- Sitemap declarado en robots.txt: "
            f"{'si' if audit.robots.declares_sitemap else 'NO'}")
    for sitemap in audit.sitemaps:
        add(f"- sitemap ({sitemap.kind}): `{sitemap.verification}`")
    add("")

    if audit.notes:
        add("## Notas")
        add("")
        for note in audit.notes:
            add(f"- {note}")
        add("")

    return "\n".join(lines)


def to_json(audit: Audit) -> str:
    payload = asdict(audit)
    payload["cannibalization"] = [
        {**asdict(c), "confirmed": c.confirmed} for c in audit.cannibalization
    ]
    return json.dumps(payload, indent=2, ensure_ascii=False, default=str)
