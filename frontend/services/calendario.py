"""
frontend/services/calendario.py — monta o Calendário Operacional dinamicamente
a partir do launch_config de cada lançamento (substitui o antigo HTML estático
com datas digitadas à mão em frontend/static/calendario/).
"""
from __future__ import annotations

from datetime import date, datetime
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

    return {
        "today": today,
        "rows": rows,
        "metrics": {
            "total": total,
            "extraido": extraido_count,
            "pendentes": pendentes,
            "programadas": programadas,
        },
    }
