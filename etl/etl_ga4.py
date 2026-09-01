"""
ETL: Google Analytics 4 (Data API) → Supabase (tabela: ga4_daily)

Uma linha por dia × propriedade × hostname × fonte/mídia/campanha × utm_term ×
landing page, com sessões, usuários, sessões engajadas e key events (leads).

Modo API:
    python etl/etl_ga4.py --since 2026-08-01 --until 2026-08-31

Pré-requisitos .env:
    GOOGLE_ADS_CLIENT_ID / GOOGLE_ADS_CLIENT_SECRET   (mesmo OAuth client do Ads)
    GA4_REFRESH_TOKEN                                 (gerado com get_ga4_token.py)
    GA4_PROPERTY_IDS                                  (lista separada por vírgula)
"""
import os
import sys
import argparse
import pandas as pd
from datetime import datetime, timezone
from pathlib import Path
from sqlalchemy import text
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).parent))
from db import get_engine
from logger import get_logger
from http_retry import http_post
from validation import validate_dataframe
from launch_resolver import resolve_launch_code

load_dotenv()

logger = get_logger("etl.ga4")

TABLE    = "ga4_daily"
DATA_API = "https://analyticsdata.googleapis.com/v1beta"

# Nome amigável das propriedades em uso (fallback: o próprio id)
PROPERTY_NAMES = {
    "503652898": "LP Brabo Concursos",
    "503309358": "LP Mateus Andrade",
    "423344224": "Brabo Concursos (institucional)",
    "387129952": "Mateus Andrade (institucional)",
    "536819663": "Brabo Editora",
}

DIMENSIONS = [
    "date",
    "hostName",
    "sessionSource",
    "sessionMedium",
    "sessionCampaignName",
    "sessionManualTerm",   # utm_term — carrega o ADxxx no nosso padrão
    "landingPage",
]

METRICS = [
    "sessions",
    "totalUsers",
    "engagedSessions",
    "keyEvents",
    "averageSessionDuration",
]

PAGE_SIZE = 100_000


def _get_access_token() -> str:
    import google.oauth2.credentials
    import google.auth.transport.requests

    creds = google.oauth2.credentials.Credentials(
        token=None,
        refresh_token=os.environ["GA4_REFRESH_TOKEN"],
        token_uri="https://oauth2.googleapis.com/token",
        client_id=os.environ["GOOGLE_ADS_CLIENT_ID"],
        client_secret=os.environ["GOOGLE_ADS_CLIENT_SECRET"],
    )
    creds.refresh(google.auth.transport.requests.Request())
    return creds.token


def fetch_report(since: str, until: str, property_ids: list[str] | None = None) -> pd.DataFrame:
    property_ids = property_ids or [
        p.strip() for p in os.environ["GA4_PROPERTY_IDS"].split(",") if p.strip()
    ]
    headers = {
        "Authorization": f"Bearer {_get_access_token()}",
        "Content-Type": "application/json",
    }

    records = []
    for prop_id in property_ids:
        logger.info("Buscando GA4 property %s (%s)", prop_id, PROPERTY_NAMES.get(prop_id, "?"))
        offset = 0
        while True:
            payload = {
                "dateRanges": [{"startDate": since, "endDate": until}],
                "dimensions": [{"name": d} for d in DIMENSIONS],
                "metrics": [{"name": m} for m in METRICS],
                "limit": PAGE_SIZE,
                "offset": offset,
            }
            r = http_post(f"{DATA_API}/properties/{prop_id}:runReport",
                          headers=headers, json=payload)
            data = r.json()
            rows = data.get("rows", [])
            for row in rows:
                dims = [v.get("value", "") for v in row.get("dimensionValues", [])]
                mets = [v.get("value", "0") for v in row.get("metricValues", [])]
                raw_date = dims[0]
                date_iso = f"{raw_date[:4]}-{raw_date[4:6]}-{raw_date[6:8]}" if len(raw_date) == 8 else raw_date
                campaign = dims[4]
                records.append({
                    "date":              date_iso,
                    "property_id":       prop_id,
                    "property_name":     PROPERTY_NAMES.get(prop_id, prop_id),
                    "hostname":          dims[1],
                    "source":            dims[2],
                    "medium":            dims[3],
                    "campaign":          campaign,
                    "utm_term":          dims[5],
                    "landing_page":      dims[6],
                    "lancamento_codigo": resolve_launch_code(campaign, date_iso),
                    "sessions":          int(mets[0] or 0),
                    "users":             int(mets[1] or 0),
                    "engaged_sessions":  int(mets[2] or 0),
                    "key_events":        float(mets[3] or 0),
                    "avg_session_duration": round(float(mets[4] or 0), 2),
                })
            row_count = data.get("rowCount", 0)
            offset += len(rows)
            if not rows or offset >= row_count:
                break

    df = pd.DataFrame(records)
    logger.info("GA4: %d linhas no total (%s a %s)", len(df), since, until)
    return df


DDL = f"""
CREATE TABLE IF NOT EXISTS {TABLE} (
  date DATE NOT NULL,
  property_id TEXT NOT NULL,
  property_name TEXT,
  hostname TEXT,
  source TEXT,
  medium TEXT,
  campaign TEXT,
  utm_term TEXT,
  landing_page TEXT,
  lancamento_codigo TEXT,
  sessions BIGINT DEFAULT 0,
  users BIGINT DEFAULT 0,
  engaged_sessions BIGINT DEFAULT 0,
  key_events DOUBLE PRECISION DEFAULT 0,
  avg_session_duration DOUBLE PRECISION DEFAULT 0,
  updated_at TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_ga4_daily_date ON {TABLE}(date);
CREATE INDEX IF NOT EXISTS idx_ga4_daily_launch ON {TABLE}(lancamento_codigo);
CREATE INDEX IF NOT EXISTS idx_ga4_daily_property ON {TABLE}(property_id);
"""

_GA4_REQUIRED_COLS = ["date", "property_id", "sessions", "users"]


def ensure_table(engine):
    with engine.begin() as conn:
        for stmt in DDL.strip().split(";"):
            if stmt.strip():
                conn.execute(text(stmt))


def upsert(df: pd.DataFrame, since: str, until: str):
    if not validate_dataframe(df, _GA4_REQUIRED_COLS, TABLE, logger):
        return
    df["updated_at"] = datetime.now(timezone.utc).isoformat()
    engine = get_engine()
    ensure_table(engine)
    with engine.begin() as conn:
        conn.execute(
            text(f"DELETE FROM {TABLE} WHERE date BETWEEN :s AND :u"),
            {"s": since, "u": until},
        )
    df.to_sql(TABLE, engine, if_exists="append", index=False, method="multi", chunksize=500)
    logger.info("Upsert concluído: %d linhas gravadas em '%s'", len(df), TABLE)


def main():
    parser = argparse.ArgumentParser(description="ETL GA4 → Supabase")
    parser.add_argument("--since", required=True, metavar="YYYY-MM-DD")
    parser.add_argument("--until", default=datetime.now().strftime("%Y-%m-%d"), metavar="YYYY-MM-DD")
    parser.add_argument("--properties", metavar="IDS", help="Sobrescreve GA4_PROPERTY_IDS (lista separada por vírgula)")
    args = parser.parse_args()

    props = [p.strip() for p in args.properties.split(",")] if args.properties else None
    df = fetch_report(args.since, args.until, props)
    upsert(df, args.since, args.until)


if __name__ == "__main__":
    main()
