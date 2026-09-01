"""
Verifica o acesso ao GA4: lista todas as contas e propriedades que o token
enxerga e roda um teste rapido (sessoes dos ultimos 7 dias) em cada uma.

    python etl/ga4_discover.py
    python etl/ga4_discover.py --env-var GA4_REFRESH_TOKEN_MATEUS

Requer que as APIs "Google Analytics Data API" e "Google Analytics Admin API"
estejam habilitadas no mesmo projeto Google Cloud do OAuth client do Ads.
"""

import os
import sys
import argparse
from pathlib import Path

import requests
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).parent.parent))
load_dotenv()

ADMIN_API = "https://analyticsadmin.googleapis.com/v1beta"
DATA_API = "https://analyticsdata.googleapis.com/v1beta"


def get_access_token(env_var: str) -> str:
    import google.oauth2.credentials
    import google.auth.transport.requests

    refresh_token = os.environ.get(env_var)
    if not refresh_token:
        sys.exit(f"Erro: {env_var} nao definido no .env. Rode antes: python etl/get_ga4_token.py")

    creds = google.oauth2.credentials.Credentials(
        token=None,
        refresh_token=refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=os.environ["GOOGLE_ADS_CLIENT_ID"],
        client_secret=os.environ["GOOGLE_ADS_CLIENT_SECRET"],
    )
    creds.refresh(google.auth.transport.requests.Request())
    return creds.token


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--env-var", default="GA4_REFRESH_TOKEN")
    args = parser.parse_args()

    headers = {"Authorization": f"Bearer {get_access_token(args.env_var)}"}

    # Lista contas + propriedades acessiveis
    summaries, page_token = [], None
    while True:
        params = {"pageSize": 200}
        if page_token:
            params["pageToken"] = page_token
        r = requests.get(f"{ADMIN_API}/accountSummaries", headers=headers, params=params)
        if r.status_code == 403:
            sys.exit(
                "403 na Admin API. Habilite a 'Google Analytics Admin API' no projeto "
                "Google Cloud e confira se a conta logada tem acesso ao GA4.\n" + r.text
            )
        r.raise_for_status()
        data = r.json()
        summaries.extend(data.get("accountSummaries", []))
        page_token = data.get("nextPageToken")
        if not page_token:
            break

    if not summaries:
        sys.exit("Nenhuma conta GA4 visivel para este token. A conta Google logada "
                 "precisa ser adicionada como usuario (Viewer) nas propriedades GA4.")

    for acc in summaries:
        print(f"\nConta: {acc.get('displayName')}  ({acc.get('account')})")
        for prop in acc.get("propertySummaries", []):
            prop_id = prop["property"].split("/")[-1]
            print(f"  Propriedade: {prop.get('displayName')}  ->  property_id = {prop_id}")

            # Teste: sessoes por dominio nos ultimos 7 dias
            r = requests.post(
                f"{DATA_API}/properties/{prop_id}:runReport",
                headers=headers,
                json={
                    "dateRanges": [{"startDate": "7daysAgo", "endDate": "today"}],
                    "dimensions": [{"name": "hostName"}],
                    "metrics": [{"name": "sessions"}, {"name": "totalUsers"}],
                    "limit": 10,
                },
            )
            if not r.ok:
                print(f"    [ERRO no teste] {r.status_code}: {r.text[:200]}")
                continue
            rows = r.json().get("rows", [])
            if not rows:
                print("    (sem dados nos ultimos 7 dias)")
            for row in rows:
                host = row["dimensionValues"][0]["value"]
                sessions = row["metricValues"][0]["value"]
                users = row["metricValues"][1]["value"]
                print(f"    {host}: {sessions} sessoes, {users} usuarios (7d)")

    print("\nAnote os property_id acima e adicione no .env, ex.:")
    print("  GA4_PROPERTY_IDS=123456789,987654321")


if __name__ == "__main__":
    main()
