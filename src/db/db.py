import sqlite3
from pathlib import Path


def init_db(db_path: Path, schema_path: Path) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db_path) as conn:
        conn.executescript(schema_path.read_text(encoding="utf-8"))
        _ensure_summary_columns(conn)
        _ensure_ri_campaign_summary_columns(conn)


def _ensure_summary_columns(conn: sqlite3.Connection) -> None:
    cur = conn.execute("PRAGMA table_info(metrics_summary)")
    existing = {str(row[1]).lower() for row in cur.fetchall()}
    wanted: list[tuple[str, str]] = [
        ("ri_sales", "INTEGER"),
        ("ri_revenue", "REAL"),
        ("ri_buyers_with_utm", "INTEGER"),
        ("ri_buyers_without_utm", "INTEGER"),
        ("hotmart_sales", "INTEGER"),
        ("tmb_sales", "INTEGER"),
    ]
    for column, col_type in wanted:
        if column not in existing:
            conn.execute(f"ALTER TABLE metrics_summary ADD COLUMN {column} {col_type}")


def _ensure_ri_campaign_summary_columns(conn: sqlite3.Connection) -> None:
    cur = conn.execute("PRAGMA table_info(ri_campaign_summary)")
    existing = {str(row[1]).lower() for row in cur.fetchall()}
    wanted: list[tuple[str, str]] = [
        ("report_html", "TEXT"),
        ("hotmart_sales", "INTEGER"),
        ("tmb_sales", "INTEGER"),
    ]
    for column, col_type in wanted:
        if column not in existing:
            conn.execute(f"ALTER TABLE ri_campaign_summary ADD COLUMN {column} {col_type}")


def _get_or_create(conn: sqlite3.Connection, table: str, key: str, value: str) -> int:
    cur = conn.execute(f"SELECT id FROM {table} WHERE {key} = ?", (value,))
    row = cur.fetchone()
    if row:
        return int(row[0])
    cur = conn.execute(f"INSERT INTO {table} ({key}) VALUES (?)", (value,))
    return int(cur.lastrowid)


def ensure_entities(conn: sqlite3.Connection, config: dict) -> tuple[int, int, int]:
    client_name = config["launch"]["client"]
    course_code = config["launch"]["course"]["code"]
    course_name = config["launch"]["course"]["name"]
    launch_code = config["launch"]["code"]

    client_id = _get_or_create(conn, "clients", "name", client_name)
    cur = conn.execute(
        "SELECT id FROM courses WHERE client_id = ? AND code = ?",
        (client_id, course_code),
    )
    row = cur.fetchone()
    if row:
        course_id = int(row[0])
    else:
        cur = conn.execute(
            "INSERT INTO courses (client_id, name, code) VALUES (?, ?, ?)",
            (client_id, course_name, course_code),
        )
        course_id = int(cur.lastrowid)

    cur = conn.execute("SELECT id FROM launches WHERE code = ?", (launch_code,))
    row = cur.fetchone()
    if row:
        launch_id = int(row[0])
    else:
        cur = conn.execute(
            "INSERT INTO launches (client_id, course_id, code, start_date, end_date) VALUES (?, ?, ?, ?, ?)",
            (
                client_id,
                course_id,
                launch_code,
                config["launch"]["date_range"]["start"],
                config["launch"]["date_range"]["end"],
            ),
        )
        launch_id = int(cur.lastrowid)
    return client_id, course_id, launch_id


def insert_snapshot(conn: sqlite3.Connection, launch_id: int, notes: str | None = None) -> int:
    cur = conn.execute(
        "INSERT INTO snapshots (launch_id, notes) VALUES (?, ?)",
        (launch_id, notes),
    )
    return int(cur.lastrowid)


def insert_summary(conn: sqlite3.Connection, snapshot_id: int, summary: dict) -> None:
    ri = summary.get("ri_summary", {})
    conn.execute(
        "INSERT INTO metrics_summary ("
        "snapshot_id, total_sales, hotmart_sales, tmb_sales, total_revenue, fb_spend, yt_spend, "
        "ri_sales, ri_revenue, ri_buyers_with_utm, ri_buyers_without_utm, roas"
        ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            snapshot_id,
            summary["total_sales_raw"],
            summary.get("hotmart_sales_raw", 0),
            summary.get("tmb_sales_raw", 0),
            summary["total_revenue_raw"],
            summary["fb_spend_raw"],
            summary["yt_spend_raw"],
            ri.get("sales", 0),
            ri.get("revenue_raw", 0.0),
            ri.get("buyers_with_utm", 0),
            ri.get("buyers_without_utm", 0),
            summary["roas_raw"],
        ),
    )


def insert_distribution(conn: sqlite3.Connection, snapshot_id: int, distribution: list[dict]) -> None:
    for row in distribution:
        conn.execute(
            "INSERT INTO metrics_by_source (snapshot_id, source, buyers, revenue, spend, roas) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (
                snapshot_id,
                row["source"],
                row["buyers"],
                row["revenue_raw"],
                row["spend_raw"],
                row["roas_raw"],
            ),
        )


def insert_top_utms(conn: sqlite3.Connection, snapshot_id: int, top_utms: dict) -> None:
    for source, items in top_utms.items():
        for item in items:
            conn.execute(
                "INSERT INTO utm_top (snapshot_id, source, utm_source, utm_medium, utm_campaign, "
                "buyers, revenue, payment_card, payment_boleto, payment_pix, payment_other) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    snapshot_id,
                    source,
                    item["utm_source"],
                    item["utm_medium"],
                    item["utm_campaign"],
                    item["buyers"],
                    item["revenue_raw"],
                    item["cartao"],
                    item["boleto"],
                    item["pix"],
                    item["outros"],
                ),
            )


def insert_ri_audit(conn: sqlite3.Connection, snapshot_id: int, ri_report_rows: list[dict]) -> None:
    for row in ri_report_rows:
        conn.execute(
            "INSERT INTO ri_audit ("
            "snapshot_id, section, source, metric, value, buyers, revenue, payment_card, payment_boleto, payment_pix, payment_other, utm_source, utm_medium, utm_campaign"
            ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                snapshot_id,
                row.get("section", ""),
                row.get("source", ""),
                row.get("metric", ""),
                row.get("value", ""),
                row.get("buyers"),
                row.get("revenue"),
                row.get("payment_card"),
                row.get("payment_boleto"),
                row.get("payment_pix"),
                row.get("payment_other"),
                row.get("utm_source"),
                row.get("utm_medium"),
                row.get("utm_campaign"),
            ),
        )


def insert_ri_campaign_summary(conn: sqlite3.Connection, snapshot_id: int, launch_id: int, launch_code: str, report_html: str, summary: dict) -> None:
    ri = summary.get("ri_summary", {})
    conn.execute(
        "INSERT INTO ri_campaign_summary ("
        "snapshot_id, launch_id, launch_code, report_html, total_sales, hotmart_sales, tmb_sales, "
        "total_revenue, fb_spend, yt_spend, "
        "ri_sales, ri_revenue, ri_buyers_with_utm, ri_buyers_without_utm, roas"
        ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            snapshot_id,
            launch_id,
            launch_code,
            report_html,
            summary["total_sales_raw"],
            summary.get("hotmart_sales_raw", 0),
            summary.get("tmb_sales_raw", 0),
            summary["total_revenue_raw"],
            summary["fb_spend_raw"],
            summary["yt_spend_raw"],
            ri.get("sales", 0),
            ri.get("revenue_raw", 0.0),
            ri.get("buyers_with_utm", 0),
            ri.get("buyers_without_utm", 0),
            summary["roas_raw"],
        ),
    )


def fetch_ri_campaign_summaries(conn: sqlite3.Connection) -> list[dict]:
    cur = conn.execute(
        "SELECT launch_code, report_html, created_at, total_sales, hotmart_sales, tmb_sales, "
        "total_revenue, fb_spend, yt_spend, "
        "ri_sales, ri_revenue, ri_buyers_with_utm, ri_buyers_without_utm, roas "
        "FROM ri_campaign_summary ORDER BY created_at DESC, launch_code ASC"
    )
    columns = [d[0] for d in cur.description]
    return [dict(zip(columns, row)) for row in cur.fetchall()]
