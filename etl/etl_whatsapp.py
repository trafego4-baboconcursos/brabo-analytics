"""
ETL: WhatsApp Business (Meta Graph API) → Supabase (tabela: whatsapp_messages_daily)

Não traz custo em R$ — as contas monitoradas são faturadas via Unichat como
parceiro, e o Meta esconde o campo de custo pra WABAs faturadas por parceiro
(erro "Custo não disponível" no endpoint conversation_analytics). O que a API
expõe sem bloqueio é volume de mensagens enviadas/entregues por dia, pelo
campo legado `analytics` de cada WhatsApp Business Account.

Uso:
    python etl/etl_whatsapp.py --since 2026-08-01 --until 2026-08-26

Pré-requisitos .env:
    META_ACCESS_TOKEN — com escopo whatsapp_business_management
Contas monitoradas: config/whatsapp_accounts.yaml (waba_id de cada número).
"""
import os
import sys
import argparse
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import yaml
from sqlalchemy import text
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).parent))
from db import get_engine
from logger import get_logger
from http_retry import http_get
from ptax import get_ptax_venda

load_dotenv()

logger = get_logger("etl.whatsapp")

API_VERSION = "v22.0"
TABLE = "whatsapp_messages_daily"
CONFIG_PATH = Path(__file__).parent.parent / "config" / "whatsapp_accounts.yaml"


def load_accounts() -> list[dict]:
    cfg = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8")) or {}
    return [a for a in cfg.get("accounts", []) if a.get("waba_id")]


def fetch_daily_volume(waba_id: str, since: str, until: str) -> list[dict]:
    token = os.environ["META_ACCESS_TOKEN"]
    start_ts = int(datetime.strptime(since, "%Y-%m-%d").replace(tzinfo=timezone.utc).timestamp())
    end_ts = int(datetime.strptime(until, "%Y-%m-%d").replace(tzinfo=timezone.utc).timestamp()) + 86400

    r = http_get(
        f"https://graph.facebook.com/{API_VERSION}/{waba_id}",
        params={
            "fields": f"analytics.start({start_ts}).end({end_ts}).granularity(DAY)",
            "access_token": token,
        },
    )
    analytics = r.json().get("analytics") or {}
    return analytics.get("data_points", [])


def fetch_pricing(waba_id: str, since: str, until: str) -> dict[str, float]:
    """{data (YYYY-MM-DD): custo em USD} via pricing_analytics (cobrança por
    mensagem) — substitui o antigo conversation_analytics, que o Meta esconde
    pra WABAs faturadas por parceiro (Unichat); pricing_analytics não é
    escondido."""
    token = os.environ["META_ACCESS_TOKEN"]
    start_ts = int(datetime.strptime(since, "%Y-%m-%d").replace(tzinfo=timezone.utc).timestamp())
    end_ts = int(datetime.strptime(until, "%Y-%m-%d").replace(tzinfo=timezone.utc).timestamp()) + 86400

    r = http_get(
        f"https://graph.facebook.com/{API_VERSION}/{waba_id}/pricing_analytics",
        params={"start": start_ts, "end": end_ts, "granularity": "DAILY", "access_token": token},
    )
    out: dict[str, float] = {}
    for block in r.json().get("data") or []:
        for p in block.get("data_points", []):
            date = datetime.fromtimestamp(p["start"], tz=timezone.utc).strftime("%Y-%m-%d")
            out[date] = out.get(date, 0.0) + float(p.get("cost") or 0)
    return out


def build_df(accounts: list[dict], since: str, until: str) -> pd.DataFrame:
    records = []
    for acc in accounts:
        waba_id = acc["waba_id"]
        try:
            points = fetch_daily_volume(waba_id, since, until)
        except Exception:
            logger.warning("WhatsApp: falha ao buscar %s (%s)", acc.get("name"), waba_id, exc_info=True)
            continue
        try:
            cost_by_date = fetch_pricing(waba_id, since, until)
        except Exception:
            logger.warning("WhatsApp: falha ao buscar custo de %s (%s)", acc.get("name"), waba_id, exc_info=True)
            cost_by_date = {}
        for p in points:
            date = datetime.fromtimestamp(p["start"], tz=timezone.utc).strftime("%Y-%m-%d")
            cost_usd = cost_by_date.get(date)
            ptax = get_ptax_venda(date) if cost_usd is not None else None
            records.append({
                "date": date,
                "waba_id": waba_id,
                "account_name": acc.get("name"),
                "phone_number": acc.get("phone"),
                "sent": int(p.get("sent", 0)),
                "delivered": int(p.get("delivered", 0)),
                "cost_usd": cost_usd,
                "ptax_venda": ptax,
                "cost_brl": (cost_usd * ptax) if (cost_usd is not None and ptax is not None) else None,
            })
        logger.info("WhatsApp: %s (%s) -> %d dias, %d com custo", acc.get("name"), waba_id, len(points), len(cost_by_date))
    return pd.DataFrame(records)


def upsert(df: pd.DataFrame, since: str, until: str):
    if df.empty:
        logger.warning("Nenhum dado de volume WhatsApp para gravar.")
        return
    df["updated_at"] = datetime.now(timezone.utc).isoformat()
    engine = get_engine()
    with engine.begin() as conn:
        conn.execute(
            text(f"DELETE FROM {TABLE} WHERE date BETWEEN :s AND :u"),
            {"s": since, "u": until},
        )
    df.to_sql(TABLE, engine, if_exists="append", index=False, method="multi", chunksize=500)
    logger.info("Upsert concluído: %d linhas gravadas em '%s'", len(df), TABLE)


def main():
    parser = argparse.ArgumentParser(description="ETL WhatsApp Business (volume de mensagens) -> Supabase")
    parser.add_argument("--since", required=True, metavar="YYYY-MM-DD")
    parser.add_argument("--until", required=True, metavar="YYYY-MM-DD")
    args = parser.parse_args()

    accounts = load_accounts()
    if not accounts:
        logger.error("Nenhuma conta configurada em %s", CONFIG_PATH)
        sys.exit(1)

    df = build_df(accounts, args.since, args.until)
    upsert(df, args.since, args.until)


if __name__ == "__main__":
    main()
