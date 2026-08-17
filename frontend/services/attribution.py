"""
frontend/services/attribution.py — Lógica de atribuição de vendas e overview de criativos.

Funções de classificação (pure): _classify_campaign, _extract_ad_code,
_classify_google_campaign_type, _utm_score, _inc_sales, _merge_google_tipo_sales.

Funções de negócio: _sales_attribution, _creative_overview, _creative_insights.
"""
from __future__ import annotations

import re
from typing import Any

from frontend.utils import _norm_text
from frontend.formatters import fmt_brl, fmt_num

# ── Classificadores puros ──────────────────────────────────────────────────────

def _find_header_col(header: list[str], *parts: str) -> int | None:
    for i, col in enumerate(header):
        norm = _norm_text(col)
        if all(part in norm for part in parts):
            return i
    return None


def _classify_campaign(campaign: str, source: str = "", medium: str = "") -> dict:
    text = _norm_text(f"{source} {medium} {campaign}")
    data = {"channel": "Outros", "etapa": "Outros", "temperatura": "Outros", "bucket": "Outros"}
    if any(token in text for token in ["[ma]", "facebook", "fb", "meta", "instagram"]):
        data["channel"] = "Meta Ads"
    elif any(token in text for token in ["[ga]", "google", "youtube", "yt", "gads", "adwords"]):
        data["channel"] = "Google Ads"
    for tokens, label in [
        (["captacao", "capta", "cadastro", "compra", "compras"], "Captação"),
        (["pre-qualificacao", "pre-quali", "pre quali"], "Pré-Qualificação"),
        (["engajamento", "replay", "trafego"], "RMK/Engajamento"),
        (["matriculas", "pitch", "roas"], "Pitch/ROAS"),
    ]:
        if any(token in text for token in tokens):
            data["etapa"] = label
            break
    for token, label in [("quente", "Quente"), ("frio", "Frio"), ("especifico", "Específico"), ("lookalike", "Frio")]:
        if token in text:
            data["temperatura"] = label
            break
    for token, label in [("principal", "Principal"), ("potencial", "Potencial"), ("reels", "Reels"), ("novos-ads", "Novos Ads (teste)"), ("novos_ads", "Novos Ads (teste)")]:
        if token in text:
            data["bucket"] = label
            break
    return data


def _extract_ad_code(value: str) -> str:
    match = re.search(r"\bAD\d+\b", str(value or ""), flags=re.IGNORECASE)
    return match.group(0).upper() if match else ""


def _classify_google_campaign_type(campaign: str = "", source: str = "", medium: str = "", content: str = "", term: str = "", campaign_type: str = "") -> str:
    text = _norm_text(f"{source} {medium} {campaign} {content} {term} {campaign_type}")
    if any(token in text for token in ["pmax", "p-max", "performance max", "performance-max"]):
        return "PMax"
    if any(token in text for token in ["display", "gdn"]):
        return "Display"
    if any(token in text for token in ["search", "pesquisa", "rede de pesquisa"]):
        return "Search"
    if any(token in text for token in ["youtube", "yt-", "video", "vídeo"]):
        return "YouTube"
    if "geracao de demanda" in text or "geração de demanda" in text:
        return "Geração de demanda"
    if "[ga]" in text and any(token in text for token in ["cadastro", "capta"]):
        return "Geração de demanda"
    return "Google sem AD"


_GOOGLE_TIPO_MERGE = {
    "YouTube": "YouTube + Geração de Demanda",
    "Geração de demanda": "YouTube + Geração de Demanda",
}
_GOOGLE_TIPO_ORDER = ["PMax", "Search", "YouTube + Geração de Demanda"]


def _merge_google_tipo_sales(tipo_sales: dict | None) -> dict:
    """Agrupa YouTube + Geração de Demanda em uma única categoria."""
    merged: dict[str, dict] = {}
    for tipo, s in (tipo_sales or {}).items():
        key = _GOOGLE_TIPO_MERGE.get(tipo, tipo)
        bucket = merged.setdefault(key, {"vendas": 0, "faturamento": 0.0})
        bucket["vendas"] += int(s.get("vendas") or 0)
        bucket["faturamento"] += float(s.get("faturamento") or 0.0)
    ordered = {k: merged[k] for k in _GOOGLE_TIPO_ORDER if k in merged}
    for k, v in merged.items():
        if k not in ordered:
            ordered[k] = v
    return ordered


def _inc_sales(target: dict, key: str, receita: float = 0.0, vendas: int = 1) -> None:
    if key not in target:
        target[key] = {"vendas": 0, "faturamento": 0.0}
    target[key]["vendas"] += vendas
    target[key]["faturamento"] += receita


def _utm_score(launch_code: str, source: str, medium: str, campaign: str, content: str, term: str = "") -> int:
    text = _norm_text(f"{source} {medium} {campaign} {content} {term}")
    score = 0
    if _norm_text(launch_code) in text:
        score += 100
    cls = _classify_campaign(campaign, source, medium)
    if cls["channel"] in ("Meta Ads", "Google Ads"):
        score += 20
    if cls["etapa"] == "Captação":
        score += 15
    if _extract_ad_code(f"{source} {medium} {campaign} {content} {term}"):
        score += 40
    if cls["channel"] == "Google Ads" and _classify_google_campaign_type(campaign, source, medium, content, term) in ("Search", "PMax", "Display"):
        score += 35
    if source or medium or campaign:
        score += 1
    return score


# ── Atribuição de vendas ───────────────────────────────────────────────────────

def _sales_attribution(launch: Any, vendas_data: Any) -> dict:
    from frontend.cache import _get_cached, _set_cached  # noqa: PLC0415
    from frontend.services.fetch import _launch_cfg, _get_global_start, _get_global_end  # noqa: PLC0415
    from frontend.db_readers.leads import read_ac_leads_for_attribution  # noqa: PLC0415

    cached = _get_cached(launch.code, "sales_attribution")
    if cached is not None:
        return cached
    result: dict = {
        "total_rastreado": 0,
        "emails_rastreados": set(),
        "por_canal": {},
        "meta_por_etapa": {},
        "meta_por_bucket": {},
        "meta_por_temperatura": {},
        "google_por_etapa": {},
        "google_por_temperatura": {},
        "google_por_tipo_campanha": {},
        "google_por_campanha": {},
        "google_sem_ad_por_tipo": {},
        "google_sem_ad_por_campanha": {},
        "por_criativo": {},
        "por_criativo_canal": {},
        "por_criativo_lancamento_atual": set(),
        "por_criativo_utm": {},
    }
    if not vendas_data:
        _set_cached(launch.code, "sales_attribution", result)
        return result
    buyers = vendas_data.emails_hotmart | vendas_data.emails_tmb
    buyer_utms: dict[str, dict] = {}
    _sa_cfg = _launch_cfg(launch.code)
    leads_df = read_ac_leads_for_attribution(
        launch.code,
        start_date=_get_global_start(_sa_cfg),
        end_date=_get_global_end(_sa_cfg),
    )
    if leads_df.empty:
        _set_cached(launch.code, "sales_attribution", result)
        return result
    leads_df_email = leads_df[leads_df["email_norm"].isin(buyers)]
    for _, row in leads_df_email.iterrows():
        email = row["email_norm"]
        if not email:
            continue
        source = row["utm_source"]
        medium = row["utm_medium"]
        campaign = row["utm_campaign"]
        content = row["utm_content"]
        term = row["utm_term"]
        if not (source or medium or campaign):
            continue
        score = _utm_score(launch.code, source, medium, campaign, content, term)
        current = buyer_utms.get(email)
        if current is None or score > current["score"]:
            buyer_utms[email] = {
                "score": score,
                "source": source,
                "medium": medium,
                "campaign": campaign,
                "content": content,
                "term": term,
            }

    # Cascata para compradores sem match por e-mail: telefone, depois nome completo.
    # Cobre casos onde o e-mail usado na compra difere do cadastrado no AC.
    unmatched = buyers - buyer_utms.keys()
    if unmatched:
        def _row_score(row) -> int:
            return _utm_score(launch.code, row["utm_source"], row["utm_medium"], row["utm_campaign"], row["utm_content"], row["utm_term"])

        # Agrupamento vetorizado (rápido mesmo em centenas de milhares de linhas) —
        # a pontuação (_utm_score, com regex) só roda nos poucos candidatos de
        # cada comprador não batido por e-mail, nunca na tabela inteira.
        phone_groups = leads_df[leads_df["phone"] != ""].groupby("phone").groups
        name_mask = leads_df["nome_norm"].str.contains(" ", na=False)
        name_groups = leads_df[name_mask].groupby("nome_norm").groups

        for email in list(unmatched):
            candidate_idx = None
            phone = vendas_data.phone_por_email.get(email)
            if phone and phone in phone_groups:
                candidate_idx = phone_groups[phone]
            else:
                nome = vendas_data.nome_por_email.get(email)
                nome_norm = _norm_text(nome) if nome else ""
                nome_norm = re.sub(r"\s+", " ", nome_norm).strip()
                if nome_norm and " " in nome_norm and nome_norm in name_groups:
                    candidate_idx = name_groups[nome_norm]
            if candidate_idx is None or len(candidate_idx) == 0:
                continue
            best_row, best_score = None, -1
            for idx in candidate_idx:
                row = leads_df.loc[idx]
                score = _row_score(row)
                if score > best_score:
                    best_row, best_score = row, score
            if best_row is not None:
                buyer_utms[email] = {
                    "score": best_score,
                    "source": best_row["utm_source"],
                    "medium": best_row["utm_medium"],
                    "campaign": best_row["utm_campaign"],
                    "content": best_row["utm_content"],
                    "term": best_row["utm_term"],
                }

    for email, utm in buyer_utms.items():
        source = utm["source"]
        medium = utm["medium"]
        campaign = utm["campaign"]
        content = utm["content"]
        term = utm.get("term", "")
        cls = _classify_campaign(campaign, source, medium)
        receita_email = float(vendas_data.receita_por_email.get(email, 0.0))
        vendas_email = int(getattr(vendas_data, "vendas_por_email", {}).get(email, 1) or 1)
        result["emails_rastreados"].add(email)
        result["total_rastreado"] += vendas_email
        _inc_sales(result["por_canal"], cls["channel"], receita_email, vendas_email)
        if cls["channel"] == "Meta Ads":
            _inc_sales(result["meta_por_etapa"], cls["etapa"], receita_email, vendas_email)
            _inc_sales(result["meta_por_bucket"], cls["bucket"], receita_email, vendas_email)
            _inc_sales(result["meta_por_temperatura"], cls["temperatura"], receita_email, vendas_email)
        elif cls["channel"] == "Google Ads":
            _inc_sales(result["google_por_etapa"], cls["etapa"], receita_email, vendas_email)
            _inc_sales(result["google_por_temperatura"], cls["temperatura"], receita_email, vendas_email)
            google_type = _classify_google_campaign_type(campaign, source, medium, content, term)
            _inc_sales(result["google_por_tipo_campanha"], google_type, receita_email, vendas_email)
            google_campaign_key = _norm_text(campaign)
            if google_campaign_key:
                _inc_sales(result["google_por_campanha"], google_campaign_key, receita_email, vendas_email)
        ad_code = _extract_ad_code(f"{source} {medium} {campaign} {content} {term}")
        if ad_code:
            _inc_sales(result["por_criativo"], ad_code, receita_email, vendas_email)
            if ad_code not in result["por_criativo_utm"]:
                detected = re.findall(r"\b(?:PBB|PES|PI)-[A-Z]{3}-\d{2}\b", f"{source} {medium} {campaign} {content} {term}", flags=re.IGNORECASE)
                result["por_criativo_utm"][ad_code] = {
                    "source": source,
                    "medium": medium,
                    "campaign": campaign,
                    "content": content,
                    "term": term,
                    "launches": sorted({item.upper() for item in detected}),
                }
            if _norm_text(launch.code) in _norm_text(f"{source} {medium} {campaign} {content} {term}"):
                result["por_criativo_lancamento_atual"].add(ad_code)
            if cls["channel"] not in result["por_criativo_canal"]:
                result["por_criativo_canal"][cls["channel"]] = {}
            _inc_sales(result["por_criativo_canal"][cls["channel"]], ad_code, receita_email, vendas_email)
        elif cls["channel"] == "Google Ads":
            google_type = _classify_google_campaign_type(campaign, source, medium, content, term)
            _inc_sales(result["google_sem_ad_por_tipo"], google_type, receita_email, vendas_email)
            google_campaign_key = _norm_text(campaign)
            if google_campaign_key:
                _inc_sales(result["google_sem_ad_por_campanha"], google_campaign_key, receita_email, vendas_email)
    _set_cached(launch.code, "sales_attribution", result)
    return result


# ── Creative Overview ──────────────────────────────────────────────────────────

def _creative_overview(meta: Any, google: Any, vendas_data: Any, sales_attr: dict | None, launch_code: str = "") -> dict:
    from frontend.database_reader import get_historico_ad_codes  # noqa: PLC0415

    rows_by_ad: dict[str, dict] = {}
    platform_source_rows: dict[str, list[dict]] = {"Meta Ads": [], "Google Ads": []}

    def add_platform(items: Any, platform: str) -> None:
        for item in items or []:
            code = str(item.get("ad_code", "")).upper()
            if not code:
                continue
            platform_source_rows.setdefault(platform, []).append(item)
            row = rows_by_ad.setdefault(code, {
                "ad_code": code,
                "nome": item.get("nome") or code,
                "origens": set(),
                "gasto": 0.0,
                "leads": 0,
                "cliques": 0,
                "impressoes": 0,
                "vendas": 0,
                "faturamento": 0.0,
                "video_id": None,
                "_hook_views": 0,
                "_meta_views_3s": 0,
                "_meta_thruplays": 0,
                "_views_100": 0,
            })
            row["origens"].add(platform)
            row["gasto"] += float(item.get("gasto") or 0.0)
            row["leads"] += int(item.get("leads") or 0)
            row["cliques"] += int(item.get("cliques") or 0)
            row["impressoes"] += int(item.get("impressoes") or 0)
            if platform == "Meta Ads":
                views_3s = int(item.get("views_3s") or 0)
                row["_hook_views"] += views_3s
                row["_meta_views_3s"] += views_3s
                row["_meta_thruplays"] += int(item.get("thruplays") or 0)
                row["_views_100"] += int(item.get("views_100") or 0)
            else:
                row["_hook_views"] += int(item.get("video_views") or 0)
                row["_views_100"] += int(item.get("video_views_100") or 0)
            if len(str(item.get("nome") or "")) > len(row["nome"]):
                row["nome"] = item.get("nome") or row["nome"]
            if item.get("video_id") and not row.get("video_id"):
                row["video_id"] = item.get("video_id")

    add_platform(getattr(meta, "captacao_por_ad", []), "Meta Ads")
    add_platform(getattr(google, "anuncios_por_ad", []), "Google Ads")

    creative_sales = (sales_attr or {}).get("por_criativo", {})
    for code, row in rows_by_ad.items():
        sales = creative_sales.get(code, {})
        row["vendas"] = int(sales.get("vendas") or 0)
        row["faturamento"] = float(sales.get("faturamento") or 0.0)
        row["cpl"] = row["gasto"] / row["leads"] if row["leads"] > 0 else 0.0
        row["ctr"] = row["cliques"] / row["impressoes"] * 100 if row["impressoes"] > 0 else 0.0
        row["hook_rate"] = row["_hook_views"] / row["impressoes"] * 100 if row["impressoes"] > 0 else 0.0
        row["hold_rate"] = (row["_meta_thruplays"] / row["_meta_views_3s"] * 100) if row["_meta_views_3s"] > 0 else None
        row["body_rate"] = (row["_views_100"] / row["_hook_views"] * 100) if row["_hook_views"] > 0 else 0.0
        for k in ("_hook_views", "_meta_views_3s", "_meta_thruplays", "_views_100"):
            row.pop(k, None)
        row["cpm"] = row["gasto"] / row["impressoes"] * 1000 if row["impressoes"] > 0 else 0.0
        row["roas"] = row["faturamento"] / row["gasto"] if row["gasto"] > 0 else 0.0
        row["origem"] = " + ".join("Meta" if origem == "Meta Ads" else "Google" for origem in sorted(row["origens"]))

    current_launch_codes = (sales_attr or {}).get("por_criativo_lancamento_atual", set())
    creative_utm_map = (sales_attr or {}).get("por_criativo_utm", {})
    google_campanhas = getattr(google, "campanhas", []) or []
    for code in current_launch_codes:
        if code in rows_by_ad:
            continue
        sales = creative_sales.get(code, {})
        utm_info = creative_utm_map.get(code, {})
        utm_campaign = utm_info.get("campaign", "")
        gasto = 0.0
        leads = 0
        cliques = 0
        impressoes = 0
        origem = "UTM"
        if utm_campaign and google_campanhas:
            norm_camp = _norm_text(utm_campaign)
            for camp in google_campanhas:
                if _norm_text(getattr(camp, "nome", "")) == norm_camp:
                    gasto += float(getattr(camp, "custo", 0.0) or 0.0)
                    leads += int(round(float(getattr(camp, "conversoes", 0.0) or 0.0)))
                    cliques += int(getattr(camp, "cliques", 0) or 0)
                    impressoes += int(getattr(camp, "impressoes", 0) or 0)
                    origem = "Google"
        faturamento = float(sales.get("faturamento") or 0.0)
        vendas_val = int(sales.get("vendas") or 0)
        rows_by_ad[code] = {
            "ad_code": code,
            "nome": f"{code} - criativo rastreado por UTM do lançamento",
            "origens": {"Google"} if gasto > 0 else {"UTM"},
            "gasto": gasto,
            "leads": leads,
            "cliques": cliques,
            "impressoes": impressoes,
            "vendas": vendas_val,
            "faturamento": faturamento,
            "cpl": gasto / leads if leads > 0 else 0.0,
            "ctr": cliques / impressoes * 100 if impressoes > 0 else 0.0,
            "cpm": gasto / impressoes * 1000 if impressoes > 0 else 0.0,
            "roas": faturamento / gasto if gasto > 0 else 0.0,
            "hook_rate": 0.0,
            "hold_rate": None,
            "body_rate": 0.0,
            "origem": origem,
        }

    sales_only_rows = []
    creative_utm = (sales_attr or {}).get("por_criativo_utm", {})
    for code, sales in creative_sales.items():
        if code in rows_by_ad:
            continue
        utm = creative_utm.get(code, {})
        sales_only_rows.append({
            "ad_code": code,
            "nome": code,
            "vendas": int(sales.get("vendas") or 0),
            "faturamento": float(sales.get("faturamento") or 0.0),
            "launches": ", ".join(utm.get("launches") or ["Sem código"]),
            "source": utm.get("source", ""),
            "medium": utm.get("medium", ""),
            "campaign": utm.get("campaign", ""),
            "content": utm.get("content", ""),
            "term": utm.get("term", ""),
        })
    sales_only_rows = sorted(
        sales_only_rows,
        key=lambda item: (item["vendas"], item["faturamento"], item["ad_code"]),
        reverse=True,
    )

    google_campaign_rows: dict[str, dict] = {}
    for campaign in getattr(google, "campanhas", []) or []:
        if "capta" not in _norm_text(getattr(campaign, "nome", "")):
            continue
        campaign_type = _classify_google_campaign_type(
            campaign=getattr(campaign, "nome", ""),
            campaign_type=getattr(campaign, "tipo", ""),
        )
        if campaign_type not in ("Search", "PMax", "Display"):
            continue
        code = f"GOOGLE-{campaign_type.upper()}"
        row = google_campaign_rows.setdefault(code, {
            "ad_code": code,
            "nome": f"Google Ads - {campaign_type}",
            "origens": {"Google Ads"},
            "gasto": 0.0,
            "leads": 0,
            "cliques": 0,
            "impressoes": 0,
            "vendas": 0,
            "faturamento": 0.0,
            "origem": "Google",
            "campaign_keys": set(),
        })
        row["campaign_keys"].add(_norm_text(getattr(campaign, "nome", "")))
        row["gasto"] += float(getattr(campaign, "custo", 0.0) or 0.0)
        row["leads"] += int(round(float(getattr(campaign, "conversoes", 0.0) or 0.0)))
        row["cliques"] += int(getattr(campaign, "cliques", 0) or 0)
        row["impressoes"] += int(getattr(campaign, "impressoes", 0) or 0)

    google_type_sales = (sales_attr or {}).get("google_por_tipo_campanha", {})
    google_campaign_sales = (sales_attr or {}).get("google_por_campanha", {})
    google_adless_sales = (sales_attr or {}).get("google_sem_ad_por_tipo", {})
    for code, row in google_campaign_rows.items():
        campaign_type = row["nome"].replace("Google Ads - ", "").replace(" sem ADxxx", "")
        campaign_keys = row.get("campaign_keys", set())
        sales = {"vendas": 0, "faturamento": 0.0}
        for campaign_key in campaign_keys:
            campaign_sales = google_campaign_sales.get(campaign_key, {})
            sales["vendas"] += int(campaign_sales.get("vendas") or 0)
            sales["faturamento"] += float(campaign_sales.get("faturamento") or 0.0)
        if not sales["vendas"]:
            sales = google_type_sales.get(campaign_type, {}) or google_adless_sales.get(campaign_type, {})
        row["vendas"] = int(sales.get("vendas") or 0)
        row["faturamento"] = float(sales.get("faturamento") or 0.0)
        row["cpl"] = row["gasto"] / row["leads"] if row["leads"] > 0 else 0.0
        row["ctr"] = row["cliques"] / row["impressoes"] * 100 if row["impressoes"] > 0 else 0.0
        row["cpm"] = row["gasto"] / row["impressoes"] * 1000 if row["impressoes"] > 0 else 0.0
        row["roas"] = row["faturamento"] / row["gasto"] if row["gasto"] > 0 else 0.0
    google_campaign_special_rows = sorted(
        google_campaign_rows.values(),
        key=lambda item: (item["vendas"], item["faturamento"], item["gasto"]),
        reverse=True,
    )

    rows = sorted(
        rows_by_ad.values(),
        key=lambda item: (item["vendas"], item["faturamento"], item["leads"], item["gasto"]),
        reverse=True,
    )
    total_buyers = len(
        (getattr(vendas_data, "emails_hotmart", set()) or set()) |
        (getattr(vendas_data, "emails_tmb", set()) or set())
    ) if vendas_data else 0
    rastreados = len((sales_attr or {}).get("emails_rastreados", set()))
    google_sem_ad = (sales_attr or {}).get("google_sem_ad_por_tipo", {})
    google_sem_ad_vendas = sum(int(v.get("vendas") or 0) for v in google_sem_ad.values())
    google_sem_ad_faturamento = sum(float(v.get("faturamento") or 0.0) for v in google_sem_ad.values())
    google_sem_ad_detail = [
        {"tipo": k, "vendas": int(v.get("vendas") or 0), "faturamento": float(v.get("faturamento") or 0.0)}
        for k, v in sorted(google_sem_ad.items(), key=lambda x: x[1].get("vendas", 0), reverse=True)
        if int(v.get("vendas") or 0) > 0
    ]

    resumo = {
        "total_ads": len(rows),
        "total_gasto": sum(item["gasto"] for item in rows),
        "total_leads": sum(item["leads"] for item in rows),
        "total_vendas_ads": sum(item["vendas"] for item in rows),
        "total_faturamento_ads": sum(item["faturamento"] for item in rows),
        "total_compradores": total_buyers,
        "compradores_com_utm": rastreados,
        "compradores_sem_utm": max(0, total_buyers - rastreados),
        "google_sem_ad_vendas": google_sem_ad_vendas,
        "google_sem_ad_faturamento": google_sem_ad_faturamento,
        "google_sem_ad_detail": google_sem_ad_detail,
    }
    resumo["roas_ads"] = resumo["total_faturamento_ads"] / resumo["total_gasto"] if resumo["total_gasto"] > 0 else 0.0

    def build_platform_rows(platform: str) -> list[dict]:
        channel_sales = (sales_attr or {}).get("por_criativo_canal", {}).get(platform, {})
        out = []
        for item in platform_source_rows.get(platform, []):
            code = str(item.get("ad_code", "")).upper()
            sales = channel_sales.get(code, {})
            gasto = float(item.get("gasto") or 0.0)
            leads = int(item.get("leads") or 0)
            faturamento = float(sales.get("faturamento") or 0.0)
            out.append({
                "ad_code": code,
                "nome": item.get("nome") or code,
                "gasto": gasto,
                "leads": leads,
                "cpl": gasto / leads if leads > 0 else 0.0,
                "ctr": float(item.get("ctr") or 0.0),
                "cpm": float(item.get("cpm") or 0.0),
                "vendas": int(sales.get("vendas") or 0),
                "faturamento": faturamento,
                "roas": faturamento / gasto if gasto > 0 else 0.0,
                "hook_rate": float(item.get("hook_rate") or 0.0),
                "hold_rate": float(item.get("hold_rate") or 0.0) if platform == "Meta Ads" else None,
                "body_rate": float(item.get("body_rate") or 0.0),
            })
        return sorted(out, key=lambda item: (item["vendas"], item["faturamento"], item["leads"], item["gasto"]), reverse=True)

    meta_rows = build_platform_rows("Meta Ads")
    google_rows = build_platform_rows("Google Ads")

    historico = get_historico_ad_codes(launch_code) if launch_code else set()
    creative_sales = (sales_attr or {}).get("por_criativo", {})

    validados_all: list[dict] = []
    novos_all: list[dict] = []

    all_captacao = (
        list(getattr(meta, "captacao_por_ad", []) or []) +
        list(getattr(google, "anuncios_por_ad", []) or [])
    )

    merged_by_code: dict[str, dict] = {}
    for item in all_captacao:
        ad_code = str(item.get("ad_code", "")).upper()
        if not ad_code:
            continue
        if ad_code not in merged_by_code:
            merged_by_code[ad_code] = {
                "ad_code": ad_code,
                "nome": item.get("nome") or ad_code,
                "gasto": 0.0,
                "leads": 0,
                "cliques": 0,
                "impressoes": 0,
                "origens": set(),
                "_hook_views": 0,
                "_meta_views_3s": 0,
                "_meta_thruplays": 0,
                "_views_100": 0,
            }
        r = merged_by_code[ad_code]
        r["gasto"] += float(item.get("gasto") or 0.0)
        r["leads"] += int(item.get("leads") or 0)
        r["cliques"] += int(item.get("cliques") or 0)
        r["impressoes"] += int(item.get("impressoes") or 0)
        origem = item.get("origem", "")
        if origem:
            r["origens"].add("Meta" if "meta" in origem.lower() else "Google")
        if "meta" in origem.lower():
            views_3s = int(item.get("views_3s") or 0)
            r["_hook_views"] += views_3s
            r["_meta_views_3s"] += views_3s
            r["_meta_thruplays"] += int(item.get("thruplays") or 0)
            r["_views_100"] += int(item.get("views_100") or 0)
        else:
            r["_hook_views"] += int(item.get("video_views") or 0)
            r["_views_100"] += int(item.get("video_views_100") or 0)
        if len(str(item.get("nome") or "")) > len(r["nome"]):
            r["nome"] = item["nome"]

    for ad_code, r in merged_by_code.items():
        sales = creative_sales.get(ad_code, {})
        faturamento = float(sales.get("faturamento") or 0.0)
        gasto = r["gasto"]
        leads = r["leads"]
        entry = {
            "ad_code": ad_code,
            "nome": r["nome"],
            "gasto": gasto,
            "leads": leads,
            "cliques": r["cliques"],
            "impressoes": r["impressoes"],
            "cpl": gasto / leads if leads > 0 else 0.0,
            "ctr": r["cliques"] / r["impressoes"] * 100 if r["impressoes"] > 0 else 0.0,
            "vendas": int(sales.get("vendas") or 0),
            "faturamento": faturamento,
            "roas": faturamento / gasto if gasto > 0 else 0.0,
            "origem": " + ".join(sorted(r["origens"])) if r["origens"] else "—",
            "hook_rate": r["_hook_views"] / r["impressoes"] * 100 if r["impressoes"] > 0 else 0.0,
            "hold_rate": (r["_meta_thruplays"] / r["_meta_views_3s"] * 100) if r["_meta_views_3s"] > 0 else None,
            "body_rate": (r["_views_100"] / r["_hook_views"] * 100) if r["_hook_views"] > 0 else 0.0,
        }
        if ad_code in historico:
            validados_all.append(entry)
        else:
            novos_all.append(entry)

    validados_all.sort(key=lambda x: (x["leads"], x["gasto"]), reverse=True)
    novos_all.sort(key=lambda x: (x["leads"], x["gasto"]), reverse=True)

    return {
        "rows": rows,
        "meta_rows": meta_rows,
        "google_rows": google_rows,
        "google_campaign_rows": google_campaign_special_rows,
        "sales_only_rows": sales_only_rows,
        "resumo": resumo,
        "insights": _creative_insights(rows, resumo),
        "validados_all": validados_all,
        "novos_all": novos_all,
    }


# ── Creative Insights ──────────────────────────────────────────────────────────

def _creative_insights(rows: list[dict], resumo: dict) -> list[str]:
    if not rows:
        return ["Sem dados de anúncios em captação para analisar."]
    insights = []
    with_sales = [row for row in rows if row["vendas"] > 0]
    without_sales = [row for row in rows if row["vendas"] == 0 and row["gasto"] > 0]
    best_roas = sorted([row for row in with_sales if row["gasto"] > 0], key=lambda item: item["roas"], reverse=True)
    high_spend_no_sales = sorted(without_sales, key=lambda item: item["gasto"], reverse=True)
    low_cpl = sorted([row for row in rows if row["leads"] >= 100 and row["cpl"] > 0], key=lambda item: item["cpl"])

    if with_sales:
        top = with_sales[0]
        insights.append(f"{top['ad_code']} lidera em vendas rastreadas ({top['vendas']}) e faturamento ({fmt_brl(top['faturamento'])}); manter como referência de ângulo criativo.")
    if best_roas:
        top_roas = best_roas[0]
        insights.append(f"{top_roas['ad_code']} tem o melhor ROAS rastreado ({top_roas['roas']:.2f}x); vale comparar hook, promessa e formato com os demais anúncios.")
    if low_cpl:
        cpl_top = low_cpl[0]
        insights.append(f"{cpl_top['ad_code']} entrega o CPL mais eficiente entre anúncios com volume relevante ({fmt_brl(cpl_top['cpl'])}); se as vendas forem baixas, o problema pode estar na qualidade do lead ou na etapa posterior.")
    if high_spend_no_sales:
        weak = high_spend_no_sales[0]
        insights.append(f"{weak['ad_code']} consumiu {fmt_brl(weak['gasto'])} sem venda rastreada por UTM; revisar antes de escalar ou exigir novo teste com variação de copy.")
    if resumo["total_compradores"]:
        pct = resumo["compradores_com_utm"] / resumo["total_compradores"] * 100
        insights.append(f"{fmt_num(resumo['compradores_com_utm'])} de {fmt_num(resumo['total_compradores'])} compradores foram rastreados com UTM ({pct:.1f}%). O restante limita a leitura por criativo.")
    return insights
