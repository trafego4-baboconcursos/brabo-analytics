-- Migration 007: Adiciona campos de Oferta & Bônus à tabela launch_config
ALTER TABLE launch_config
    ADD COLUMN IF NOT EXISTS produto_nome             TEXT,
    ADD COLUMN IF NOT EXISTS produto_preco_vista      NUMERIC(12,2),
    ADD COLUMN IF NOT EXISTS produto_preco_parcelado  NUMERIC(12,2),
    ADD COLUMN IF NOT EXISTS bonus_oferta             JSONB DEFAULT '[]';
