#!/usr/bin/env python3
"""
Aplica o orcamento diario (Facebook + Google) das campanhas de captacao do PES-SET-26,
lendo o valor do dia em performance-manager/PES-SET-26/orcamento_diario.json.

Uso:
    python scripts/apply_daily_budget_pes_set_26.py                # aplica o orcamento de hoje
    python scripts/apply_daily_budget_pes_set_26.py --date 2026-09-05  # aplica um dia especifico (teste/reprocesso)

Pensado para rodar via GitHub Actions (cron diario, 00:05 America/Sao_Paulo) ou manualmente.
Precisa de: META_ACCESS_TOKEN, GOOGLE_ADS_REFRESH_TOKEN, GOOGLE_ADS_CLIENT_ID,
GOOGLE_ADS_CLIENT_SECRET, GOOGLE_ADS_DEVELOPER_TOKEN, GOOGLE_ADS_LOGIN_CUSTOMER_ID no ambiente.

Campanhas Meta usam CBO (orcamento no nivel da campanha, nao do ad set).
Campanhas Google usam bidding TARGET_CPA fixo (R$12, configurado uma vez fora deste script);
este script so atualiza o orcamento diario (campaignBudget.amountMicros).
"""
import os
import sys
import json
import argparse
import datetime
import requests
from dotenv import load_dotenv

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PLAN_PATH = os.path.join(ROOT, "performance-manager", "PES-SET-26", "orcamento_diario.json")

load_dotenv(os.path.join(ROOT, ".env"))

META_ACCOUNT_ID = "act_1407542209639031"
GOOGLE_CUSTOMER_ID = "6482320788"
GOOGLE_API_VERSION = "v22"


def load_plan():
    with open(PLAN_PATH, encoding="utf-8") as f:
        return json.load(f)


def apply_meta(plan, date_str):
    day = plan["meta"].get(date_str)
    if not day:
        print(f"[meta] sem plano pro dia {date_str}, pulando")
        return
    token = os.environ["META_ACCESS_TOKEN"]
    for key, value_reais in day.items():
        campaign_id = plan["meta_campaign_ids"][key]
        cents = int(round(value_reais * 100))
        url = f"https://graph.facebook.com/v21.0/{campaign_id}"
        resp = requests.post(url, data={"daily_budget": cents, "access_token": token})
        ok = resp.status_code == 200 and resp.json().get("success", True)
        print(f"[meta] {key} ({campaign_id}) -> R${value_reais:.2f} | status={resp.status_code} {'OK' if ok else resp.text[:200]}")


def get_google_access_token():
    import google.oauth2.credentials
    import google.auth.transport.requests

    creds = google.oauth2.credentials.Credentials(
        token=None,
        refresh_token=os.environ["GOOGLE_ADS_REFRESH_TOKEN"],
        token_uri="https://oauth2.googleapis.com/token",
        client_id=os.environ["GOOGLE_ADS_CLIENT_ID"],
        client_secret=os.environ["GOOGLE_ADS_CLIENT_SECRET"],
    )
    creds.refresh(google.auth.transport.requests.Request())
    return creds.token


def apply_google(plan, date_str):
    day = plan["google"].get(date_str)
    if not day:
        print(f"[google] sem plano pro dia {date_str}, pulando")
        return

    token = get_google_access_token()
    login_customer_id = os.environ.get("GOOGLE_ADS_LOGIN_CUSTOMER_ID", "").replace("-", "")
    headers = {
        "Authorization": f"Bearer {token}",
        "developer-token": os.environ["GOOGLE_ADS_DEVELOPER_TOKEN"],
        "Content-Type": "application/json; charset=utf-8",
    }
    if login_customer_id:
        headers["login-customer-id"] = login_customer_id

    operations = []
    keys = []
    for key, value_reais in day.items():
        budget_id = plan["google_budget_ids"][key]
        micros = int(round(value_reais * 1_000_000))
        operations.append({
            "updateMask": "amountMicros",
            "update": {
                "resourceName": f"customers/{GOOGLE_CUSTOMER_ID}/campaignBudgets/{budget_id}",
                "amountMicros": str(micros),
            },
        })
        keys.append((key, value_reais))

    url = f"https://googleads.googleapis.com/{GOOGLE_API_VERSION}/customers/{GOOGLE_CUSTOMER_ID}/campaignBudgets:mutate"
    resp = requests.post(url, headers=headers, json={"operations": operations})
    if resp.status_code != 200:
        print(f"[google] ERRO {resp.status_code}: {resp.text[:2000]}")
        sys.exit(1)
    for key, value_reais in keys:
        print(f"[google] {key} -> R${value_reais:.2f}")
    print("[google] OK, aplicado via API")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", default=None, help="Data no formato YYYY-MM-DD (default: hoje)")
    args = parser.parse_args()

    date_str = args.date or datetime.date.today().isoformat()
    print(f"=== Aplicando orcamento PES-SET-26 para {date_str} ===")

    plan = load_plan()
    apply_meta(plan, date_str)
    apply_google(plan, date_str)


if __name__ == "__main__":
    main()
