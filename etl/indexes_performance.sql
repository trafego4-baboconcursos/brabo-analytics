-- Indexes de performance para o Brabo Analytics
-- Rodar no Supabase > SQL Editor (Analytics DB: SUPABASE_DB_URL)
-- Todos são CONCURRENTLY — não bloqueiam leituras em produção

-- meta_ads_daily: filtragem por lançamento + data (leitura do dashboard e comparativo)
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_meta_lancamento_date
    ON meta_ads_daily (lancamento_codigo, date);

-- google_ads_daily: idem
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_google_lancamento_date
    ON google_ads_daily (lancamento_codigo, date);

-- leads: filtragem por lançamento + data de criação
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_leads_lancamento_created
    ON leads (lancamento_codigo, (created_at::date));

-- leads: busca por email (atribuição de vendas)
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_leads_email
    ON leads (email);

-- Rodar no Supabase > SQL Editor (Operational DB: SUPABASE_USERS_URL)

-- tmb_clean_oficial: lookup por lancamento_id (inteiro, filtro mais preciso)
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_tmb_lancamento_id
    ON tmb_clean_oficial (lancamento_id);

-- Nota: hotmart_clean_oficial filtra por produto com ILIKE + parsing de data via regex
-- no SQL — não há coluna indexável que reduza o custo dessas queries de forma simples.
-- A melhoria real aqui seria no ETL: limpar as datas de hotmart no momento da ingestão
-- e adicionar coluna data_transacao_parsed DATE para indexar diretamente.
