"""
frontend/db_readers/ga4.py — Leitor de dados do GA4 (banco analytics).
"""
from __future__ import annotations

import re
from typing import Any

import pandas as pd
from sqlalchemy import text

from frontend.db import _get_engine
from frontend.utils import _extract_launch_code

_ETAPAS = ["Pré-Qualificação", "Captação"]


def _etapa_from_landing_page(landing_page: Any, code_slug: str) -> str | None:
    """Classifica a landing page em Pré-Qualificação/Captação pelo próprio
    caminho da URL — não pelo campo `campaign` do GA4, que só vem preenchido
    quando a sessão chega com UTM de campanha atribuída (a maioria do
    tráfego cai em "(not set)"/direto, então classificar por campanha
    deixava praticamente tudo de fora). O padrão de nome das LPs (Meta/
    Google/YouTube) sempre carrega o código do lançamento e, nas páginas de
    Pré-Qualificação, o sufixo "-pq-" (ex: "projeto-inss-pi-ago-26-v5-pq-fb",
    "obg-pi-ago-26-v5-pq-fb"). Páginas sem o código do lançamento no path
    (ex: "(not set)", "/matricula-inss") ficam fora de ambas as etapas."""
    lp = str(landing_page or "").lower()
    if not code_slug or code_slug not in lp:
        return None
    if "-pq-" in lp or lp.endswith("-pq"):
        return "Pré-Qualificação"
    return "Captação"


def read_landing_pages_por_etapa(launch_folder_or_code: Any, top_n: int = 8) -> dict[str, list[dict]]:
    """Landing pages que mais converteram em cada etapa (Pré-Qualificação e
    Captação) — classifica cada linha do ga4_daily pelo caminho da própria
    landing page (ver _etapa_from_landing_page), agrupa por landing_page e
    ordena por conversões (key_events)."""
    code = _extract_launch_code(launch_folder_or_code)
    code_slug = re.sub(r"[^a-z0-9]+", "-", code.lower()).strip("-") if code else ""
    engine = _get_engine()

    df = pd.read_sql(
        text("""
            SELECT landing_page, sessions, key_events
            FROM ga4_daily
            WHERE lancamento_codigo = :code
        """),
        engine,
        params={"code": code},
    )
    if df.empty:
        return {etapa: [] for etapa in _ETAPAS}

    df["etapa"] = df["landing_page"].map(lambda lp: _etapa_from_landing_page(lp, code_slug))
    df["landing_page"] = df["landing_page"].fillna("(não identificada)").replace("", "(não identificada)")

    result: dict[str, list[dict]] = {}
    for etapa in _ETAPAS:
        d = df[df["etapa"] == etapa]
        if d.empty:
            result[etapa] = []
            continue
        grouped = d.groupby("landing_page").agg(
            sessions=("sessions", "sum"),
            conversoes=("key_events", "sum"),
        ).reset_index()
        grouped = grouped[grouped["sessions"] > 0]
        grouped["taxa_conversao"] = grouped["conversoes"] / grouped["sessions"] * 100
        grouped = grouped.sort_values("conversoes", ascending=False).head(top_n)
        result[etapa] = [
            {
                "landing_page": r["landing_page"],
                "sessions": int(r["sessions"]),
                "conversoes": int(r["conversoes"]),
                "taxa_conversao": float(r["taxa_conversao"]),
            }
            for _, r in grouped.iterrows()
        ]
    return result


_VERSAO_RE = re.compile(r"-(v\d+(?:-pq-(?:fb|yt))?)$")


def _versao_da_pagina(landing_page: Any) -> str | None:
    """Extrai a versão da página do path (ex: "v5-pq-fb", "v8") — mesmo
    sufixo usado tanto na LP quanto na página de obrigado, então serve pra
    agrupar as duas. None quando o path não segue o padrão."""
    lp = str(landing_page or "").lower().rstrip("/")
    m = _VERSAO_RE.search(lp)
    return m.group(1) if m else None


def _rotulo_versao(versao: str) -> str:
    """"v5-pq-fb" -> "V5-PQ-FB" (Pré-Quali); "v8" -> "Versão 8" (Captação)."""
    if "-pq-" in versao:
        return versao.upper()
    num = versao.lstrip("v")
    return f"Versão {num}"


def read_conversao_pagina_captura(launch_folder_or_code: Any, top_n: int = 10) -> dict[str, list[dict]]:
    """Funil de conversão da página de captura, por etapa e versão de
    página: Sessões da LP → CTR → "chegou no obrigado" (evento
    generate_lead) → CTR → "clicou pra entrar no grupo" (evento
    qualify_lead). Os dois eventos disparam na própria LP (client-side,
    sem navegar pra uma URL de obrigado separada) — confirmado com o
    usuário em 06/09/26. Pauta debriefing/Captação/Pré-Qualificação."""
    code = _extract_launch_code(launch_folder_or_code)
    code_slug = re.sub(r"[^a-z0-9]+", "-", code.lower()).strip("-") if code else ""
    engine = _get_engine()

    df_sessions = pd.read_sql(
        text("SELECT landing_page, sessions FROM ga4_daily WHERE lancamento_codigo = :code"),
        engine, params={"code": code},
    )
    df_events = pd.read_sql(
        text("SELECT landing_page, event_name, sessions FROM ga4_events_daily WHERE lancamento_codigo = :code"),
        engine, params={"code": code},
    )
    if df_sessions.empty:
        return {etapa: [] for etapa in _ETAPAS}

    df_sessions["etapa"] = df_sessions["landing_page"].map(lambda lp: _etapa_from_landing_page(lp, code_slug))
    df_sessions["versao"] = df_sessions["landing_page"].map(_versao_da_pagina)
    df_sessions = df_sessions.dropna(subset=["etapa", "versao"])

    if not df_events.empty:
        df_events["etapa"] = df_events["landing_page"].map(lambda lp: _etapa_from_landing_page(lp, code_slug))
        df_events["versao"] = df_events["landing_page"].map(_versao_da_pagina)
        df_events = df_events.dropna(subset=["etapa", "versao"])

    result: dict[str, list[dict]] = {}
    for etapa in _ETAPAS:
        d = df_sessions[df_sessions["etapa"] == etapa]
        if d.empty:
            result[etapa] = []
            continue
        sessoes_por_versao = d.groupby("versao")["sessions"].sum()

        if not df_events.empty:
            de = df_events[df_events["etapa"] == etapa]
            gen_lead = de[de["event_name"] == "generate_lead"].groupby("versao")["sessions"].sum()
            qual_lead = de[de["event_name"] == "qualify_lead"].groupby("versao")["sessions"].sum()
        else:
            gen_lead = pd.Series(dtype=float)
            qual_lead = pd.Series(dtype=float)

        rows = []
        for versao, sessoes in sessoes_por_versao.items():
            sessoes = int(sessoes)
            if sessoes <= 0:
                continue
            obrigado = int(gen_lead.get(versao, 0))
            grupo = int(qual_lead.get(versao, 0))
            rows.append({
                "pagina": _rotulo_versao(versao),
                "sessoes_captura": sessoes,
                "ctr_obrigado": (obrigado / sessoes * 100) if sessoes > 0 else 0.0,
                "sessoes_obrigado": obrigado,
                "ctr_grupo": (grupo / obrigado * 100) if obrigado > 0 else 0.0,
                "clicaram_grupo": grupo,
            })
        rows.sort(key=lambda r: r["sessoes_captura"], reverse=True)
        result[etapa] = rows[:top_n]
    return result
