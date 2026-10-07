"""Padrões da casa para criar e operar campanhas — fonte única dos valores fixos.

Explicação de cada item em docs/performance/playbooks/MANUAL_OPERACAO_ADS.md. Mudou um padrão? Muda aqui e
no manual, no mesmo commit.
"""
from __future__ import annotations

# --------------------------------------------------------------------------- Meta (Facebook/Instagram)
GRAPH_VERSAO = "v21.0"

# Contas de anúncio. Mateus e Ivan dividem a CA2-Anunciante na Black; a conta própria do Ivan
# (act_1572917053349409) é dos lançamentos regulares do PES.
META_CONTAS = {
    "ca2_anunciante": "act_1407542209639031",   # Mateus (INSS) + Ivan (TJ-SP) nas Blacks
    "ca2_publicos": "act_1025995894927376",     # pool de públicos (compartilhar com a conta da campanha)
    "felipe_nova": "act_1175937361058463",      # Felipe (BB) — "CA - Felipe Graton (Nova)"
    "felipe_antiga": "act_438212624024216",     # Felipe, anterior (BV-25 e perpétuo)
    "ivan_pes": "act_1572917053349409",         # "CA Ivan Anunciante" — PES regular
}

# Identidade de cada expert no Meta: página que publica, Instagram e pixel da conta.
# A conta Felipe Nova NÃO acessa o pixel 608 (subcode 1815045) — usar o 990.
META_EXPERTS = {
    "mateus": {"page_id": "1960068844278670", "instagram_user_id": "17841402341156659",
               "pixel_id": "608218362997432", "conta": META_CONTAS["ca2_anunciante"]},
    "ivan": {"page_id": "109116185339128", "instagram_user_id": "17841456180884668",   # página Brabo Concursos
             "pixel_id": "608218362997432", "conta": META_CONTAS["ca2_anunciante"]},
    "felipe": {"page_id": "418887747980692", "instagram_user_id": "17841460679248187",
               "pixel_id": "990033038146806", "conta": META_CONTAS["felipe_nova"]},
}

# UTM padrão — vai no campo url_tags do criativo, NUNCA concatenada no link.
UTM_META = ("utm_source=facebook&utm_medium=paid_social&utm_campaign={{campaign.name}}"
            "&utm_content={{adset.name}}&utm_term={{ad.name}}&vk_source=paid_metaads&vk_ad_id={{ad.id}}")

IDADE_MIN, IDADE_MAX = 25, 55

# Regulação regional do Brasil: obrigatória em ad set com geo BR (subcode 3858634 sem ela).
# ID de "Identificação" do anunciante verificado (APROVASIM CURSOS TREINAMENTOS E COACHING LTDA).
REGULACAO_BR = {
    "regional_regulated_categories": ["BRAZIL_REGULATION"],
    "regional_regulation_identities": {"universal_beneficiary": "962929000162121",
                                       "universal_payer": "962929000162121"},
}

# location_types e chave da região conferidos nos ad sets vivos (29/09/26).
GEO_BRASIL = {"countries": ["BR"], "location_types": ["frequently_in", "home", "recent"]}
GEO_SAO_PAULO = {"regions": [{"key": "460"}], "location_types": ["frequently_in", "home", "recent"]}  # TJ-SP (PES)

# Posicionamentos. "Reels" no nome da campanha = só Story + Reels, sem Feed.
POSICOES_REELS = {"publisher_platforms": ["facebook", "instagram"],
                  "facebook_positions": ["story", "facebook_reels"],
                  "instagram_positions": ["story", "reels"]}
POSICOES_FEED = {"publisher_platforms": ["facebook", "instagram"],
                 "facebook_positions": ["feed"], "instagram_positions": ["stream"]}

# Ad set de captação (lead) — o que as campanhas vivas usam.
ADSET_LEAD = {"optimization_goal": "OFFSITE_CONVERSIONS", "billing_event": "IMPRESSIONS",
              "destination_type": "WEBSITE",
              "attribution_spec": [{"event_type": "CLICK_THROUGH", "window_days": 7}]}
# Ad set de aquecimento (ThruPlay) — promoted_object={"page_id": ...} é obrigatório e imutável.
ADSET_THRUPLAY = {"optimization_goal": "THRUPLAY", "billing_event": "IMPRESSIONS", "destination_type": "ON_VIDEO"}

# Mínimo de verba diária por campanha CBO observado (abaixo disso o Meta recusa, subcode 1885650).
META_CBO_MINIMO = 24.00

# --------------------------------------------------------------------------- Google Ads
GOOGLE_API_VERSAO = "v22"
GOOGLE_MCC = "9335944411"          # login-customer-id e login_account da Data Manager
GOOGLE_CONTAS = {
    "lancamentos": "6482320788",   # Mateus (INSS) + Ivan (TJ-SP) — tag AW-828953349
    "felipe": "1450466453",        # Felipe (BB) — tag AW-1001175831
}
GOOGLE_AW = {"6482320788": "AW-828953349", "1450466453": "AW-1001175831"}

# Metas de conversão usadas na Base Forte / Black (nível da campanha, sobrepõem as da conta).
GOOGLE_CONVERSAO_LEAD = {"6482320788": "[TYP PES-26]", "1450466453": "[TYP-PBB-26] [LEADS]"}

GEO_GOOGLE_BRASIL = "geoTargetConstants/2076"
GEO_GOOGLE_SAO_PAULO = "geoTargetConstants/20106"
IDIOMAS_GOOGLE = ["languageConstants/1000", "languageConstants/1003", "languageConstants/1014"]  # en, es, pt

# Piso de verba diária do Demand Gen com Target CPA (abaixo disso o Google recusa).
DEMAND_GEN_TCPA_MINIMO = 25.40

# Duração padrão das listas de site (regra de URL). 0 = a pessoa sai da lista na hora (erro real, BV-26).
LISTA_SITE_DURACAO = 540

# Parâmetros personalizados que o tracking_url_template usa — precisam existir nos 3 níveis.
GOOGLE_PARAMETROS = {"campanha": "campaignname", "grupo": "adgroupname", "anuncio": "adname"}

# --------------------------------------------------------------------------- Nomes
EXPERTS = ("mateus", "ivan", "felipe")
