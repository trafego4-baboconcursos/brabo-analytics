"""
frontend/services/calendario.py — monta o Calendário Operacional dinamicamente
a partir do launch_config de cada lançamento (substitui o antigo HTML estático
com datas digitadas à mão em frontend/static/calendario/).
"""
from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any

from src.constants import PRODUCT_BY_PREFIX

_PROJ_CLASS = {"INSS": "proj-inss", "TJ-SP": "proj-tj", "Banco do Brasil": "proj-bb"}
_PROJ_SHORT = {"INSS": "INSS", "TJ-SP": "TJ", "Banco do Brasil": "BB"}
_LAUNCH_CLASS = {"PI": "launch-pi", "PES": "launch-pes", "PBB": "launch-pbb"}

# (campo início, campo fim, classe css do chip/stage, rótulo)
_STAGE_FIELDS: list[tuple[str, str, str, str]] = [
    ("pre_quali_start_date",  "pre_quali_end_date",  "pre", "Pré-Quali"),
    ("captacao_start_date",   "captacao_end_date",   "cap", "Captação"),
    ("depoimento_start_date", "depoimento_end_date", "dep", "Depoimento"),
    ("aulas_start_date",      "aulas_end_date",       "aul", "Aulas Semana 0"),
    ("carrinho_start_date",   "carrinho_end_date",    "car", "Carrinho aberto"),
]


def _parse_date(value: Any) -> date | None:
    if not value:
        return None
    if isinstance(value, date):
        return value
    try:
        return datetime.strptime(str(value)[:10], "%Y-%m-%d").date()
    except Exception:
        return None


def build_calendario_ctx(launches: list, read_launch_config_fn) -> dict:
    """Monta as linhas do calendário a partir do launch_config de cada
    lançamento conhecido (get_launches()). Lançamentos sem nenhuma data
    cadastrada em Configurações não aparecem."""
    today = date.today()
    rows: list[dict] = []

    for launch in launches:
        code = getattr(launch, "code", "") or ""
        if not code or code.upper() == "PERPETUO":
            continue

        cfg = read_launch_config_fn(code) or {}
        stages = []
        for start_key, end_key, css, label in _STAGE_FIELDS:
            s = _parse_date(cfg.get(start_key))
            e = _parse_date(cfg.get(end_key))
            if not s or not e:
                continue
            stages.append({
                "css": css,
                "label": label,
                "start": s,
                "end": e,
                "days": (e - s).days + 1,
            })
        if not stages:
            continue

        bounds_start = min(st["start"] for st in stages)
        bounds_end = max(st["end"] for st in stages)

        prefix = code.split("-")[0]
        product = getattr(launch, "product", "") or PRODUCT_BY_PREFIX.get(prefix, (prefix,))[0]

        if today > bounds_end:
            state = "completed"
        elif today >= bounds_start:
            state = "running"
        else:
            state = "scheduled"

        extraido = bool(getattr(launch, "has_meta", False) or getattr(launch, "has_vendas", False))

        rows.append({
            "code": code,
            "project": _PROJ_SHORT.get(product, product),
            "proj_class": _PROJ_CLASS.get(product, "proj-inss"),
            "launch_class": _LAUNCH_CLASS.get(prefix, "launch-pi"),
            "stages": stages,
            "by_css": {st["css"]: st for st in stages},
            "bounds_start": bounds_start,
            "bounds_end": bounds_end,
            "state": state,
            "extraido": extraido,
        })

    rows.sort(key=lambda r: r["bounds_start"])

    total = len(rows)
    extraido_count = sum(1 for r in rows if r["extraido"])
    pendentes = sum(1 for r in rows if r["state"] == "completed" and not r["extraido"])
    programadas = sum(1 for r in rows if r["state"] != "completed")

    timeline_groups, timeline_items = _build_timeline(rows)

    return {
        "today": today,
        "rows": rows,
        "metrics": {
            "total": total,
            "extraido": extraido_count,
            "pendentes": pendentes,
            "programadas": programadas,
        },
        "timeline_groups": timeline_groups,
        "timeline_items": timeline_items,
    }


def _build_timeline(rows: list[dict]) -> tuple[list[dict], list[dict]]:
    """Monta grupos (1 por lançamento) e items (1 por etapa) pro vis-timeline.

    Etapa sem data vira um item "fantasma" (ghost=True) — aparece na régua
    como uma barra tracejada, arrastável, num período padrão logo após a
    última etapa conhecida daquele lançamento. Arrastar/redimensionar um
    ghost grava a data pela primeira vez; arrastar uma barra real edita a
    data já existente. Os dois casos batem no mesmo endpoint
    (POST /api/launch-config/{code}), que só grava as 2 colunas mandadas —
    não tem risco de sobrescrever o resto da config do lançamento.
    """
    groups: list[dict] = []
    items: list[dict] = []
    for r in rows:
        groups.append({
            "id": r["code"],
            "content": r["code"],
            "className": r["launch_class"],
        })
        for start_key, end_key, css, label in _STAGE_FIELDS:
            st = r["by_css"].get(css)
            if st:
                items.append({
                    "id": f"{r['code']}::{css}",
                    "group": r["code"],
                    "content": label,
                    "start": st["start"].isoformat(),
                    "end": (st["end"] + timedelta(days=1)).isoformat(),
                    "className": f"tl-stage-{css}",
                    "startField": start_key,
                    "endField": end_key,
                    "ghost": False,
                })
            else:
                ghost_start = r["bounds_end"] + timedelta(days=1)
                ghost_end = ghost_start + timedelta(days=6)
                items.append({
                    "id": f"{r['code']}::{css}::ghost",
                    "group": r["code"],
                    "content": f"+ {label}",
                    "start": ghost_start.isoformat(),
                    "end": (ghost_end + timedelta(days=1)).isoformat(),
                    "className": f"tl-ghost tl-stage-{css}",
                    "startField": start_key,
                    "endField": end_key,
                    "ghost": True,
                })
    return groups, items
