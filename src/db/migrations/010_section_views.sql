-- Migration 010: Visualizações de seções (ordem, visibilidade, tags e nomes)
-- por página do dashboard — o que antes só existia no localStorage de cada
-- navegador. Duas coisas dependem de estar no banco: a "Padrão" da página,
-- que todo mundo abre (escopo 'global', is_padrao), e as visualizações
-- pessoais, que seguem a pessoa entre navegadores/máquinas (escopo 'user').
--
-- Rodar no Supabase > SQL Editor do banco OPERACIONAL (SUPABASE_USERS_URL),
-- que é onde moram users/launch_config.
CREATE TABLE IF NOT EXISTS section_views (
    id             BIGSERIAL PRIMARY KEY,
    pagina         TEXT        NOT NULL,
    escopo         TEXT        NOT NULL CHECK (escopo IN ('global', 'user')),
    -- '' (e não NULL) no escopo global: NULL não colide em índice único, e é
    -- exatamente a colisão que queremos para impedir duas "Padrão" na página.
    user_email     TEXT        NOT NULL DEFAULT '',
    nome           TEXT        NOT NULL,
    is_padrao      BOOLEAN     NOT NULL DEFAULT FALSE,
    estado         JSONB       NOT NULL,
    atualizado_em  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    atualizado_por TEXT
);

-- Nome é chave natural dentro do escopo: salvar com um nome que já existe
-- sobrescreve (é o "editar" pedido), não cria uma segunda linha igual.
CREATE UNIQUE INDEX IF NOT EXISTS section_views_uniq
    ON section_views (pagina, escopo, user_email, LOWER(nome));

-- No máximo uma padrão por página.
CREATE UNIQUE INDEX IF NOT EXISTS section_views_padrao_uniq
    ON section_views (pagina) WHERE is_padrao;

CREATE INDEX IF NOT EXISTS section_views_pagina_idx
    ON section_views (pagina, escopo, user_email);
