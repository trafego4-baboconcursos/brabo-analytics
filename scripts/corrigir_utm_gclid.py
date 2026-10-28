"""Corrige a campanha do UTM dos COMPRADORES de um lançamento pelo `gclid`, usando o Google Ads como fonte.

POR QUE EXISTE: no PI-AGO-26 e no PBB-AGO-26 a campanha escrita no UTM não era a do clique real (erro manual de nomenclatura):
  - as campanhas "potencial" (e "new-ads"/"best-ads" no PBB) usavam o nome da "principal" — medido em 05/08/26 no PI-AGO-26, 27% dos
    leads do Google (869 de 3.191) clicaram numa campanha Potencial e o UTM dizia "principal";
  - a campanha Específico principal do PI-AGO-26 saiu com a data de OUTRA campanha (`24.03.26` em vez de `27.07.26`).
O `gclid` do lead identifica o clique, e o relatório `click_view` do Google Ads devolve a campanha real (Search, Demand Gen, Vídeo e P-Max).

O QUE FAZ: só para os compradores com origem Google e `gclid`, troca `utm_campaign` pelo nome real da campanha em `atribuicao_congelada`
(origem='gclid_google_ads'). Fonte, mídia, conteúdo e termo (código do anúncio) ficam como estão. NÃO mexe na tabela `leads` nem em
`lead_utm_lancamento`. Guarda um CSV com o que havia antes em `outputs/`.

LIMITE: `click_view` só guarda 90 dias. Clique mais antigo que isso não é resolvido e o comprador fica como estava.

Uso:
    python scripts/corrigir_utm_gclid.py --launch PI-AGO-26            # simula (padrão): não grava nada
    python scripts/corrigir_utm_gclid.py --launch PI-AGO-26 --aplicar  # grava, com backup
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import os
import re
import sys
import urllib.parse
from pathlib import Path

_RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_RAIZ))
sys.path.insert(0, str(_RAIZ / "src"))
sys.path.insert(0, str(_RAIZ / "etl"))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(_RAIZ / ".env")

import requests  # noqa: E402
from sqlalchemy import text  # noqa: E402

_CHUNK = 250
_JANELA_CLICK_VIEW_DIAS = 89


def _norm(s) -> str:
    return urllib.parse.unquote(str(s or "")).strip().lower()


def _sem_data(nome: str) -> str:
    """Tira os colchetes de data (`[27.07.26]`) para comparar o resto do nome."""
    return re.sub(r"\[\d{2}\.\d{2}\.\d{2,4}\]", "", nome)


def _classificar(atual: str, real: str) -> str:
    if not atual:
        return "sem_campanha_no_utm"
    if atual == real:
        return "igual"
    if _sem_data(atual) == _sem_data(real):
        return "so_a_data"
    return "outra_campanha"      # ex.: principal no UTM, potencial no clique


def _compradores_google(code: str, emails: list[str]) -> list[dict]:
    from frontend.db import _get_engine  # noqa: PLC0415

    with _get_engine().connect() as conn:
        conn.execute(text("SET LOCAL statement_timeout = 120000"))
        linhas = conn.execute(text("""
            SELECT DISTINCT ON (lower(email)) lower(email) AS email, gclid, utm_source, utm_medium, utm_campaign, utm_content, utm_term
            FROM lead_utm_lancamento
            WHERE lancamento_codigo = :c AND lower(email) = ANY(:em)
              AND (lower(utm_source) LIKE '%google%' OR lower(utm_source) LIKE '%youtube%')
              AND coalesce(trim(gclid), '') <> ''
            ORDER BY lower(email), ultimo_visto_em DESC NULLS LAST
        """), {"c": code, "em": emails}).fetchall()
    return [dict(zip(("email", "gclid", "source", "medium", "campaign", "content", "term"), r)) for r in linhas]


def _campanhas_reais(customer_id: str, gclids: set[str], dias: list[dt.date]) -> dict[str, str]:
    from etl.etl_google_ads import API_VERSION, _get_access_token  # noqa: PLC0415

    headers = {"Authorization": f"Bearer {_get_access_token()}", "developer-token": os.environ["GOOGLE_ADS_DEVELOPER_TOKEN"],
               "Content-Type": "application/json"}
    login = os.environ.get("GOOGLE_ADS_LOGIN_CUSTOMER_ID", "").replace("-", "")
    if login:
        headers["login-customer-id"] = login
    url = f"https://googleads.googleapis.com/{API_VERSION}/customers/{customer_id}/googleAds:search"
    achados: dict[str, str] = {}
    for dia in dias:
        pendentes = sorted(gclids - achados.keys())
        if not pendentes:
            break
        for i in range(0, len(pendentes), _CHUNK):
            lista = ", ".join("'" + g.replace("'", "") + "'" for g in pendentes[i:i + _CHUNK])
            q = f"SELECT click_view.gclid, campaign.name FROM click_view WHERE segments.date = '{dia}' AND click_view.gclid IN ({lista})"
            token = None
            while True:
                body = {"query": q}
                if token:
                    body["pageToken"] = token
                r = requests.post(url, headers=headers, json=body, timeout=120)
                r.raise_for_status()
                j = r.json()
                for x in j.get("results", []):
                    achados[x["clickView"]["gclid"]] = x["campaign"]["name"]
                token = j.get("nextPageToken")
                if not token:
                    break
        print(f"  {dia}: {len(achados)}/{len(gclids)} gclids resolvidos", flush=True)
    return achados


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--launch", required=True)
    ap.add_argument("--aplicar", action="store_true", help="grava em atribuicao_congelada (sem isto, só simula)")
    a = ap.parse_args()
    code = a.launch.upper()

    from frontend.core import get_launches, resolve_launch  # noqa: PLC0415
    from frontend.db_readers.atribuicao_congelada import corrigir_congelada, ler_congelada  # noqa: PLC0415
    from frontend.db_readers.launches import read_launch_config  # noqa: PLC0415
    from frontend.db_readers.sales import read_vendas  # noqa: PLC0415
    from frontend.services.classificadores import _utm_score  # noqa: PLC0415

    cfg = read_launch_config(code)
    contas = cfg.get("google_ad_account_ids") or []
    if not contas:
        print("lançamento sem conta Google cadastrada")
        return 1
    launch = resolve_launch(code, get_launches())
    vendas = read_vendas(launch.folder)
    emails = sorted({e.lower().strip() for e in (vendas.emails_hotmart | vendas.emails_tmb)})
    compr = _compradores_google(code, emails)
    print(f"{code}: {len(emails)} compradores | com origem Google e gclid: {len(compr)} | conta {contas[0]}")

    hoje = dt.date.today()
    ini = max(hoje - dt.timedelta(days=_JANELA_CLICK_VIEW_DIAS), dt.date.fromisoformat(str(cfg.get("pre_quali_start_date") or cfg.get("captacao_start_date"))))
    fim = dt.date.fromisoformat(str(cfg.get("carrinho_end_date"))) + dt.timedelta(days=1)
    dias = [ini + dt.timedelta(days=i) for i in range((fim - ini).days + 1)]
    print(f"consultando o click_view de {dias[0]} a {dias[-1]} ({len(dias)} dias; limite do Google = 90 dias)")
    reais = _campanhas_reais(contas[0], {c["gclid"] for c in compr}, dias)

    congeladas = ler_congelada(code)
    cats: dict[str, int] = {}
    mudar: list[dict] = []
    planilha: list[list] = []
    for c in compr:
        real = _norm(reais.get(c["gclid"], ""))
        if not real:
            cats["nao_resolvido (clique fora dos 90 dias ou de outra conta)"] = cats.get("nao_resolvido (clique fora dos 90 dias ou de outra conta)", 0) + 1
            continue
        atual = _norm(c["campaign"])
        cat = _classificar(atual, real)
        cats[cat] = cats.get(cat, 0) + 1
        planilha.append([c["email"], c["gclid"][:12] + "...", cat, atual, real])
        if cat == "igual":
            continue
        score = _utm_score(code, c["source"] or "", c["medium"] or "", real, c["content"] or "", c["term"] or "")
        anterior = congeladas.get(c["email"], {})
        score = max(score, int(anterior.get("score") or 0))     # o congelador não pode passar por cima da correção
        mudar.append({"email": c["email"], "score": score, "source": c["source"] or "", "medium": c["medium"] or "", "campaign": real,
                      "content": c["content"] or "", "term": c["term"] or "", "_antes": anterior})

    print("\nresultado da comparação (campanha do UTM x campanha real do clique):")
    for k, v in sorted(cats.items(), key=lambda x: -x[1]):
        print(f"   {k:62s} {v:>5}")
    print(f"a corrigir: {len(mudar)} compradores")
    pastas = _RAIZ / "outputs"
    pastas.mkdir(exist_ok=True)
    carimbo = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    plano = pastas / f"utm_gclid_plano_{code}_{carimbo}.csv"
    with open(plano, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["email", "gclid", "categoria", "campanha_no_utm", "campanha_real"])
        w.writerows(planilha)
    print("plano completo:", plano)
    if not a.aplicar:
        print("\nSIMULAÇÃO — nada foi gravado. Rode com --aplicar para gravar.")
        return 0

    backup = pastas / f"backup_atribuicao_congelada_{code}_{carimbo}.csv"
    with open(backup, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["email", "tinha_linha", "score", "source", "medium", "campaign", "content", "term", "origem"])
        for m in mudar:
            ant = m["_antes"]
            w.writerow([m["email"], bool(ant), ant.get("score", ""), ant.get("source", ""), ant.get("medium", ""), ant.get("campaign", ""),
                        ant.get("content", ""), ant.get("term", ""), ant.get("origem", "")])
    n = corrigir_congelada(code, {m["email"]: {k: v for k, v in m.items() if not k.startswith("_")} for m in mudar}, origem="gclid_google_ads")
    print(f"GRAVADO: {n} linhas em atribuicao_congelada (origem=gclid_google_ads) | backup do que havia: {backup}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
