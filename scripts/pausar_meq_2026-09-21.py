"""
scripts/pausar_meq_2026-09-21.py — Pausa o que a rodada de 21/09/26 do perpétuo
Mestre em Questões apontou como queima de verba.

Contexto e números: docs/performance/perpetuo/ACOMPANHAMENTO_PERPETUO_MEQ.md § 2.2

O que pausa:

  GOOGLE (customer 8399986700)
    - campanha   [GA][TJSP][compra][frio][p-max][02.07.26]   R$ 1.269,51 / 0 conversões em 21d
    - asset group 6727231384 (AD019 - PP-PES-26)
      Os DOIS níveis de propósito: no Google e no Meta o status não cascateia
      (regra VER-1). Pausar só a campanha deixa o asset group ENABLED, e ele
      volta a veicular sozinho se alguém reativar a campanha depois.

  META (conta act_754583761035107)
    - 120243362906470144  AD018 - Apostila PP-PI (Feed)          INSS  CPA R$ 135,46
    - 120245106060430144  AD031 - Estúdio Brabo V15 + cx         BB    CPA R$ 167,85
    - 120244996102180144  AD0034 - Estúdio Brabo ACELERADO V03   BB    CPA R$ 429,14

  NÃO pausa as cópias desses mesmos criativos no TJ-SP (120243061652560144,
  120247063880390144, 120244465669540144): gastam centavos e o AD018 de lá
  converteu a R$ 5,90. Cortar por nome de criativo, ignorando a vertical,
  mataria um anúncio bom — foi o erro que quase entrou nesta rodada.

Uso:
    python scripts/pausar_meq_2026-09-21.py              # dry-run: só mostra o estado atual
    python scripts/pausar_meq_2026-09-21.py --aplicar    # executa e reconfere

Idempotente: pausar o que já está pausado não quebra nem muda nada.
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import requests
from dotenv import load_dotenv

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "etl"))
load_dotenv(dotenv_path=RAIZ / ".env")

GOOGLE_CID = "8399986700"
GOOGLE_CAMPANHA = "[GA][TJSP][compra][frio][p-max][02.07.26]"
META_CONTA = "act_754583761035107"
META_API = "v21.0"
META_ALVOS = {
    "120243362906470144": "AD018 - Apostila PP-PI (Feed)          [INSS] CPA R$ 135,46",
    "120245106060430144": "AD031 - Estudio Brabo V15 + cx         [BB]   CPA R$ 167,85",
    "120244996102180144": "AD0034 - Estudio Brabo ACELERADO V03   [BB]   CPA R$ 429,14",
}


# ── Google ───────────────────────────────────────────────────────────────────
def _google_headers():
    import etl_google_ads as g  # importa aqui pra não exigir .env no --help

    return {
        "Authorization": f"Bearer {g._get_access_token()}",
        "developer-token": os.environ["GOOGLE_ADS_DEVELOPER_TOKEN"],
        "Content-Type": "application/json",
        "login-customer-id": os.environ["GOOGLE_ADS_LOGIN_CUSTOMER_ID"].replace("-", ""),
    }, g.API_VERSION


def _google_estado(base, headers):
    """[(campaign_id, campaign_status, asset_group_id, asset_group_name, ag_status)]"""
    query = (
        "SELECT campaign.id, campaign.name, campaign.status, asset_group.id, "
        "asset_group.name, asset_group.status "
        f"FROM asset_group WHERE campaign.name = '{GOOGLE_CAMPANHA}'"
    )
    r = requests.post(f"{base}/googleAds:search", headers=headers,
                      json={"query": query}, timeout=60)
    r.raise_for_status()
    return [
        (x["campaign"]["id"], x["campaign"]["status"], x["assetGroup"]["id"],
         x["assetGroup"].get("name", ""), x["assetGroup"]["status"])
        for x in r.json().get("results", [])
    ]


def google(aplicar: bool) -> bool:
    headers, api_version = _google_headers()
    base = f"https://googleads.googleapis.com/{api_version}/customers/{GOOGLE_CID}"

    estado = _google_estado(base, headers)
    if not estado:
        print(f"  !! campanha nao encontrada: {GOOGLE_CAMPANHA}")
        return False
    for camp_id, camp_st, ag_id, ag_nome, ag_st in estado:
        print(f"  ANTES  campanha {camp_id}={camp_st}  asset_group {ag_id} ({ag_nome})={ag_st}")
    if not aplicar:
        return True

    camp_id = estado[0][0]
    r = requests.post(
        f"{base}/campaigns:mutate", headers=headers, timeout=60,
        json={"operations": [{
            "update": {"resourceName": f"customers/{GOOGLE_CID}/campaigns/{camp_id}",
                       "status": "PAUSED"},
            "updateMask": "status"}]},
    )
    print(f"  mutate campanha    -> HTTP {r.status_code} {r.text[:200]}")
    ok = r.status_code == 200

    r = requests.post(
        f"{base}/assetGroups:mutate", headers=headers, timeout=60,
        json={"operations": [{
            "update": {"resourceName": f"customers/{GOOGLE_CID}/assetGroups/{ag_id}",
                       "status": "PAUSED"},
            "updateMask": "status"} for _, _, ag_id, _, _ in estado]},
    )
    print(f"  mutate asset group -> HTTP {r.status_code} {r.text[:200]}")
    ok = ok and r.status_code == 200

    for camp_id, camp_st, ag_id, ag_nome, ag_st in _google_estado(base, headers):
        print(f"  DEPOIS campanha {camp_id}={camp_st}  asset_group {ag_id}={ag_st}")
        ok = ok and camp_st == "PAUSED" and ag_st == "PAUSED"
    return ok


# ── Meta ─────────────────────────────────────────────────────────────────────
def _meta_estado(ad_id: str, token: str) -> str:
    r = requests.get(f"https://graph.facebook.com/{META_API}/{ad_id}",
                     params={"fields": "name,status,effective_status",
                             "access_token": token}, timeout=30)
    if r.status_code != 200:
        return f"ERRO {r.status_code}: {r.text[:160]}"
    d = r.json()
    return f"{d.get('status')} / entrega={d.get('effective_status')}"


def meta(aplicar: bool) -> bool:
    token = os.environ["META_ACCESS_TOKEN"]
    for ad_id, desc in META_ALVOS.items():
        print(f"  ANTES  {ad_id}  {desc}\n           {_meta_estado(ad_id, token)}")
    if not aplicar:
        return True

    ok = True
    for ad_id, desc in META_ALVOS.items():
        r = requests.post(f"https://graph.facebook.com/{META_API}/{ad_id}",
                          data={"status": "PAUSED", "access_token": token}, timeout=30)
        print(f"  pause {ad_id} -> HTTP {r.status_code} {r.text[:160]}")
        ok = ok and r.status_code == 200
    for ad_id in META_ALVOS:
        estado = _meta_estado(ad_id, token)
        print(f"  DEPOIS {ad_id}  {estado}")
        ok = ok and estado.startswith("PAUSED")
    return ok


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--aplicar", action="store_true",
                    help="executa as pausas (sem isso, só mostra o estado atual)")
    args = ap.parse_args()

    if not args.aplicar:
        print(">>> DRY-RUN — nada sera alterado. Use --aplicar para executar.\n")

    print("GOOGLE ADS")
    ok_google = google(args.aplicar)
    print("\nMETA ADS")
    ok_meta = meta(args.aplicar)

    if args.aplicar:
        print(f"\nResultado: google={'ok' if ok_google else 'FALHOU'}  "
              f"meta={'ok' if ok_meta else 'FALHOU'}")
        if not (ok_google and ok_meta):
            print("Alguma pausa nao confirmou. Conferir na interface antes de registrar.")
            return 1
        print("Registrar em docs/performance/perpetuo/ACOMPANHAMENTO_PERPETUO_MEQ.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
