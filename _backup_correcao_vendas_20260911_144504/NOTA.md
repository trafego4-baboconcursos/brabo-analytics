# Backup pré-atualização — 2026-09-11 14:45:04

**Feito por**: Mateus (Aprova Sim, operacional.and@aprovasim.com)

**Motivo**: backup do `frontend/db_readers/sales.py` como estava **antes** da
correção da contagem de vendas Hotmart (commit `bf25396`), guardado à parte
seguindo o mesmo padrão de `_backup_otimizacao_20260901_110913/`.

## O que mudou no commit seguinte

1. `_parcela_unica_info` só tratava `quantidade_de_cobrancas > 1` como
   retentativa de cobrança quando `tipo_de_cobranca` era "Recuperador
   Inteligente" ou vazio — cobranças repetidas de outros tipos eram contadas
   como venda nova.
2. Filtro de data em SQL extraía a data em UTC (`::date` direto) — vendas
   tarde da noite (horário de Brasília) caíam no dia seguinte em UTC e
   saíam da janela do carrinho do lançamento.
3. Lógica de data extraída para `_hm_data_sql()`, única fonte usada em
   `_query_hotmart` e `read_hotmart_details` (antes duplicada nos dois
   lugares, só um tinha a correção de fuso horário).

Confirmado contra o export oficial da Hotmart do PI-AGO-26: contagem foi de
1.960 para 1.640 vendas (bate com a contagem manual de referência).

Pra restaurar esse arquivo específico: copiar
`frontend/db_readers/sales.py` desta pasta de volta pro lugar, ou
`git checkout bf25396~1 -- frontend/db_readers/sales.py`.
