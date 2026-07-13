import os
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

load_dotenv(r"c:\Users\trafe\OneDrive\Desktop\workspace-mmm\.env")

SUPABASE_URL = os.environ.get("SUPABASE_DB_URL")
if not SUPABASE_URL:
    print("SUPABASE_DB_URL não encontrado!")
    exit(1)

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
CREATE TABLE IF NOT EXISTS google_ads_audiences_daily (
    id              BIGSERIAL PRIMARY KEY,
    date            DATE    NOT NULL,
    audience_name   TEXT    NOT NULL,
    campaign_name   TEXT,
    impressions     INTEGER      DEFAULT 0,
    clicks          INTEGER      DEFAULT 0,
    cost            NUMERIC(12,2) DEFAULT 0,
    conversions     NUMERIC(10,2) DEFAULT 0,
    lancamento_codigo TEXT,
    updated_at      TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (audience_name, campaign_name, date, lancamento_codigo)
);

CREATE INDEX IF NOT EXISTS idx_ga_aud_date ON google_ads_audiences_daily (date);
CREATE INDEX IF NOT EXISTS idx_ga_aud_lancamento ON google_ads_audiences_daily (lancamento_codigo);
"""

try:
    with engine.begin() as conn:
        conn.execute(text(SQL))
    print("Tabela google_ads_audiences_daily criada com sucesso!")
except Exception as e:
    print("Erro ao criar tabela:", e)
