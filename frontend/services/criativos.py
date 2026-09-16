"""
frontend/services/criativos.py — Overview de criativos (ADxxx) e seus insights.

Cruza o que cada anúncio gastou em cada plataforma com as vendas atribuídas a
ele, e monta o ranking de criativos da Captação, o recorte por plataforma e o
comparativo Validados × Novos.

Ler os comentários de escopo antes de mexer: vários blocos aqui distinguem
"gasto de Captação" de "gasto do lançamento inteiro" de propósito, porque somar
receita de todas as etapas em cima de gasto só-de-Captação inflava o ROAS
(achado de 14/09/26, registrado em docs/sistema/ARQUITETURA.md).
"""
from __future__ import annotations

from typing import Any

from frontend.formatters import fmt_brl, fmt_num
from frontend.services.classificadores import _classify_google_campaign_type


def _creative_overview(meta: Any, google: Any, vendas_data: Any, sales_attr: dict | None, launch_code: str = "") -> dict:
    from frontend.db_readers.ads_meta import get_historico_ad_codes  # noqa: PLC0415

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
    # rows_by_ad só tem gasto/leads de Captação (add_platform acima só recebe
    # captacao_por_ad/anuncios_por_ad) — usar por_criativo (global, todas as
    # etapas) pra vendas misturaria receita de Pré-Qualificação/Remarketing
    # em cima do gasto só-Captação e infla o ROAS (achado 14/09/26, mesma
    # causa do bug corrigido no Debriefing — aqui o impacto no PI-AGO-26 é
    # pequeno só porque o único ADxxx com reaproveitamento entre etapas
    # gastou irrisório na Pré-Qualificação, não porque o código estivesse
    # certo).
    creative_sales_captacao = (sales_attr or {}).get("por_criativo_por_etapa", {}).get("Captação", {}) or {}
    for code, row in rows_by_ad.items():
        sales = creative_sales_captacao.get(code, {})
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
        # Casa contra TODAS as campanhas vistas nos UTMs desse ADxxx, não só a do
        # representante: um criativo que veiculou na Meta e no Google tinha o
        # investimento do Google perdido sempre que o representante sorteado era
        # o UTM da Meta, e caía em "vendas sem veiculação".
        utm_campaigns = utm_info.get("campaigns") or ([utm_campaign] if utm_campaign else [])
        if utm_campaigns and google_campanhas:
            norm_camps = {_norm_text(c) for c in utm_campaigns if c}
            for camp in google_campanhas:
                if _norm_text(getattr(camp, "nome", "")) in norm_camps:
                    gasto += float(getattr(camp, "custo", 0.0) or 0.0)
                    leads += int(round(float(getattr(camp, "conversoes", 0.0) or 0.0)))
                    cliques += int(getattr(camp, "cliques", 0) or 0)
                    impressoes += int(getattr(camp, "impressoes", 0) or 0)
                    origem = "Google"
        if gasto <= 0:
            # Sem investimento real casado (nem ad-level, nem campanha Google) —
            # não é veiculação do lançamento atual, só um UTM antigo/duplicado
            # "grudado" num comprador. Fica de fora do ranking principal (seção 2)
            # e cai no bloco de vendas sem veiculação (seção 3), como qualquer
            # outro AD sem match — ver loop de sales_only_rows logo abaixo.
            continue
        faturamento = float(sales.get("faturamento") or 0.0)
        vendas_val = int(sales.get("vendas") or 0)
        rows_by_ad[code] = {
            "ad_code": code,
            "nome": f"{code} - criativo rastreado por UTM do lançamento",
            "origens": {"Google"},
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
    # O ranking (seção 2) é declaradamente só de Captação, mas as vendas vêm de
    # qualquer etapa — então criativo que só veiculou na Pré-Qualificação caía na
    # seção 3 como "sem veiculação neste lançamento", o que é falso: o gasto dele
    # está no meta_ads_daily/google_ads_daily do próprio lançamento, só que na
    # outra etapa (ex: AD030 no PI-AGO-26, R$ 17.443). Aqui levantamos esse gasto
    # pra seção 3 poder dizer a verdade, sem mexer nos totais do ranking.
    preq_gasto_por_ad: dict[str, float] = {}
    for _items, _plat in ((getattr(meta, "preq_por_ad", []), "Meta Ads"),
                          (getattr(google, "preq_por_ad", []), "Google Ads")):
        for _item in _items or []:
            _code = str(_item.get("ad_code", "")).upper()
            if _code:
                preq_gasto_por_ad[_code] = preq_gasto_por_ad.get(_code, 0.0) + float(_item.get("gasto") or 0.0)
    _codes_sem_veiculacao = {code for code in creative_sales if code not in rows_by_ad}
    real_launches_by_code: dict[str, list[dict]] = {}
    if launch_code and _codes_sem_veiculacao:
        from frontend.db_readers.ads_meta import find_ad_code_real_launches  # noqa: PLC0415
        real_launches_by_code = find_ad_code_real_launches(_codes_sem_veiculacao, launch_code)
    for code, sales in creative_sales.items():
        if code in rows_by_ad:
            continue
        utm = creative_utm.get(code, {})
        real = real_launches_by_code.get(code, [])
        sales_only_rows.append({
            "ad_code": code,
            "nome": code,
            "vendas": int(sales.get("vendas") or 0),
            "faturamento": float(sales.get("faturamento") or 0.0),
            "launches": ", ".join(utm.get("launches") or ["Sem código"]),
            "real_launch": real[0]["launch"] if real else "",
            "real_launch_gasto": real[0]["gasto"] if real else 0.0,
            # > 0 quando o AD veiculou neste lançamento, só que na Pré-Qualificação
            "preq_gasto": round(preq_gasto_por_ad.get(code, 0.0), 2),
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
        # Um mesmo AD código pode aparecer em vários ad_name/adset (ex.: mesmo
        # criativo rodando em Quente e Frio) — unifica por ad_code antes de exibir,
        # senão o mesmo anúncio aparece duplicado na tabela.
        # platform_source_rows só tem Captação (mesma fonte de rows_by_ad) —
        # escopa vendas por etapa também, mesmo motivo do fix acima.
        channel_sales = (sales_attr or {}).get("por_criativo_canal_por_etapa", {}).get(platform, {}).get("Captação", {})
        grouped: dict[str, dict] = {}
        for item in platform_source_rows.get(platform, []):
            code = str(item.get("ad_code", "")).upper()
            if not code:
                continue
            g = grouped.setdefault(code, {
                "ad_code": code, "nome": item.get("nome") or code, "video_id": None,
                "gasto": 0.0, "leads": 0, "cliques": 0, "impressoes": 0,
                "_hook_views": 0, "_meta_views_3s": 0, "_meta_thruplays": 0, "_views_100": 0,
            })
            g["gasto"] += float(item.get("gasto") or 0.0)
            g["leads"] += int(item.get("leads") or 0)
            g["cliques"] += int(item.get("cliques") or 0)
            g["impressoes"] += int(item.get("impressoes") or 0)
            if platform == "Meta Ads":
                views_3s = int(item.get("views_3s") or 0)
                g["_hook_views"] += views_3s
                g["_meta_views_3s"] += views_3s
                g["_meta_thruplays"] += int(item.get("thruplays") or 0)
                g["_views_100"] += int(item.get("views_100") or 0)
            else:
                g["_hook_views"] += int(item.get("video_views") or 0)
                g["_views_100"] += int(item.get("video_views_100") or 0)
            if item.get("video_id") and not g.get("video_id"):
                g["video_id"] = item.get("video_id")
            if len(str(item.get("nome") or "")) > len(g["nome"]):
                g["nome"] = item.get("nome") or g["nome"]

        out = []
        for code, g in grouped.items():
            sales = channel_sales.get(code, {})
            gasto = g["gasto"]
            leads = g["leads"]
            impressoes = g["impressoes"]
            faturamento = float(sales.get("faturamento") or 0.0)
            out.append({
                "ad_code": code,
                "nome": g["nome"],
                "video_id": g.get("video_id"),
                "gasto": gasto,
                "leads": leads,
                "cpl": gasto / leads if leads > 0 else 0.0,
                "ctr": g["cliques"] / impressoes * 100 if impressoes > 0 else 0.0,
                "cpm": gasto / impressoes * 1000 if impressoes > 0 else 0.0,
                "vendas": int(sales.get("vendas") or 0),
                "faturamento": faturamento,
                "roas": faturamento / gasto if gasto > 0 else 0.0,
                "hook_rate": g["_hook_views"] / impressoes * 100 if impressoes > 0 else 0.0,
                "hold_rate": (g["_meta_thruplays"] / g["_meta_views_3s"] * 100) if platform == "Meta Ads" and g["_meta_views_3s"] > 0 else None,
                "body_rate": (g["_views_100"] / g["_hook_views"] * 100) if g["_hook_views"] > 0 else 0.0,
            })
        return sorted(out, key=lambda item: (item["vendas"], item["faturamento"], item["leads"], item["gasto"]), reverse=True)

    meta_rows = build_platform_rows("Meta Ads")
    google_rows = build_platform_rows("Google Ads")

    historico = get_historico_ad_codes(launch_code) if launch_code else set()
    creative_sales = (sales_attr or {}).get("por_criativo", {})
    # all_captacao (abaixo) só tem gasto de Captação — mesmo fix de escopo
    # dos blocos acima, aqui pra Validados × Novos.
    creative_sales_captacao_vn = (sales_attr or {}).get("por_criativo_por_etapa", {}).get("Captação", {}) or {}

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
        sales = creative_sales_captacao_vn.get(ad_code, {})
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
