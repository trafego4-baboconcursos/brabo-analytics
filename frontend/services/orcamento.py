"""
frontend/services/orcamento.py — Verba prevista x realizada por etapa.

Extraído de debriefing.py pra ser reaproveitado também na página
"Verba do Lançamento" (/verba), sem duplicar a lógica.
"""
from __future__ import annotations

from typing import Any

REMARKETING_SUBETAPAS = ["Lembrete", "Depoimento", "Aulas no Ar", "Replay", "Matrículas Abertas"]


def _f(x: Any) -> float:
    return float(x or 0)


def _i(x: Any) -> int:
    return int(x or 0)


def get_etapa(meta: Any, google: Any, name: str, whatsapp: float = 0.0) -> dict:
    """Investimento/leads realizados de uma etapa, combinando Meta + Google.
    "Remarketing" não existe como chave própria em por_etapa — Meta/Google
    classificam essas campanhas nas sub-etapas (Lembrete, Depoimento, etc.),
    então soma todas elas pra compor o total de Remarketing. O WhatsApp
    também é 100% remarketing (só dispara pra quem já é lead), então entra
    no mesmo bucket."""
    names = REMARKETING_SUBETAPAS if name == "Remarketing" else [name]
    m_por = (getattr(meta, "por_etapa", {}) or {}) if meta else {}
    g_por = (getattr(google, "por_etapa", {}) or {}) if google else {}
    m_c = m_l = g_c = g_l = 0
    for n in names:
        m_d = m_por.get(n) or {}
        g_d = g_por.get(n) or {}
        m_c += _f(m_d.get("custo") or m_d.get("gasto"))
        g_c += _f(g_d.get("custo"))
        m_l += _i(m_d.get("leads"))
        g_l += _i(g_d.get("conversoes"))
    total = m_c + g_c + whatsapp
    return {"nome": name, "invest": total, "meta": m_c, "google": g_c, "tiktok": 0.0, "whatsapp": whatsapp, "leads": m_l + g_l}


def previsto_por_etapa(cfg: dict | None) -> dict:
    """Verba planejada por etapa (cadastrada no wizard) — Pré-Qualificação e
    Captação têm campo próprio; Remarketing soma o 'total' de cada
    sub-etapa (Lembrete/Depoimento/Aulas no Ar/Replay/Matrículas Abertas)
    provisionada na aba Evento."""
    cfg = cfg or {}
    remarketing_previsto = sum(
        _f(et.get("total")) for et in (cfg.get("etapas") or [])
        if et.get("nome") in REMARKETING_SUBETAPAS
    )
    return {
        "Pré-Qualificação": _f(cfg.get("meta_investimento_pre_quali")),
        "Captação": _f(cfg.get("meta_investimento_captacao")),
        "Remarketing": remarketing_previsto,
    }


def previsto_por_subetapa(cfg: dict | None) -> dict:
    """Verba planejada de cada sub-etapa de remarketing individualmente
    (Lembrete/Depoimento/Aulas no Ar/Replay/Matrículas Abertas)."""
    cfg = cfg or {}
    return {
        et.get("nome"): _f(et.get("total"))
        for et in (cfg.get("etapas") or [])
        if et.get("nome") in REMARKETING_SUBETAPAS
    }
