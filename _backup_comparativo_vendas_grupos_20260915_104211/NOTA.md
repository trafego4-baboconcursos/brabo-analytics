# Backup pré-atualização — 2026-09-15 10:42:11

**Feito por**: Mateus (Aprova Sim, operacional.and@aprovasim.com)

**Motivo**: backup de `frontend/routes/analytics.py`,
`frontend/services/debriefing_build.py`, `frontend/services/fetch.py` e
`frontend/templates/debriefing/_secao_vendas_grupos_whatsapp.html` como
estavam **antes** de adicionar o comparativo (badges ▲/▼) vs PI-ABR-26 no
card "Vendas × Grupos de WhatsApp" do `/debriefing` — mesmo padrão já
aplicado no card "Leads × Grupos de WhatsApp"
(`_backup_comparativo_whatsapp_20260915_094131/`).

## O que mudou no commit seguinte

`frontend/services/fetch.py::_vendas_grupos_whatsapp()` ganha parâmetro
opcional `previous` — quando informado, mescla `prev_dentro_vip`/
`prev_dentro_normal`/`prev_fora`/`prev_com_telefone` do lançamento
anterior. `debriefing_build.py`/`routes/analytics.py` passam o
`previous` já resolvido (`find_previous_launch`). Template mostra o
badge + "ant.: valor" nos 4 campos (VIP/Normal com polaridade 'up', Fora
com polaridade 'down' — sair dos grupos crescer é ruim).

Diferente do card de Leads, esse NÃO precisou de nenhum backfill — o
PI-ABR-26 já tinha tudo que esse card usa (vendas Hotmart/TMB + presença
nas tabelas brutas de grupo `PI_ABR_26`/`PI_ABR_26_VIPS`, que
`_compradores_grupos()` já sabia encontrar via `_escolhe_tabela`).

## Números confirmados (rodado contra o banco real)

| Campo | PI-AGO-26 | PI-ABR-26 | Variação |
|---|---|---|---|
| Vendas — Grupos VIP | 2.209 | 1.807 | ▲ 22,2% |
| Vendas — Grupos Normais | 182 | 641 | ▼ 71,6% |
| Vendas — Fora dos Grupos | 115 | 627 | ▼ 81,7% (bom) |
| Total de compradores | 2.506 | 3.075 | ▼ 18,5% |

Pra restaurar: copiar os arquivos desta pasta de volta pro lugar, ou
`git checkout <commit_anterior> -- frontend/routes/analytics.py frontend/services/debriefing_build.py frontend/services/fetch.py frontend/templates/debriefing/_secao_vendas_grupos_whatsapp.html`.
