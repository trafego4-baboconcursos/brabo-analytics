# Backup pré-atualização — 2026-09-11 16:35:44

**Feito por**: Mateus (Aprova Sim, operacional.and@aprovasim.com)

**Motivo**: backup de `frontend/db_readers/whatsapp_groups.py` e
`frontend/templates/debriefing/_secao_vendas_grupos_whatsapp.html` como
estavam **antes** da correção do card "Vendas × Grupos de WhatsApp" no
`/debriefing`, seguindo o mesmo padrão de
`_backup_correcao_vendas_20260911_144504/`.

## O que mudou no commit seguinte

Categorias VIP/Normal do card passam a ser **mutuamente exclusivas**: antes,
`_compradores_grupos()` contava a mesma pessoa em `dentro_vip` E
`dentro_normal` quando ela estava presente nos dois grupos, e a soma
(2.209 + 2.340) passava do total de compradores (2.506) — não representava
categorias reais.

Agora VIP tem prioridade: quem está no VIP conta só em `dentro_vip`; só quem
NÃO está no VIP e está num grupo normal conta em `dentro_normal`
(`if` → `elif` em `frontend/db_readers/whatsapp_groups.py`, dentro de
`_compradores_grupos`). Texto do card atualizado para refletir isso.

Confirmado rodando `read_vendas_grupos_whatsapp("PI-AGO-26")` de verdade
contra o banco: `dentro_vip=2209, dentro_normal=182, fora=115` — bate com os
números de referência confirmados pelo usuário (2.209 / 182 / 115, soma
2.506).

Pra restaurar esses arquivos: copiar de volta desta pasta pro lugar, ou
`git checkout <commit_anterior> -- frontend/db_readers/whatsapp_groups.py frontend/templates/debriefing/_secao_vendas_grupos_whatsapp.html`.
