# Backup pré-atualização — 2026-09-15 11:18:59

**Feito por**: Mateus (Aprova Sim, operacional.and@aprovasim.com)

**Motivo**: backup de `frontend/routes/analytics.py`,
`frontend/services/debriefing_build.py`, `frontend/services/fetch.py` e
`frontend/templates/debriefing/_secao_funil_pesquisa.html` como estavam
**antes** de adicionar o comparativo (badge ▲/▼) vs PI-ABR-26 no card
"Funil da Pesquisa — Leads" do `/debriefing` — mesmo padrão já aplicado
nos cards de WhatsApp (Leads/Vendas).

## O que mudou no commit seguinte

`frontend/services/fetch.py::_pesquisa_engajamento()` ganha parâmetro
opcional `previous` — quando informado, mescla `prev_respostas` do
lançamento anterior. Só é passado nos dois pontos que alimentam o card
"Funil da Pesquisa" (`routes/analytics.py`, seção `funil_pesquisa`, e
`debriefing_build.py::f_perfil_pesquisa`, usado no snapshot) — a seção
"pesquisa_engajamento" (perfil demográfico completo) continua chamando
sem `previous`, sem mudança de comportamento lá.

Antes de implementar, o usuário perguntou por que o número batia
diferente do "Submissions" do próprio Typeform (25.951 vs 24.673 no
PI-ABR-26) — investigado e confirmado: são **1.278 respostas repetidas
pela mesma pessoa** (1.278 = 25.951 linhas deduplicadas por
`response_id` menos 24.673 e-mails únicos). O card sempre contou pessoas
únicas, não envios — comportamento mantido como estava, só confirmado
com número real antes de prosseguir.

## Números confirmados (rodado contra o banco real)

| Campo | PI-AGO-26 | PI-ABR-26 | Variação |
|---|---|---|---|
| Finalizaram/Responderam a pesquisa | 47.140 | 24.673 | ▲ 91,1% |

Pra restaurar: copiar os arquivos desta pasta de volta pro lugar, ou
`git checkout <commit_anterior> -- frontend/routes/analytics.py frontend/services/debriefing_build.py frontend/services/fetch.py frontend/templates/debriefing/_secao_funil_pesquisa.html`.
