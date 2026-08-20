-- Migration 005: Adiciona etapas (provisão de verba por etapa/bucket) à tabela launch_config
ALTER TABLE launch_config
    ADD COLUMN IF NOT EXISTS etapas JSONB DEFAULT '[]';
