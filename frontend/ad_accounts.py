"""
frontend/ad_accounts.py — Descobre dinamicamente as contas de anúncio (Meta e
Google) que o token/credencial configurado no .env consegue acessar.

Substitui as listas estáticas antigas (KNOWN_META_ACCOUNTS / KNOWN_GOOGLE_ACCOUNTS
em database_reader.py) que ficavam desatualizadas sempre que uma conta nova era
criada (ex: conta separada do Ivan pro PES/PI). Resultado é cacheado em memória
por algumas horas — contas de anúncio raramente mudam e cada chamada é uma ida
na API externa.
"""
from __future__ import annotations

import os
import time as _time_module

import requests

from logger import get_logger

logger = get_logger("frontend.ad_accounts")

_ACCOUNTS_CACHE: dict[str, tuple[list[dict], float]] = {}
_ACCOUNTS_CACHE_TTL = 6 * 3600  # 6 horas — contas de anúncio raramente mudam

META_API_VERSION = "v22.0"
GOOGLE_ADS_API_VERSION = "v22"


def _cached(key: str) -> list[dict] | None:
    entry = _ACCOUNTS_CACHE.get(key)
    if entry is None:
        return None
    value, expires_at = entry
    if _time_module.time() > expires_at:
        return None
    return value


def _set_cached(key: str, value: list[dict]) -> None:
    _ACCOUNTS_CACHE[key] = (value, _time_module.time() + _ACCOUNTS_CACHE_TTL)


def _fetch_meta_accounts_live() -> list[dict]:
    token = os.environ.get("META_ACCESS_TOKEN")
    if not token:
        return []
    accounts: list[dict] = []
    url = f"https://graph.facebook.com/{META_API_VERSION}/me/adaccounts"
    params = {"fields": "name,account_id,account_status", "limit": 200, "access_token": token}
    while url:
        r = requests.get(url, params=params, timeout=20)
        r.raise_for_status()
        data = r.json()
        for acc in data.get("data", []):
            accounts.append({
                "id": f"act_{acc['account_id']}",
                "name": acc.get("name") or acc["account_id"],
                "active": acc.get("account_status") == 1,
            })
        url = data.get("paging", {}).get("next")
        params = {}  # a URL "next" já vem com todos os params
    return sorted(accounts, key=lambda a: a["name"].lower())


def _fetch_google_accounts_live() -> list[dict]:
    dev_token = os.environ.get("GOOGLE_ADS_DEVELOPER_TOKEN")
    refresh_token = os.environ.get("GOOGLE_ADS_REFRESH_TOKEN")
    client_id = os.environ.get("GOOGLE_ADS_CLIENT_ID")
    client_secret = os.environ.get("GOOGLE_ADS_CLIENT_SECRET")
    if not all([dev_token, refresh_token, client_id, client_secret]):
        return []

    import google.oauth2.credentials
    import google.auth.transport.requests

    creds = google.oauth2.credentials.Credentials(
        token=None,
        refresh_token=refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=client_id,
        client_secret=client_secret,
    )
    creds.refresh(google.auth.transport.requests.Request())

    login_customer_id = os.environ.get("GOOGLE_ADS_LOGIN_CUSTOMER_ID", "").replace("-", "")
    headers = {
        "Authorization": f"Bearer {creds.token}",
        "developer-token": dev_token,
        "Content-Type": "application/json",
    }
    if login_customer_id:
        headers["login-customer-id"] = login_customer_id

    r = requests.get(
        f"https://googleads.googleapis.com/{GOOGLE_ADS_API_VERSION}/customers:listAccessibleCustomers",
        headers=headers, timeout=20,
    )
    r.raise_for_status()
    customer_ids = [rn.split("/")[-1] for rn in r.json().get("resourceNames", [])]

    accounts: list[dict] = []
    for customer_id in customer_ids:
        name = customer_id
        try:
            search_url = (
                f"https://googleads.googleapis.com/{GOOGLE_ADS_API_VERSION}"
                f"/customers/{customer_id}/googleAds:search"
            )
            payload = {"query": "SELECT customer.descriptive_name FROM customer LIMIT 1"}
            resp = requests.post(search_url, headers=headers, json=payload, timeout=20)
            if resp.ok:
                results = resp.json().get("results", [])
                if results:
                    name = results[0].get("customer", {}).get("descriptiveName") or customer_id
        except requests.RequestException:
            pass
        accounts.append({"id": customer_id, "name": name})

    return sorted(accounts, key=lambda a: a["name"].lower())


def get_meta_accounts(force: bool = False) -> list[dict]:
    if not force:
        cached = _cached("meta")
        if cached is not None:
            return cached
    try:
        accounts = _fetch_meta_accounts_live()
    except Exception:
        logger.exception("Falha ao buscar contas de anúncio Meta ao vivo")
        return _cached("meta") or []
    if accounts:
        _set_cached("meta", accounts)
    return accounts


def get_google_accounts(force: bool = False) -> list[dict]:
    if not force:
        cached = _cached("google")
        if cached is not None:
            return cached
    try:
        accounts = _fetch_google_accounts_live()
    except Exception:
        logger.exception("Falha ao buscar contas de anúncio Google ao vivo")
        return _cached("google") or []
    if accounts:
        _set_cached("google", accounts)
    return accounts
