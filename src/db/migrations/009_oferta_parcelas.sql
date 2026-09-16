-- Migration 009: Valor da parcela (12x) por forma de pagamento, na oferta
-- do lançamento (debriefing, seção "Detalhamento de Oferta").
ALTER TABLE launch_config
    ADD COLUMN IF NOT EXISTS oferta_parcela_cartao  NUMERIC(12,2),
    ADD COLUMN IF NOT EXISTS oferta_parcela_boleto   NUMERIC(12,2);
