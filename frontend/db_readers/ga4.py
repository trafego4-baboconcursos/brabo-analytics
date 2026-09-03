"""
frontend/db_readers/ga4.py — Leitor de dados do GA4 (banco analytics).
"""
from __future__ import annotations

from typing import Any

import pandas as pd
from sqlalchemy import text

from frontend.db import _get_engine
from frontend.db_readers.ads_google import _categorize_campaign
from frontend.utils import _extract_launch_code

_ETAPAS = ["Pré-Qualificação", "Captação"]


def read_landing_pages_por_etapa(launch_folder_or_code: Any, top_n: int = 8) -> dict[str, list[dict]]:
    """Landing pages que mais converteram em cada etapa (Pré-Qualificação e
    Captação) — classifica cada linha do ga4_daily pelo nome da campanha
    (mesma lógica já usada pra categorizar Meta/Google, reaproveitada aqui
    porque o utm_campaign do GA4 carrega o nome real da campanha de origem,
    com as mesmas tags [Pré-Qualificação]/[Captação]), agrupa por
    landing_page e ordena por conversões (key_events)."""
    code = _extract_launch_code(launch_folder_or_code)
    engine = _get_engine()

    df = pd.read_sql(
        text("""
            SELECT campaign, landing_page, sessions, key_events
            FROM ga4_daily
            WHERE lancamento_codigo = :code
        """),
        engine,
        params={"code": code},
    )
    if df.empty:
        return {etapa: [] for etapa in _ETAPAS}

    df["etapa"] = df["campaign"].map(lambda c: _categorize_campaign(c)[0])
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
