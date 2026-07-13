-- Migration 002: Tabela de configuração de lançamentos
-- Armazena as metas, filtros e configurações do wizard de lançamento

CREATE TABLE IF NOT EXISTS launch_config (
    lancamento_codigo TEXT PRIMARY KEY,

    -- Step 1: Leads
    captacao_start_date DATE,
    captacao_end_date   DATE,
    meta_leads          INTEGER,

    -- Step 2: Tráfego
    meta_investimento_captacao NUMERIC(12,2),
    meta_ad_account_ids        TEXT[]  DEFAULT '{}',
    google_ad_account_ids      TEXT[]  DEFAULT '{}',
    filtro_lancamento          TEXT,
    filtro_captacao            TEXT    DEFAULT 'captacao',
    filtro_quente              TEXT    DEFAULT 'quente',
    filtro_quente_scope        TEXT    DEFAULT 'campanhas',
    filtro_frio                TEXT    DEFAULT 'frio',
    filtro_frio_scope          TEXT    DEFAULT 'campanhas',
    outras_temperaturas        JSONB   DEFAULT '[]',

    -- Step 3: Vendas
    carrinho_start_date DATE,
    carrinho_end_date   DATE,
    hotmart_produto_ids TEXT[]  DEFAULT '{}',

    -- Metadata
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
