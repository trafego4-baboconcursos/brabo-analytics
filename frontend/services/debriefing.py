"""
frontend/services/debriefing.py — Builders de contexto para debriefing.html.
"""
from __future__ import annotations

from typing import Any

from frontend.services.attribution import _merge_google_tipo_sales
from frontend.services.fetch import _launch_cfg

_CLIMA_ORDER = ["Quente", "Frio", "Específico"]


def _build_clima_breakdown(obj: Any, attr: str, leads_key: str = "leads") -> list:
    d = getattr(obj, attr, {}) or {} if obj else {}
    rows = []
    for c in _CLIMA_ORDER:
        v = d.get(c) or {}
        gasto = float(v.get("gasto") or v.get("custo") or 0)
        leads = v.get(leads_key)
        if leads is None:
            leads = v.get("conversoes") or 0
        rows.append({"clima": c, "gasto": gasto, "leads": float(leads or 0)})
    total = sum(r["gasto"] for r in rows) or 1
    for r in rows:
        r["pct"] = r["gasto"] / total * 100 if r["gasto"] > 0 else 0.0
    return rows


def _attach_clima_sales(rows: list, sales_dict: dict | None) -> list:
    sales_dict = sales_dict or {}
    for r in rows:
        s = sales_dict.get(r["clima"]) or {}
        r["vendas"] = int(s.get("vendas") or 0)
        r["faturamento"] = float(s.get("faturamento") or 0)
    return rows


def _attach_clima_variation(curr_rows: list, prev_rows: list) -> list:
    prev_map = {r["clima"]: r for r in prev_rows}
    for r in curr_rows:
        p = prev_map.get(r["clima"]) or {}
        prev_gasto = float(p.get("gasto") or 0)
        r["prev_gasto"] = prev_gasto
        r["var_pct"] = ((r["gasto"] - prev_gasto) / prev_gasto * 100) if prev_gasto > 0 else None
    return curr_rows


def _clima_raw(obj: Any, attr: str, clima: str, leads_key: str = "leads") -> tuple:
    d = (getattr(obj, attr, {}) or {}) if obj else {}
    v = d.get(clima) or {}
    gasto = float(v.get("gasto") or v.get("custo") or 0)
    leads = v.get(leads_key)
    if leads is None:
        leads = v.get("conversoes") or 0
    return gasto, float(leads or 0)


def _sales_raw(sales_dict: dict | None, clima: str) -> tuple:
    s = (sales_dict or {}).get(clima) or {}
    return int(s.get("vendas") or 0), float(s.get("faturamento") or 0)


def _build_leads_detail_table(
    meta: Any, google: Any,
    prev_meta: Any, prev_google: Any,
    sales_attr: Any, prev_sales_attr: Any,
) -> list:
    specs = [
        ("FB Quente",     meta,   "por_temperatura_captacao", "Quente",     "leads",      (sales_attr or {}).get("meta_por_temperatura")),
        ("FB Frio",       meta,   "por_temperatura_captacao", "Frio",       "leads",      (sales_attr or {}).get("meta_por_temperatura")),
        ("FB Específico", meta,   "por_temperatura_captacao", "Específico", "leads",      (sales_attr or {}).get("meta_por_temperatura")),
        ("YT Quente",     google, "por_temperatura",          "Quente",     "conversoes", (sales_attr or {}).get("google_por_temperatura")),
        ("YT Frio",       google, "por_temperatura",          "Frio",       "conversoes", (sales_attr or {}).get("google_por_temperatura")),
        ("YT Específico", google, "por_temperatura",          "Específico", "conversoes", (sales_attr or {}).get("google_por_temperatura")),
    ]
    prev_specs = [
        ("FB Quente",     prev_meta,   "por_temperatura_captacao", "Quente",     "leads",      (prev_sales_attr or {}).get("meta_por_temperatura")),
        ("FB Frio",       prev_meta,   "por_temperatura_captacao", "Frio",       "leads",      (prev_sales_attr or {}).get("meta_por_temperatura")),
        ("FB Específico", prev_meta,   "por_temperatura_captacao", "Específico", "leads",      (prev_sales_attr or {}).get("meta_por_temperatura")),
        ("YT Quente",     prev_google, "por_temperatura",          "Quente",     "conversoes", (prev_sales_attr or {}).get("google_por_temperatura")),
        ("YT Frio",       prev_google, "por_temperatura",          "Frio",       "conversoes", (prev_sales_attr or {}).get("google_por_temperatura")),
        ("YT Específico", prev_google, "por_temperatura",          "Específico", "conversoes", (prev_sales_attr or {}).get("google_por_temperatura")),
    ]

    def _calc(specs_list):
        raws = []
        for label, obj, attr, clima, leads_key, sales_dict in specs_list:
            gasto, leads = _clima_raw(obj, attr, clima, leads_key)
            vendas, faturamento = _sales_raw(sales_dict, clima)
            raws.append({"label": label, "gasto": gasto, "leads": leads, "vendas": vendas, "faturamento": faturamento})
        total = sum(r["gasto"] for r in raws) or 1
        for r in raws:
            r["cpl"] = r["gasto"] / r["leads"] if r["leads"] > 0 else 0.0
            r["conversao"] = (r["vendas"] / r["leads"] * 100) if r["leads"] > 0 else 0.0
            r["custo_venda"] = r["gasto"] / r["vendas"] if r["vendas"] > 0 else 0.0
            r["roas"] = r["faturamento"] / r["gasto"] if r["gasto"] > 0 else 0.0
            r["pct"] = r["gasto"] / total * 100 if total > 0 else 0.0
        return raws

    curr_rows = _calc(specs)
    prev_rows = _calc(prev_specs)
    prev_map = {r["label"]: r for r in prev_rows}

    def _pct_change(curr, prev):
        return ((curr - prev) / prev * 100) if prev else None

    for r in curr_rows:
        p = prev_map.get(r["label"]) or {}
        has_prev = bool(p.get("gasto") or p.get("leads"))
        r["has_prev"] = has_prev
        if has_prev:
            r["leads_var"]       = _pct_change(r["leads"], p["leads"])
            r["gasto_var"]       = _pct_change(r["gasto"], p["gasto"])
            r["cpl_var"]         = _pct_change(r["cpl"], p["cpl"])
            r["conversao_var"]   = r["conversao"] - p["conversao"]
            r["vendas_var"]      = _pct_change(r["vendas"], p["vendas"])
            r["custo_venda_var"] = _pct_change(r["custo_venda"], p["custo_venda"])
            r["roas_var"]        = _pct_change(r["roas"], p["roas"])
        else:
            r["leads_var"] = r["gasto_var"] = r["cpl_var"] = r["conversao_var"] = None
            r["vendas_var"] = r["custo_venda_var"] = r["roas_var"] = None

    return curr_rows


def _build_rmkt_adsets(meta: Any) -> list:
    _order = ["Lembrete", "Depoimento", "Aulas no Ar", "Replay", "Matrículas Abertas"]
    por_etapa = getattr(meta, "por_etapa", {}) or {}
    rows = []
    for e in _order:
        d = por_etapa.get(e) or {}
        gasto = float(d.get("gasto") or d.get("custo") or 0)
        rows.append({"adset": e, "gasto": gasto, "leads": int(d.get("leads") or 0), "pct": 0.0})
    total = sum(r["gasto"] for r in rows) or 1
    for r in rows:
        r["pct"] = r["gasto"] / total * 100 if r["gasto"] > 0 else 0.0
    return rows


def _compute_debriefing_ctx(
    launch: Any,
    previous: Any,
    meta: Any,
    google: Any,
    vendas: Any,
    sales_attr: Any,
    daily: Any,
    hotmart: Any,
    creative_data: Any,
    prev_meta: Any,
    prev_google: Any,
    prev_vendas: Any,
    youtube_aulas: Any = None,
    prev_sales_attr: Any = None,
    tmb: Any = None,
) -> dict:
    def _f(x): return float(x or 0)
    def _i(x): return int(x or 0)

    invest = _f(getattr(meta, "total_gasto", 0)) + _f(getattr(google, "total_custo", 0))
    receita = _f(getattr(vendas, "total_receita", 0))
    receita_bruta = _f(getattr(vendas, "total_receita_bruta", 0)) or receita
    roas = receita / invest if invest > 0 else 0.0
    roas_bruto = receita_bruta / invest if invest > 0 else 0.0
    total_vendas = _i(getattr(vendas, "total_vendas", 0))
    ticket = _f(getattr(vendas, "total_ticket_medio", 0))
    meta_leads  = _i(getattr(meta,   "total_leads",    0))
    meta_spend  = _f(getattr(meta,   "total_gasto",    0))
    meta_cpl    = meta_spend  / meta_leads  if meta_leads  > 0 else 0.0

    google_leads = int(_f(getattr(google, "total_conversoes", 0)))
    google_spend = _f(getattr(google, "total_custo", 0))
    google_cpl   = google_spend / google_leads if google_leads > 0 else 0.0

    # TikTok — sem integração ainda
    tiktok_leads = 0
    tiktok_spend = 0.0
    tiktok_cpl   = 0.0

    total_leads = meta_leads + google_leads + tiktok_leads
    total_spend_all = meta_spend + google_spend + tiktok_spend
    cpl = total_spend_all / total_leads if total_leads > 0 else 0.0

    prev_invest = _f(getattr(prev_meta, "total_gasto", 0)) + _f(getattr(prev_google, "total_custo", 0))
    prev_receita = _f(getattr(prev_vendas, "total_receita", 0))
    prev_receita_bruta = _f(getattr(prev_vendas, "total_receita_bruta", 0)) or prev_receita
    prev_roas = prev_receita / prev_invest if prev_invest > 0 else 0.0
    prev_roas_bruto = prev_receita_bruta / prev_invest if prev_invest > 0 else 0.0
    prev_total_vendas = _i(getattr(prev_vendas, "total_vendas", 0))
    prev_ticket = _f(getattr(prev_vendas, "total_ticket_medio", 0))
    prev_meta_leads   = _i(getattr(prev_meta,   "total_leads",      0))
    prev_meta_spend   = _f(getattr(prev_meta,   "total_gasto",      0))
    prev_meta_cpl     = prev_meta_spend  / prev_meta_leads  if prev_meta_leads  > 0 else 0.0
    prev_google_leads = int(_f(getattr(prev_google, "total_conversoes", 0)))
    prev_google_spend = _f(getattr(prev_google, "total_custo", 0))
    prev_google_cpl   = prev_google_spend / prev_google_leads if prev_google_leads > 0 else 0.0
    prev_total_leads  = prev_meta_leads + prev_google_leads
    prev_cpl = prev_invest / prev_total_leads if prev_total_leads > 0 else 0.0

    fontes_leads = [
        {"fonte": "Meta",   "icon": "ti-brand-meta",   "color": "#1877F2",
         "spend": meta_spend,   "leads": meta_leads,   "cpl": meta_cpl,
         "prev_leads": prev_meta_leads,   "prev_cpl": prev_meta_cpl,   "has_data": meta_leads > 0},
        {"fonte": "Google", "icon": "ti-brand-google", "color": "#EA4335",
         "spend": google_spend, "leads": google_leads, "cpl": google_cpl,
         "prev_leads": prev_google_leads, "prev_cpl": prev_google_cpl, "has_data": google_leads > 0},
        {"fonte": "TikTok", "icon": "ti-brand-tiktok", "color": "#000000",
         "spend": tiktok_spend, "leads": tiktok_leads, "cpl": tiktok_cpl,
         "prev_leads": 0, "prev_cpl": 0.0, "has_data": False},
    ]

    def get_etapa(m, g, name):
        m_d = (getattr(m, "por_etapa", {}) or {}).get(name, {}) if m else {}
        g_d = (getattr(g, "por_etapa", {}) or {}).get(name, {}) if g else {}
        m_c = _f(m_d.get("custo") or m_d.get("gasto"))
        g_c = _f(g_d.get("custo"))
        m_l = _i(m_d.get("leads"))
        g_l = _i(g_d.get("conversoes"))
        total = m_c + g_c
        return {"nome": name, "invest": total, "meta": m_c, "google": g_c, "leads": m_l + g_l}

    base = invest or 1.0
    etapas = []
    for name in ["Pré-Qualificação", "Captação", "Remarketing"]:
        e = get_etapa(meta, google, name)
        e["pct"] = e["invest"] / base * 100
        etapas.append(e)

    prev_etapas: list = []
    if prev_meta or prev_google:
        prev_base = prev_invest or 1.0
        for name in ["Pré-Qualificação", "Captação", "Remarketing"]:
            e = get_etapa(prev_meta, prev_google, name)
            e["pct"] = e["invest"] / prev_base * 100
            prev_etapas.append(e)

    top_geral  = ((creative_data or {}).get("rows")        or [])[:5]
    top_meta   = ((creative_data or {}).get("meta_rows")   or [])[:5]
    top_google = ((creative_data or {}).get("google_rows") or [])[:5]

    # Mescla timelines Hotmart + TMB por data
    _hm_tl = getattr(hotmart, "timeline", []) or []
    _tmb_tl = getattr(tmb, "timeline", []) or []
    _merged: dict = {}
    for t in _hm_tl:
        d = t.get("data", "")
        _merged[d] = {"data": d, "data_str": t.get("data_str", d), "vendas": _i(t.get("vendas")), "faturamento": float(t.get("faturamento") or 0)}
    for t in _tmb_tl:
        d = t.get("data", "")
        if d in _merged:
            _merged[d]["vendas"] += _i(t.get("vendas"))
            _merged[d]["faturamento"] += float(t.get("faturamento") or 0)
        else:
            _merged[d] = {"data": d, "data_str": t.get("data_str", d), "vendas": _i(t.get("vendas")), "faturamento": float(t.get("faturamento") or 0)}
    timeline_raw = sorted(_merged.values(), key=lambda x: x["data"])
    if launch:
        cfg = _launch_cfg(launch.code)
        c_start = cfg.get("carrinho_start_date") or ""
        c_end   = cfg.get("carrinho_end_date")   or ""

        def _fmt_periodo(s, e):
            try:
                from datetime import date
                ds = date.fromisoformat(str(s))
                de = date.fromisoformat(str(e))
                if ds.year == de.year:
                    return f"{ds.strftime('%d/%m')} a {de.strftime('%d/%m/%Y')}"
                return f"{ds.strftime('%d/%m/%Y')} a {de.strftime('%d/%m/%Y')}"
            except Exception:
                return f"{s} a {e}"

        periodo_atual = _fmt_periodo(c_start, c_end) if c_start and c_end else ""
        if previous:
            prev_cfg = _launch_cfg(previous.code)
            ps = prev_cfg.get("carrinho_start_date") or ""
            pe = prev_cfg.get("carrinho_end_date") or ""
            periodo_prev = _fmt_periodo(ps, pe) if ps and pe else ""
        else:
            periodo_prev = ""
        if c_start and c_end:
            timeline = [t for t in timeline_raw if c_start <= t.get("data", "") <= c_end]
        else:
            timeline = timeline_raw
    else:
        timeline = timeline_raw
        periodo_atual = ""
        periodo_prev  = ""

    max_vendas_dia = max((_i(t.get("vendas")) for t in timeline), default=1) or 1

    pagamentos_hm = getattr(hotmart, "pagamentos", []) or []
    total_tmb  = _i(getattr(vendas, "tmb_vendas",    0))
    total_hm_v = _i(getattr(vendas, "hotmart_vendas", 0))

    def _find_pay(metodo_keywords):
        for p in pagamentos_hm:
            m = (p.get("metodo") or "").lower()
            if any(k in m for k in metodo_keywords):
                return p
        return None

    boleto_hm = _find_pay(["boleto"])
    cartao_hm = _find_pay(["crédito", "credito", "cartão", "cartao", "credit"])
    pix_hm    = _find_pay(["pix"])

    max_peak_yt = max((getattr(a, "peak_concurrent", 0) or 0 for a in (youtube_aulas or [])), default=0)

    meta_segmentos = sorted(
        [{"segmento": k, **v} for k, v in (getattr(meta, "por_segmento", {}) or {}).items()],
        key=lambda x: _f(x.get("gasto")), reverse=True,
    )[:12] if meta else []

    google_segmentos = sorted(
        [{"segmento": k, **v} for k, v in (getattr(google, "por_segmento", {}) or {}).items()],
        key=lambda x: _f(x.get("gasto")), reverse=True,
    )[:12] if google else []

    meta_clima = _build_clima_breakdown(meta, "por_temperatura_captacao")
    prev_meta_clima = _build_clima_breakdown(prev_meta, "por_temperatura_captacao")
    _attach_clima_variation(meta_clima, prev_meta_clima)
    _attach_clima_sales(meta_clima, (sales_attr or {}).get("meta_por_temperatura"))

    google_clima = _build_clima_breakdown(google, "por_temperatura", leads_key="conversoes")
    prev_google_clima = _build_clima_breakdown(prev_google, "por_temperatura", leads_key="conversoes")
    _attach_clima_variation(google_clima, prev_google_clima)
    _attach_clima_sales(google_clima, (sales_attr or {}).get("google_por_temperatura"))

    leads_detail_table = _build_leads_detail_table(
        meta, google, prev_meta, prev_google, sales_attr, prev_sales_attr,
    )

    meta_temp_sales        = (sales_attr or {}).get("meta_por_temperatura",   {}) or {}
    prev_meta_temp_sales   = (prev_sales_attr or {}).get("meta_por_temperatura", {}) or {}
    google_temp_sales      = (sales_attr or {}).get("google_por_temperatura", {}) or {}
    prev_google_temp_sales = (prev_sales_attr or {}).get("google_por_temperatura", {}) or {}
    google_tipo_sales      = _merge_google_tipo_sales((sales_attr or {}).get("google_por_tipo_campanha"))
    prev_google_tipo_sales = _merge_google_tipo_sales((prev_sales_attr or {}).get("google_por_tipo_campanha"))
    max_mt = max((_i(v.get("vendas")) for v in meta_temp_sales.values()),   default=1) or 1
    max_gt = max((_i(v.get("vendas")) for v in google_tipo_sales.values()), default=1) or 1

    return {
        "has_data": bool(meta or google or vendas),
        "has_prev": bool(previous and (prev_meta or prev_google or prev_vendas)),
        "prev_code": previous.code if previous else "",
        "periodo_atual": periodo_atual, "periodo_prev": periodo_prev,
        # KPIs
        "invest": invest, "receita": receita, "roas": roas,
        "receita_bruta": receita_bruta, "roas_bruto": roas_bruto,
        "total_vendas": total_vendas, "ticket": ticket,
        "total_leads": total_leads, "cpl": cpl,
        "fontes_leads": fontes_leads,
        # Prev KPIs
        "prev_invest": prev_invest, "prev_receita": prev_receita, "prev_roas": prev_roas,
        "prev_receita_bruta": prev_receita_bruta, "prev_roas_bruto": prev_roas_bruto,
        "prev_total_vendas": prev_total_vendas, "prev_ticket": prev_ticket,
        "prev_total_leads": prev_total_leads, "prev_cpl": prev_cpl,
        # Etapas
        "etapas": etapas, "prev_etapas": prev_etapas,
        # Top ads
        "top_geral": top_geral, "top_meta": top_meta, "top_google": top_google,
        # Daily breakdown
        "daily": daily or [],
        # Timeline vendas (Hotmart)
        "timeline": timeline, "max_vendas_dia": max_vendas_dia,
        # Pagamentos
        "pagamentos_hm": pagamentos_hm, "total_tmb": total_tmb,
        "total_hm": total_hm_v, "total_vendas_pay": total_tmb + total_hm_v,
        "boleto_hm": boleto_hm, "cartao_hm": cartao_hm, "pix_hm": pix_hm,
        # Audiences (captação only)
        "meta_segmentos": meta_segmentos, "google_segmentos": google_segmentos,
        "meta_clima": meta_clima, "google_clima": google_clima,
        "leads_detail_table": leads_detail_table,
        "rmkt_adsets": _build_rmkt_adsets(meta),
        "prev_rmkt_adsets": _build_rmkt_adsets(prev_meta),
        # Sales por temperatura/tipo
        "meta_temp_sales": meta_temp_sales, "google_tipo_sales": google_tipo_sales,
        "prev_meta_temp_sales": prev_meta_temp_sales, "prev_google_tipo_sales": prev_google_tipo_sales,
        "google_temp_sales": google_temp_sales, "prev_google_temp_sales": prev_google_temp_sales,
        "clima_order": _CLIMA_ORDER,
        "max_mt": max_mt, "max_gt": max_gt,
        "youtube_aulas": youtube_aulas or [],
        "max_peak_yt": max_peak_yt,
    }
