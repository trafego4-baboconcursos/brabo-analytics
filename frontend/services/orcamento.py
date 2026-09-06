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


def _norm(s: str) -> str:
    import unicodedata
    return unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().lower()


def _temperatura_de_bucket(nome: str) -> str | None:
    n = _norm(nome)
    if "quente" in n:
        return "Quente"
    if "frio" in n:
        return "Frio"
    if "especific" in n:
        return "Específico"
    return None


def etapa_cfg(cfg: dict | None, nome: str) -> dict:
    """Devolve a entrada de `etapas` (buckets/curva_pct/distribuicao) de uma
    etapa pelo nome, ou {} se não tiver sido cadastrada no wizard."""
    for et in ((cfg or {}).get("etapas") or []):
        if et.get("nome") == nome:
            return et
    return {}


def bucket_realizado(meta: Any, google: Any, bucket: dict, etapa_nome: str) -> float:
    """Gasto real (Meta/Google) do público de um bucket, pela temperatura
    extraída do nome ("FB Quente" → Meta/Quente) e pela plataforma marcada
    no bucket. TikTok não tem fonte de dado ainda (sempre 0 — ver memória
    project_tiktok_integracao_futura)."""
    plataforma = bucket.get("plataforma")
    temp = _temperatura_de_bucket(bucket.get("nome", ""))
    if not temp:
        return 0.0
    if plataforma == "meta":
        attr = "por_temperatura_captacao" if etapa_nome == "Captação" else "por_temperatura_prequali"
        d = (getattr(meta, attr, {}) or {}).get(temp) or {}
        return _f(d.get("custo") or d.get("gasto"))
    if plataforma == "google":
        attr = "por_temperatura" if etapa_nome == "Captação" else "por_temperatura_prequali"
        d = (getattr(google, attr, {}) or {}).get(temp) or {}
        return _f(d.get("custo"))
    return 0.0


def buckets_previsto_x_realizado(meta: Any, google: Any, cfg: dict | None, etapa_nome: str) -> dict:
    """Linhas Previsto x Realizado por público (bucket) de uma etapa, mais o
    total e a divisão por plataforma (Meta/Google/TikTok) — pauta "Verba do
    Lançamento" (Investimento em Captação / Pré-Qualificação por Público)."""
    et = etapa_cfg(cfg, etapa_nome)
    buckets = et.get("buckets") or []
    total_previsto = _f(et.get("total"))
    linhas = []
    for b in buckets:
        previsto = total_previsto * _f(b.get("pct")) / 100 if total_previsto > 0 else 0.0
        realizado = bucket_realizado(meta, google, b, etapa_nome)
        linhas.append({
            "nome": b.get("nome"), "plataforma": b.get("plataforma"),
            "pct_previsto": _f(b.get("pct")), "previsto": previsto, "realizado": realizado,
        })
    total_realizado = sum(l["realizado"] for l in linhas)
    for l in linhas:
        l["pct_realizado"] = (l["realizado"] / total_realizado * 100) if total_realizado > 0 else 0.0
    por_plataforma_prev: dict = {}
    por_plataforma_real: dict = {}
    for l in linhas:
        p = l["plataforma"] or "outro"
        por_plataforma_prev[p] = por_plataforma_prev.get(p, 0.0) + l["previsto"]
        por_plataforma_real[p] = por_plataforma_real.get(p, 0.0) + l["realizado"]
    return {
        "linhas": linhas, "total_previsto": total_previsto, "total_realizado": total_realizado,
        "por_plataforma_previsto": por_plataforma_prev, "por_plataforma_realizado": por_plataforma_real,
    }


def curva_diaria(cfg: dict | None, etapa_nome: str) -> dict:
    """Curva prevista x realizada de investimento por dia de uma etapa —
    `distribuicao: personalizada` usa `curva_pct`; `uniforme` distribui o
    total igualmente entre os dias da janela (start_date/end_date)."""
    from datetime import date, timedelta

    et = etapa_cfg(cfg, etapa_nome)
    start = et.get("start_date")
    end = et.get("end_date")
    total = _f(et.get("total"))
    if not (start and end):
        return {"dias": [], "total": total}
    try:
        d0 = date.fromisoformat(str(start))
        d1 = date.fromisoformat(str(end))
    except Exception:
        return {"dias": [], "total": total}
    n_dias = (d1 - d0).days + 1
    if n_dias <= 0:
        return {"dias": [], "total": total}

    if et.get("distribuicao") == "personalizada" and et.get("curva_pct"):
        pcts = et["curva_pct"]
    else:
        pcts = [100.0 / n_dias] * n_dias

    dias = []
    for i in range(n_dias):
        d = d0 + timedelta(days=i)
        pct = pcts[i] if i < len(pcts) else 0.0
        dias.append({
            "data": d.isoformat(), "data_str": d.strftime("%d/%m"),
            "pct": pct, "previsto": total * pct / 100,
        })
    return {"dias": dias, "total": total}


def com_realizado_diario(curva: dict, daily_rows: list) -> dict:
    """Anexa o gasto real por dia (de read_daily_breakdown, campo "date" no
    formato DD/MM) em cada dia da curva prevista, casando por dia/mês (a
    janela de uma etapa não atravessa virada de ano)."""
    por_dia_mes = {r.get("date"): _f(r.get("total_gasto")) for r in (daily_rows or [])}
    total_realizado = 0.0
    for d in curva.get("dias") or []:
        realizado = por_dia_mes.get(d["data_str"], 0.0)
        d["realizado"] = realizado
        total_realizado += realizado
    curva["total_realizado"] = total_realizado
    return curva
