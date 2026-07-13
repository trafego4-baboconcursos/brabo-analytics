from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path


CAMPAIGN_DIR_RE = re.compile(r"^\[(?P<code>[A-Z]{2,5}-[A-Z]{3}-\d{2})\]$")


@dataclass(frozen=True)
class CampaignInputs:
    code: str
    campaign_dir: Path
    leads_csv: Path
    meta_campaigns_csv: Path
    google_campaigns_csv: Path
    hotmart_csv: Path
    boleto_csv: Path


def _norm(text: str) -> str:
    return text.strip().lower().replace("_", " ").replace("-", " ")


def _find_child_dir(base: Path, aliases: list[str]) -> Path | None:
    if not base.exists():
        return None
    wanted = {_norm(a) for a in aliases}
    for child in base.iterdir():
        if child.is_dir() and _norm(child.name) in wanted:
            return child
    return None


def _pick_latest_csv(folder: Path, predicates: list[str]) -> Path | None:
    if not folder.exists():
        return None
    rows: list[Path] = [p for p in folder.glob("*.csv") if p.is_file()]
    if not rows:
        return None

    lowered = [(p, _norm(p.name)) for p in rows]
    for token in predicates:
        token_n = _norm(token)
        filtered = [p for p, low in lowered if token_n in low]
        if filtered:
            return max(filtered, key=lambda p: p.stat().st_mtime)
    return max(rows, key=lambda p: p.stat().st_mtime)


def discover_campaign_inputs(campaign_dir: Path) -> CampaignInputs | None:
    match = CAMPAIGN_DIR_RE.match(campaign_dir.name)
    if not match:
        return None

    code = match.group("code")

    active = _find_child_dir(campaign_dir, ["Active Campaign", "active-campaing", "active campaign"])
    meta = _find_child_dir(campaign_dir, ["Meta Ads", "meta ads"])
    google = _find_child_dir(campaign_dir, ["Google Ads", "google ads"])
    sales = _find_child_dir(campaign_dir, ["Vendas", "vendas", "sales"])

    if not all([active, meta, google, sales]):
        return None

    leads = _pick_latest_csv(active, ["lead", code.lower()])
    meta_campaigns = _pick_latest_csv(meta, ["campanhas", "meta", code.lower()])
    google_campaigns = _pick_latest_csv(google, ["performance da campanha", "campanha", code.lower()])
    hotmart = _pick_latest_csv(sales, ["hotmart", code.lower()])
    boleto = _pick_latest_csv(sales, ["tmb", "boleto", "pedido", code.lower()])

    if not all([leads, meta_campaigns, google_campaigns, hotmart, boleto]):
        return None

    return CampaignInputs(
        code=code,
        campaign_dir=campaign_dir,
        leads_csv=leads,
        meta_campaigns_csv=meta_campaigns,
        google_campaigns_csv=google_campaigns,
        hotmart_csv=hotmart,
        boleto_csv=boleto,
    )


def discover_all_campaigns(analises_dir: Path) -> list[CampaignInputs]:
    if not analises_dir.exists():
        return []
    found: list[CampaignInputs] = []
    for child in analises_dir.iterdir():
        if not child.is_dir():
            continue
        campaign = discover_campaign_inputs(child)
        if campaign:
            found.append(campaign)
    return sorted(found, key=lambda c: c.code)


def _default_date_range() -> tuple[str, str]:
    today = date.today().isoformat()
    return today, today


def build_auto_config(inputs: CampaignInputs, workspace_root: Path) -> dict:
    files = [
        inputs.leads_csv,
        inputs.meta_campaigns_csv,
        inputs.google_campaigns_csv,
        inputs.hotmart_csv,
        inputs.boleto_csv,
    ]
    if files:
        start = min(f.stat().st_mtime for f in files)
        end = max(f.stat().st_mtime for f in files)
        start_iso = date.fromtimestamp(start).isoformat()
        end_iso = date.fromtimestamp(end).isoformat()
    else:
        start_iso, end_iso = _default_date_range()

    prefix = inputs.code.split("-")[0]
    course_name = {
        "PBB": "Projeto Banco do Brasil",
        "PES": "Projeto Escrevente (Sao Paulo)",
        "PI": "Projeto INSS",
    }.get(prefix, prefix)

    def rel(path: Path) -> str:
        return str(path.relative_to(workspace_root)).replace("\\", "/")

    code = inputs.code
    return {
        "launch": {
            "code": code,
            "client": "Brabo Concursos",
            "course": {"code": prefix, "name": course_name},
            "date_range": {"start": start_iso, "end": end_iso},
        },
        "inputs": {
            "active_campaign": {"leads_csv": rel(inputs.leads_csv)},
            "meta_ads": {"campaigns_csv": rel(inputs.meta_campaigns_csv)},
            "google_ads": {"campaigns_csv": rel(inputs.google_campaigns_csv)},
            "sales": {
                "hotmart_csv": rel(inputs.hotmart_csv),
                "boleto_csv": rel(inputs.boleto_csv),
            },
        },
        "filters": {"campaign_name_contains": code},
        "outputs": {
            "persist_db": False,
            "db_path": "outputs/analysis.db",
            "snapshot_dir": f"outputs/snapshots/{code}",
            "report_html": f"outputs/reports/ANALISE_ATRIBUICAO_UTM_[{code}].html",
            "ri_csv": f"outputs/reports/RI_[{code}].csv",
        },
    }
