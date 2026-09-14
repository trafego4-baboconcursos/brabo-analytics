# Backup pré-atualização — 2026-09-14 15:54:35

**Feito por**: Mateus (Aprova Sim, operacional.and@aprovasim.com)

**Motivo**: backup de `frontend/db_readers/whatsapp_groups.py`,
`frontend/db_readers/whatsapp_sheets.py` e
`frontend/templates/debriefing/_secao_leads_x_whatsapp.html` como estavam
**antes** de adicionar o "Pico de Saída" (além do "Pico no Grupo" já
existente) e a data de cada pico embaixo do valor, no card "Leads X Grupos
de WhatsApp" do `/debriefing`.

## O que mudou no commit seguinte

`whatsapp_sheets.py::pico_por_bloco()` passa a retornar valor **e data**
de dois picos por bloco (normal/vip): `leads_no_dia` (pico de pessoas no
grupo) e `saidas` (pico de saída num único dia — não confundir com total
acumulado). `read_leads_x_whatsapp()` usa os dois; "Saída" no card vira
"Pico de Saída" (antes mostrava um total acumulado calculado nas tabelas
brutas do Supabase, não confiável). Template mostra a data de cada pico
embaixo do valor, em cinza claro (`var(--bs-ink-subtle)`).

Como bônus, a função não chama mais `read_whatsapp_groups()` (que batia
nas tabelas brutas de 400k+/14k linhas) — usa só `whatsapp_sheets_diario`
(pequena, já sincronizada) e a tabela `leads`. Menos uma fonte de egress.

Confirmado contra o banco real (PI-AGO-26): Normal pico grupo=216.039
(09/08), pico saída=19.086 (10/08); VIP pico grupo=12.110 (13/08), pico
saída=2.917 (13/08).

Pra restaurar: copiar os arquivos desta pasta de volta pro lugar, ou
`git checkout <commit_anterior> -- frontend/db_readers/whatsapp_groups.py frontend/db_readers/whatsapp_sheets.py frontend/templates/debriefing/_secao_leads_x_whatsapp.html`.
