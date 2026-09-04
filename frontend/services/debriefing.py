"""
frontend/services/debriefing.py — Builders de contexto para debriefing.html.
"""
from __future__ import annotations

from typing import Any

from frontend.services.attribution import _merge_google_tipo_sales
from frontend.services.fetch import _launch_cfg

_CLIMA_ORDER = ["Quente", "Frio", "Específico"]
_REMARKETING_SUBETAPAS = ["Lembrete", "Depoimento", "Aulas no Ar", "Replay", "Matrículas Abertas"]


def _build_clima_breakdown(obj: Any, attr: str, leads_key: str = "leads") -> list:
    d = getattr(obj, attr, {}) or {} if obj else {}
    rows = []
    for c in _CLIMA_ORDER:
        v = d.get(c) or {}
        gasto = float(v.get("gasto") or v.get("custo") or 0)
        leads = v.get(leads_key)
        if leads is None:
            leads = v.get("conversoes") or 0
        thruplays = int(v.get("thruplays") or 0)
        views_50 = int(v.get("views_50") or 0)
        rows.append({
            "clima": c, "gasto": gasto, "leads": float(leads or 0),
            "thruplays": thruplays, "views_50": views_50,
            "custo_thruplay": (gasto / thruplays) if thruplays > 0 else 0.0,
            "pct_50": (views_50 / thruplays * 100) if thruplays > 0 else 0.0,
        })
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


def _build_rmkt_adsets(meta: Any, whatsapp: float = 0.0, cfg: dict | None = None) -> list:
    _order = ["Lembrete", "Depoimento", "Aulas no Ar", "Replay", "Matrículas Abertas"]
    por_etapa = getattr(meta, "por_etapa", {}) or {}
    previsto_por_subetapa = {
        et.get("nome"): float(et.get("total") or 0)
        for et in ((cfg or {}).get("etapas") or [])
    }
    rows = []
    for e in _order:
        d = por_etapa.get(e) or {}
        gasto = float(d.get("gasto") or d.get("custo") or 0)
        rows.append({
            "adset": e, "gasto": gasto, "leads": int(d.get("leads") or 0), "pct": 0.0,
            "previsto": previsto_por_subetapa.get(e, 0.0),
        })
    if whatsapp > 0:
        rows.append({"adset": "WhatsApp", "gasto": whatsapp, "leads": 0, "pct": 0.0, "previsto": 0.0})
    total = sum(r["gasto"] for r in rows) or 1
    for r in rows:
        r["pct"] = r["gasto"] / total * 100 if r["gasto"] > 0 else 0.0
    return rows


def _build_top_ads_captacao(meta: Any, google: Any, sales_attr: Any = None, n: int = 5) -> dict:
    """Top N anúncios de Captação por quantidade de vendas (atribuição UTM
    por ad_code), em 3 recortes: combinado (Meta + Google somados pelo mesmo
    código ADxxx), só Meta, só Google."""
    por_criativo = (sales_attr or {}).get("por_criativo", {}) or {}
    meta_ads = getattr(meta, "captacao_por_ad", None) or []
    google_ads = getattr(google, "anuncios_por_ad", None) or []

    def _row(code: str, nome: str, gasto: float, leads: int) -> dict:
        venda = por_criativo.get(code, {})
        vendas = int(venda.get("vendas") or 0)
        receita = float(venda.get("faturamento") or 0)
        return {
            "ad_code": code, "nome": nome, "gasto": gasto, "leads": leads,
            "vendas": vendas, "receita": receita,
            "roas": receita / gasto if gasto > 0 else 0.0,
        }

    def _top(ads: list) -> list:
        rows = [
            _row(str(a.get("ad_code") or "").upper(), a.get("nome"), float(a.get("gasto") or 0), int(a.get("leads") or 0))
            for a in ads
        ]
        return sorted(rows, key=lambda x: x["vendas"], reverse=True)[:n]

    combinado_acc: dict[str, dict] = {}
    for a in meta_ads + google_ads:
        code = str(a.get("ad_code") or "").upper()
        if not code:
            continue
        c = combinado_acc.setdefault(code, {"nome": a.get("nome"), "gasto": 0.0, "leads": 0})
        c["gasto"] += float(a.get("gasto") or 0)
        c["leads"] += int(a.get("leads") or 0)
    combinado_rows = sorted(
        (_row(code, c["nome"], c["gasto"], c["leads"]) for code, c in combinado_acc.items()),
        key=lambda x: x["vendas"], reverse=True,
    )[:n]

    return {"combinado": combinado_rows, "meta": _top(meta_ads), "google": _top(google_ads)}


def _enrich_perfil_por_anuncio(
    perfil: dict | None, meta: Any, google: Any, sales_attr: Any = None,
    prev_meta: Any = None, prev_google: Any = None, prev_sales_attr: Any = None,
) -> dict | None:
    """Completa cada linha de perfil_por_anuncio (que só tem ad_code/leads/
    respostas/dist, vindos da pesquisa) com nome, investimento, vendas e ROAS —
    somando Meta + Google quando o mesmo ADxxx roda nas duas plataformas.
    Também marca se o criativo é "antigo" (já rodou no lançamento anterior,
    ou seja, validado) ou "novo" (sem histórico pra comparar) e, quando
    antigo, traz o ROAS do lançamento passado pro mesmo ad_code."""
    if not perfil or not perfil.get("ads"):
        return perfil
    por_criativo = (sales_attr or {}).get("por_criativo", {}) or {}
    prev_por_criativo = (prev_sales_attr or {}).get("por_criativo", {}) or {}
    todos_ads = [
        *(getattr(meta, "preq_por_ad", None) or []),
        *(getattr(meta, "captacao_por_ad", None) or []),
        *(getattr(google, "preq_por_ad", None) or []),
        *(getattr(google, "anuncios_por_ad", None) or []),
    ]
    info: dict[str, dict] = {}
    for a in todos_ads:
        code = str(a.get("ad_code") or "").upper()
        if not code:
            continue
        d = info.setdefault(code, {"nome": a.get("nome"), "gasto": 0.0, "antigo": False})
        d["gasto"] += float(a.get("gasto") or 0)
        if a.get("antigo"):
            d["antigo"] = True

    prev_todos_ads = [
        *(getattr(prev_meta, "preq_por_ad", None) or []),
        *(getattr(prev_meta, "captacao_por_ad", None) or []),
        *(getattr(prev_google, "preq_por_ad", None) or []),
        *(getattr(prev_google, "anuncios_por_ad", None) or []),
    ]
    prev_gasto_por_ad: dict[str, float] = {}
    for a in prev_todos_ads:
        code = str(a.get("ad_code") or "").upper()
        if not code:
            continue
        prev_gasto_por_ad[code] = prev_gasto_por_ad.get(code, 0.0) + float(a.get("gasto") or 0)

    for row in perfil["ads"]:
        code = str(row.get("ad_code") or "").upper()
        d = info.get(code, {})
        row["nome"] = d.get("nome") or code
        row["gasto"] = d.get("gasto") or 0.0
        venda = por_criativo.get(code) or {}
        row["vendas"] = int(venda.get("vendas") or 0)
        row["receita"] = float(venda.get("faturamento") or 0)
        row["roas"] = (row["receita"] / row["gasto"]) if row["gasto"] > 0 else 0.0
        row["antigo"] = bool(d.get("antigo"))
        row["prev_roas"] = None
        if row["antigo"]:
            prev_gasto = prev_gasto_por_ad.get(code) or 0.0
            prev_receita = float((prev_por_criativo.get(code) or {}).get("faturamento") or 0)
            if prev_gasto > 0:
                row["prev_roas"] = prev_receita / prev_gasto
    return perfil


def _build_antigo_novo(meta: Any, google: Any, sales_attr: Any = None) -> dict:
    """Investimento/leads/vendas em anúncios antigos (ADxxx já usado em
    lançamento anterior do mesmo produto) × novos, por etapa. Combina Meta +
    Google; vendas/receita cruzadas por ad_code via atribuição UTM (mesma
    fonte da seção 'Vendas por Público')."""
    por_criativo = (sales_attr or {}).get("por_criativo", {}) or {}
    listas = {
        "Pré-Qualificação": [
            *(getattr(meta, "preq_por_ad", None) or []),
            *(getattr(google, "preq_por_ad", None) or []),
        ],
        "Captação": [
            *(getattr(meta, "captacao_por_ad", None) or []),
            *(getattr(google, "anuncios_por_ad", None) or []),
        ],
    }
    out: dict[str, dict] = {}
    for etapa, ads in listas.items():
        if not ads:
            continue
        grupos = {
            "antigo": {"gasto": 0.0, "leads": 0, "n": 0, "vendas": 0, "receita": 0.0},
            "novo": {"gasto": 0.0, "leads": 0, "n": 0, "vendas": 0, "receita": 0.0},
        }
        for a in ads:
            key = "antigo" if a.get("antigo") else "novo"
            grupos[key]["gasto"] += float(a.get("gasto") or 0)
            grupos[key]["leads"] += int(a.get("leads") or 0)
            grupos[key]["n"] += 1
            venda = por_criativo.get(str(a.get("ad_code") or "").upper(), {})
            grupos[key]["vendas"] += int(venda.get("vendas") or 0)
            grupos[key]["receita"] += float(venda.get("faturamento") or 0)
        total_gasto = grupos["antigo"]["gasto"] + grupos["novo"]["gasto"] or 1
        for g in grupos.values():
            g["cpl"] = g["gasto"] / g["leads"] if g["leads"] > 0 else 0.0
            g["pct"] = g["gasto"] / total_gasto * 100
            g["roas"] = g["receita"] / g["gasto"] if g["gasto"] > 0 else 0.0
        out[etapa] = grupos
    return out


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
    leads_antigos: Any = None,
    perfil_por_anuncio: Any = None,
    pesquisa_engajamento: Any = None,
    qualidade_regiao: Any = None,
    caminho_comprador: Any = None,
    landing_pages_por_etapa: Any = None,
    leads_x_whatsapp: Any = None,
    vendas_grupos_whatsapp: Any = None,
    disparo_resumo: Any = None,
    wa_cost: Any = None,
    prev_wa_cost: Any = None,
) -> dict:
    def _f(x): return float(x or 0)
    def _i(x): return int(x or 0)

    # Leads e CPL consideram só a etapa de Captação — leads de campanhas de
    # lembrete/remarketing/pré-quali distorcem o CPL real da captação. O
    # investimento total (invest) segue sendo o lançamento inteiro.
    def _captacao(summary) -> dict:
        return (getattr(summary, "por_etapa", None) or {}).get("Captação") or {}

    wa_gasto = _f((wa_cost or {}).get("total_cost_brl"))
    prev_wa_gasto = _f((prev_wa_cost or {}).get("total_cost_brl"))

    invest = _f(getattr(meta, "total_gasto", 0)) + _f(getattr(google, "total_custo", 0)) + wa_gasto
    receita = _f(getattr(vendas, "total_receita_liquida", 0)) or _f(getattr(vendas, "total_receita", 0))
    receita_bruta = _f(getattr(vendas, "total_receita_bruta", 0)) or _f(getattr(vendas, "total_receita", 0))
    roas = receita / invest if invest > 0 else 0.0
    roas_bruto = receita_bruta / invest if invest > 0 else 0.0
    total_vendas = _i(getattr(vendas, "total_vendas", 0))
    ticket = _f(getattr(vendas, "total_ticket_medio", 0))
    meta_capt   = _captacao(meta)
    meta_leads  = _i(meta_capt.get("leads"))
    meta_spend  = _f(meta_capt.get("custo"))
    meta_cpl    = meta_spend  / meta_leads  if meta_leads  > 0 else 0.0

    google_capt  = _captacao(google)
    google_leads = int(_f(google_capt.get("conversoes")))
    google_spend = _f(google_capt.get("custo"))
    google_cpl   = google_spend / google_leads if google_leads > 0 else 0.0

    # TikTok — sem integração ainda
    tiktok_leads = 0
    tiktok_spend = 0.0
    tiktok_cpl   = 0.0

    total_leads = meta_leads + google_leads + tiktok_leads
    total_spend_all = meta_spend + google_spend + tiktok_spend
    cpl = total_spend_all / total_leads if total_leads > 0 else 0.0

    prev_invest = _f(getattr(prev_meta, "total_gasto", 0)) + _f(getattr(prev_google, "total_custo", 0)) + prev_wa_gasto
    prev_receita = _f(getattr(prev_vendas, "total_receita_liquida", 0)) or _f(getattr(prev_vendas, "total_receita", 0))
    prev_receita_bruta = _f(getattr(prev_vendas, "total_receita_bruta", 0)) or _f(getattr(prev_vendas, "total_receita", 0))
    prev_roas = prev_receita / prev_invest if prev_invest > 0 else 0.0
    prev_roas_bruto = prev_receita_bruta / prev_invest if prev_invest > 0 else 0.0
    prev_total_vendas = _i(getattr(prev_vendas, "total_vendas", 0))
    prev_ticket = _f(getattr(prev_vendas, "total_ticket_medio", 0))
    prev_meta_capt    = _captacao(prev_meta)
    prev_meta_leads   = _i(prev_meta_capt.get("leads"))
    prev_meta_spend   = _f(prev_meta_capt.get("custo"))
    prev_meta_cpl     = prev_meta_spend  / prev_meta_leads  if prev_meta_leads  > 0 else 0.0
    prev_google_capt  = _captacao(prev_google)
    prev_google_leads = int(_f(prev_google_capt.get("conversoes")))
    prev_google_spend = _f(prev_google_capt.get("custo"))
    prev_google_cpl   = prev_google_spend / prev_google_leads if prev_google_leads > 0 else 0.0
    prev_total_leads  = prev_meta_leads + prev_google_leads
    prev_cpl = (prev_meta_spend + prev_google_spend) / prev_total_leads if prev_total_leads > 0 else 0.0

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

    def get_etapa(m, g, name, whatsapp=0.0):
        # "Remarketing" não existe como chave própria em por_etapa — Meta/Google
        # classificam essas campanhas nas sub-etapas (Lembrete, Depoimento, etc.),
        # então somamos todas elas para compor o total de Remarketing. O WhatsApp
        # também é 100% remarketing (só dispara pra quem já é lead), então entra
        # no mesmo bucket.
        names = _REMARKETING_SUBETAPAS if name == "Remarketing" else [name]
        m_por = (getattr(m, "por_etapa", {}) or {}) if m else {}
        g_por = (getattr(g, "por_etapa", {}) or {}) if g else {}
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

    def _previsto_por_etapa(cfg: dict) -> dict:
        """Verba planejada por etapa (cadastrada no wizard) — Pré-Qualificação e
        Captação têm campo próprio; Remarketing soma o 'total' de cada
        sub-etapa (Lembrete/Depoimento/Aulas no Ar/Replay/Matrículas Abertas)
        provisionada na aba Evento."""
        cfg = cfg or {}
        remarketing_previsto = sum(
            _f(et.get("total")) for et in (cfg.get("etapas") or [])
            if et.get("nome") in _REMARKETING_SUBETAPAS
        )
        return {
            "Pré-Qualificação": _f(cfg.get("meta_investimento_pre_quali")),
            "Captação": _f(cfg.get("meta_investimento_captacao")),
            "Remarketing": remarketing_previsto,
        }

    cfg = _launch_cfg(launch.code) if launch else {}
    previsto_map = _previsto_por_etapa(cfg)

    base = invest or 1.0
    etapas = []
    for name in ["Pré-Qualificação", "Captação", "Remarketing"]:
        e = get_etapa(meta, google, name, whatsapp=wa_gasto if name == "Remarketing" else 0.0)
        e["pct"] = e["invest"] / base * 100
        e["previsto"] = previsto_map.get(name, 0.0)
        etapas.append(e)

    prev_etapas: list = []
    if prev_meta or prev_google:
        prev_cfg = _launch_cfg(previous.code) if previous else {}
        prev_previsto_map = _previsto_por_etapa(prev_cfg)
        prev_base = prev_invest or 1.0
        for name in ["Pré-Qualificação", "Captação", "Remarketing"]:
            e = get_etapa(prev_meta, prev_google, name, whatsapp=prev_wa_gasto if name == "Remarketing" else 0.0)
            e["pct"] = e["invest"] / prev_base * 100
            e["previsto"] = prev_previsto_map.get(name, 0.0)
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

    meta_preq_clima = _build_clima_breakdown(meta, "por_temperatura_prequali")
    prev_meta_preq_clima = _build_clima_breakdown(prev_meta, "por_temperatura_prequali")
    _attach_clima_variation(meta_preq_clima, prev_meta_preq_clima)

    google_preq_clima = _build_clima_breakdown(google, "por_temperatura_prequali", leads_key="conversoes")
    prev_google_preq_clima = _build_clima_breakdown(prev_google, "por_temperatura_prequali", leads_key="conversoes")
    _attach_clima_variation(google_preq_clima, prev_google_preq_clima)

    meta_preq_etapa = (getattr(meta, "por_etapa", {}) or {}).get("Pré-Qualificação") or {}
    prev_meta_preq_etapa = (getattr(prev_meta, "por_etapa", {}) or {}).get("Pré-Qualificação") or {}
    google_preq_etapa = (getattr(google, "por_etapa", {}) or {}).get("Pré-Qualificação") or {}
    prev_google_preq_etapa = (getattr(prev_google, "por_etapa", {}) or {}).get("Pré-Qualificação") or {}
    prequali_invest = {
        "meta": {
            "total": _f(meta_preq_etapa.get("custo")),
            "prev_total": _f(prev_meta_preq_etapa.get("custo")),
            "data_inicio": meta_preq_etapa.get("data_inicio") or "",
            "climas": meta_preq_clima,
        },
        "google": {
            "total": _f(google_preq_etapa.get("custo")),
            "prev_total": _f(prev_google_preq_etapa.get("custo")),
            "data_inicio": google_preq_etapa.get("data_inicio") or "",
            "climas": google_preq_clima,
        },
    }
    prequali_invest["total"] = prequali_invest["meta"]["total"] + prequali_invest["google"]["total"]
    prequali_invest["prev_total"] = prequali_invest["meta"]["prev_total"] + prequali_invest["google"]["prev_total"]

    # Top 3 anúncios (por leads) da Pré-Qualificação, por plataforma — TikTok
    # fica vazio até existir integração.
    preq_top_ads = {
        "meta":   (getattr(meta, "preq_por_ad", None) or [])[:3],
        "google": (getattr(google, "preq_por_ad", None) or [])[:3],
        "tiktok": [],
    }

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
        "invest": invest, "wa_gasto": wa_gasto, "receita": receita, "roas": roas,
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
        "prequali_invest": prequali_invest,
        "preq_top_ads": preq_top_ads,
        "top_ads_captacao": _build_top_ads_captacao(meta, google, sales_attr),
        "leads_detail_table": leads_detail_table,
        # Detalhamento dos públicos (categoria de adset) por clima — Captação Meta
        "publicos_captacao": {
            c: v for c, v in (
                (c, (getattr(meta, "por_publico_captacao", {}) or {}).get(c))
                for c in _CLIMA_ORDER
            ) if v
        },
        # Idem, Google Ads (audiências reais da API, sem categorização por nome)
        "publicos_captacao_google": {
            c: v for c, v in (
                (c, (getattr(google, "por_publico_captacao", {}) or {}).get(c))
                for c in _CLIMA_ORDER
            ) if v
        },
        "rmkt_adsets": _build_rmkt_adsets(meta, whatsapp=wa_gasto, cfg=cfg),
        "prev_rmkt_adsets": _build_rmkt_adsets(prev_meta, whatsapp=prev_wa_gasto, cfg=_launch_cfg(previous.code) if previous else None),
        # Sales por temperatura/tipo
        "meta_temp_sales": meta_temp_sales, "google_tipo_sales": google_tipo_sales,
        "prev_meta_temp_sales": prev_meta_temp_sales, "prev_google_tipo_sales": prev_google_tipo_sales,
        "google_temp_sales": google_temp_sales, "prev_google_temp_sales": prev_google_temp_sales,
        "clima_order": _CLIMA_ORDER,
        "max_mt": max_mt, "max_gt": max_gt,
        "youtube_aulas": youtube_aulas or [],
        "max_peak_yt": max_peak_yt,
        # Compradores × histórico de lead (novo/antigo/sem cadastro)
        "leads_antigos": leads_antigos,
        # Perfil do lead por anúncio (top 5 × pesquisa)
        "perfil_por_anuncio": _enrich_perfil_por_anuncio(
            perfil_por_anuncio, meta, google, sales_attr,
            prev_meta=prev_meta, prev_google=prev_google, prev_sales_attr=prev_sales_attr,
        ),
        # Engajamento da pesquisa (respostas × base de leads)
        "pesquisa_engajamento": pesquisa_engajamento,
        # Comercial × IA × Orgânico (sck Hotmart / utm_source TMB)
        "vendas_por_canal": getattr(vendas, "por_canal", {}) or {},
        # Antigo × novo (ADxxx já usado em lançamento anterior do produto)
        "antigo_novo": _build_antigo_novo(meta, google, sales_attr),
        # Qualidade por estado (Meta invest/leads + compradores/receita)
        "qualidade_regiao": qualidade_regiao,
        # Caminho do comprador — funil unificado por pessoa (lead→grupo→pesquisa→compra)
        "caminho_comprador": (caminho_comprador or {}).get("resumo"),
        # Landing pages que mais converteram (GA4), por etapa
        "landing_pages_preq": (landing_pages_por_etapa or {}).get("Pré-Qualificação") or [],
        "landing_pages_capt": (landing_pages_por_etapa or {}).get("Captação") or [],
        # Leads (Active Campaign) × pessoas nos grupos de WhatsApp
        "leads_x_whatsapp": leads_x_whatsapp,
        "vendas_grupos_whatsapp": vendas_grupos_whatsapp,
        "disparo_resumo": disparo_resumo,
        # Oferta & bônus — preenchido manualmente no wizard de configuração
        "oferta_descricao": cfg.get("produto_nome"),
        "oferta_preco_vista": cfg.get("produto_preco_vista"),
        "oferta_preco_parcelado": cfg.get("produto_preco_parcelado"),
        "oferta_carrinho_start": cfg.get("carrinho_start_date"),
        "oferta_carrinho_end": cfg.get("carrinho_end_date"),
    }
