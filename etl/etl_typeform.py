"""
ETL: Typeform API → Supabase (tabela: typeform_respostas)

Uso:
    python etl/etl_typeform.py --since 2026-04-01 --until 2026-04-30

Pré-requisitos .env:
    TYPEFORM_TOKEN    — Personal Token (app.typeform.com > Conta > Settings)
    TYPEFORM_FORM_ID  — ID do formulário (encontre na URL do form)

A deduplicação por email segue a mesma regra do pipeline atual:
    keep="last" — mantém a resposta mais recente por email.
"""
import os
import sys
import json
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
from http_retry import http_get
from validation import validate_dataframe

load_dotenv()

logger = get_logger("etl.typeform")

TABLE = "typeform_respostas"


def fetch_responses(since: str, until: str, form_id: str | None = None) -> list[dict]:
    token   = os.environ["TYPEFORM_TOKEN"]
    form_id = form_id or os.environ["TYPEFORM_FORM_ID"]
    headers = {"Authorization": f"Bearer {token}"}
    base    = f"https://api.typeform.com/forms/{form_id}/responses"

    rows, before = [], None
    while True:
        params = {
            "page_size": 200,
            "completed": "true",
            "since":     f"{since}T00:00:00Z",
            "until":     f"{until}T23:59:59Z",
        }
        if before:
            params["before"] = before

        r = http_get(base, headers=headers, params=params)
        data  = r.json()
        batch = data.get("items", [])
        rows.extend(batch)

        if len(batch) < 200:
            break
        before = batch[-1]["token"]   # cursor para próxima página

    return rows


def _find_email(answers: list) -> str | None:
    for a in (answers or []):
        if a.get("type") == "email":
            return a.get("email")
    return None


def build_dataframe(responses: list[dict], form_id: str | None = None) -> pd.DataFrame:
    form_id = form_id or os.environ["TYPEFORM_FORM_ID"]
    records = []
    for resp in responses:
        records.append({
            "response_id":  resp["token"],
            "form_id":      form_id,
            "submitted_at": resp.get("submitted_at"),
            "email":        _find_email(resp.get("answers", [])),
            "answers":      json.dumps(resp.get("answers", []), ensure_ascii=False),
        })

    df = pd.DataFrame(records)
    if df.empty:
        return df

    df["submitted_at"] = pd.to_datetime(df["submitted_at"], errors="coerce")

    # Dedup por email: mantém última resposta — alinhado com o pipeline existente
    df = (
        df.sort_values("submitted_at")
        .drop_duplicates(subset=["email"], keep="last")
    )
    df["updated_at"] = datetime.now(timezone.utc).isoformat()
    return df


_TF_REQUIRED_COLS = ["response_id", "form_id", "submitted_at", "email"]

def upsert(df: pd.DataFrame, form_id: str, since: str | None = None, until: str | None = None):
    if not validate_dataframe(df, _TF_REQUIRED_COLS, "typeform_respostas", logger):
        return
    engine = get_engine()
    with engine.begin() as conn:
        if since and until:
            # Deleta apenas o período importado — preserva dados históricos fora do range
            conn.execute(
                text(f"DELETE FROM {TABLE} WHERE form_id = :fid AND submitted_at::date BETWEEN :since AND :until"),
                {"fid": form_id, "since": since, "until": until},
            )
        else:
            conn.execute(
                text(f"DELETE FROM {TABLE} WHERE form_id = :fid"),
                {"fid": form_id},
            )
    df.to_sql(TABLE, engine, if_exists="append", index=False, method="multi", chunksize=500)
    logger.info("Upsert concluído: %d respostas gravadas em '%s'", len(df), TABLE)


def main():
    parser = argparse.ArgumentParser(description="ETL Typeform → Supabase")
    parser.add_argument("--since", required=True,  metavar="YYYY-MM-DD")
    parser.add_argument("--until", metavar="YYYY-MM-DD", default=datetime.now().strftime("%Y-%m-%d"))
    parser.add_argument("--form-id", metavar="ID", help="Sobrescreve TYPEFORM_FORM_ID do .env")
    args = parser.parse_args()

    form_id = args.form_id or os.environ["TYPEFORM_FORM_ID"]
    logger.info("[Typeform] %s  form=%s  [%s -> %s]", TABLE, form_id, args.since, args.until)
    responses = fetch_responses(args.since, args.until, form_id)
    logger.info("%d respostas encontradas", len(responses))
    df = build_dataframe(responses, form_id)
    upsert(df, form_id, since=args.since, until=args.until)


if __name__ == "__main__":
    main()
