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
    """Devolve a entrada de `etapas` (buckets/curva_pct/distribuicao/
    start_date/end_date/total) de uma etapa pelo nome. Pré-Qualificação e
    Captação têm data e orçamento definidos nos passos 1/2 do wizard
    (pre_quali_start_date/meta_investimento_pre_quali etc) — campos
    próprios, independentes de a etapa ter sido aberta na aba "Verba" (que
    só existe pra guardar buckets/curva_pct). Por isso essas duas SEMPRE
    caem de volta nesses campos quando a entrada em `etapas` não tiver
    data/total preenchido, pra funcionar em qualquer lançamento — não só
    nos que tiveram a aba Verba configurada manualmente."""
    cfg = cfg or {}
    et = {}
    for e in (cfg.get("etapas") or []):
        if e.get("nome") == nome:
            et = dict(e)
            break

    fallback_map = {
        "Captação": ("captacao_start_date", "captacao_end_date", "meta_investimento_captacao"),
        "Pré-Qualificação": ("pre_quali_start_date", "pre_quali_end_date", "meta_investimento_pre_quali"),
    }
    if nome in fallback_map:
        k_start, k_end, k_total = fallback_map[nome]
        if not et.get("start_date"):
            et["start_date"] = cfg.get(k_start)
        if not et.get("end_date"):
            et["end_date"] = cfg.get(k_end)
        if not et.get("total"):
            et["total"] = cfg.get(k_total)
    return et


def bucket_realizado(meta: Any, google: Any, bucket: dict, etapa_nome: str) -> float:
    """Gasto real (Meta/Google) de um bucket. Em Captação/Pré-Qualificação o
    bucket tem temperatura no nome ("FB Quente" → Meta/Quente); nas
    sub-etapas de remarketing (Lembrete, etc.) o bucket é só a plataforma
    ("Facebook ADS"/"Google ADS", sem temperatura) — usa o total já
    calculado por get_etapa pra essa etapa. TikTok não tem fonte de dado
    ainda (sempre 0 — ver memória project_tiktok_integracao_futura)."""
    plataforma = bucket.get("plataforma")
    temp = _temperatura_de_bucket(bucket.get("nome", ""))
    if temp:
        if plataforma == "meta":
            attr = "por_temperatura_captacao" if etapa_nome == "Captação" else "por_temperatura_prequali"
            d = (getattr(meta, attr, {}) or {}).get(temp) or {}
            return _f(d.get("custo") or d.get("gasto"))
        if plataforma == "google":
            attr = "por_temperatura" if etapa_nome == "Captação" else "por_temperatura_prequali"
            d = (getattr(google, attr, {}) or {}).get(temp) or {}
            return _f(d.get("custo"))
        return 0.0
    # Sem temperatura no nome — bucket de plataforma pura (sub-etapa de
    # remarketing): usa o gasto já somado por get_etapa.
    e = get_etapa(meta, google, etapa_nome)
    if plataforma == "meta":
        return e["meta"]
    if plataforma == "google":
        return e["google"]
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


def previsto_publico_por_dia(cfg: dict | None, etapa_nome: str) -> dict:
    """Previsão da divisão de verba por público em cada dia — % do bucket ×
    % do dia (curva) × total da etapa. Só faz sentido pra etapas com
    buckets de temperatura (Captação); não tenta reconstruir uma curva
    própria por público, assume a mesma curva diária do total da etapa."""
    et = etapa_cfg(cfg, etapa_nome)
    buckets = et.get("buckets") or []
    curva = curva_diaria(cfg, etapa_nome)
    dias_out = []
    for d in curva.get("dias") or []:
        publicos = {b.get("nome"): d["previsto"] * _f(b.get("pct")) / 100 for b in buckets}
        dias_out.append({"data": d["data"], "data_str": d["data_str"], "publicos": publicos})
    totais = {b.get("nome"): curva.get("total", 0.0) * _f(b.get("pct")) / 100 for b in buckets}
    return {"dias": dias_out, "buckets": [b.get("nome") for b in buckets], "totais": totais}


def publico_por_dia(code: str, cfg: dict | None, etapa_nome: str) -> dict:
    """Gasto real por dia x público (bucket) — consulta direto
    meta_ads_daily/google_ads_daily (não os summaries cacheados) e
    classifica cada campanha com a mesma lógica de categorização usada no
    resto do sistema, pra bater com os buckets configurados no wizard."""
    import pandas as pd
    from datetime import date as _date, timedelta
    from sqlalchemy import text
    from frontend.db import _get_engine
    from frontend.db_readers.ads_meta import _categorize_campaign as _cat_meta
    from frontend.db_readers.ads_google import _categorize_campaign as _cat_google

    et = etapa_cfg(cfg, etapa_nome)
    start, end = et.get("start_date"), et.get("end_date")
    buckets = et.get("buckets") or []
    if not (start and end) or not buckets:
        return {"dias": [], "buckets": [], "totais": {}}

    engine = _get_engine()
    gasto_por_chave: dict = {}  # {(data_str, plataforma, temperatura): gasto}

    meta_df = pd.read_sql(
        text("SELECT date, campaign_name, spend FROM meta_ads_daily WHERE lancamento_codigo = :code AND date BETWEEN :start AND :end"),
        engine, params={"code": code, "start": start, "end": end},
    )
    if not meta_df.empty:
        cats = meta_df["campaign_name"].map(_cat_meta)
        meta_df = meta_df.assign(etapa=[c[0] for c in cats], temperatura=[c[1] for c in cats])
        meta_df = meta_df[meta_df["etapa"] == etapa_nome]
        for _, r in meta_df.groupby(["date", "temperatura"])["spend"].sum().reset_index().iterrows():
            key = (r["date"].strftime("%d/%m"), "meta", r["temperatura"])
            gasto_por_chave[key] = gasto_por_chave.get(key, 0.0) + float(r["spend"])

    google_df = pd.read_sql(
        text("SELECT date, campaign_name, cost FROM google_ads_daily WHERE lancamento_codigo = :code AND date BETWEEN :start AND :end"),
        engine, params={"code": code, "start": start, "end": end},
    )
    if not google_df.empty:
        cats = google_df["campaign_name"].map(_cat_google)
        google_df = google_df.assign(etapa=[c[0] for c in cats], temperatura=[c[1] for c in cats])
        google_df = google_df[google_df["etapa"] == etapa_nome]
        for _, r in google_df.groupby(["date", "temperatura"])["cost"].sum().reset_index().iterrows():
            key = (r["date"].strftime("%d/%m"), "google", r["temperatura"])
            gasto_por_chave[key] = gasto_por_chave.get(key, 0.0) + float(r["cost"])

    try:
        d0 = _date.fromisoformat(str(start))
        d1 = _date.fromisoformat(str(end))
    except Exception:
        return {"dias": [], "buckets": [], "totais": {}}
    n_dias = (d1 - d0).days + 1

    dias = []
    totais: dict = {b.get("nome"): 0.0 for b in buckets}
    for i in range(n_dias):
        d = d0 + timedelta(days=i)
        data_str = d.strftime("%d/%m")
        publicos = {}
        for b in buckets:
            temp = _temperatura_de_bucket(b.get("nome", ""))
            gasto = gasto_por_chave.get((data_str, b.get("plataforma"), temp), 0.0)
            publicos[b.get("nome")] = gasto
            totais[b.get("nome")] += gasto
        dias.append({"data": d.isoformat(), "data_str": data_str, "publicos": publicos})
    return {"dias": dias, "buckets": [b.get("nome") for b in buckets], "totais": totais}


def com_percentuais(dados: dict) -> dict:
    """Adiciona a % de cada público sobre o total geral (coluna "%" da
    planilha) e a % de cada dia sobre o total geral (linha "Investimento
    por Dia") a um resultado de publico_por_dia()/previsto_publico_por_dia()."""
    totais = dados.get("totais") or {}
    grand_total = sum(totais.values())
    dados["pct_publico"] = {
        nome: (v / grand_total * 100) if grand_total > 0 else 0.0
        for nome, v in totais.items()
    }
    for d in dados.get("dias") or []:
        dia_total = sum((d.get("publicos") or {}).values())
        d["total"] = dia_total
        d["pct_dia"] = (dia_total / grand_total * 100) if grand_total > 0 else 0.0
    dados["grand_total"] = grand_total
    return dados


def combinar_previsto_realizado(previsto: dict, realizado: dict) -> dict:
    """Junta previsto_publico_por_dia()/publico_por_dia() (já com
    com_percentuais aplicado) numa estrutura única, pra renderizar uma só
    tabela "Verba Diária — Previsto × Realizado" em vez de duas tabelas
    separadas."""
    buckets = previsto.get("buckets") or realizado.get("buckets") or []
    dias_prev = {d["data_str"]: d for d in (previsto.get("dias") or [])}
    dias_real = {d["data_str"]: d for d in (realizado.get("dias") or [])}
    labels = list(dias_prev.keys()) or list(dias_real.keys())

    dias: list[dict] = []
    for label in labels:
        dp = dias_prev.get(label) or {}
        dr = dias_real.get(label) or {}
        publicos = {}
        for pub in buckets:
            publicos[pub] = {
                "previsto": (dp.get("publicos") or {}).get(pub, 0.0),
                "realizado": (dr.get("publicos") or {}).get(pub, 0.0),
            }
        dias.append({
            "data_str": label,
            "publicos": publicos,
            "pct_dia_previsto": dp.get("pct_dia", 0.0),
            "pct_dia_realizado": dr.get("pct_dia", 0.0),
        })

    return {
        "buckets": buckets,
        "dias": dias,
        "totais_previsto": previsto.get("totais") or {},
        "totais_realizado": realizado.get("totais") or {},
        "pct_publico_previsto": previsto.get("pct_publico") or {},
        "pct_publico_realizado": realizado.get("pct_publico") or {},
        "grand_total_previsto": previsto.get("grand_total", 0.0),
        "grand_total_realizado": realizado.get("grand_total", 0.0),
    }


def investimento_diario_etapa(code: str, etapa_nome: str, start: str | None, end: str | None) -> list[dict]:
    """Gasto real por dia (Meta+Google) de uma etapa qualquer, classificando
    cada campanha com a mesma categorização usada no resto do sistema.
    Diferente de read_daily_breakdown (que filtra por substring do nome da
    campanha, só serve pra Captação/Pré-Qualificação), esta função cobre
    também as sub-etapas de remarketing (Lembrete, Depoimento, etc.), que
    são identificadas pela tag [Etapa] no nome da campanha."""
    import pandas as pd
    from sqlalchemy import text
    from frontend.db import _get_engine
    from frontend.db_readers.ads_meta import _categorize_campaign as _cat_meta
    from frontend.db_readers.ads_google import _categorize_campaign as _cat_google

    if not (start and end):
        return []
    engine = _get_engine()
    out: dict = {}

    meta_df = pd.read_sql(
        text("SELECT date, campaign_name, spend FROM meta_ads_daily WHERE lancamento_codigo = :code AND date BETWEEN :start AND :end"),
        engine, params={"code": code, "start": start, "end": end},
    )
    if not meta_df.empty:
        cats = meta_df["campaign_name"].map(_cat_meta)
        meta_df = meta_df.assign(etapa=[c[0] for c in cats])
        meta_df = meta_df[meta_df["etapa"] == etapa_nome]
        for _, r in meta_df.groupby("date")["spend"].sum().reset_index().iterrows():
            key = r["date"].strftime("%d/%m")
            out[key] = out.get(key, 0.0) + float(r["spend"])

    google_df = pd.read_sql(
        text("SELECT date, campaign_name, cost FROM google_ads_daily WHERE lancamento_codigo = :code AND date BETWEEN :start AND :end"),
        engine, params={"code": code, "start": start, "end": end},
    )
    if not google_df.empty:
        cats = google_df["campaign_name"].map(_cat_google)
        google_df = google_df.assign(etapa=[c[0] for c in cats])
        google_df = google_df[google_df["etapa"] == etapa_nome]
        for _, r in google_df.groupby("date")["cost"].sum().reset_index().iterrows():
            key = r["date"].strftime("%d/%m")
            out[key] = out.get(key, 0.0) + float(r["cost"])

    return [{"date": k, "total_gasto": v} for k, v in out.items()]


def kpis_captacao_periodo_comparavel(launch, previous, cfg: dict | None, prev_cfg: dict | None) -> dict | None:
    """KPIs de Captação do lançamento anterior, na MESMA janela relativa
    (mesma quantidade de dias corridos desde o início da Captação) que o
    lançamento atual já percorreu até hoje — não a mesma data de
    calendário, nem a janela inteira do lançamento anterior. Pauta
    debriefing 08/09/26 — "1. KPIs Principais" precisa do comparativo."""
    from datetime import date, timedelta
    from frontend.database_reader import read_meta, read_google, read_vendas

    if not (launch and previous and cfg and prev_cfg):
        return None
    c_start = cfg.get("captacao_start_date")
    c_end = cfg.get("captacao_end_date")
    p_start = prev_cfg.get("captacao_start_date")
    p_end = prev_cfg.get("captacao_end_date")
    if not (c_start and c_end and p_start and p_end):
        return None
    try:
        cs = date.fromisoformat(str(c_start))
        ce = date.fromisoformat(str(c_end))
        p_cs = date.fromisoformat(str(p_start))
        p_ce = date.fromisoformat(str(p_end))
    except Exception:
        return None

    hoje = date.today()
    elapsed = (min(hoje, ce) - cs).days + 1
    elapsed = max(1, elapsed)
    p_window_end = min(p_cs + timedelta(days=elapsed - 1), p_ce)
    p_start_str = p_cs.isoformat()
    p_end_str = p_window_end.isoformat()

    p_meta = read_meta(previous.code, start_date=p_start_str, end_date=p_end_str)
    p_google = read_google(previous.code, start_date=p_start_str, end_date=p_end_str)
    p_vendas = read_vendas(previous.code, start_date=p_start_str, end_date=p_end_str)

    p_meta_capt = (getattr(p_meta, "por_etapa", {}) or {}).get("Captação") or {}
    p_google_capt = (getattr(p_google, "por_etapa", {}) or {}).get("Captação") or {}
    p_meta_gasto = _f(p_meta_capt.get("gasto") or p_meta_capt.get("custo"))
    p_google_gasto = _f(p_google_capt.get("custo"))
    p_invest = p_meta_gasto + p_google_gasto
    p_leads = _i(p_meta_capt.get("leads")) + int(round(_f(p_google_capt.get("conversoes"))))
    p_receita = _f(getattr(p_vendas, "total_receita", 0)) if p_vendas else 0.0
    p_vendas_n = _i(getattr(p_vendas, "total_vendas", 0)) if p_vendas else 0

    return {
        "invest": p_invest, "receita": p_receita,
        "roas": (p_receita / p_invest) if p_invest > 0 else 0.0,
        "vendas": p_vendas_n, "leads": p_leads,
        "cpl": (p_invest / p_leads) if p_leads > 0 else 0.0,
        "periodo": f"{p_cs.strftime('%d/%m')} a {p_window_end.strftime('%d/%m')}",
        "dias": elapsed,
    }
