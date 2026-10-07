"""Previsto × realizado de verba de um lançamento.

Lê docs/performance/lancamentos/<LANC>/ORCAMENTO_<LANC>.md: o bloco CONFIG (contas, início da janela, como
reconhecer a etapa pelo nome da campanha) e a tabela PLANO. Busca ao vivo todas as campanhas com o código do
lançamento no nome e reescreve as seções PREVISTO e NO_AR do doc. Teto = gasto até agora + verba/dia × tempo até
o fim real da campanha (Meta: maior end_time dos ad sets; Google: end_date às 23h59). Campanha pausada entra só
com o que gastou.

Falha alto em qualquer erro de API — um relatório de verba com uma conta faltando em silêncio é pior que nenhum.

Bloco CONFIG (comentário HTML no ORCAMENTO; uma chave por linha, etapas na ordem em que devem ser testadas —
"base forte" antes de "captação", porque o nome da campanha de Base Forte também tem "captação"):

    <!-- CONFIG:INICIO
    desde: 2026-09-15
    meta: act_1407542209639031, act_1175937361058463
    google: 6482320788, 1450466453
    etapas: aquecimento=Aquecimento Black; base forte|base-forte=Base Forte; captação|captacao=Captação Black
    CONFIG:FIM -->

Uso:
    python scripts/orcamento.py BV-26            # reescreve o doc
    python scripts/orcamento.py BV-26 --dry-run  # só imprime
"""
from __future__ import annotations

import json
import os
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests
from dotenv import load_dotenv

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
load_dotenv(RAIZ / ".env")

from scripts.ads.padroes import GOOGLE_MCC, META_EXPERTS  # noqa: E402

BRT = timezone(timedelta(hours=-3))
GRAPH = "https://graph.facebook.com/v21.0"
GADS_VERSAO = "v22"
EXPERTS = list(META_EXPERTS)


def doc_do(lanc: str) -> Path:
    return RAIZ / f"docs/performance/lancamentos/{lanc}/ORCAMENTO_{lanc}.md"


def ler_config(texto: str) -> dict:
    m = re.search(r"<!-- CONFIG:INICIO\n(.*?)\nCONFIG:FIM -->", texto, flags=re.S)
    if not m:
        raise RuntimeError("bloco CONFIG ausente no ORCAMENTO (ver docstring de scripts/orcamento.py)")
    cfg = dict(linha.split(":", 1) for linha in m.group(1).strip().splitlines() if ":" in linha)
    cfg = {k.strip(): v.strip() for k, v in cfg.items()}
    etapas = []
    for par in cfg["etapas"].split(";"):
        chaves, rotulo = par.split("=")
        etapas.append(([c.strip().lower() for c in chaves.split("|")], rotulo.strip()))
    return {"desde": cfg["desde"],
            "meta": [c.strip() for c in cfg.get("meta", "").split(",") if c.strip()],
            "google": [c.strip() for c in cfg.get("google", "").split(",") if c.strip()],
            "etapas": etapas}


def etapa(nome: str, etapas: list) -> str:
    n = nome.lower()
    return next((rotulo for chaves, rotulo in etapas if any(c in n for c in chaves)), "Outros")


def expert(nome: str) -> str:
    n = nome.lower()
    return next((e.capitalize() for e in EXPERTS if f"[{e}]" in n), "?")


# ------------------------------------------------------------------ Meta
def _meta_get(url: str, params: dict | None) -> list[dict]:
    out = []
    while url:
        r = requests.get(url, params=params, timeout=60).json()
        params = None
        if "error" in r:
            raise RuntimeError(f"Meta: {r['error'].get('message')} ({url})")
        out += r.get("data", [])
        url = r.get("paging", {}).get("next")
    return out


def meta_campanhas(lanc: str, contas: list[str], desde: str, hoje: str) -> list[dict]:
    tok = os.environ["META_ACCESS_TOKEN"]
    filtro = json.dumps([{"field": "name", "operator": "CONTAIN", "value": lanc}])
    linhas = []
    for conta in contas:
        gasto = {d["campaign_id"]: float(d["spend"]) for d in _meta_get(
            f"{GRAPH}/{conta}/insights",
            {"access_token": tok, "level": "campaign", "fields": "campaign_id,spend", "limit": 500,
             "time_range": json.dumps({"since": desde, "until": hoje}),
             "filtering": json.dumps([{"field": "campaign.name", "operator": "CONTAIN", "value": lanc}])})}
        for c in _meta_get(f"{GRAPH}/{conta}/campaigns",
                           {"access_token": tok, "limit": 200, "filtering": filtro,
                            "fields": "id,name,effective_status,daily_budget,"
                                      "adsets.limit(100){end_time,effective_status,daily_budget}"}):
            adsets = c.get("adsets", {}).get("data", [])
            fins = [datetime.fromisoformat(a["end_time"]) for a in adsets if a.get("end_time")]
            dia = int(c.get("daily_budget") or 0) / 100 or sum(
                int(a.get("daily_budget") or 0) for a in adsets if a.get("effective_status") == "ACTIVE") / 100
            linhas.append({"plataforma": "Facebook", "id": c["id"], "nome": c["name"],
                           "ativa": c["effective_status"] == "ACTIVE", "status": c["effective_status"],
                           "dia": dia, "fim": max(fins) if fins else None, "gasto": gasto.get(c["id"], 0.0)})
    return linhas


# ------------------------------------------------------------------ Google
def _google_token() -> str:
    r = requests.post("https://oauth2.googleapis.com/token", timeout=30, data={
        "grant_type": "refresh_token", "refresh_token": os.environ["GOOGLE_ADS_REFRESH_TOKEN"],
        "client_id": os.environ["GOOGLE_ADS_CLIENT_ID"], "client_secret": os.environ["GOOGLE_ADS_CLIENT_SECRET"]})
    r.raise_for_status()
    return r.json()["access_token"]


def _google_search(token: str, conta: str, query: str) -> list[dict]:
    headers = {"Authorization": f"Bearer {token}", "developer-token": os.environ["GOOGLE_ADS_DEVELOPER_TOKEN"],
               "login-customer-id": os.environ.get("GOOGLE_ADS_LOGIN_CUSTOMER_ID", GOOGLE_MCC).replace("-", "")}
    url = f"https://googleads.googleapis.com/{GADS_VERSAO}/customers/{conta}/googleAds:search"
    out, page = [], None
    while True:
        r = requests.post(url, headers=headers, json={"query": query, **({"pageToken": page} if page else {})},
                          timeout=60)
        if r.status_code != 200:
            raise RuntimeError(f"Google {conta}: HTTP {r.status_code} {r.text[:300]}")
        d = r.json()
        out += d.get("results", [])
        page = d.get("nextPageToken")
        if not page:
            return out


def google_campanhas(lanc: str, contas: list[str], desde: str, hoje: str) -> list[dict]:
    if not contas:
        return []
    token = _google_token()
    linhas = []
    for conta in contas:
        base = {}
        for r in _google_search(token, conta, f"""
                SELECT campaign.id, campaign.name, campaign.status, campaign.end_date,
                       campaign_budget.amount_micros
                FROM campaign WHERE campaign.name LIKE '%{lanc}%' AND campaign.status != 'REMOVED'"""):
            c = r["campaign"]
            fim = datetime.fromisoformat(c["endDate"]).replace(hour=23, minute=59, tzinfo=BRT) \
                if c.get("endDate") else None
            base[c["id"]] = {"plataforma": "Google", "id": c["id"], "nome": c["name"],
                             "ativa": c["status"] == "ENABLED", "status": c["status"],
                             "dia": int(r["campaignBudget"]["amountMicros"]) / 1e6, "fim": fim, "gasto": 0.0}
        for r in _google_search(token, conta, f"""
                SELECT campaign.id, metrics.cost_micros FROM campaign
                WHERE campaign.name LIKE '%{lanc}%' AND segments.date BETWEEN '{desde}' AND '{hoje}'"""):
            if r["campaign"]["id"] in base:
                base[r["campaign"]["id"]]["gasto"] += int(r["metrics"].get("costMicros", 0)) / 1e6
        linhas += base.values()
    return linhas


# ------------------------------------------------------------------ plano e relatório
def ler_plano(texto: str) -> dict[tuple[str, str, str], float]:
    bloco = texto.split("<!-- PLANO:INICIO -->")[1].split("<!-- PLANO:FIM -->")[0]
    plano = {}
    for linha in bloco.strip().splitlines()[2:]:
        et, ex, pl, valor = [c.strip() for c in linha.strip("|").split("|")]
        plano[(et, ex, pl)] = float(valor)
    if not plano:
        raise RuntimeError("tabela PLANO vazia ou ilegível no ORCAMENTO")
    return plano


def brl(v: float) -> str:
    return f"{v:,.0f}".replace(",", ".")


def reais(v: float) -> str:
    return f"{v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def montar(lanc: str, linhas: list[dict], plano: dict, etapas: list, agora: datetime) -> tuple[str, str]:
    for r in linhas:
        restante = max(0.0, (r["fim"] - agora).total_seconds() / 86400) if (r["ativa"] and r["fim"]) else 0.0
        r["teto"] = r["gasto"] + r["dia"] * restante
        r["chave"] = (etapa(r["nome"], etapas), expert(r["nome"]), r["plataforma"])

    ordem_expert = [e.capitalize() for e in EXPERTS] + ["?"]
    carimbo = agora.strftime("%d/%m/%Y %H:%M")
    agg: dict[tuple, dict] = {}
    for k in plano:
        agg[k] = {"plano": plano[k], "gasto": 0.0, "dia": 0.0, "teto": 0.0, "fins": set()}
    for r in linhas:
        a = agg.setdefault(r["chave"], {"plano": 0.0, "gasto": 0.0, "dia": 0.0, "teto": 0.0, "fins": set()})
        a["gasto"] += r["gasto"]
        a["teto"] += r["teto"]
        if r["ativa"]:
            a["dia"] += r["dia"]
            if r["fim"]:
                a["fins"].add(r["fim"].astimezone(BRT).strftime("%d/%m %Hh%M"))

    prev = [f"*Gerado em {carimbo} (horário de Brasília).*", "",
            "| Etapa | Expert | Plataforma | Plano | Gasto | R$/dia no ar | Teto até o fim | Diferença | Fim no ar |",
            "|---|---|---|---|---|---|---|---|---|"]
    totais: dict[str, list[float]] = {}
    for k in sorted(agg, key=lambda k: (k[0], ordem_expert.index(k[1]) if k[1] in ordem_expert else 99, k[2])):
        a = agg[k]
        dif = a["teto"] - a["plano"]
        marca = "**" if a["plano"] and abs(dif) > 0.10 * a["plano"] else ""
        fim = ", ".join(sorted(a["fins"])) or ("sem campanha" if not a["gasto"] else "encerrada/pausada")
        prev.append(f"| {k[0]} | {k[1]} | {k[2]} | {brl(a['plano'])} | {brl(a['gasto'])} | {brl(a['dia'])} | "
                    f"{brl(a['teto'])} | {marca}{'+' if dif >= 0 else '−'}{brl(abs(dif))}{marca} | {fim} |")
        t = totais.setdefault(k[0], [0.0, 0.0, 0.0])
        t[0] += a["plano"]; t[1] += a["gasto"]; t[2] += a["teto"]
    prev += ["", "**Totais por etapa:** " + " · ".join(
        f"{e}: plano {brl(p)} · gasto {brl(g)} · teto {brl(t)} ({'+' if t - p >= 0 else '−'}{brl(abs(t - p))})"
        for e, (p, g, t) in totais.items()),
        "", "Diferença em **negrito** = mais de 10% do plano."]

    noar = [f"*Gerado em {carimbo}.* Todas as campanhas com `{lanc}` no nome.", "",
            "| Plataforma | Etapa | Expert | Status | R$/dia | Fim | Gasto | Campanha |", "|---|---|---|---|---|---|---|---|"]
    for r in sorted(linhas, key=lambda r: (r["chave"], not r["ativa"], r["nome"])):
        fim = r["fim"].astimezone(BRT).strftime("%d/%m %Hh%M") if r["fim"] else "—"
        noar.append(f"| {r['plataforma']} | {r['chave'][0]} | {r['chave'][1]} | {r['status']} | "
                    f"{reais(r['dia'])} | {fim} | {brl(r['gasto'])} | `{r['nome']}` |")
    return "\n".join(prev), "\n".join(noar)


def main() -> None:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if len(args) != 1:
        sys.exit("uso: python scripts/orcamento.py <LANC> [--dry-run]")
    lanc, dry = args[0].upper(), "--dry-run" in sys.argv
    doc = doc_do(lanc)
    if not doc.exists():
        sys.exit(f"não achei {doc.relative_to(RAIZ)} — crie a partir de "
                 "docs/performance/playbooks/MODELO_ORCAMENTO.md")
    agora = datetime.now(BRT)
    hoje = agora.strftime("%Y-%m-%d")
    texto = doc.read_text(encoding="utf-8")
    cfg, plano = ler_config(texto), ler_plano(texto)
    linhas = (meta_campanhas(lanc, cfg["meta"], cfg["desde"], hoje)
              + google_campanhas(lanc, cfg["google"], cfg["desde"], hoje))
    prev, noar = montar(lanc, linhas, plano, cfg["etapas"], agora)
    if dry:
        print(prev, "\n\n", noar)
        return
    for marca, conteudo in (("PREVISTO", prev), ("NO_AR", noar)):
        texto = re.sub(rf"(<!-- {marca}:INICIO -->\n).*?(\n<!-- {marca}:FIM -->)",
                       lambda m: m.group(1) + conteudo + m.group(2), texto, count=1, flags=re.S)
    texto = re.sub(r"^atualizado: .*$", f"atualizado: {hoje}", texto, count=1, flags=re.M)
    doc.write_text(texto, encoding="utf-8")
    print(f"{doc.name} atualizado ({len(linhas)} campanhas, {agora:%d/%m %H:%M})")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
