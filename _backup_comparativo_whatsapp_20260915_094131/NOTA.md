# Backup pré-atualização — 2026-09-15 09:41:31

**Feito por**: Mateus (Aprova Sim, operacional.and@aprovasim.com)

**Motivo**: backup de `config/sheets_contagem.yaml`, `frontend/routes/analytics.py`,
`frontend/services/debriefing_build.py`, `frontend/services/fetch.py`,
`frontend/templates/debriefing/_macros.html` e
`frontend/templates/debriefing/_secao_leads_x_whatsapp.html` como estavam
**antes** de adicionar o comparativo (badges ▲/▼) vs o último lançamento
INSS (PI-ABR-26) no card "Leads X Grupos de WhatsApp" do `/debriefing`.

## O que mudou no commit seguinte

1. `dbadge()` — macro de badge ▲/▼ com % de variação, já usado no resto do
   debriefing (definido inline em `debriefing.html`) — movido/copiado pra
   `debriefing/_macros.html` (compartilhado com os fragmentos `_secao_*`,
   que não tinham acesso a ele).
2. `frontend/services/fetch.py::_leads_x_whatsapp()` ganha parâmetro
   opcional `previous` — quando informado, mescla `prev_total_leads` e,
   por bloco (normal/vip), `prev_total_whatsapp`/`prev_taxa_entrada`/
   `prev_saida_total` do lançamento anterior. Sem `previous` (uso em
   `/captacao`), comportamento idêntico a antes.
3. `debriefing_build.py`/`routes/analytics.py` passam o lançamento
   anterior (`find_previous_launch`, já resolvido nos dois lugares) pra
   `_leads_x_whatsapp`.
4. Template mostra o badge + "ant.: valor" pros 7 campos (Total de Leads,
   e Pico no grupo/Taxa de entrada/Pico de saída de cada bloco) — nos dois
   que têm data (Pico no grupo, Pico de saída), o badge fica entre o valor
   e a data. Pico de saída usa polaridade invertida (mais saída = ruim).
5. `config/sheets_contagem.yaml` ganha entrada pro PI-ABR-26 (lançamento
   INSS anterior, fechado em abril) — sheet_id fornecido pelo usuário.
   `linha_resumo`/`linha_total_limpo` são PALPITE sem garantia (não usados
   por essa feature, só o histórico diário importa aqui).

## Por que precisou de investigação

O card já mostrava "Pico no grupo"/"Pico de saída" (trabalho de 14/09),
mas comparar com PI-ABR-26 exigia dado desse lançamento em
`whatsapp_sheets_diario` — que não existia (PI-ABR-26 fechou antes do
sistema de sync do Sheets existir, e as tabelas brutas do Supabase pra
esse lançamento, achadas com nome antigo `PI_ABR_26`/`PI_ABR_26_VIPS`,
não são confiáveis pro mesmo padrão de "pico" — não têm data de saída
nem exclusão de admin). Usuário forneceu a planilha antiga
("Captação [PI-ABR-26]", mesmo formato do sendflow-analytics-poller) e a
credencial `GOOGLE_SHEETS_CONTAGEM_JSON` pra eu rodar
`etl/etl_sheets_contagem.py` manualmente e popular o histórico.

## Números confirmados (rodado contra o banco real)

| Campo | PI-AGO-26 | PI-ABR-26 | Variação |
|---|---|---|---|
| Total de Leads | 269.211 | 235.169 | ▲ 14,5% |
| Normal — Pico no grupo | 216.039 (09/08) | 233.104 (05/04) | ▼ 7,3% |
| Normal — Taxa de entrada | 80,2% | 99,1% | ▼ 19,0% |
| Normal — Pico de saída | 19.086 (10/08) | 3.682 (06/04) | ▲ 418,4% (ruim) |
| VIP — Pico no grupo | 12.110 (13/08) | 19.562 (08/04) | ▼ 38,1% |
| VIP — Taxa de entrada | 4,5% | 8,3% | ▼ 45,9% |
| VIP — Pico de saída | 2.917 (13/08) | 3.244 (09/04) | ▼ 10,1% (bom) |

Pra restaurar: copiar os arquivos desta pasta de volta pro lugar, ou
`git checkout <commit_anterior> -- config/sheets_contagem.yaml frontend/routes/analytics.py frontend/services/debriefing_build.py frontend/services/fetch.py frontend/templates/debriefing/_macros.html frontend/templates/debriefing/_secao_leads_x_whatsapp.html`.
