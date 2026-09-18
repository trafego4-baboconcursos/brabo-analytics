-- Materializa as respostas do Typeform já com os VALORES extraídos, no lugar do
-- `answers` cru. O answers carrega metadado do Typeform (id/tipo/ref por
-- resposta) que o frontend joga fora em _reconstruct_tabular_df: 4.844 bytes por
-- linha contra 704 só dos valores, 6,9x. A extração roda no servidor, então a
-- carga inicial não transporta nada.
DROP TABLE IF EXISTS typeform_respostas_valores;

CREATE TABLE typeform_respostas_valores AS
WITH fonte AS (
    SELECT DISTINCT ON (response_id) *
    FROM (
        SELECT response_id, form_id, submitted_at, email, answers, updated_at FROM typeform_respostas
        UNION ALL
        SELECT response_id, form_id, submitted_at, email, answers, updated_at FROM typeform_respostas_backup
        UNION ALL
        SELECT response_id, form_id, submitted_at, email, answers, updated_at FROM typeform_respostas_backup_2
    ) u
    ORDER BY response_id, updated_at DESC NULLS LAST
),
-- Só respostas com e-mail: _reconstruct_tabular_df descarta a linha inteira
-- quando falta "@" (o `continue` antes de montar row_data).
validas AS (
    SELECT response_id, form_id, submitted_at, updated_at, email,
           lower(btrim(email)) AS email_norm, answers
    FROM fonte
    WHERE email IS NOT NULL AND email LIKE '%@%'
),
itens AS (
    SELECT v.response_id, a.ord,
           COALESCE(a.item->'field'->>'title', a.item->'field'->>'id') AS titulo,
           CASE a.item->>'type'
               WHEN 'choice'  THEN COALESCE(a.item->'choice'->>'label', '')
               WHEN 'choices' THEN COALESCE((
                        SELECT string_agg(x, ', ')
                        FROM jsonb_array_elements_text(a.item->'choices'->'labels') x), '')
               WHEN 'text'    THEN COALESCE(a.item->>'text', '')
               WHEN 'email'   THEN COALESCE(a.item->>'email', '')
               WHEN 'number'  THEN COALESCE(a.item->>'number', '')
               -- Python faz str(True) -> "True" e o ->> do Postgres da "true"
               WHEN 'boolean' THEN CASE a.item->>'boolean'
                                       WHEN 'true' THEN 'True'
                                       WHEN 'false' THEN 'False'
                                       ELSE '' END
               ELSE ''
           END AS valor
    FROM validas v,
         LATERAL jsonb_array_elements(
             CASE WHEN jsonb_typeof(v.answers) = 'array' THEN v.answers ELSE '[]'::jsonb END
         ) WITH ORDINALITY AS a(item, ord)
    -- `if not title: continue`
    WHERE COALESCE(a.item->'field'->>'title', a.item->'field'->>'id') IS NOT NULL
      AND COALESCE(a.item->'field'->>'title', a.item->'field'->>'id') <> ''
),
-- Título repetido: o dict do Python fica com o ÚLTIMO da lista, então a
-- agregação precisa respeitar a ordem do array (daí o WITH ORDINALITY).
agregado AS (
    SELECT response_id, jsonb_object_agg(titulo, valor ORDER BY ord) AS valores
    FROM itens GROUP BY response_id
)
SELECT v.response_id, v.form_id, v.submitted_at, v.updated_at, v.email, v.email_norm,
       COALESCE(g.valores, '{}'::jsonb) AS valores
FROM validas v
LEFT JOIN agregado g ON g.response_id = v.response_id;

ALTER TABLE typeform_respostas_valores ADD PRIMARY KEY (response_id);
CREATE INDEX idx_tf_val_fid ON typeform_respostas_valores ((upper(coalesce(form_id, ''))));
CREATE INDEX idx_tf_val_email ON typeform_respostas_valores (email_norm);
ANALYZE typeform_respostas_valores;
