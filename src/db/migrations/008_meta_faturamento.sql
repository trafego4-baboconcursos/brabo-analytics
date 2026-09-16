-- Migration 008: Meta de faturamento do lançamento (usada na Saúde do
-- Lançamento — indicador "Atingimento da meta de faturamento", debriefing).
ALTER TABLE launch_config
    ADD COLUMN IF NOT EXISTS meta_faturamento NUMERIC(12,2);
