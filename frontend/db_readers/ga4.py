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
    if not code_slug:
        return None
    # A LP do PBB se chama "/projeto-bb-ago-26-v2", sem o "P" do código
    # PBB-AGO-26 — só as páginas de obrigado usam o código inteiro
    # ("/obg-pbb-ago-26-v2"). Exigindo o slug completo, TODO lançamento PBB
    # listava só páginas de obrigado e nenhuma LP de verdade (achado 18/09/26,
    # valia pra PBB-FEV/ABR/JUN/AGO-26). Aceitar também o slug sem a primeira
    # letra resolve sem risco de pegar outro lançamento: o mês/ano continua no
    # meio, então "bb-ago-26" não casa com "/projeto-inss-pi-ago-26".
    aceitos = {code_slug}
    if code_slug.startswith("p") and len(code_slug) > 1:
        aceitos.add(code_slug[1:])
    if not any(s in lp for s in aceitos):
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

    # Agrega por landing_page no banco em vez de baixar uma linha por dia por
    # página: etapa e versão são função pura do landing_page, e todo o resto do
    # cálculo aqui embaixo já é soma por página — então soma de somas dá o mesmo
    # número trazendo uma fração das linhas (ver ARQUITETURA.md, 14/09/26 —
    # egress). NULL e '' classificam igual em _etapa_from_landing_page (ambos
    # viram ""), então ficarem em grupos separados aqui não muda o resultado.
    df = pd.read_sql(
        text("""
            SELECT landing_page,
                   SUM(sessions)   AS sessions,
                   SUM(key_events) AS key_events
            FROM ga4_daily
            WHERE lancamento_codigo = :code
            GROUP BY landing_page
        """),
        engine,
        params={"code": code},
    )
    if df.empty:
        return {etapa: [] for etapa in _ETAPAS}

    # Conversão = SESSÃO em que o evento ocorreu, não contagem de evento.
    # `ga4_daily.key_events` conta disparos, e os dois eventos da LP disparam
    # ~1,5-1,8x por sessão — a Pré-Quali do PES-SET-26 mostrava 1.000
    # "conversões" para 636 sessões, e páginas de obrigado passavam de 100%
    # de taxa, o que é impossível (achado 18/09/26).
    #
    # Os dois eventos são etapas diferentes do funil, conforme a configuração
    # feita no GA4: `generate_lead` dispara quando a pessoa preenche o
    # formulário e cai na página de obrigado (é o lead); `qualify_lead`
    # quando ela clica pra entrar no grupo de WhatsApp.
    ev = pd.read_sql(
        text("""
            SELECT landing_page,
                   SUM(sessions) FILTER (WHERE event_name = 'generate_lead') AS leads,
                   SUM(sessions) FILTER (WHERE event_name = 'qualify_lead')  AS whatsapp
            FROM ga4_events_daily
            WHERE lancamento_codigo = :code
            GROUP BY landing_page
        """),
        engine,
        params={"code": code},
    )
    df = df.merge(ev, on="landing_page", how="left")
    df["leads"] = df["leads"].fillna(0)
    df["whatsapp"] = df["whatsapp"].fillna(0)

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
            conversoes=("leads", "sum"),
            whatsapp=("whatsapp", "sum"),
        ).reset_index()
        grouped = grouped[grouped["sessions"] > 0]
        grouped["taxa_conversao"] = grouped["conversoes"] / grouped["sessions"] * 100
        grouped["taxa_whatsapp"] = grouped["whatsapp"] / grouped["sessions"] * 100
        grouped = grouped.sort_values("conversoes", ascending=False).head(top_n)
        result[etapa] = [
            {
                "landing_page": r["landing_page"],
                "sessions": int(r["sessions"]),
                "conversoes": int(r["conversoes"]),
                "taxa_conversao": float(r["taxa_conversao"]),
                "whatsapp": int(r["whatsapp"]),
                "taxa_whatsapp": float(r["taxa_whatsapp"]),
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

    # Mesma agregação no banco de read_landing_pages_por_etapa: o funil abaixo
    # só soma sessões por versão de página, e versão/etapa saem do landing_page.
    df_sessions = pd.read_sql(
        text("SELECT landing_page, SUM(sessions) AS sessions FROM ga4_daily "
             "WHERE lancamento_codigo = :code GROUP BY landing_page"),
        engine, params={"code": code},
    )
    df_events = pd.read_sql(
        text("SELECT landing_page, event_name, SUM(sessions) AS sessions FROM ga4_events_daily "
             "WHERE lancamento_codigo = :code GROUP BY landing_page, event_name"),
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
