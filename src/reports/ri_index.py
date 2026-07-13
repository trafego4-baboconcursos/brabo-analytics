from __future__ import annotations

import csv
from pathlib import Path


def write_ri_campaign_index_csv(output_path: Path, rows: list[dict]) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "launch_code",
        "report_html",
        "created_at",
        "total_sales",
        "hotmart_sales",
        "tmb_sales",
        "total_revenue",
        "fb_spend",
        "yt_spend",
        "ri_sales",
        "ri_revenue",
        "ri_buyers_with_utm",
        "ri_buyers_without_utm",
        "roas",
    ]
    with output_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)