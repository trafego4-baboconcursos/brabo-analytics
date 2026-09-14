# Backup pré-atualização — 2026-09-14 09:40:59

**Feito por**: Mateus (Aprova Sim, operacional.and@aprovasim.com)

**Motivo**: backup de `frontend/db_readers/whatsapp_groups.py` e
`frontend/templates/debriefing/_secao_leads_x_whatsapp.html` como estavam
**antes** de separar o card "Leads X Grupos de WhatsApp" (debriefing) em
duas linhas — Grupos Normais e Grupos VIP — em vez de um total combinado,
seguindo o mesmo padrão de `_backup_grupos_whatsapp_20260911_163544/` e
`_backup_leads_whatsapp_20260911_165024/`.

## O que mudou no commit seguinte

O card "Total nos Grupos de WhatsApp" dava um número matematicamente
impossível (154.691, menor que o total confiável da Normal sozinha,
157.938) porque a sobreposição Normal×VIP era calculada aqui com uma
lógica (SQL bruto nas tabelas `PI_AGO_26_API`/`_VIP_API`) que diverge da
dedup + exclusão de admin que só o `sendflow-analytics-poller` faz
(confirmado: nem normalizando telefone bate — 222.590 vs 157.938
confiável). Investigação completa documentada no relatório do turno de
11/09 (`_relatorio_turno_20260911.html`).

Decisão (do usuário): não tentar mais calcular essa sobreposição — separar
o card em duas linhas independentes (Grupos Normais / Grupos VIP), cada
uma só com os números do próprio bloco, que já vêm certos, cópia literal
da planilha (`whatsapp_sheets_resumo`/`whatsapp_sheets_diario`). Elimina o
bug por completo, sem inventar nenhum número.

Bônus: removidas as duas queries SQL de overlap (`overlap_ativo_vip`/
`overlap_saida_vip`) que faziam JOIN nas tabelas brutas de 400k+/14k
linhas — menos carga no banco, relevante com o Supabase no limite de
egress (grace period até 15/09).

`total_whatsapp`/`taxa_entrada`/`saida_total` no nível raiz do dict
(usados em `frontend/templates/dashboard.html`, não no debriefing) foram
mantidos por compatibilidade, mas viraram soma simples Normal+VIP (sem
subtrair sobreposição) — aproximação pra cima, mas nunca mais um valor
impossível.

Confirmado rodando `read_leads_x_whatsapp("PI-AGO-26")` de verdade contra
o banco: Normal 157.938/58,6%/29.382 saída, VIP 10.097/3,7%/16 saída —
bate exatamente com a planilha.

Pra restaurar: copiar os arquivos desta pasta de volta pro lugar, ou
`git checkout <commit_anterior> -- frontend/db_readers/whatsapp_groups.py frontend/templates/debriefing/_secao_leads_x_whatsapp.html`.
