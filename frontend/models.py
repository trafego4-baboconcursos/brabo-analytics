"""
frontend/models.py — Dataclasses de domínio do Brabo Analytics.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any


# ── Lançamentos ───────────────────────────────────────────────────────────────

@dataclass
class Launch:
    code: str
    folder: Any  # Path ou compatibilidade legada
    accent: str
    short: str
    name: str
    product: str = ""
    product_name: str = ""
    product_order: int = 99
    has_meta: bool = False
    has_google: bool = False
    has_vendas: bool = False
    has_hotmart: bool = False
    has_tmb: bool = False
    has_ac: bool = False
    has_typeform: bool = False
    project: str = ""
    data_inicio: date = None
    data_fim: date = None


# ── Mídia — Meta Ads ──────────────────────────────────────────────────────────

@dataclass
class MetaCriativo:
    nome: str
    campanha: str
    conjunto: str
    etapa: str
    temperatura: str
    bucket: str
    gasto: float = 0.0
    impressoes: int = 0
    alcance: int = 0
    cliques: int = 0
    leads: int = 0
    thruplays: int = 0
    cpl: float = 0.0
    ctr: float = 0.0
    cpc: float = 0.0
    cpm: float = 0.0
    custo_thruplay: float = 0.0
    ad_code: str = ""
    hook_rate: float = 0.0
    hold_rate: float = 0.0
    body_rate: float = 0.0

@dataclass
class MetaSummary:
    total_gasto: float = 0.0
    total_leads: int = 0
    total_cliques: int = 0
    total_impressoes: int = 0
    total_thruplays: int = 0
    cpl_medio: float = 0.0
    ctr_medio: float = 0.0
    cpm_medio: float = 0.0
    por_etapa: dict = field(default_factory=dict)
    por_temperatura: dict = field(default_factory=dict)
    por_temperatura_captacao: dict = field(default_factory=dict)
    por_bucket: dict = field(default_factory=dict)
    por_segmento: dict = field(default_factory=dict)
    remarketing_por_adset: list = field(default_factory=list)
    por_dia: list = field(default_factory=list)
    top_por_leads: list = field(default_factory=list)
    top_por_cpl: list = field(default_factory=list)
    piores_cpl: list = field(default_factory=list)
    validados: list = field(default_factory=list)
    novos: list = field(default_factory=list)
    captacao_por_ad: list = field(default_factory=list)
    preq_por_ad: list = field(default_factory=list)
    publicos: list = field(default_factory=list)
    por_publico_captacao: dict = field(default_factory=dict)
    demografia_idade: list = field(default_factory=list)
    demografia_genero: list = field(default_factory=list)
    data_inicio: str = ""
    data_fim: str = ""


# ── Mídia — Google Ads ────────────────────────────────────────────────────────

@dataclass
class GoogleCampanha:
    nome: str
    etapa: str
    temperatura: str
    tipo: str = ""
    cliques: int = 0
    impressoes: int = 0
    ctr: float = 0.0
    custo: float = 0.0
    cpc: float = 0.0
    conversoes: float = 0.0
    custo_conv: float = 0.0
    taxa_conv: float = 0.0
    visualizacoes: int = 0

@dataclass
class GooglePublico:
    segmento: str
    campanha: str
    grupo: str
    cliques: int = 0
    impressoes: int = 0
    custo: float = 0.0
    conversoes: float = 0.0
    ctr: float = 0.0
    cpc: float = 0.0

@dataclass
class GoogleSummary:
    total_custo: float = 0.0
    total_cliques: int = 0
    total_impressoes: int = 0
    total_conversoes: float = 0.0
    total_visualizacoes: int = 0
    custo_conv_medio: float = 0.0
    ctr_medio: float = 0.0
    por_etapa: dict = field(default_factory=dict)
    por_temperatura: dict = field(default_factory=dict)
    por_segmento: dict = field(default_factory=dict)
    campanhas: list = field(default_factory=list)
    publicos: list = field(default_factory=list)
    por_publico_captacao: dict = field(default_factory=dict)
    demografia_idade: list = field(default_factory=list)
    demografia_genero: list = field(default_factory=list)
    anuncios_por_ad: list = field(default_factory=list)
    preq_por_ad: list = field(default_factory=list)
    data_inicio: str = ""
    data_fim: str = ""


# ── Vendas ────────────────────────────────────────────────────────────────────

@dataclass
class VendasSummary:
    hotmart_vendas: int = 0
    hotmart_receita: float = 0.0
    hotmart_receita_bruta: float = 0.0
    hotmart_receita_liquida: float = 0.0
    hotmart_ticket_medio: float = 0.0
    tmb_vendas: int = 0
    tmb_receita: float = 0.0
    tmb_receita_bruta: float = 0.0
    tmb_ticket_medio: float = 0.0
    total_vendas: int = 0
    total_receita: float = 0.0
    total_receita_bruta: float = 0.0
    total_receita_liquida: float = 0.0
    total_ticket_medio: float = 0.0
    pagamento_cartao: int = 0
    pagamento_boleto: int = 0
    pagamento_pix: int = 0
    pagamento_outros: int = 0
    por_status: dict = field(default_factory=dict)
    emails_hotmart: set[str] = field(default_factory=set)
    emails_tmb: set[str] = field(default_factory=set)
    receita_por_email: dict[str, float] = field(default_factory=dict)
    vendas_por_email: dict[str, int] = field(default_factory=dict)
    phone_por_email: dict[str, str] = field(default_factory=dict)
    por_canal: dict[str, dict] = field(default_factory=dict)
    estado_por_email: dict[str, str] = field(default_factory=dict)
    canal_por_email: dict[str, str] = field(default_factory=dict)
    nome_por_email: dict[str, str] = field(default_factory=dict)

@dataclass
class LeadsSummary:
    total_leads: int = 0
    compradores_rastreados: int = 0
    compradores_sem_utm: int = 0
    total_compradores: int = 0
    cpl: float = 0.0
    tx_conversao: float = 0.0
    por_utm_source: dict = field(default_factory=dict)
    por_utm_medium: dict = field(default_factory=dict)
    emails_rastreados: set[str] = field(default_factory=set)
    por_canal: list = field(default_factory=list)
    por_dia: list = field(default_factory=list)
    por_etapa: list = field(default_factory=list)
    por_temperatura: list = field(default_factory=list)

@dataclass
class HotmartDetails:
    file_name: str = "Supabase DB"
    has_data: bool = False
    total_emitidos: int = 0
    total_vendas: int = 0
    faturamento: float = 0.0
    receita_bruta: float = 0.0
    receita_liquida: float = 0.0
    taxas: float = 0.0
    taxas_pct: float = 0.0
    ticket_medio: float = 0.0
    total_cancelados: int = 0
    taxa_cancelamento: float = 0.0
    taxa_boleto_gerado: float = 0.0
    total_reclamacoes: int = 0
    taxa_reclamacao: float = 0.0
    boleto_emitido_qtd: int = 0
    boleto_pago_qtd: int = 0
    taxa_conversao_boleto: float = 0.0
    pix_ticket: float = 0.0
    card_ticket: float = 0.0
    pix_premium: float = 0.0
    vendas_12x_pct: float = 0.0
    pagamentos: list[dict] = field(default_factory=list)
    parcelas: list[dict] = field(default_factory=list)
    fluxo_caixa: dict = field(default_factory=dict)
    timeline: list[dict] = field(default_factory=list)
    ofertas: list[dict] = field(default_factory=list)
    estados: list[dict] = field(default_factory=list)
    cidades: list[dict] = field(default_factory=list)

@dataclass
class TmbDetails:
    file_name: str = "Supabase DB"
    has_data: bool = False
    total_emitidos: int = 0
    total_vendas: int = 0
    faturamento: float = 0.0
    ticket_medio: float = 0.0
    total_cancelados: int = 0
    taxa_cancelamento: float = 0.0
    status_emitidos: list[dict] = field(default_factory=list)
    timeline: list[dict] = field(default_factory=list)
    vendas_d1: int = 0
    vendas_d1_pct: float = 0.0
    ofertas: list[dict] = field(default_factory=list)
    com_utm_qtd: int = 0
    com_utm_pct: float = 0.0
    utm_sources: list[dict] = field(default_factory=list)
    estados: list[dict] = field(default_factory=list)
    cidades: list[dict] = field(default_factory=list)

@dataclass
class YoutubeAulaStat:
    aula_num: int = 0
    video_id: str = ""
    titulo: str = ""
    duration_sec: int = 0
    views_total: int = 0
    views_live: int = 0
    views_replay: int = 0
    likes: int = 0
    comments: int = 0
    watch_time_min: float = 0.0
    avg_view_dur_sec: float = 0.0
    avg_view_pct: float = 0.0
    peak_concurrent: int = 0

@dataclass
class ConsolidadoVendasSummary:
    has_data: bool = False
    total_receita: float = 0.0
    total_transacoes: int = 0
    compradores_unicos: int = 0
    ticket_medio: float = 0.0
    fechamento: list[dict] = field(default_factory=list)
    leads_crm: int = 0
    compradores_crm: int = 0
    compradores_sem_crm: int = 0
    tx_compradores_crm_pct: float = 0.0
    canais: list[dict] = field(default_factory=list)
    propensao_uf: list[dict] = field(default_factory=list)
    conversao_lead_venda: float = 0.0
    compradores_typeform: int = 0
    top_canais: list[dict] = field(default_factory=list)
    top_campanhas: list[dict] = field(default_factory=list)
    top_estados: list[dict] = field(default_factory=list)
    propensao: list[dict] = field(default_factory=list)
    genero: list[dict] = field(default_factory=list)
    idade: list[dict] = field(default_factory=list)
    escolaridade: list[dict] = field(default_factory=list)
    situacao_prof: list[dict] = field(default_factory=list)
    top_origem_nome: str = ""
    top_origem_compradores: int = 0
    top_origem_faturamento: float = 0.0
    top_origem_ticket: float = 0.0
    top_estado_nome: str = ""
    top_estado_compradores: int = 0
    top_estado_faturamento: float = 0.0
    volume_insight: dict | None = None
    ticket_insight: dict | None = None
    conv_insight: dict | None = None
    top_cidades: list[dict] = field(default_factory=list)


# ── Typeform ──────────────────────────────────────────────────────────────────

@dataclass
class TypeformSummary:
    has_data: bool = False
    total_tf_raw: int = 0
    total_tf: int = 0
    tf_leads_crm: int = 0
    tf_compras: int = 0
    tf_compras_crm: int = 0
    tx_lead_pct: float = 0.0
    tx_venda_tf_pct: float = 0.0
    tx_venda_lead_pct: float = 0.0
    receita_tf: float = 0.0
    receita_total: float = 0.0
    receita_tf_pct: float = 0.0
    genero_comp_pct: dict[str, float] = field(default_factory=dict)
    genero_ncomp_pct: dict[str, float] = field(default_factory=dict)
    genero_diff: dict[str, float] = field(default_factory=dict)
    situacao_comp_pct: dict[str, float] = field(default_factory=dict)
    situacao_ncomp_pct: dict[str, float] = field(default_factory=dict)
    situacao_diff: dict[str, float] = field(default_factory=dict)
    nivel_comp_pct: dict[str, float] = field(default_factory=dict)
    nivel_ncomp_pct: dict[str, float] = field(default_factory=dict)
    nivel_diff: dict[str, float] = field(default_factory=dict)
    idade_comp_pct: dict[str, float] = field(default_factory=dict)
    idade_ncomp_pct: dict[str, float] = field(default_factory=dict)
    idade_diff: dict[str, float] = field(default_factory=dict)
    graton_comp_pct: dict[str, float] = field(default_factory=dict)
    graton_ncomp_pct: dict[str, float] = field(default_factory=dict)
    graton_diff: dict[str, float] = field(default_factory=dict)
    obstaculos_comp_pct: dict[str, float] = field(default_factory=dict)
    obstaculos_ncomp_pct: dict[str, float] = field(default_factory=dict)
    obstaculos_diff: dict[str, float] = field(default_factory=dict)
    top_estados_comp: list[dict] = field(default_factory=list)
    top_estados_geral: list[dict] = field(default_factory=list)
    top_utm_sources: list[dict] = field(default_factory=list)
    top_influence_factors: list[dict] = field(default_factory=list)
    alunos_depoimentos_decidir: list[str] = field(default_factory=list)
    alunos_depoimentos_convenceu: list[str] = field(default_factory=list)
    alunos_depoimentos_atencao: list[str] = field(default_factory=list)
    ia_insights: list[dict] = field(default_factory=list)
    leads_crm_total: int = 0
    vendas_hotmart_total: int = 0
    vendas_tmb_total: int = 0
    tf_file_name: str = "Supabase DB"
    leads_file_name: str = "Supabase DB"
    hotmart_file_name: str = "Supabase DB"
    tmb_file_name: str = "Supabase DB"
    compare_available: bool = False
    compare_identical: bool = False
    compare_label_a: str = ""
    compare_label_b: str = ""
    compare_total_a: int = 0
    compare_total_b: int = 0
    compare_overlap: int = 0
    compare_only_a: int = 0
    compare_only_b: int = 0
    compare_insights: list[str] = field(default_factory=list)


# ── Active Campaign ───────────────────────────────────────────────────────────

@dataclass
class AcCampaign:
    id: str
    nome: str
    data_envio: str
    envios: int = 0
    aberturas: int = 0
    aberturas_unicas: int = 0
    cliques: int = 0
    descadastros: int = 0
    bounces: int = 0
    tx_abertura: float = 0.0
    tx_clique: float = 0.0
    tx_descadastro: float = 0.0

@dataclass
class AcCampaignSummary:
    has_data: bool = False
    total_envios: int = 0
    total_aberturas: int = 0
    total_cliques: int = 0
    tx_abertura_media: float = 0.0
    tx_clique_media: float = 0.0
    campanhas: list[AcCampaign] = field(default_factory=list)
    por_dia: list[dict] = field(default_factory=list)


# ── Comparativo entre lançamentos ─────────────────────────────────────────────

@dataclass
class ComparativoAd:
    nome: str
    inv: float = 0.0
    leads: int = 0
    vendas: int = 0
    cpl: float = 0.0
    cpa: float = 0.0
    total_vendido: float = 0.0

@dataclass
class ComparativoData:
    has_data: bool = False
    code_a: str = ""
    code_b: str = ""
    accent_a: str = "#667eea"
    accent_b: str = "#f5576c"
    inv_a: float = 0.0
    inv_b: float = 0.0
    inv_meta_a: float = 0.0
    inv_meta_b: float = 0.0
    inv_google_a: float = 0.0
    inv_google_b: float = 0.0
    leads_a: int = 0
    leads_b: int = 0
    cpl_a: float = 0.0
    cpl_b: float = 0.0
    inv_prequali_a: float = 0.0
    inv_prequali_b: float = 0.0
    cpl_geral_a: float = 0.0
    cpl_geral_b: float = 0.0
    por_segmento: list = field(default_factory=list)
    dia1_a: dict = field(default_factory=dict)
    dia1_b: dict = field(default_factory=dict)
    dia1_a2: dict = field(default_factory=dict)
    code_a2: str = ""
    google_conv_a: int = 0
    google_conv_b: int = 0
    google_cpa_a: float = 0.0
    google_cpa_b: float = 0.0
    google_camps_a: int = 0
    google_camps_b: int = 0
    google_cpc_a: float = 0.0
    google_cpc_b: float = 0.0
    google_ctr_a: float = 0.0
    google_ctr_b: float = 0.0
    meta_leads_a: int = 0
    meta_leads_b: int = 0
    meta_cpl_a: float = 0.0
    meta_cpl_b: float = 0.0
    meta_ads_a: int = 0
    meta_ads_b: int = 0
    funil_a: dict = field(default_factory=dict)
    funil_b: dict = field(default_factory=dict)
    vendas_a: int = 0
    vendas_b: int = 0
    hotmart_a: int = 0
    hotmart_b: int = 0
    tmb_a: int = 0
    tmb_b: int = 0
    receita_a: float = 0.0
    receita_b: float = 0.0
    ticket_a: float = 0.0
    ticket_b: float = 0.0
    roas_a: float = 0.0
    roas_b: float = 0.0
    tx_conv_a: float = 0.0
    tx_conv_b: float = 0.0
    cpa_a: float = 0.0
    cpa_b: float = 0.0
    top_ads_a: list = field(default_factory=list)
    top_ads_b: list = field(default_factory=list)
    top_google_a: list = field(default_factory=list)
    top_google_b: list = field(default_factory=list)
    canal_quality: list = field(default_factory=list)
