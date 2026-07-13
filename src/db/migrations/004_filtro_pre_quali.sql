-- Migration 004: Adiciona filtro_pre_quali à tabela launch_config
ALTER TABLE launch_config
    ADD COLUMN IF NOT EXISTS filtro_pre_quali TEXT;
