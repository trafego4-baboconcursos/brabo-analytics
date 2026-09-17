-- ══════════════════════════════════════════════════════════════════════════
-- MIGRACAO: legendas dos criativos (17/09/26)
--
-- Recorte de etl/schema.sql com SO o que e novo, pra colar no SQL Editor do
-- Supabase (banco de ANALYTICS, o do SUPABASE_DB_URL) sem reprocessar o schema
-- inteiro. Nao contem DROP nem ALTER: so CREATE TABLE/INDEX IF NOT EXISTS e um
-- CREATE OR REPLACE VIEW. Rodar duas vezes nao faz mal.
--
-- Depende de views que ja existem no banco: view_investimento_total_por_ad,
-- view_meta_performance_criativos, view_google_performance_criativos.
--
-- Depois de aplicar:  python etl/etl_legendas.py --launch PES-SET-26
-- Plano: docs/projetos/PLANO_ANALISE_COPYS.md
-- ══════════════════════════════════════════════════════════════════════════

-- ── LEGENDAS DOS CRIATIVOS — transcricao com minutagem por ADxxx ───────────
-- Fonte: analises/[LANCAMENTO]/Legendas/*.txt, ingerido por etl/etl_legendas.py.
-- Um arquivo por anuncio, dividido em blocos "--- Fonte: ARQUIVO.MP4 ---".
--
-- ATENCAO (achado 17/09/26, PES-SET-26): a maioria dos blocos e transcricao do
-- MATERIAL BRUTO de camera, nao do corte final publicado. Em AD269 os 3 blocos
-- abrem todos em [00:00] com falas diferentes (um por ator); AD247 tem 299s de
-- filmagem crua com takes descartados para um anuncio de ~60s. Por isso
-- hook_confiavel existe: so e TRUE quando fonte_tipo='corte_final'. Toda
-- analise temporal (gancho de 3s, quartil, segundo do CTA) DEVE filtrar por
-- hook_confiavel, senao mede texto que nunca foi ao ar.
CREATE TABLE IF NOT EXISTS ad_transcricoes (
    id                BIGSERIAL PRIMARY KEY,
    lancamento_codigo TEXT NOT NULL,
    ad_code           TEXT NOT NULL,          -- AD269
    ad_name           TEXT,                   -- nome do .txt, sem extensao
    fonte             TEXT NOT NULL,          -- 'C0068.MP4' | '__unico__'
    fonte_ordem       SMALLINT NOT NULL,      -- ordem do bloco dentro do arquivo
    fonte_tipo        TEXT NOT NULL,          -- 'corte_final' | 'bruto' | 'sem_fala'
    is_canonica       BOOLEAN DEFAULT FALSE,  -- o bloco que representa o anuncio
    hook_confiavel    BOOLEAN DEFAULT FALSE,  -- ver comentario acima
    duracao_seg       INTEGER,                -- ultimo timestamp do bloco
    n_linhas          INTEGER,
    n_palavras        INTEGER,
    texto_completo    TEXT,                   -- busca full-text
    roteiro_hash      TEXT,                   -- sha1(texto normalizado) → agrupa AD269=AD292
    arquivo_origem    TEXT,                   -- caminho do .txt
    updated_at        TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (lancamento_codigo, ad_code, fonte)
);

CREATE INDEX IF NOT EXISTS idx_transc_lanc    ON ad_transcricoes (lancamento_codigo, ad_code);
CREATE INDEX IF NOT EXISTS idx_transc_roteiro ON ad_transcricoes (roteiro_hash);
CREATE INDEX IF NOT EXISTS idx_transc_fts     ON ad_transcricoes
    USING GIN (to_tsvector('portuguese', texto_completo));


-- ── LEGENDAS — a minutagem, uma linha por fala ─────────────────────────────
-- Tabela separada de proposito: a pergunta da analise e temporal ("o que e dito
-- nos 3 primeiros segundos", "o que e dito quando 50% desiste"), entao vira
-- WHERE t_ini_seg < 3 em vez de parsing de string a cada consulta.
-- quartil e a ponte com views_25/50/75/100 do Meta/Google.
CREATE TABLE IF NOT EXISTS ad_transcricao_linhas (
    id             BIGSERIAL PRIMARY KEY,
    transcricao_id BIGINT NOT NULL REFERENCES ad_transcricoes(id) ON DELETE CASCADE,
    ordem          INTEGER NOT NULL,
    t_ini_seg      INTEGER NOT NULL,   -- [00:02] → 2
    t_fim_seg      INTEGER,            -- t_ini da linha seguinte (derivado)
    quartil        SMALLINT,           -- 1..4 — em qual quarto do video a fala cai
    falante        TEXT,               -- 'A'/'B' quando o "- " marca dialogo
    texto          TEXT NOT NULL,
    n_palavras     INTEGER,
    UNIQUE (transcricao_id, ordem)
);

CREATE INDEX IF NOT EXISTS idx_transc_linhas_t ON ad_transcricao_linhas (transcricao_id, t_ini_seg);


-- ── LEGENDAS — classificacao do copy (EAV) ─────────────────────────────────
-- EAV e nao colunas fixas porque a taxonomia muda toda semana ("citou a banca?",
-- "falou de idade?"): coluna fixa = migracao por pergunta, e um anuncio pode ter
-- dois valores na mesma dimensao (trata preco E tempo).
-- origem='humano' NUNCA e sobrescrito pelo ETL.
CREATE TABLE IF NOT EXISTS ad_copy_atributos (
    id                BIGSERIAL PRIMARY KEY,
    lancamento_codigo TEXT NOT NULL,
    ad_code           TEXT NOT NULL,
    dimensao          TEXT NOT NULL,   -- gancho_tipo | promessa | objecao | prova | cta_tipo | formato | cenario | segmento
    valor             TEXT NOT NULL,
    origem            TEXT NOT NULL,   -- 'auto' | 'llm' | 'humano'
    confianca         NUMERIC(3,2),    -- 0..1 quando origem='llm'
    updated_at        TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (lancamento_codigo, ad_code, dimensao, valor)
);

CREATE INDEX IF NOT EXISTS idx_copy_attr ON ad_copy_atributos (lancamento_codigo, dimensao, valor);


-- ── COPY × PERFORMANCE — so o lado de midia ────────────────────────────────
-- Junta a transcricao canonica de cada ADxxx com gasto e metricas de video.
-- VENDAS NAO ENTRAM AQUI DE PROPOSITO: moram no banco operacional
-- (hotmart_clean_oficial/tmb_clean_oficial) e view_atribuicao subestima
-- gravemente (43 vs 2502 no PI-AGO-26). A pagina junta vendas em Python, via
-- frontend/services/criativos.py::_creative_overview, como o resto do sistema.
CREATE OR REPLACE VIEW view_copy_performance AS
SELECT t.lancamento_codigo,
       t.ad_code,
       t.ad_name,
       t.roteiro_hash,
       t.fonte_tipo,
       t.hook_confiavel,
       t.duracao_seg,
       t.n_palavras,
       COALESCE(i.investimento_meta, 0)    AS investimento_meta,
       COALESCE(i.investimento_google, 0)  AS investimento_google,
       COALESCE(i.investimento_total, 0)   AS investimento_total,
       m.impressoes      AS meta_impressoes,
       m.views_3s        AS meta_views_3s,
       m.thruplays       AS meta_thruplays,
       m.views_25        AS meta_views_25,
       m.views_50        AS meta_views_50,
       m.views_75        AS meta_views_75,
       m.views_100       AS meta_views_100,
       m.hook_rate       AS meta_hook_rate,
       m.hold_rate       AS meta_hold_rate,
       m.leads_pixel     AS meta_leads_pixel,
       g.impressoes      AS google_impressoes,
       g.video_views     AS google_views,
       g.views_100       AS google_views_100,
       g.hook_rate       AS google_hook_rate,
       g.completion_rate AS google_completion_rate
FROM   ad_transcricoes t
LEFT   JOIN view_investimento_total_por_ad    i USING (ad_code, lancamento_codigo)
LEFT   JOIN view_meta_performance_criativos   m USING (ad_code, lancamento_codigo)
LEFT   JOIN view_google_performance_criativos g USING (ad_code, lancamento_codigo)
WHERE  t.is_canonica;
