-- Materialização da pesquisa nova (formularios → perguntas → submissoes → respostas)
-- numa linha por submissão, com os valores já extraídos do jsonb.
--
-- Por que existe: o dashboard lia `jsonb_object_agg(p.titulo, r.valor)` sobre o
-- JOIN de ~929 mil respostas a cada recarga de cache, devolvendo ~20 mil linhas
-- de ~1,8 KB por lançamento (2,6 GB/dia em 30/09/26). O envelope de cada
-- resposta ({'texto': ...}, {'opcao': ..., 'texto_outro': ...}, {'opcoes': [...]})
-- era descartado no Python logo em seguida (`_extract_valor`). Aqui a extração
-- é feita uma vez, no servidor — recriar/atualizar a view não gera egress.
--
-- A extração replica `_extract_valor` de frontend/db_readers/typeform.py:
--   opcoes  -> "op1, op2[, texto_outro]"
--   opcao   -> "opcao" ou "opcao (texto_outro)"
--   senão   -> texto (vazio se não for objeto)
-- Mudou a regra lá? Muda aqui também, e roda `REFRESH MATERIALIZED VIEW`.
--
-- Atualização: pg_cron a cada 15 min (REFRESH ... CONCURRENTLY exige o índice
-- único abaixo). O leitor cacheia por 1h, então esse atraso não aparece.
-- Idempotente: pode rodar de novo.

CREATE MATERIALIZED VIEW IF NOT EXISTS pesquisa_respostas_valores AS
SELECT
    s.id AS submissao_id,
    s.formulario_id,
    s.created_at,
    lower(btrim(max(CASE WHEN p.tipo = 'email' THEN r.valor->>'texto' END))) AS email_norm,
    jsonb_object_agg(
        p.titulo,
        CASE
            WHEN jsonb_typeof(r.valor) <> 'object' THEN ''
            WHEN r.valor ? 'opcoes' THEN concat_ws(
                ', ',
                NULLIF((
                    SELECT string_agg(x, ', ' ORDER BY ord)
                    FROM jsonb_array_elements_text(
                        CASE WHEN jsonb_typeof(r.valor->'opcoes') = 'array' THEN r.valor->'opcoes' ELSE '[]'::jsonb END
                    ) WITH ORDINALITY AS t(x, ord)
                ), ''),
                NULLIF(r.valor->>'texto_outro', '')
            )
            WHEN r.valor ? 'opcao' THEN
                CASE WHEN coalesce(r.valor->>'texto_outro', '') <> ''
                     THEN coalesce(r.valor->>'opcao', '') || ' (' || (r.valor->>'texto_outro') || ')'
                     ELSE coalesce(r.valor->>'opcao', '') END
            ELSE coalesce(r.valor->>'texto', '')
        END
    ) AS valores
FROM submissoes s
JOIN respostas r ON r.submissao_id = s.id
JOIN perguntas p ON p.id = r.pergunta_id
GROUP BY s.id, s.formulario_id, s.created_at
WITH DATA;

CREATE UNIQUE INDEX IF NOT EXISTS idx_prv_submissao ON pesquisa_respostas_valores (submissao_id);
CREATE INDEX IF NOT EXISTS idx_prv_form ON pesquisa_respostas_valores (formulario_id, submissao_id);

-- Agendamento (pg_cron já está habilitado no projeto). Re-agendar é idempotente.
SELECT cron.unschedule(jobid) FROM cron.job WHERE jobname = 'pesquisa_respostas_valores_refresh';
SELECT cron.schedule('pesquisa_respostas_valores_refresh', '*/15 * * * *',
                     'REFRESH MATERIALIZED VIEW CONCURRENTLY public.pesquisa_respostas_valores');
