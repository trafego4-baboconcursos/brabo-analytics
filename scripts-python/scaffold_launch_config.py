#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Cria um arquivo de configuracao em config/launches a partir da estrutura analises/[CODE].
Exemplo de uso no terminal:
python scripts-python/scaffold_launch_config.py --code PBB-ABR-26 --start 2026-04-01 --end 2026-04-30
"""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(r"c:\Users\trafe\OneDrive\Desktop\workspace-mmm")
ANALISES_DIR = ROOT / "analises"
CONFIG_DIR = ROOT / "config" / "launches"

COURSE_MAP = {
    "PBB": "Projeto Banco do Brasil",
    "PES": "Projeto Escrevente (Sao Paulo)",
    "PI": "Projeto INSS",
}


def pick_first(folder: Path, patterns: list[str]) -> str | None:
    if not folder.exists():
        return None
    files = [p for p in folder.iterdir() if p.is_file()]
    lower = [(p, p.name.lower()) for p in files]
    for pattern in patterns:
        for path, name in lower:
            if pattern in name:
                return str(path.relative_to(ROOT)).replace('\\', '/')
    if files:
        return str(sorted(files)[0].relative_to(ROOT)).replace('\\', '/')
    return None


def build_config(code: str, start: str, end: str, client: str) -> str:
    folder = ANALISES_DIR / f"[{code}]"
    if not folder.exists():
        raise FileNotFoundError(f"Pasta nao encontrada: {folder}")

    prefix = code.split('-')[0].upper()
    course_name = COURSE_MAP.get(prefix, prefix)
    code_slug = code.lower()

    active_campaign = pick_first(folder / "active-campaing", ["banco do brasil", "leads", code_slug])
    meta_campaigns = pick_first(folder / "meta ads", ["campanhas", "meta", code_slug])
    google_campaigns = pick_first(folder / "google ads", ["campanha", "campaign", code_slug])
    hotmart = pick_first(folder / "vendas", ["hotmart", "sales_history", code_slug])
    boleto = pick_first(folder / "vendas", ["tmb", "pedido", "boleto", code_slug])

    if not active_campaign:
        raise RuntimeError("Nao encontrei CSV de Active Campaign")
    if not meta_campaigns:
        raise RuntimeError("Nao encontrei CSV de Meta Ads")
    if not google_campaigns:
        raise RuntimeError("Nao encontrei CSV de Google Ads")
    if not hotmart:
        raise RuntimeError("Nao encontrei CSV de vendas Hotmart")
    if not boleto:
        raise RuntimeError("Nao encontrei CSV de vendas boleto/TMB")

    return f"""launch:
  code: {code}
  client: {client}
  course:
    code: {prefix}
    name: {course_name}
  date_range:
    start: {start}
    end: {end}

inputs:
  active_campaign:
    leads_csv: {active_campaign}
  meta_ads:
    campaigns_csv: {meta_campaigns}
  google_ads:
    campaigns_csv: {google_campaigns}
  sales:
    hotmart_csv: {hotmart}
    boleto_csv: {boleto}

filters:
  campaign_name_contains: {code}

outputs:
  persist_db: false
  db_path: outputs/analysis.db
  snapshot_dir: outputs/snapshots/{code}
  report_html: outputs/reports/ANALISE_ATRIBUICAO_UTM_[{code}].html
"""


def main() -> int:
    parser = argparse.ArgumentParser(description="Scaffold launch config from analises/[CODE]")
    parser.add_argument("--code", required=True, help="Codigo do lancamento, ex: PBB-ABR-26")
    parser.add_argument("--start", required=True, help="Data inicial YYYY-MM-DD")
    parser.add_argument("--end", required=True, help="Data final YYYY-MM-DD")
    parser.add_argument("--client", default="Brabo Concursos", help="Nome do cliente")
    args = parser.parse_args()

    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    out = CONFIG_DIR / f"{args.code.lower()}.yaml"
    content = build_config(args.code, args.start, args.end, args.client)
    out.write_text(content, encoding="utf-8")
    print(f"[ok] config criada: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
