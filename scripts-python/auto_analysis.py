#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from automation.campaign_discovery import build_auto_config, discover_all_campaigns
from automation.state_store import compute_fingerprint, load_state, save_state
from run import execute_analysis


def _yaml_dump_simple(data: dict, indent: int = 0) -> str:
    lines: list[str] = []
    prefix = " " * indent
    for key, value in data.items():
        if isinstance(value, dict):
            lines.append(f"{prefix}{key}:")
            lines.append(_yaml_dump_simple(value, indent + 2))
        elif isinstance(value, bool):
            lines.append(f"{prefix}{key}: {'true' if value else 'false'}")
        else:
            lines.append(f"{prefix}{key}: {value}")
    return "\n".join(lines)


def _write_auto_config(config: dict, config_dir: Path, code: str) -> Path:
    config_dir.mkdir(parents=True, exist_ok=True)
    out = config_dir / f"{code.lower()}.auto.yaml"
    out.write_text(_yaml_dump_simple(config) + "\n", encoding="utf-8")
    return out


def _run_campaign(config: dict, dry_run: bool) -> None:
    code = config["launch"]["code"]
    if dry_run:
        print(f"[dry-run] {code} pronto para execucao")
        return
    print(f"[run] iniciando {code}")
    execute_analysis(config)
    print(f"[run] finalizado {code}")


def _campaign_files(config: dict) -> list[Path]:
    inputs = config["inputs"]
    return [
        ROOT / inputs["active_campaign"]["leads_csv"],
        ROOT / inputs["meta_ads"]["campaigns_csv"],
        ROOT / inputs["google_ads"]["campaigns_csv"],
        ROOT / inputs["sales"]["hotmart_csv"],
        ROOT / inputs["sales"]["boleto_csv"],
    ]


def _process_once(state_path: Path, config_dir: Path, campaign_filter: str | None, force: bool, dry_run: bool) -> int:
    state = load_state(state_path)
    campaigns = discover_all_campaigns(ROOT / "analises")
    if campaign_filter:
        campaigns = [c for c in campaigns if c.code.lower() == campaign_filter.lower()]

    if not campaigns:
        print("[warn] nenhuma campanha valida encontrada em analises/[CODE]")
        return 1

    changed_count = 0
    for campaign in campaigns:
        config = build_auto_config(campaign, ROOT)
        files = _campaign_files(config)
        fingerprint = compute_fingerprint(files, ROOT)

        previous = state.setdefault("campaigns", {}).get(campaign.code, {})
        has_changed = previous.get("fingerprint") != fingerprint

        _write_auto_config(config, config_dir, campaign.code)

        if has_changed or force:
            _run_campaign(config, dry_run=dry_run)
            state["campaigns"][campaign.code] = {
                "fingerprint": fingerprint,
                "last_run": datetime.now().isoformat(timespec="seconds"),
            }
            changed_count += 1
        else:
            print(f"[skip] sem alteracao: {campaign.code}")

    save_state(state_path, state)
    print(f"[ok] campanhas processadas: {changed_count}/{len(campaigns)}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Auto runner para analises por atualizacao de CSV")
    parser.add_argument("--campaign", help="Executa apenas um code, ex: PBB-ABR-26")
    parser.add_argument("--watch", action="store_true", help="Mantem monitoramento continuo")
    parser.add_argument("--interval", type=int, default=30, help="Segundos entre scans em watch")
    parser.add_argument("--force", action="store_true", help="Forca execucao mesmo sem mudanca")
    parser.add_argument("--dry-run", action="store_true", help="Nao executa analise, apenas simula")
    args = parser.parse_args()

    state_path = ROOT / "outputs" / "snapshots" / "auto_analysis_state.json"
    config_dir = ROOT / "config" / "launches"

    if not args.watch:
        return _process_once(state_path, config_dir, args.campaign, args.force, args.dry_run)

    print(f"[watch] iniciado com intervalo de {args.interval}s")
    try:
        while True:
            _process_once(state_path, config_dir, args.campaign, args.force, args.dry_run)
            time.sleep(max(args.interval, 5))
    except KeyboardInterrupt:
        print("\n[watch] encerrado")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
