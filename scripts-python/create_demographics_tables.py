import os
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

load_dotenv(r"c:\Users\trafe\OneDrive\Desktop\workspace-mmm\.env")

SUPABASE_URL = os.environ.get("SUPABASE_DB_URL")
from urllib.parse import urlparse, unquote
from sqlalchemy.engine import URL as SA_URL

p = urlparse(SUPABASE_URL)
engine = create_engine(
    SA_URL.create(
        "postgresql+psycopg2",
        username=unquote(p.username or ""),
        password=unquote(p.password or ""),
        host=p.hostname,
        port=p.port or 5432,
        database=(p.path or "/postgres").lstrip("/"),
    )
)

SQL = """
CREATE TABLE IF NOT EXISTS google_ads_demographics_daily (
    id              BIGSERIAL PRIMARY KEY,
    date            DATE    NOT NULL,
    demographic_type TEXT    NOT NULL,
    demographic_value TEXT   NOT NULL,
    campaign_name   TEXT,
    impressions     INTEGER      DEFAULT 0,
    clicks          INTEGER      DEFAULT 0,
    cost            NUMERIC(12,2) DEFAULT 0,
    conversions     NUMERIC(10,2) DEFAULT 0,
    lancamento_codigo TEXT,
    updated_at      TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (demographic_type, demographic_value, campaign_name, date, lancamento_codigo)
);

CREATE INDEX IF NOT EXISTS idx_ga_demo_date ON google_ads_demographics_daily (date);
CREATE INDEX IF NOT EXISTS idx_ga_demo_lancamento ON google_ads_demographics_daily (lancamento_codigo);

CREATE TABLE IF NOT EXISTS meta_ads_demographics_daily (
    id              BIGSERIAL PRIMARY KEY,
    date            DATE    NOT NULL,
    age             TEXT,
    gender          TEXT,
    campaign_name   TEXT,
    impressions     INTEGER      DEFAULT 0,
    clicks          INTEGER      DEFAULT 0,
    cost            NUMERIC(12,2) DEFAULT 0,
    leads           INTEGER      DEFAULT 0,
    lancamento_codigo TEXT,
    updated_at      TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (age, gender, campaign_name, date, lancamento_codigo)
);

CREATE INDEX IF NOT EXISTS idx_ma_demo_date ON meta_ads_demographics_daily (date);
CREATE INDEX IF NOT EXISTS idx_ma_demo_lancamento ON meta_ads_demographics_daily (lancamento_codigo);
"""

with engine.begin() as conn:
    conn.execute(text(SQL))
print("Tabelas de demografia criadas!")
