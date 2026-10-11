-- Migration 012: lista oficial de landing pages por lançamento (banco operacional)
-- Fonte única da lista que a auditoria (scripts/ads/auditar_lps.py) confere e que a página
-- /landing-pages edita. Antes vivia em scripts/ads/padroes.py: LP nova exigia commit.
-- Nasceu do erro da -v3a/ na BV-26: URL fora da lista, formulário da Black 2025.

CREATE TABLE IF NOT EXISTS lp_oficiais (
    lancamento_codigo TEXT NOT NULL,
    url               TEXT NOT NULL,          -- normalizada: https://host/caminho/ (sem query)
    tag_esperada      TEXT,                   -- trecho da tag que o form do AC tem que aplicar
    funcao            TEXT,                   -- captação, aquecimento, pré-qualificação...
    observacao        TEXT,
    atualizado_por    TEXT,
    updated_at        TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (lancamento_codigo, url)
);
