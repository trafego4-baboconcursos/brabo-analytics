"""
Orquestrador ETL — roda todos os scripts em sequência.

Uso:
    python etl/run_all.py --since 2026-04-01 --until 2026-04-30

    # Roda apenas um ETL específico:
    python etl/run_all.py --since 2026-04-01 --until 2026-04-30 --only meta_ads

    # Cargas via CSV (para fontes sem API configurada ainda):
    python etl/run_all.py --csv-mode --campaign-folder "analises/[PBB-ABR-26]" --period 2026-04
"""
import argparse
import subprocess
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
from logger import get_logger
from etl_runs import start_run, finish_run

BASE = Path(__file__).parent
logger = get_logger("etl.run_all")


def run(cmd: list[str], label: str, source: str | None = None) -> int:
    logger.info("Iniciando: %s", label)
    run_id = start_run(source) if source else None
    result = subprocess.run(cmd)
    if result.returncode != 0:
        logger.error("Falha em '%s' (código %d)", label, result.returncode)
        finish_run(run_id, status="error", error=f"exit code {result.returncode}")
    else:
        logger.info("Concluído: %s", label)
        finish_run(run_id, status="ok")
    return result.returncode


def run_api_mode(since: str, until: str, only: str | None):
    scripts = {
        "active_campaign": [sys.executable, str(BASE / "etl_active_campaign.py"),
                            "--api", "--since", since, "--until", until],
        "meta_ads":        [sys.executable, str(BASE / "etl_meta_ads.py"),
                            "--since", since, "--until", until],
        "google_ads":      [sys.executable, str(BASE / "etl_google_ads.py"),
                            "--since", since, "--until", until],
        "typeform":        [sys.executable, str(BASE / "etl_typeform.py"),
                            "--since", since, "--until", until],
    }

    targets = {only: scripts[only]} if only else scripts
    errors = []
    for name, cmd in targets.items():
        code = run(cmd, name, source=name)
        if code != 0:
            errors.append(name)
    return errors


def run_csv_mode(campaign_folder: str, period: str):
    """
    Modo CSV: importa os exports manuais de uma pasta de campanha específica.
    Detecta automaticamente os CSVs pela estrutura de pastas padrão do projeto.
    """
    folder = Path(campaign_folder)
    errors = []

    # Active Campaign — CSV mais recente
    ac_dir  = folder / "Active Campaign"
    ac_csvs = sorted(ac_dir.glob("*.csv"), key=lambda p: p.stat().st_mtime, reverse=True)
    if ac_csvs:
        code = run(
            [sys.executable, str(BASE / "etl_active_campaign.py"), "--from-csv", str(ac_csvs[0])],
            f"active_campaign  <- {ac_csvs[0].name}",
        )
        if code != 0:
            errors.append("active_campaign")
    else:
        logger.warning("[SKIP] Nenhum CSV encontrado em %s", ac_dir)

    # Meta Ads
    meta_dir  = folder / "Meta Ads"
    meta_csvs = sorted(meta_dir.glob("*.csv"), key=lambda p: p.stat().st_mtime, reverse=True)
    if meta_csvs:
        code = run(
            [sys.executable, str(BASE / "etl_meta_ads.py"),
             "--from-csv", str(meta_csvs[0])],
            f"meta_ads  <- {meta_csvs[0].name}",
        )
        if code != 0:
            errors.append("meta_ads")
    else:
        logger.warning("[SKIP] Nenhum CSV encontrado em %s", meta_dir)

    # Google Ads — usa o CSV de performance de anúncios
    ga_dir  = folder / "Google Ads"
    ga_csvs = sorted(ga_dir.glob("*anuncios*.csv"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not ga_csvs:
        ga_csvs = sorted(ga_dir.glob("*.csv"), key=lambda p: p.stat().st_mtime, reverse=True)
    if ga_csvs:
        code = run(
            [sys.executable, str(BASE / "etl_google_ads.py"),
             "--from-csv", str(ga_csvs[0]), "--period", period],
            f"google_ads  <- {ga_csvs[0].name}",
        )
        if code != 0:
            errors.append("google_ads")
    else:
        logger.warning("[SKIP] Nenhum CSV encontrado em %s", ga_dir)

    return errors


def main():
    parser = argparse.ArgumentParser(description="Orquestrador ETL → Supabase")

    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--since",           metavar="YYYY-MM-DD", help="Data inicial (modo API)")
    mode.add_argument("--csv-mode",        action="store_true",  help="Importa via CSVs exportados manualmente")

    parser.add_argument("--until",          metavar="YYYY-MM-DD", default=datetime.now().strftime("%Y-%m-%d"))
    parser.add_argument("--only",           metavar="SCRIPT",    help="Roda somente: active_campaign | meta_ads | google_ads | typeform")
    parser.add_argument("--campaign-folder", metavar="PATH",      help="Pasta da campanha (modo --csv-mode), ex: analises/[PBB-ABR-26]")
    parser.add_argument("--period",          metavar="YYYY-MM",   help="Período da campanha (modo --csv-mode), ex: 2026-04")
    args = parser.parse_args()

    if args.csv_mode:
        if not args.campaign_folder or not args.period:
            parser.error("--csv-mode requer --campaign-folder e --period")
        errors = run_csv_mode(args.campaign_folder, args.period)
    else:
        errors = run_api_mode(args.since, args.until, args.only)

    if errors:
        logger.error("ETL concluído com erros em: %s", ", ".join(errors))
        sys.exit(1)
    else:
        logger.info("Todos os ETLs concluídos com sucesso.")


if __name__ == "__main__":
    main()
