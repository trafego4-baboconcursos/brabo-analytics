import argparse
import pathlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from db.db import ensure_entities, fetch_ri_campaign_summaries, init_db, insert_distribution, insert_ri_audit, insert_ri_campaign_summary, insert_snapshot, insert_summary, insert_top_utms
from reports.csv_report import build_ri_report_rows, write_ri_report_csv
from reports.html_report import render_report
from reports.ri_index_html import write_ri_campaign_index_html
from reports.ri_index import write_ri_campaign_index_csv
from transforms.analysis import run_analysis


def load_config(path: pathlib.Path) -> dict:
    try:
        import yaml  # type: ignore
    except Exception as exc:  # pragma: no cover
        raise RuntimeError(
            "PyYAML is required. Install with: pip install pyyaml"
        ) from exc
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def execute_analysis(config: dict) -> dict:
    launch_code = config.get("launch", {}).get("code", "unknown")
    print(f"[ok] loaded config for {launch_code}")

    results = run_analysis(config)
    ri_report_rows = build_ri_report_rows(results)
    results["ri_report_rows"] = ri_report_rows

    outputs_cfg = config.get("outputs", {})
    report_path = Path(outputs_cfg.get("report_html", "outputs/reports/report.html"))
    persist_db = outputs_cfg.get("persist_db", True)
    if persist_db:
        db_path = Path(outputs_cfg.get("db_path", "outputs/analysis.db"))
        schema_path = Path("src/db/schema.sql")
        init_db(db_path, schema_path)

        import sqlite3

        with sqlite3.connect(db_path) as conn:
            _, _, launch_id = ensure_entities(conn, config)
            snapshot_id = insert_snapshot(conn, launch_id, notes="auto")
            insert_summary(conn, snapshot_id, results)
            insert_distribution(conn, snapshot_id, results["distribution"])
            insert_top_utms(conn, snapshot_id, results["top_utms"])
            insert_ri_audit(conn, snapshot_id, ri_report_rows)
            insert_ri_campaign_summary(conn, snapshot_id, launch_id, launch_code, str(report_path).replace("\\", "/"), results)
            conn.commit()

            ri_index_rows = fetch_ri_campaign_summaries(conn)
            write_ri_campaign_index_csv(Path("outputs/reports/RI_INDEX.csv"), ri_index_rows)
            write_ri_campaign_index_html(Path("outputs/reports/RI_INDEX.html"), ri_index_rows)
        print(f"[ok] database written to {db_path}")
    else:
        print("[ok] database persistence skipped by config")

    render_report(report_path, results)
    print(f"[ok] report written to {report_path}")

    ri_csv_path = Path(outputs_cfg.get("ri_csv", report_path.with_name(f"RI_[{launch_code}].csv")))
    write_ri_report_csv(ri_csv_path, results)
    print(f"[ok] ri csv written to {ri_csv_path}")

    results["report_html"] = str(report_path).replace("\\", "/")
    return results


def execute_analysis_from_path(config_path: pathlib.Path) -> dict:
    if not config_path.exists():
        raise FileNotFoundError(f"Config not found: {config_path}")
    return execute_analysis(load_config(config_path))


def main() -> int:
    parser = argparse.ArgumentParser(description="Local analysis runner")
    parser.add_argument("--config", required=True, help="Path to launch yaml")
    args = parser.parse_args()

    config_path = pathlib.Path(args.config)
    try:
        execute_analysis_from_path(config_path)
        return 0
    except FileNotFoundError as exc:
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
