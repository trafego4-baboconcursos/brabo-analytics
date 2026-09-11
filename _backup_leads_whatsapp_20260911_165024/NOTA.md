# Backup pré-atualização — 2026-09-11 16:50:24

**Feito por**: Mateus (Aprova Sim, operacional.and@aprovasim.com)

**Motivo**: backup de `frontend/templates/debriefing/_secao_leads_x_whatsapp.html`
como estava **antes** de remover o bloco "Página de Obrigado" do card
"Leads X Grupos de WhatsApp" no `/debriefing`, seguindo o mesmo padrão de
`_backup_grupos_whatsapp_20260911_163544/`.

## O que mudou no commit seguinte

O bloco "Página de Obrigado" ("Taxa de Comparecimento (entrou no grupo)" e
"Leads que foram para os grupos") duplicava exatamente os valores de
`lw.taxa_entrada` e `lw.total_whatsapp` já mostrados nos cards
"Taxa de entrada" e "Total nos grupos de WhatsApp" logo acima, só com
nomenclatura diferente — sem dado novo. Removido por pedido do usuário.

Nenhum cálculo em Python mudou, só o template (remoção de HTML).

Pra restaurar: copiar o arquivo desta pasta de volta pro lugar, ou
`git checkout <commit_anterior> -- frontend/templates/debriefing/_secao_leads_x_whatsapp.html`.
