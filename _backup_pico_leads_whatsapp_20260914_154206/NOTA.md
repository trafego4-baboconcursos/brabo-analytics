# Backup pré-atualização — 2026-09-14 15:42:06

**Feito por**: Mateus (Aprova Sim, operacional.and@aprovasim.com)

**Motivo**: backup de `frontend/db_readers/whatsapp_groups.py`,
`frontend/db_readers/whatsapp_sheets.py` e
`frontend/templates/debriefing/_secao_leads_x_whatsapp.html` como estavam
**antes** de trocar "Total no grupo" (valor atual) pelo **pico histórico**
por bloco no card "Leads X Grupos de WhatsApp" do `/debriefing`.

## Contexto

Havia DUAS sessões do Claude Code mexendo nisso em paralelo (usuário
confundiu os chats): uma outra sessão já tinha implementado uma versão
("máximo corrente" acumulado via merge com o snapshot anterior a cada
rebuild, função `mesclar_maximo_leads_x_whatsapp` em
`debriefing_build.py`/`whatsapp_groups.py`, ver
`_backup_maximo_leads_whatsapp_20260914_133127/`) — não testada contra o
banco real, e dependente de vários ciclos de prewarm (30 min cada) pra
convergir no valor certo.

Optamos por esta versão em vez daquela: consulta direto
`MAX(leads_no_dia)` em `whatsapp_sheets_diario` (já sincronizado,
histórico completo desde o início da campanha) — pico real desde o
primeiro deploy, sem depender de acumular ao longo de rebuilds. A versão
da outra sessão foi revertida (`debriefing_build.py` voltou pro HEAD,
função `mesclar_maximo_leads_x_whatsapp` removida de
`whatsapp_groups.py`).

## O que mudou no commit seguinte

Nova função `whatsapp_sheets.py::pico_por_bloco(code)` — `{"normal": pico,
"vip": pico}`, maior "leads no dia" já registrado por bloco.
`read_leads_x_whatsapp()` passa a usar esse pico em vez de `total_limpo`
(valor atual) pros campos `total_whatsapp`/`taxa_entrada` de cada bloco —
`saida_total` continua igual (já era cumulativo). Motivo (usuário,
14/09): lançamento fechou há um mês, sem contato novo com esse lead — o
número atual só cai por saída natural e não representa mais o alcance
real da campanha; o pico sim.

Confirmado contra o banco real (PI-AGO-26): Normal pico=216.039/80,2%,
VIP pico=12.110/4,5%.

Pra restaurar: copiar os arquivos desta pasta de volta pro lugar, ou
`git checkout <commit_anterior> -- frontend/db_readers/whatsapp_groups.py frontend/db_readers/whatsapp_sheets.py frontend/templates/debriefing/_secao_leads_x_whatsapp.html`.
