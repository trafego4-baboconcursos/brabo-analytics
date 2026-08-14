-- ════════════════════════════════════════════════════════════════════════════
-- Schema ETL — Brabo Analytics
-- Execute no Supabase > SQL Editor
-- As tabelas de Hotmart e TMB já existem no Supabase; este script cria
-- apenas as tabelas novas para as demais fontes.
-- ════════════════════════════════════════════════════════════════════════════


-- ── LEADS (Active Campaign) ───────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS leads (
    id           TEXT PRIMARY KEY,          -- ID do contato no Active Campaign
    email        TEXT NOT NULL,
    created_at   TIMESTAMPTZ,
    utm_source   TEXT,
    utm_medium   TEXT,
    utm_campaign TEXT,
    utm_content  TEXT,                      -- chave de atribuição (ex: "AD110 - ...")
    utm_term     TEXT,
    nome         TEXT,
    sobrenome    TEXT,
    phone        TEXT,                      -- só dígitos, últimos 11 (DDD+número)
    updated_at   TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_leads_email       ON leads (email);
CREATE INDEX IF NOT EXISTS idx_leads_utm_content ON leads (utm_content);
CREATE INDEX IF NOT EXISTS idx_leads_created_at  ON leads (created_at);


-- ── META ADS — performance diária por anúncio ────────────────────────────
CREATE TABLE IF NOT EXISTS meta_ads_daily (
    id               BIGSERIAL PRIMARY KEY,
    date             DATE    NOT NULL,
    ad_id            TEXT    NOT NULL,         -- ID numérico do Facebook
    ad_name          TEXT,                     -- "AD110 - Banco do Brasil 2 - ..."
    adset_id         TEXT,
    adset_name       TEXT,
    campaign_id      TEXT,
    campaign_name    TEXT,
    impressions      INTEGER      DEFAULT 0,
    clicks           INTEGER      DEFAULT 0,   -- cliques no link (geral)
    spend            NUMERIC(12,2) DEFAULT 0,  -- em BRL
    leads            INTEGER      DEFAULT 0,   -- ação lead rastreada pelo pixel
    link_clicks      INTEGER      DEFAULT 0,
    outbound_clicks  INTEGER      DEFAULT 0,   -- cliques reais de saída para o site
    video_views_3s   INTEGER      DEFAULT 0,   -- views de 3 segundos
    video_views_25   INTEGER      DEFAULT 0,   -- views até 25% do vídeo
    video_views_50   INTEGER      DEFAULT 0,   -- views até 50% do vídeo
    video_views_75   INTEGER      DEFAULT 0,   -- views até 75% do vídeo
    video_views_100  INTEGER      DEFAULT 0,   -- views até 100% do vídeo
    video_thruplays  INTEGER      DEFAULT 0,   -- ThruPlays (15s+)
    lancamento_codigo TEXT,
    updated_at       TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (ad_id, date, lancamento_codigo)
);

CREATE INDEX IF NOT EXISTS idx_meta_date   ON meta_ads_daily (date);
CREATE INDEX IF NOT EXISTS idx_meta_ad_id  ON meta_ads_daily (ad_id);


-- ── GOOGLE ADS — performance diária por anúncio ──────────────────────────
CREATE TABLE IF NOT EXISTS google_ads_daily (
    id              BIGSERIAL PRIMARY KEY,
    date            DATE    NOT NULL,
    ad_id           TEXT    NOT NULL,         -- ID numérico do Google Ads
    ad_name         TEXT,                     -- "AD092 - Dois personagens casa do Thales - ..."
    ad_group_id     TEXT,
    ad_group_name   TEXT,
    campaign_id     TEXT,
    campaign_name   TEXT,
    impressions     INTEGER      DEFAULT 0,
    clicks          INTEGER      DEFAULT 0,
    cost            NUMERIC(12,2) DEFAULT 0,  -- em BRL (já convertido de micros)
    conversions     NUMERIC(10,2) DEFAULT 0,
    video_views     INTEGER      DEFAULT 0,   -- visualizações de vídeo
    video_views_25  INTEGER      DEFAULT 0,   -- views estimadas de 25%
    video_views_50  INTEGER      DEFAULT 0,   -- views estimadas de 50%
    video_views_75  INTEGER      DEFAULT 0,   -- views estimadas de 75%
    video_views_100 INTEGER      DEFAULT 0,   -- views estimadas de 100%
    lancamento_codigo TEXT,
    updated_at      TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (ad_id, date, lancamento_codigo)
);

CREATE INDEX IF NOT EXISTS idx_google_date   ON google_ads_daily (date);
CREATE INDEX IF NOT EXISTS idx_google_ad_id  ON google_ads_daily (ad_id);


-- ── TYPEFORM — respostas da pesquisa ─────────────────────────────────────
CREATE TABLE IF NOT EXISTS typeform_respostas (
    response_id  TEXT PRIMARY KEY,
    form_id      TEXT,
    submitted_at TIMESTAMPTZ,
    email        TEXT,
    answers      JSONB,                     -- respostas completas em JSON
    updated_at   TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_tf_email ON typeform_respostas (email);
CREATE INDEX IF NOT EXISTS idx_tf_date  ON typeform_respostas (submitted_at);


-- ── FUNÇÕES DUMMY PARA TRIGGERS DE VENDAS ──────────────────────────────────
CREATE OR REPLACE FUNCTION processar_comissao_tmb()
RETURNS TRIGGER AS $$
BEGIN
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION processar_comissao_hotmart()
RETURNS TRIGGER AS $$
BEGIN
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;


-- ── TABELAS OFICIAIS DE VENDAS ──────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS tmb_clean_oficial (
  pedido TEXT NOT NULL,
  produto TEXT NULL,
  oferta TEXT NULL,
  status TEXT NULL,
  data_efetivado TIMESTAMP WITHOUT TIME ZONE NULL,
  valor_liquido NUMERIC NULL,
  forma_pagamento TEXT NULL,
  nome_cliente TEXT NULL,
  email_cliente TEXT NULL,
  cpf_cliente TEXT NULL,
  telefone TEXT NULL,
  cidade TEXT NULL,
  estado TEXT NULL,
  utm_source TEXT NULL,
  utm_medium TEXT NULL,
  utm_campaign TEXT NULL,
  CONSTRAINT tmb_clean_oficial_pkey PRIMARY KEY (pedido)
) TABLESPACE pg_default;

-- Trigger TMB
DROP TRIGGER IF EXISTS trg_processar_tmb ON tmb_clean_oficial;
CREATE TRIGGER trg_processar_tmb
AFTER INSERT OR UPDATE ON tmb_clean_oficial
FOR EACH ROW EXECUTE FUNCTION processar_comissao_tmb();


CREATE TABLE IF NOT EXISTS hotmart_clean_oficial (
  codigo_da_transacao TEXT NOT NULL,
  status_da_transacao TEXT NULL,
  data_da_transacao TEXT NULL,
  confirmacao_do_pagamento TEXT NULL,
  produtor_a TEXT NULL,
  codigo_do_produto TEXT NULL,
  produto TEXT NULL,
  codigo_do_preco TEXT NULL,
  nome_deste_preco TEXT NULL,
  taxa_de_conversao_moeda_de_compra TEXT NULL,
  moeda_de_compra TEXT NULL,
  valor_de_compra_com_impostos TEXT NULL,
  impostos_locais_de_compra_taxa_de_parcelamento TEXT NULL,
  valor_de_compra_sem_impostos TEXT NULL,
  taxa_de_conversao_moeda_de_recebimento TEXT NULL,
  moeda_de_recebimento TEXT NULL,
  faturamento_bruto_sem_impostos TEXT NULL,
  faturamento_liquido TEXT NULL,
  venda_feita_como TEXT NULL,
  faturamento_liquido_do_a_produtor_a TEXT NULL,
  comissao_do_a_afiliado_a TEXT NULL,
  faturamento_do_a_coprodutor_a TEXT NULL,
  moeda_das_taxas TEXT NULL,
  taxa_de_processamento TEXT NULL,
  taxa_de_streaming TEXT NULL,
  outras_taxas TEXT NULL,
  nome_do_a_afiliado_a TEXT NULL,
  canal_usado_para_venda TEXT NULL,
  codigo_src TEXT NULL,
  codigo_sck TEXT NULL,
  metodo_de_pagamento TEXT NULL,
  tipo_de_cobranca TEXT NULL,
  quantidade_total_de_parcelas TEXT NULL,
  quantidade_de_cobrancas TEXT NULL,
  data_de_vencimento_vouchers TEXT NULL,
  codigo_de_cupom TEXT NULL,
  periodo_gratuito_trial TEXT NULL,
  quantidade_de_itens TEXT NULL,
  comprador_a TEXT NULL,
  email_do_a_comprador_a TEXT NULL,
  pais TEXT NULL,
  telefone TEXT NULL,
  documento TEXT NULL,
  codigo_postal TEXT NULL,
  cidade TEXT NULL,
  estado_provincia TEXT NULL,
  endereco TEXT NULL,
  bairro TEXT NULL,
  numero TEXT NULL,
  complemento TEXT NULL,
  instagram TEXT NULL,
  codigo_do_assinante TEXT NULL,
  tax_solutions TEXT NULL,
  tax_collected TEXT NULL,
  tax_jurisdiction TEXT NULL,
  ferramenta_de_venda TEXT NULL,
  transacao_do_produto_principal TEXT NULL,
  tipo_da_antecipacao_de_assinatura TEXT NULL,
  motivo_de_recusa_de_cartao TEXT NULL,
  imposto_sobre_servico_hotmart TEXT NULL,
  impostos_locais TEXT NULL,
  taxa_de_parcelamento TEXT NULL,
  valor_do_frete_bruto TEXT NULL,
  CONSTRAINT hotmart_clean_oficial_pkey PRIMARY KEY (codigo_da_transacao)
) TABLESPACE pg_default;

-- Trigger Hotmart
DROP TRIGGER IF EXISTS tr_processar_comissao_hotmart ON hotmart_clean_oficial;
CREATE TRIGGER tr_processar_comissao_hotmart
AFTER INSERT OR UPDATE OR DELETE ON hotmart_clean_oficial
FOR EACH ROW EXECUTE FUNCTION processar_comissao_hotmart();


-- ── DIMENSÃO LANÇAMENTOS ────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS dim_lancamentos (
    codigo       TEXT PRIMARY KEY,
    nome         TEXT NOT NULL,
    projeto      TEXT,
    data_inicio  DATE NOT NULL,
    data_fim     DATE NOT NULL,
    updated_at   TIMESTAMPTZ DEFAULT NOW()
);


-- ── COLUNAS E ÍNDICES OPERACIONAIS ──────────────────────────────────────────
ALTER TABLE meta_ads_daily ADD COLUMN IF NOT EXISTS lancamento_codigo TEXT;
ALTER TABLE google_ads_daily ADD COLUMN IF NOT EXISTS lancamento_codigo TEXT;
ALTER TABLE leads ADD COLUMN IF NOT EXISTS lancamento_codigo TEXT;

CREATE INDEX IF NOT EXISTS idx_meta_lancamento ON meta_ads_daily(lancamento_codigo);
CREATE INDEX IF NOT EXISTS idx_google_lancamento ON google_ads_daily(lancamento_codigo);
CREATE INDEX IF NOT EXISTS idx_leads_lancamento ON leads(lancamento_codigo);

ALTER TABLE meta_ads_daily DROP CONSTRAINT IF EXISTS meta_ads_daily_ad_id_date_key;
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'meta_ads_daily_ad_id_date_lancamento_key'
    ) THEN
        ALTER TABLE meta_ads_daily
        ADD CONSTRAINT meta_ads_daily_ad_id_date_lancamento_key
        UNIQUE (ad_id, date, lancamento_codigo);
    END IF;
END $$;

ALTER TABLE google_ads_daily DROP CONSTRAINT IF EXISTS google_ads_daily_ad_id_date_key;
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'google_ads_daily_ad_id_date_lancamento_key'
    ) THEN
        ALTER TABLE google_ads_daily
        ADD CONSTRAINT google_ads_daily_ad_id_date_lancamento_key
        UNIQUE (ad_id, date, lancamento_codigo);
    END IF;
END $$;


-- ════════════════════════════════════════════════════════════════════════════
-- DROPS DE VIEWS ANTIGAS (evita conflito ao alterar a assinatura de colunas)
-- ════════════════════════════════════════════════════════════════════════════
DROP VIEW IF EXISTS view_atribuicao CASCADE;
DROP VIEW IF EXISTS view_investimento_total_por_ad CASCADE;
DROP VIEW IF EXISTS view_meta_performance_criativos CASCADE;
DROP VIEW IF EXISTS view_google_performance_criativos CASCADE;
DROP VIEW IF EXISTS view_meta_spend_por_ad CASCADE;
DROP VIEW IF EXISTS view_google_spend_por_ad CASCADE;


-- ════════════════════════════════════════════════════════════════════════════
-- VIEWS DE SPEND — fontes de mídia agregadas por código de anúncio (ADXXX)
-- ════════════════════════════════════════════════════════════════════════════

CREATE OR REPLACE VIEW view_meta_spend_por_ad AS
SELECT
    upper(regexp_replace(ad_name, '^(AD\d+).*', '\1'))  AS ad_code,
    ad_name,
    lancamento_codigo,
    SUM(spend)       AS investimento,
    SUM(impressions) AS impressoes,
    SUM(clicks)      AS cliques,
    SUM(leads)       AS leads_pixel
FROM meta_ads_daily
GROUP BY ad_name, lancamento_codigo;


CREATE OR REPLACE VIEW view_google_spend_por_ad AS
SELECT
    upper(regexp_replace(ad_name, '^(AD\d+).*', '\1'))  AS ad_code,
    ad_name,
    lancamento_codigo,
    SUM(cost)        AS investimento,
    SUM(impressions) AS impressoes,
    SUM(clicks)      AS cliques,
    SUM(conversions) AS conversoes
FROM google_ads_daily
GROUP BY ad_name, lancamento_codigo;


CREATE OR REPLACE VIEW view_meta_performance_criativos AS
SELECT
    upper(regexp_replace(ad_name, '^(AD\d+).*', '\1'))  AS ad_code,
    ad_name,
    lancamento_codigo,
    SUM(spend)                                          AS investimento,
    SUM(impressions)                                    AS impressoes,
    SUM(clicks)                                         AS cliques_todos,
    SUM(outbound_clicks)                                AS cliques_site,
    SUM(leads)                                          AS leads_pixel,
    SUM(video_views_3s)                                 AS views_3s,
    SUM(video_thruplays)                                AS thruplays,
    SUM(video_views_25)                                 AS views_25,
    SUM(video_views_50)                                 AS views_50,
    SUM(video_views_75)                                 AS views_75,
    SUM(video_views_100)                                AS views_100,
    -- Métricas de Performance de Vídeo
    CASE WHEN SUM(video_views_3s) > 0 
         THEN SUM(spend) / SUM(video_views_3s) 
         ELSE 0 END                                     AS cpv_3s,
    CASE WHEN SUM(impressions) > 0 
         THEN CAST(SUM(video_views_3s) AS NUMERIC) / SUM(impressions) 
         ELSE 0 END                                     AS hook_rate, -- Taxa de Gancho (3s/Imp)
    CASE WHEN SUM(video_views_3s) > 0 
         THEN CAST(SUM(video_thruplays) AS NUMERIC) / SUM(video_views_3s) 
         ELSE 0 END                                     AS hold_rate -- Taxa de Retenção (Thruplay/3s)
FROM meta_ads_daily
GROUP BY ad_name, lancamento_codigo;


CREATE OR REPLACE VIEW view_google_performance_criativos AS
SELECT
    upper(regexp_replace(ad_name, '^(AD\d+).*', '\1'))  AS ad_code,
    ad_name,
    lancamento_codigo,
    SUM(cost)                                           AS investimento,
    SUM(impressions)                                    AS impressoes,
    SUM(clicks)                                         AS cliques,
    SUM(conversions)                                    AS conversoes_pixel,
    SUM(video_views)                                    AS video_views,
    SUM(video_views_25)                                 AS views_25,
    SUM(video_views_50)                                 AS views_50,
    SUM(video_views_75)                                 AS views_75,
    SUM(video_views_100)                                AS views_100,
    -- Métricas de Performance de Vídeo
    CASE WHEN SUM(video_views) > 0 
         THEN SUM(cost) / SUM(video_views) 
         ELSE 0 END                                     AS cpv,
    CASE WHEN SUM(impressions) > 0 
         THEN CAST(SUM(video_views) AS NUMERIC) / SUM(impressions) 
         ELSE 0 END                                     AS hook_rate, -- Taxa de Gancho
    CASE WHEN SUM(video_views) > 0 
         THEN CAST(SUM(video_views_100) AS NUMERIC) / SUM(video_views) 
         ELSE 0 END                                     AS completion_rate -- Taxa de Conclusão (100%/Views)
FROM google_ads_daily
GROUP BY ad_name, lancamento_codigo;


CREATE OR REPLACE VIEW view_investimento_total_por_ad AS
SELECT
    COALESCE(m.ad_code, g.ad_code) AS ad_code,
    COALESCE(m.lancamento_codigo, g.lancamento_codigo) AS lancamento_codigo,
    COALESCE(m.investimento, 0)    AS investimento_meta,
    COALESCE(g.investimento, 0)    AS investimento_google,
    COALESCE(m.investimento, 0) + COALESCE(g.investimento, 0) AS investimento_total
FROM view_meta_spend_por_ad    m
FULL OUTER JOIN view_google_spend_por_ad g USING (ad_code, lancamento_codigo);


-- ════════════════════════════════════════════════════════════════════════════
-- VIEW PRINCIPAL DE ATRIBUIÇÃO (LEAD → VENDA → ROAS)
-- ════════════════════════════════════════════════════════════════════════════

CREATE OR REPLACE VIEW view_atribuicao AS
WITH

-- Extrai código ADXXX do campo de anúncio (utm_term nas UTMs novas, utm_content nas antigas)
leads_por_ad AS (
    SELECT
        upper(regexp_replace(
            COALESCE(NULLIF(l.utm_term, ''), NULLIF(l.utm_content, '')),
            '^(AD\d+).*', '\1'
        )) AS ad_code,
        COALESCE(NULLIF(l.utm_term, ''), NULLIF(l.utm_content, '')) AS utm_ad_name,
        l.email,
        l.created_at,
        l.lancamento_codigo,
        dl.projeto
    FROM leads l
    LEFT JOIN dim_lancamentos dl ON dl.codigo = l.lancamento_codigo
    WHERE (l.utm_content IS NOT NULL AND l.utm_content <> '')
       OR (l.utm_term    IS NOT NULL AND l.utm_term    <> '')
),

-- Vendas Hotmart por lead e projeto
vendas_hotmart AS (
    SELECT
        lower(trim(email_do_a_comprador_a))  AS email,
        CASE 
            WHEN produto ILIKE '%inss%' THEN 'INSS'
            WHEN (produto ILIKE '%tj%' OR produto ILIKE '%tjsp%') THEN 'TJ'
            WHEN (produto ILIKE '%bb%' OR produto ILIKE '%banco do brasil%' OR produto ILIKE '%bbsa%') THEN 'BB'
            ELSE 'OUTRO'
        END AS projeto_venda,
        SUM(CAST(NULLIF(faturamento_liquido, '') AS NUMERIC)) AS faturamento,
        COUNT(*)            AS transacoes
    FROM hotmart_clean_oficial
    WHERE status_da_transacao IN ('Completa', 'Aprovada', 'Paga', 'Completo', 'Aprovado', 'Pago', 'approved', 'complete', 'Completo')
    GROUP BY 1, 2
),

-- Vendas TMB por lead e projeto
vendas_tmb AS (
    SELECT
        lower(trim(email_cliente))  AS email,
        CASE 
            WHEN produto ILIKE '%inss%' THEN 'INSS'
            WHEN (produto ILIKE '%tj%' OR produto ILIKE '%tjsp%') THEN 'TJ'
            WHEN (produto ILIKE '%bb%' OR produto ILIKE '%banco do brasil%' OR produto ILIKE '%bbsa%') THEN 'BB'
            ELSE 'OUTRO'
        END AS projeto_venda,
        SUM(valor_liquido)          AS faturamento,
        COUNT(*)            AS transacoes
    FROM tmb_clean_oficial
    WHERE status IN ('Vigente', 'Efetivado', 'Pago', 'Em dia', 'Integralizado', 'Aprovado', 'Concluido', 'Active')
    GROUP BY 1, 2
)

SELECT
    l.ad_code,
    l.utm_ad_name                                                           AS ad_name,
    l.lancamento_codigo,
    COUNT(DISTINCT l.email)                                                 AS leads,
    COUNT(DISTINCT CASE WHEN (h.email IS NOT NULL OR t.email IS NOT NULL)
                        THEN l.email END)                                   AS vendas,
    COALESCE(SUM(h.faturamento), 0) + COALESCE(SUM(t.faturamento), 0)      AS faturamento_total,
    sp.investimento_total,
    CASE
        WHEN sp.investimento_total > 0
        THEN (COALESCE(SUM(h.faturamento), 0) + COALESCE(SUM(t.faturamento), 0))
             / sp.investimento_total
        ELSE NULL
    END                                                                     AS roas,
    CASE
        WHEN COUNT(DISTINCT CASE WHEN (h.email IS NOT NULL OR t.email IS NOT NULL)
                                 THEN l.email END) > 0
        THEN sp.investimento_total
             / NULLIF(COUNT(DISTINCT CASE WHEN (h.email IS NOT NULL OR t.email IS NOT NULL)
                                          THEN l.email END), 0)
        ELSE NULL
    END                                                                     AS cpa
FROM leads_por_ad l
LEFT JOIN vendas_hotmart h  ON h.email = lower(trim(l.email)) AND h.projeto_venda = l.projeto
LEFT JOIN vendas_tmb     t  ON t.email = lower(trim(l.email)) AND t.projeto_venda = l.projeto
LEFT JOIN view_investimento_total_por_ad sp ON sp.ad_code = l.ad_code AND sp.lancamento_codigo = l.lancamento_codigo
GROUP BY l.ad_code, l.utm_ad_name, l.lancamento_codigo, sp.investimento_total;

-- -- TABELA DE PÚBLICOS GOOGLE ADS -------------------------------------------

CREATE TABLE IF NOT EXISTS google_ads_audiences_daily (
    id              BIGSERIAL PRIMARY KEY,
    date            DATE    NOT NULL,
    audience_name   TEXT    NOT NULL,
    ad_group_name   TEXT,
    campaign_name   TEXT,
    impressions     INTEGER      DEFAULT 0,
    clicks          INTEGER      DEFAULT 0,
    cost            NUMERIC(12,2) DEFAULT 0,
    conversions     NUMERIC(10,2) DEFAULT 0,
    lancamento_codigo TEXT,
    updated_at      TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (audience_name, campaign_name, date, lancamento_codigo)
);

ALTER TABLE google_ads_audiences_daily ADD COLUMN IF NOT EXISTS ad_group_name TEXT;

CREATE INDEX IF NOT EXISTS idx_ga_aud_date ON google_ads_audiences_daily (date);
CREATE INDEX IF NOT EXISTS idx_ga_aud_lancamento ON google_ads_audiences_daily (lancamento_codigo);

-- -- TABELAS DE DEMOGRAFIA (GOOGLE E META) -----------------------------------

CREATE TABLE IF NOT EXISTS google_ads_demographics_daily (
    id              BIGSERIAL PRIMARY KEY,
    date            DATE    NOT NULL,
    demographic_type TEXT    NOT NULL,
    demographic_value TEXT   NOT NULL,
    campaign_name   TEXT,
    impressions     INTEGER      DEFAULT 0,
    clicks          INTEGER      DEFAULT 0,
    cost            NUMERIC(12,2) DEFAULT 0,
    conversions     NUMERIC(10,2) DEFAULT 0,
    lancamento_codigo TEXT,
    updated_at      TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (demographic_type, demographic_value, campaign_name, date, lancamento_codigo)
);

CREATE INDEX IF NOT EXISTS idx_ga_demo_date ON google_ads_demographics_daily (date);
CREATE INDEX IF NOT EXISTS idx_ga_demo_lancamento ON google_ads_demographics_daily (lancamento_codigo);

CREATE TABLE IF NOT EXISTS meta_ads_demographics_daily (
    id              BIGSERIAL PRIMARY KEY,
    date            DATE    NOT NULL,
    age             TEXT,
    gender          TEXT,
    campaign_name   TEXT,
    impressions     INTEGER      DEFAULT 0,
    clicks          INTEGER      DEFAULT 0,
    cost            NUMERIC(12,2) DEFAULT 0,
    leads           INTEGER      DEFAULT 0,
    lancamento_codigo TEXT,
    updated_at      TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (age, gender, campaign_name, date, lancamento_codigo)
);

CREATE INDEX IF NOT EXISTS idx_ma_demo_date ON meta_ads_demographics_daily (date);
CREATE INDEX IF NOT EXISTS idx_ma_demo_lancamento ON meta_ads_demographics_daily (lancamento_codigo);

-- ── ETL Run History ────────────────────────────────────────────────────────────
-- ─────────────────────────────────────────────────────────────────────────────
-- YouTube Analytics por aula
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS youtube_aulas_stats (
    id               BIGSERIAL    PRIMARY KEY,
    launch_code      TEXT         NOT NULL,
    video_id         TEXT         NOT NULL,
    aula_num         INTEGER,
    titulo           TEXT,
    published_at     TIMESTAMPTZ,
    duration_sec     INTEGER      DEFAULT 0,
    views_total      BIGINT       DEFAULT 0,
    views_live       BIGINT       DEFAULT 0,
    views_replay     BIGINT       DEFAULT 0,
    likes            INTEGER      DEFAULT 0,
    comments         INTEGER      DEFAULT 0,
    watch_time_min   FLOAT        DEFAULT 0,
    avg_view_dur_sec FLOAT        DEFAULT 0,
    avg_view_pct     FLOAT        DEFAULT 0,
    peak_concurrent  INTEGER      DEFAULT 0,
    fetched_at       TIMESTAMPTZ  DEFAULT NOW(),
    UNIQUE(launch_code, video_id)
);

CREATE INDEX IF NOT EXISTS idx_yt_aulas_launch ON youtube_aulas_stats (launch_code, aula_num);

CREATE TABLE IF NOT EXISTS etl_runs (
    id              BIGSERIAL PRIMARY KEY,
    source          TEXT        NOT NULL,
    started_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    finished_at     TIMESTAMPTZ,
    status          TEXT        NOT NULL DEFAULT 'running',
    rows_upserted   INTEGER,
    error_message   TEXT,
    CONSTRAINT etl_runs_status_check CHECK (status IN ('running', 'ok', 'error'))
);

CREATE INDEX IF NOT EXISTS idx_etl_runs_source ON etl_runs (source, finished_at DESC);
