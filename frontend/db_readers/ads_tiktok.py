"""
frontend/db_readers/ads_tiktok.py — Leitor do TikTok Ads (tabela tiktok_ads_daily, banco analytics).

Gravada por etl/etl_tiktok_ads.py desde 13/11/26. A classificação (etapa/temperatura)
já vem do ETL. As chaves dos dicionários seguem o MetaSummary (`gasto`/`custo`,
`leads`, `impressoes`...) para as páginas somarem o TikTok sem caso especial.

`leads` = coluna `conversions` (evento de otimização do grupo: lead em
LEAD_GENERATION). Em campanha de VIDEO_VIEWS é 0 — o resultado dela é a view de 6s.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any

from sqlalchemy import text

from logger import get_logger
from frontend.db import _get_engine
from src.ad_codes import extract_ad_code
from src.constants import etapa_prequali

logger = get_logger("db")

_COLUNAS = (
    "date, ad_id, ad_name, adgroup_name, campaign_id, campaign_name, objective_type, account_id, "
    "impressions, clicks, spend, reach, conversions, results, video_plays, video_views_2s, "
    "video_views_6s, video_views_25, video_views_50, video_views_75, video_views_100, "
    "video_avg_time_watched, likes, comments, shares, follows, profile_visits, "
    "COALESCE(etapa, 'Outros') AS etapa, COALESCE(temperatura, 'Outros') AS temperatura"
)


@dataclass
class TikTokSummary:
    total_gasto: float = 0.0
    total_leads: int = 0
    total_impressoes: int = 0
    total_cliques: int = 0
    total_alcance: int = 0
    por_etapa: dict = field(default_factory=dict)
    por_temperatura_captacao: dict = field(default_factory=dict)
    por_temperatura_prequali: dict = field(default_factory=dict)
    por_conta: dict = field(default_factory=dict)
    por_conta_captacao: dict = field(default_factory=dict)
    campanhas: list = field(default_factory=list)
    captacao_por_ad: list = field(default_factory=list)
    preq_por_ad: list = field(default_factory=list)
    por_dia: dict = field(default_factory=dict)   # {"YYYY-MM-DD": {"gasto", "leads", "por_etapa": {etapa: gasto}}}


def _vazio() -> dict:
    return {"gasto": 0.0, "custo": 0.0, "leads": 0, "impressoes": 0, "cliques": 0, "alcance": 0,
            "views_2s": 0, "views_6s": 0, "views_25": 0, "views_50": 0, "views_100": 0, "plays": 0}


def _somar(d: dict, r: Any) -> None:
    gasto = float(r.spend or 0)
    d["gasto"] += gasto
    d["custo"] += gasto
    d["leads"] += int(r.conversions or 0)
    d["impressoes"] += int(r.impressions or 0)
    d["cliques"] += int(r.clicks or 0)
    d["alcance"] += int(r.reach or 0)
    d["plays"] += int(r.video_plays or 0)
    d["views_2s"] += int(r.video_views_2s or 0)
    d["views_6s"] += int(r.video_views_6s or 0)
    d["views_25"] += int(r.video_views_25 or 0)
    d["views_50"] += int(r.video_views_50 or 0)
    d["views_100"] += int(r.video_views_100 or 0)


def _derivadas(d: dict) -> dict:
    d["cpl"] = d["gasto"] / d["leads"] if d["leads"] else 0.0
    d["ctr"] = d["cliques"] / d["impressoes"] * 100 if d["impressoes"] else 0.0
    d["cpm"] = d["gasto"] / d["impressoes"] * 1000 if d["impressoes"] else 0.0
    # "Hook" do TikTok = view de 2s ÷ impressão; "hold" = 6s ÷ 2s (o TikTok não tem ThruPlay).
    d["hook_rate"] = d["views_2s"] / d["impressoes"] * 100 if d["impressoes"] else 0.0
    d["hold_rate"] = d["views_6s"] / d["views_2s"] * 100 if d["views_2s"] else 0.0
    d["custo_view_6s"] = d["gasto"] / d["views_6s"] if d["views_6s"] else 0.0
    # Chaves com o nome que os blocos de pré-quali do Meta/Google usam.
    d["thruplays"] = d["views_6s"]
    return d


def _ler_linhas(code: str, start: str | None, end: str | None) -> list:
    filtro, params = ["lancamento_codigo = :code"], {"code": code}
    if start:
        filtro.append("date >= :start")
        params["start"] = start
    if end:
        filtro.append("date <= :end")
        params["end"] = end
    with _get_engine().connect() as conn:
        return conn.execute(text(f"SELECT {_COLUNAS} FROM tiktok_ads_daily WHERE {' AND '.join(filtro)}"),
                            params).fetchall()


def _por_ad(linhas: list, code: str) -> list[dict]:
    por: dict[str, dict] = {}
    for r in linhas:
        ad_code = extract_ad_code(r.ad_name or "", code) or ""
        chave = ad_code or str(r.ad_id)
        d = por.get(chave)
        if d is None:
            d = por[chave] = {**_vazio(), "ad_code": ad_code or (r.ad_name or "")[:24],
                              "nome": r.ad_name or "", "campanha": r.campaign_name or "",
                              "temperatura": r.temperatura}
        _somar(d, r)
    out = [_derivadas(d) for d in por.values()]
    return sorted(out, key=lambda d: (-d["leads"], -d["gasto"]))


def read_tiktok(code: str, start_date: str | None = None, end_date: str | None = None) -> TikTokSummary | None:
    """Resumo do TikTok de um lançamento (ou pseudo-lançamento DISTRIBUICAO-*).
    None quando não há linha nenhuma — a página trata como "sem TikTok"."""
    if not code:
        return None
    linhas = _ler_linhas(code, start_date, end_date)
    if not linhas:
        return None

    s = TikTokSummary()
    tot, etapas, temp_capt, temp_preq, contas, contas_capt, camps = _vazio(), {}, {}, {}, {}, {}, {}
    etapa_pq = etapa_prequali(code)
    for r in linhas:
        _somar(tot, r)
        _somar(etapas.setdefault(r.etapa, {**_vazio(), "etapa": r.etapa}), r)
        _somar(contas.setdefault(str(r.account_id), _vazio()), r)
        if r.etapa == "Captação":
            _somar(temp_capt.setdefault(r.temperatura, {**_vazio(), "temperatura": r.temperatura}), r)
            _somar(contas_capt.setdefault(str(r.account_id), _vazio()), r)
        elif r.etapa == etapa_pq:
            _somar(temp_preq.setdefault(r.temperatura, {**_vazio(), "temperatura": r.temperatura}), r)
        c = camps.setdefault(str(r.campaign_id), {**_vazio(), "nome": r.campaign_name, "etapa": r.etapa,
                                                  "temperatura": r.temperatura, "objetivo": r.objective_type,
                                                  "inicio": r.date, "fim": r.date})
        _somar(c, r)
        c["inicio"], c["fim"] = min(c["inicio"], r.date), max(c["fim"], r.date)
        dia = s.por_dia.setdefault(str(r.date), {"gasto": 0.0, "leads": 0, "por_etapa": {}})
        dia["gasto"] += float(r.spend or 0)
        dia["leads"] += int(r.conversions or 0)
        dia["por_etapa"][r.etapa] = dia["por_etapa"].get(r.etapa, 0.0) + float(r.spend or 0)

    s.total_gasto, s.total_leads = tot["gasto"], tot["leads"]
    s.total_impressoes, s.total_cliques, s.total_alcance = tot["impressoes"], tot["cliques"], tot["alcance"]
    total = tot["gasto"] or 1.0
    s.por_etapa = {k: {**_derivadas(v), "pct": v["gasto"] / total * 100} for k, v in etapas.items()}
    s.por_temperatura_captacao = {k: _derivadas(v) for k, v in temp_capt.items()}
    s.por_temperatura_prequali = {k: _derivadas(v) for k, v in temp_preq.items()}
    s.por_conta = {k: _derivadas(v) for k, v in contas.items()}
    s.por_conta_captacao = {k: _derivadas(v) for k, v in contas_capt.items()}
    s.campanhas = sorted((_derivadas(v) for v in camps.values()), key=lambda c: -c["gasto"])
    s.captacao_por_ad = _por_ad([r for r in linhas if r.etapa == "Captação"], code)
    s.preq_por_ad = _por_ad([r for r in linhas if r.etapa == etapa_pq], code)
    return s


def read_tiktok_distribuicao(codigo: str, start: date, end: date) -> list:
    """Linhas cruas do período para /distribuicao/{username} (que agrega por criativo)."""
    with _get_engine().connect() as conn:
        return conn.execute(text(
            "SELECT date, ad_name, spend, impressions, clicks, reach, video_plays, video_views_2s, "
            "video_views_6s, video_views_25, video_views_50, video_views_75, video_views_100, "
            "likes, comments, shares, follows, profile_visits "
            "FROM tiktok_ads_daily WHERE lancamento_codigo = :c AND date BETWEEN :s AND :e"
        ), {"c": codigo, "s": start, "e": end}).fetchall()
