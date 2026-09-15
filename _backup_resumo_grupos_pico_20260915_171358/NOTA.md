# Backup pré-atualização — 2026-09-15 17:13:58

**Feito por**: Mateus (Aprova Sim, operacional.and@aprovasim.com)

**Motivo**: backup de `frontend/db_readers/whatsapp_groups.py`,
`frontend/services/debriefing.py`, `frontend/services/fetch.py` e
`frontend/templates/debriefing.html` como estavam **antes** de:
1. Simplificar a fonte de "grupos" em `_mesclar_contagem_sheets` (sempre
   SQL próprio, nunca planilha — achado 15/09: planilha nunca rastreou
   VIP em alguns lançamentos).
2. Trocar "Pessoas nos Grupos" (Normal/VIP) no card "Resumo Executivo" do
   debriefing pelo **pico histórico** (mesmo raciocínio do card Leads x
   Grupos: número atual só cai com saída natural, não representa mais o
   alcance real de um lançamento fechado).
3. **Remover "Total de Grupos" da exibição** — decisão final do usuário:
   a tabela bruta do Supabase ficava incompleta em alguns lançamentos
   (PI-ABR-26 Normal real era 309, a tabela só tinha 133 — uma campanha
   inteira do SendFlow nunca chegou no banco; VIP real era 7, tabela
   tinha 42) e não dava pra confiar nesse número sem correção manual por
   lançamento, então saiu da tela.

## Números confirmados (rodado contra o banco real)

| Campo | PI-AGO-26 | PI-ABR-26 | Variação |
|---|---|---|---|
| Pessoas nos Grupos Normais (pico) | 216.039 (09/08) | 233.104 (05/04) | ▼ 7,3% |
| Pessoas nos Grupos VIP (pico) | 12.110 (13/08) | 19.562 (08/04) | ▼ 38,1% |

Pra restaurar: copiar os arquivos desta pasta de volta pro lugar, ou
`git checkout <commit_anterior> -- frontend/db_readers/whatsapp_groups.py frontend/services/debriefing.py frontend/services/fetch.py frontend/templates/debriefing.html`.
