"""
frontend/services/attribution.py — Atribuição de vendas a anúncio e campanha.

``_sales_attribution`` é o coração: casa cada venda com o lead que a originou
(por e-mail e telefone) e, a partir das UTMs desse lead, decide de qual anúncio,
campanha, etapa e plataforma aquela receita veio.

O que era classificação pura de texto foi para ``classificadores.py``; o
overview de criativos, para ``criativos.py``. Os dois seguem reexportados aqui
porque `core.py` e outros módulos importam por este caminho há muito tempo.
"""
from __future__ import annotations

from typing import Any

from frontend.services.classificadores import (  # noqa: F401 — reexport
    _classify_campaign,
    _classify_google_campaign_type,
    _extract_ad_code,
    _find_header_col,
    _inc_sales,
    _match_google_type_tokens,
    _merge_google_tipo_sales,
    _utm_score,
)
from frontend.services.criativos import (  # noqa: F401 — reexport
    _creative_insights,
    _creative_overview,
)


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
        # Vendas/receita nas MESMAS categorias (etapa/temperatura/bucket/segmento)
        # que as páginas /meta e /google usam pra montar suas tabelas de
        # investimento — categorizadas com as funções desses readers, não a
        # classificação simplificada de _classify_campaign, pra as chaves
        # baterem exatamente com as das tabelas.
        "meta_etapa_sales": {},
        "meta_temperatura_sales": {},
        "meta_bucket_sales": {},
        "meta_segmento_sales": {},
        # Vendas por temperatura CRUZADA com etapa — meta_temperatura_sales
        # sozinho mistura Captação+Pré-Qualificação+Remarketing no mesmo
        # bucket "Quente"/"Frio"/etc; isso serve pra tabelas escopadas por
        # etapa (ex.: "Performance da Qualificação", pauta 10/09/26).
        "meta_temperatura_sales_por_etapa": {},
        "google_etapa_sales": {},
        "google_temperatura_sales": {},
        "google_temperatura_sales_por_etapa": {},
        "google_segmento_sales": {},
        "google_campanha_sales": {},
        "por_criativo": {},
        # Vendas por criativo CRUZADAS com etapa — o mesmo ADxxx pode rodar
        # com gasto irrisório numa etapa e gasto pesado em outra (ex.: AD127
        # no PI-AGO-26: R$0,52 na Pré-Qualificação, R$28mil na Captação);
        # "por_criativo" sozinho jogaria TODA a venda na etapa errada se a
        # tabela olhar só o gasto daquela etapa. Ver debriefing 14/09/26.
        "por_criativo_por_etapa": {},
        "por_criativo_canal": {},
        # Vendas por criativo cruzadas com etapa E plataforma — o mesmo
        # ADxxx pode rodar pesado no Google e irrisório no Meta (ex.: AD174
        # no PI-AGO-26: R$103mil Google vs R$675 Meta); a tabela "Top Ads
        # (Meta)" precisa só da fatia de vendas atribuível ao Meta, senão
        # herda as vendas do Google inteiras e o ROAS do Meta explode.
        "por_criativo_canal_por_etapa": {},
        "por_criativo_lancamento_atual": set(),
        "por_criativo_utm": {},
    }
    if not vendas_data:
        _set_cached(launch.code, "sales_attribution", result)
        return result
    buyers = vendas_data.emails_hotmart | vendas_data.emails_tmb
    buyer_utms: dict[str, dict] = {}
    _sa_cfg = _launch_cfg(launch.code)
    # Só interessam os leads que casam com um comprador (por e-mail ou por
    # telefone) — o filtro vai pro SQL em vez de baixar a base inteira do
    # lançamento pra descartar quase tudo (ver ARQUITETURA.md, 14/09/26).
    _buyer_phones = {
        str(p).strip()
        for p in (getattr(vendas_data, "phone_por_email", {}) or {}).values()
        if p and str(p).strip()
    }
    leads_df = read_ac_leads_for_attribution(
        launch.code,
        start_date=_get_global_start(_sa_cfg),
        end_date=_get_global_end(_sa_cfg),
        emails=buyers,
        phones=_buyer_phones,
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

    # Cascata para compradores sem match por e-mail: telefone.
    # Cobre casos onde o e-mail usado na compra difere do cadastrado no AC.
    # Nome completo NÃO entra como fallback: homônimos herdariam UTM de outra pessoa.
    unmatched = buyers - buyer_utms.keys()
    if unmatched:
        def _row_score(row) -> int:
            return _utm_score(launch.code, row["utm_source"], row["utm_medium"], row["utm_campaign"], row["utm_content"], row["utm_term"])

        # Agrupamento vetorizado (rápido mesmo em centenas de milhares de linhas) —
        # a pontuação (_utm_score, com regex) só roda nos poucos candidatos de
        # cada comprador não batido por e-mail, nunca na tabela inteira.
        phone_groups = leads_df[leads_df["phone"] != ""].groupby("phone").groups

        for email in list(unmatched):
            phone = vendas_data.phone_por_email.get(email)
            candidate_idx = phone_groups.get(phone) if phone else None
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

    # Mapa term→campanha aprendido dos próprios leads (só tráfego Google): recupera
    # vendas de períodos com UTM quebrada, onde campanha/grupo vieram vazios e apenas
    # o utm_term identifica o grupo de recursos (ex.: PI-AGO-26 — AD219/AD220/AD232
    # eram grupos da p-max e AD400 da search). Voto majoritário resolve variantes
    # URL-encoded do mesmo nome de campanha.
    # Voto majoritário calculado no servidor (era feito sobre a base inteira
    # de leads carregada em memória; agora leads_df só tem compradores).
    from frontend.db_readers.leads import read_term_campaign_map  # noqa: PLC0415
    term_campaign_map: dict[str, str] = read_term_campaign_map(launch.code)

    from frontend.db_readers.ads_meta import _categorize_campaign as _categorize_meta_campaign  # noqa: PLC0415
    from frontend.db_readers.ads_google import _categorize_campaign as _categorize_google_campaign  # noqa: PLC0415

    for email, utm in buyer_utms.items():
        source = utm["source"]
        medium = utm["medium"]
        campaign = utm["campaign"]
        content = utm["content"]
        term = utm.get("term", "")
        if not campaign and term and "google" in _norm_text(source):
            campaign = term_campaign_map.get(term, "")
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
            m_etapa, m_temp, m_bucket, m_segmento = _categorize_meta_campaign(campaign)
            # _categorize_meta_campaign só lê colchetes no NOME da campanha
            # ([MA][captação]...). Lançamentos com convenção de UTM antiga
            # (ex.: PI-ABR-26) guardam essa info no utm_source, não no
            # utm_campaign ("fb-captacao-quente-principal-v9" vs campaign
            # = só o código do lançamento) — cai tudo em "Outros". cls já
            # classificou certo pegando source+medium+campaign juntos (achado
            # 14/09/26); usa como fallback só quando a leitura estrita falhar,
            # sem mudar nada pra lançamentos que já classificam certo.
            if m_etapa == "Outros" and cls["etapa"] != "Outros":
                m_etapa = cls["etapa"]
            if m_temp == "Outros" and cls["temperatura"] != "Outros":
                m_temp = cls["temperatura"]
            _inc_sales(result["meta_etapa_sales"], m_etapa, receita_email, vendas_email)
            _inc_sales(result["meta_temperatura_sales"], m_temp, receita_email, vendas_email)
            _inc_sales(result["meta_bucket_sales"], m_bucket, receita_email, vendas_email)
            _inc_sales(result["meta_segmento_sales"], m_segmento, receita_email, vendas_email)
            result["meta_temperatura_sales_por_etapa"].setdefault(m_etapa, {})
            _inc_sales(result["meta_temperatura_sales_por_etapa"][m_etapa], m_temp, receita_email, vendas_email)
        elif cls["channel"] == "Google Ads":
            _inc_sales(result["google_por_etapa"], cls["etapa"], receita_email, vendas_email)
            _inc_sales(result["google_por_temperatura"], cls["temperatura"], receita_email, vendas_email)
            google_type = _classify_google_campaign_type(campaign, source, medium, content, term)
            _inc_sales(result["google_por_tipo_campanha"], google_type, receita_email, vendas_email)
            google_campaign_key = _norm_text(campaign)
            if google_campaign_key:
                _inc_sales(result["google_por_campanha"], google_campaign_key, receita_email, vendas_email)
            g_etapa, g_temp, g_segmento = _categorize_google_campaign(campaign)
            # Mesmo fallback do bloco Meta acima, mesmo motivo.
            if g_etapa == "Outros" and cls["etapa"] != "Outros":
                g_etapa = cls["etapa"]
            if g_temp == "Outros" and cls["temperatura"] != "Outros":
                g_temp = cls["temperatura"]
            _inc_sales(result["google_etapa_sales"], g_etapa, receita_email, vendas_email)
            _inc_sales(result["google_temperatura_sales"], g_temp, receita_email, vendas_email)
            _inc_sales(result["google_segmento_sales"], g_segmento, receita_email, vendas_email)
            result["google_temperatura_sales_por_etapa"].setdefault(g_etapa, {})
            _inc_sales(result["google_temperatura_sales_por_etapa"][g_etapa], g_temp, receita_email, vendas_email)
            if campaign:
                _inc_sales(result["google_campanha_sales"], campaign, receita_email, vendas_email)
        ad_code = _extract_ad_code(f"{source} {medium} {campaign} {content} {term}")
        if ad_code:
            _inc_sales(result["por_criativo"], ad_code, receita_email, vendas_email)
            result["por_criativo_por_etapa"].setdefault(cls["etapa"], {})
            _inc_sales(result["por_criativo_por_etapa"][cls["etapa"]], ad_code, receita_email, vendas_email)
            # O mesmo ADxxx costuma aparecer com UTMs diferentes entre compradores
            # (veiculou na Meta e no Google, ou mudou de campanha no meio do
            # lançamento). Antes valia "o primeiro comprador que chegar vence" —
            # e a ordem vinha do banco, sem ORDER BY, então o representante mudava
            # a cada recomputação do cache. Pior que instável: se o sorteado fosse
            # um UTM da Meta, nenhuma campanha Google casava lá embaixo, o gasto
            # dava zero e o criativo era descartado do ranking principal.
            # Agora acumula tudo e o representante é determinístico.
            detected = re.findall(r"\b(?:PBB|PES|PI)-[A-Z]{3}-\d{2}\b", f"{source} {medium} {campaign} {content} {term}", flags=re.IGNORECASE)
            entry = result["por_criativo_utm"].get(ad_code)
            if entry is None:
                entry = result["por_criativo_utm"][ad_code] = {
                    "source": source,
                    "medium": medium,
                    "campaign": campaign,
                    "content": content,
                    "term": term,
                    "launches": [],
                    "campaigns": [],
                }
            entry["launches"] = sorted(set(entry["launches"]) | {item.upper() for item in detected})
            if campaign:
                entry["campaigns"] = sorted(set(entry["campaigns"]) | {campaign})
            _chave_atual = tuple(str(entry[k] or "") for k in ("source", "medium", "campaign", "content", "term"))
            _chave_nova = tuple(str(v or "") for v in (source, medium, campaign, content, term))
            if _chave_nova < _chave_atual:
                entry.update(source=source, medium=medium, campaign=campaign, content=content, term=term)
            if _norm_text(launch.code) in _norm_text(f"{source} {medium} {campaign} {content} {term}"):
                result["por_criativo_lancamento_atual"].add(ad_code)
            if cls["channel"] not in result["por_criativo_canal"]:
                result["por_criativo_canal"][cls["channel"]] = {}
            _inc_sales(result["por_criativo_canal"][cls["channel"]], ad_code, receita_email, vendas_email)
            result["por_criativo_canal_por_etapa"].setdefault(cls["channel"], {}).setdefault(cls["etapa"], {})
            _inc_sales(result["por_criativo_canal_por_etapa"][cls["channel"]][cls["etapa"]], ad_code, receita_email, vendas_email)
        elif cls["channel"] == "Google Ads":
            google_type = _classify_google_campaign_type(campaign, source, medium, content, term)
            _inc_sales(result["google_sem_ad_por_tipo"], google_type, receita_email, vendas_email)
            google_campaign_key = _norm_text(campaign)
            if google_campaign_key:
                _inc_sales(result["google_sem_ad_por_campanha"], google_campaign_key, receita_email, vendas_email)
    _set_cached(launch.code, "sales_attribution", result)
    return result
