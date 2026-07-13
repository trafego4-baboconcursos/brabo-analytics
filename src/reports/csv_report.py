from __future__ import annotations

import csv
from pathlib import Path


def build_ri_report_rows(data: dict) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []

    ri = data.get("ri_summary", {})
    summary_fields = [
        ("sales", ri.get("sales", 0)),
        ("revenue", ri.get("revenue_raw", 0.0)),
        ("buyers_with_utm", ri.get("buyers_with_utm", 0)),
        ("buyers_without_utm", ri.get("buyers_without_utm", 0)),
        ("buyers_with_utm_pct", ri.get("buyers_with_utm_pct", "0,0%")),
        ("buyers_without_utm_pct", ri.get("buyers_without_utm_pct", "0,0%")),
    ]
    for metric, value in summary_fields:
        rows.append(
            {
                "section": "ri_summary",
                "source": "RI",
                "metric": metric,
                "value": value,
                "buyers": "",
                "revenue": "",
                "payment_card": "",
                "payment_boleto": "",
                "payment_pix": "",
                "payment_other": "",
                "utm_source": "",
                "utm_medium": "",
                "utm_campaign": "",
            }
        )

    for source, items in data.get("top_utms", {}).items():
        for item in items:
            rows.append(
                {
                    "section": "ri_top_utm",
                    "source": source,
                    "metric": "",
                    "value": "",
                    "buyers": item.get("buyers", 0),
                    "revenue": item.get("revenue_raw", 0.0),
                    "payment_card": item.get("cartao", 0),
                    "payment_boleto": item.get("boleto", 0),
                    "payment_pix": item.get("pix", 0),
                    "payment_other": item.get("outros", 0),
                    "utm_source": item.get("utm_source", ""),
                    "utm_medium": item.get("utm_medium", ""),
                    "utm_campaign": item.get("utm_campaign", ""),
                }
            )

    return rows


def write_ri_report_csv(output_path: Path, data: dict) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    rows = build_ri_report_rows(data)

    fieldnames = [
        "section",
        "source",
        "metric",
        "value",
        "buyers",
        "revenue",
        "payment_card",
        "payment_boleto",
        "payment_pix",
        "payment_other",
        "utm_source",
        "utm_medium",
        "utm_campaign",
    ]
    with output_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
