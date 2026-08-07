# Registro de mudanças — Google Ads + Meta Ads PBB-AGO-26

Contas: Google `1450466453`, Meta `act_438212624024216`. Todas as mudanças abaixo foram aplicadas via API (script ad-hoc), não pela interface, salvo indicação contrária.

## 2026-08-03

### 1. Divisão de verba de captação — cálculo e ativação inicial (Facebook, 12 campanhas)
- **Contexto:** planilha de previsão de verba por público (Facebook Quente/Frio/Específico, YouTube Quente/Frio/Específico, TikTok) trazida pelo usuário, cobrindo 03/08 a 17/08 (dia 1 ao dia de início das aulas ao vivo).
- **Metodologia:** dentro de cada clima (quente/frio/específico), verba dividida entre as variantes principal/potencial/teste/reels na proporção **70% / 20% / 5% / 5%**, baseada no histórico real de gasto do PBB-JUN-26 (que mostrou 70/25/5 entre principal/potencial/reels — ajustado pra abrir espaço aos 5% de "teste", variante nova que não existia em junho).
- **Aplicado:** `daily_budget` das 12 campanhas de captação (quente/frio/específico × principal/potencial/teste/reels) atualizado pro valor do dia 03/08, e as campanhas "teste" e "reels" (que estavam pausadas) **reativadas**.
- **Total do dia:** R$7.581,93.
- **Status:** ✅ aplicado, 12/12 confirmado via API.

### 2. Divisão de verba de captação — cálculo e ativação inicial (Google, 6 campanhas)
- **Metodologia:** mesma lógica do item 1, mas sem "teste"/"reels" (confirmado pelo usuário que o Google não teria essas variantes) e com Quente dividido também em base/Search/P-Max, proporção extraída do histórico real do PBB-JUN-26 (`google_ads_daily`): Quente base 56,86% / Search 5,84% / P-Max 12,36% / potencial 24,94%; Frio e Específico ~71,7% principal / ~28,3% potencial.
- **Aplicado:** `campaignBudget.amountMicros` das 6 campanhas reais existentes (quente/frio/específico × principal/potencial) atualizado pro valor do dia 03/08, e as 6 campanhas (que estavam pausadas) **reativadas**.
- **Total do dia:** R$14.727,31 (valores: quente principal R$4.755,24 / quente potencial R$2.086,03 / frio principal R$1.648,77 / frio potencial R$648,78 / específico principal R$2.910,65 / específico potencial R$1.156,02).
- **Pendência registrada:** Search e P-Max ainda não existiam como campanhas — só a projeção de verba deles foi calculada.
- **Status:** ✅ aplicado, 6/6 confirmado via API.

### 3. Reforço de +R$2.000 no Facebook, rateado por performance (CPL do dia)
- **Contexto:** pedido do usuário pra aumentar a verba do Facebook em R$2.000 no mesmo dia, distribuindo mais pra quem estava com melhor retorno.
- **Metodologia:** puxado gasto e leads reais do dia (via `meta_ads_daily`) das 12 campanhas, calculado CPL de cada uma, peso proporcional a `1/CPL` (quem custa menos por lead recebe fatia maior do reforço).
- **Aplicado:** `daily_budget` das 12 campanhas incrementado — Frio Potencial (CPL R$2,08, melhor do dia) recebeu a maior fatia (+R$247,68); Específico Teste (CPL R$6,47, pior do dia) recebeu a menor (+R$79,54).
- **Ressalva registrada na hora:** amostra de só ~13h do primeiro dia, volume baixo em teste/reels — CPL sujeito a mudar bastante no dia seguinte.
- **Total do dia após o reforço:** R$9.581,93.
- **Status:** ✅ aplicado, 12/12 confirmado via API.

## 2026-08-04

### 4. Verba do dia 04/08 — Facebook (12) + Google (6)
- **O que:** `daily_budget`/`campaignBudget.amountMicros` das 18 campanhas atualizado pro valor do dia 04/08 do plano original (sem o reforço de performance do item 3, que era só pontual pro dia 03/08).
- **Facebook:** total R$7.193,11. **Google:** total R$12.528,29 (quente principal R$4.511,38 / quente potencial R$1.979,06 / frio principal R$1.564,22 / frio potencial R$615,51 / específico principal R$2.761,39 / específico potencial R$1.096,73).
- **Status:** ✅ aplicado, 18/18 confirmado via API.

### 5. Criação da campanha de Search (Google) — estrutura replicada do PI-AGO-26
- **Contexto:** usuário pediu pra copiar a estrutura da campanha `[GA][captação][quente][search][PI-AGO-26]` (id `24074486341`), trocando as palavras-chave pro produto BB.
- **Criado:** campanha `[GA][captação][quente][principal][search][PBB-AGO-26]` (id `24108291340`), budget inicial R$463,10/dia, bidding Maximize Conversions, redes Google Search + Parceiros + Display, período 05/08–20/08 (depois ajustado pelo usuário pra 04/08–17/08, ver item 6).
- **4 grupos de anúncio** (PHRASE match): Cargo Específico (5 kw), Concurso BB - genérico (7 kw), Grupo de marca — "felipe graton"/"brabo concursos" (10 kw), Intenção de estudo/preparação (8 kw) = 30 keywords.
- **38 negativas de campanha**, adaptadas do PI pra excluir quem busca o banco de verdade (conta, cartão, empréstimo, app, agência, estágio/trainee BB) além do ruído genérico (vaga de emprego, processo seletivo).
- **4 RSAs** (5 headlines + 4 descriptions cada, mesmo texto nos 4 grupos, mencionando aulas ao vivo 17-20/08 e "Com Felipe Graton"), URLs sorteadas entre as 6 landing pages fornecidas pelo usuário (v2, v4, v6, v10 usadas; v5 e v11 sobraram sem uso).
- **Criada como PAUSED** por segurança (anúncios ainda em revisão de política).
- **Status:** ✅ criada e confirmada via API.

### 6. Ajustes do usuário na campanha de Search (revisão)
- Usuário **ativou** a campanha, ajustou a data no nome pra `[04.08.26]` e o período pra **04/08–17/08** (padrão da conta: campanhas sempre terminam às 17h do primeiro dia de aula ao vivo).
- Adicionou **UTMs** via tracking template de campanha: `{lpurl}?utm_source=google&utm_medium=cpc&utm_campaign={_campaignname}&utm_content={_adgroupname}&utm_term={_adname}&vk_source=paid_googleads&vk_ad_id={creative}`, com parâmetro customizado `adname = AD400` (código de atribuição cruzada Meta/Google/AC) em todos os 4 anúncios.
- Adicionou os assets de **Nome da Empresa** ("Brabo Concursos") e **Logotipo** no nível de campanha.
- **Status:** ✅ revisado e confirmado via API — tudo consistente, nada a ajustar.

### 7. Diagnóstico de CPL — Google vs Meta, validação do relatório do Felipe Graton
- **Contexto:** Felipe enviou um diagnóstico (PDF) mostrando Google Ads a R$6,70/lead contra R$2,14 do Meta nos dois primeiros dias de captação (03-04/08), com hipótese de causa em uma lista de remarketing pequena + "Segmentação Otimizada" ligada.
- **Validação:** cruzei os números do relatório com dado ao vivo puxado direto da API do Google Ads e do banco (`meta_ads_daily`/`google_ads_daily`) — os valores batem quase ao centavo (CPL de cada ad group conferido, diferença de 1-3% por causa do timing da consulta).
- **Achado 1 confirmado:** lista "Viu vídeos PBB Pré-Quali - 540D - [PBB-AGO-26]" (user list id `9386506819`) tem `sizeForDisplay: 0` — abaixo do volume mínimo que o YouTube exige pra servir remarketing corretamente.
- **Achado 2 (correção ao relatório):** "Segmentação Otimizada" estava ligada em agosto, mas **também estava ligada em junho** (PBB-JUN-26, mesmas 12 campanhas) — não é o que mudou entre os dois lançamentos, é uma configuração antiga.
- **Achado 3 (real diferença jun→ago):** Target CPA de campanha subiu de R$6,00 pra R$7,50 nas campanhas "potencial" (quente e frio) entre junho e agosto — não muda em "principal", que ficou igual (R$7,50 nos dois).
- **Achado 4:** dado horário (03-04/08) mostrou o padrão clássico de trava/pico do Smart Bidding depois que o usuário baixou o CPA pra perto de R$6,00 na noite de 03/08 — buraco de entrega de madrugada (impressões quase zeradas 02h-04h) seguido de picos de CPL de R$23-32 em horários específicos.

### 8. Consolidação de CPA-alvo por grupo de anúncios — campanhas Específico (TESTE)
- **O que:** confirmado que, igual ao PI-AGO-26 (ver `MUDANCAS_PI-AGO-26.md`, itens 3 e 21), as 6 campanhas Demand Gen de captação do PBB tinham CPA-alvo sobreposto por grupo de anúncios (`effectiveTargetCpaSource: AD_GROUP`, valores de R$6,50 a R$7,50), com o CPA da campanha (R$7,50) decorativo.
- **Aplicado:** removido o override de CPA-alvo dos 4 grupos de anúncio das campanhas Específico:
  - `[GA][captação][específico][potencial][PBB-AGO-26][03.08.26]` (id `24088528524`) — grupos "00 - Viu vídeos Pré-quali" e "01 - Viu vídeos Pré-quali Lançamentos Anteriores"
  - `[GA][captação][específico][principal][PBB-AGO-26][03.08.26]` (id `24095767624`) — mesmos 2 grupos
- **Confirmado via API:** os 4 grupos agora mostram `effectiveTargetCpaSource: CAMPAIGN_BIDDING_STRATEGY`, puxando o CPA único de R$7,50 da campanha.
- **Escopo:** só Específico por enquanto — teste isolado antes de replicar em Quente e Frio.
- **⚠️ Risco identificado:** no PI, a réplica desse teste nas outras 5 campanhas ficou bloqueada porque o time ajusta o CPA-alvo manualmente 3x/dia, o que reseta a fase de aprendizado do Smart Bidding e anula o ganho da consolidação. Usuário confirmou que esse hábito existe no PBB também (baixaram o CPA manualmente na noite de 03/08) — **combinado que os ajustes manuais de CPA ficam pausados nas campanhas Específico enquanto o teste roda**.
- **Meta do teste:** replicar o resultado do PI (CPA caiu de R$4,84 pra R$4,28, -12%, sem cortar orçamento).
- **Pendência:** usuário pediu CPA de campanha próximo de R$5 — recomendado NÃO baixar agora (CPL atual já está acima do R$7,50 vigente, e duas mudanças simultâneas — corte de CPA + consolidação — impediriam saber qual delas gerou o resultado). Plano: deixar estabilizar 2-3 dias, reavaliar, e se cortar, fazer em passos pequenos (R$7,50→R$6,50→R$5,50), não direto pra R$5.
- **Status:** 🟡 em teste, aguardando resultado.

### 9. Segmentação Otimizada — tentativa de desativação (campanhas Específico)
- **O que:** tentei desligar `demandGenCampaignSettings.upgradedTargeting` via API nas 6 campanhas — bloqueado, campo retorna `IMMUTABLE_FIELD` (só pode ser definido na criação da campanha).
- **Usuário desativou manualmente pela interface** (tela "Segmentação Otimizada" dentro da configuração do grupo de anúncios) nas campanhas Específico e salvou.
- **Não confirmado via API:** reconsultei depois da ação do usuário e nem `campaign.demandGenCampaignSettings.upgradedTargeting` nem `ad_group.targeting_setting.target_restrictions` (dimensão AUDIENCE) mudaram — os dois seguem exatamente como antes (`True` / `bidOnly: false`).
- **Conclusão:** ou esse toggle de UI não é exposto pelos campos que a API v22 disponibiliza pra Demand Gen, ou há outro mecanismo interno não identificado. **Vamos validar pelo resultado de performance, não pela configuração** — se o CPL não melhorar nos próximos dias mesmo com a consolidação de CPA, reconsiderar se o toggle realmente teve efeito.
- **Status:** ⚠️ ação feita pelo usuário na UI, efeito não confirmável via API.

### 10. Dayparting — campanhas Específico
- **O que:** cronograma de anúncios com ajuste de lance por horário, baseado em CPA por hora agregado das 2 campanhas Específico (potencial + principal), dado de 03-04/08 (700 conversões, CPA médio R$9,05).
- **Antes:** sem ajuste, cronograma neutro (0h-24h, 1 entrada por dia, sem `bidModifier`).
- **Removido:** as 14 entradas neutras (7 dias × 2 campanhas).
- **Criado — 6 faixas, repetidas nos 7 dias da semana (84 critérios, 2 campanhas):**

  | Horário | Ajuste | CPA no período / índice |
  |---|---|---|
  | 00h–05h | 0% | próximo da média |
  | 05h–08h | −15% | R$11-17 / 1,23-1,85x |
  | 08h–13h | +25% | R$5-9 / 0,57-1,01x (9h-12h puxando pra baixo) |
  | 13h–15h | 0% | próximo da média |
  | 15h–18h | −15% | R$9-15 / 1,03-1,71x |
  | 18h–24h | 0% | volume baixo à noite, sem sinal forte o suficiente |

- **Pendência:** amostra de só 2 dias — recalcular com mais dado em 3-4 dias, igual à ressalva do PI pra campanha de Search.
- **Status:** ✅ aplicado, 84/84 confirmado via API.

## 2026-08-05

### 11. Automação de orçamento diário (Meta + Google) via GitHub Actions
- **O que:** criado `scripts/apply_daily_budget.py` + `performance-manager/PBB-AGO-26/orcamento_diario.json` (tabela dia-a-dia de 03/08 a 17/08 pras 18 campanhas de captação) + workflow `.github/workflows/pbb-ago-26-daily-budget.yml`, rodando via cron todo dia às 00h05 (America/Sao_Paulo), com gatilho manual (`workflow_dispatch`) também disponível.
- **Credenciais:** usuário cadastrou os 6 secrets necessários (`META_ACCESS_TOKEN`, `GOOGLE_ADS_REFRESH_TOKEN`, `GOOGLE_ADS_CLIENT_ID`, `GOOGLE_ADS_CLIENT_SECRET`, `GOOGLE_ADS_DEVELOPER_TOKEN`, `GOOGLE_ADS_LOGIN_CUSTOMER_ID`) em Settings → Secrets and variables → Actions do repositório.
- **Teste manual (04/08):** disparado via `workflow_dispatch`, sucesso em 30s, 18/18 campanhas aplicadas.
- **Primeira execução agendada (05/08, 00h05):** rodou com atraso (log mostra `updated_time` 08:33 no Meta, não 00:05) — atraso conhecido do agendador de cron do GitHub Actions em horários de alta demanda, não é falha nossa. **Confirmado via API que os valores aplicados batem 100% com o plano do dia** (18/18 campanhas conferidas).
- **Status:** ✅ automação ativa e validada, rodando sozinha até 17/08.

### 12. Diagnóstico de entrega — Google Ads, comparativo 04/08 x 05/08
- **Contexto:** pedido pra analisar performance entre os dois dias e investigar causa de baixa entrega, visando montar um plano de "forçar a entrega".
- **Achado 1 — todas as 6 campanhas Demand Gen em `primary_status: LEARNING` (`BIDDING_STRATEGY_LEARNING`).** Esperado em Específico (mexemos em CPA e dayparting ontem), mas Quente e Frio também estão em learning sem termos mexido na configuração deles — suspeita de que a troca diária de orçamento pela automação (item 11) reinicia parcialmente o aprendizado do Smart Bidding todo dia, o que pode estar impedindo a conta de sair do modo de aprendizado.
- **Achado 2 — 14 anúncios das campanhas "principal" (quente/frio/específico) com `APPROVED_LIMITED` por `FINANCIAL_SERVICES_VERIFICATION`**, restritos a `AREA_OF_INTEREST_ONLY` (só serve pra públicos de interesse específico, não pro público geral). Campanhas "potencial" não têm esse problema. Causa provável de under-delivery nas campanhas de maior orçamento.
  - **Confirmado com o usuário:** a empresa não presta serviço financeiro (é curso preparatório pra concurso público do Banco do Brasil) — classificação do Google é equivocada. Caminho correto é **contestar a classificação no Policy Manager**, não entrar no processo de Verificação de Anunciante de Serviços Financeiros (que é pra instituição financeira de verdade).
- **Achado 3 — campanha de Search (`24108291340`) pausada, R$0 gasto em 05/08.** Confirmado com o usuário: **decisão deles, intencional, manter pausada.**
- **Achado 4 — CPA fragmentado por grupo de anúncios voltou, e não só em Específico.** A diretoria vinha ajustando o CPA manualmente em **todas as 6 campanhas** (não só as 2 que testamos ontem) — a consolidação de Específico do item 8 tinha sido desfeita (3 dos 4 grupos com override novo), e Quente/Frio nunca chegaram a ser consolidadas, todas com override individual por grupo (valores na faixa R$5,40-6,90).
- **Números do comparativo (04/08 dia inteiro x 05/08 parcial):** Quente Principal R$4.508,03/810 leads (CPL R$5,57) → R$1.949,11/265 leads (CPL R$7,36); Frio Principal R$1.562,32/127 leads (CPL R$12,30) → R$545,81/19 leads (CPL R$28,73); Específico Potencial R$761,02/56 leads (CPL R$13,59) → R$7,16/1 lead, praticamente parada; Quente Search R$666,91/3 leads (CPL R$222,30) → R$0 (pausada, intencional).
- **Status:** ✅ investigação concluída, ações do item 13 aplicadas em seguida.

### 13. Consolidação de CPA-alvo em TODAS as 6 campanhas Demand Gen
- **O que:** a pedido do usuário ("ajuste todos os CPAs para conseguirmos equalizar melhor as campanhas, veja em todas"), removido o override de CPA-alvo por grupo de anúncios nas 6 campanhas (não só Específico como no item 8) — **27 grupos de anúncio no total** (7 em quente principal, 7 em quente potencial, 5 em frio principal, 5 em frio potencial, 2 em específico principal, 2 em específico potencial já estavam limpos do item 8, refeito porque a diretoria tinha refragmentado).
- **Confirmado via API:** todos os 27 grupos agora mostram `effectiveTargetCpaSource: CAMPAIGN_BIDDING_STRATEGY`. **As 6 campanhas estão equalizadas no mesmo CPA de campanha, R$7,50.**
- **⚠️ Risco em aberto:** a diretoria ajusta CPA manualmente e já desfez essa mesma consolidação uma vez (em Específico, no dia anterior). Sem alinhar com quem faz esses ajustes, a consolidação pode ser desfeita de novo a qualquer momento — **combinar formalmente que os ajustes manuais de CPA ficam pausados em todas as 6 campanhas** enquanto o teste roda.
- **Status:** ✅ aplicado, 27/27 confirmado via API.

## 2026-08-06

### 14. Contestação de Serviços Financeiros — redigida
- **O que:** criado `performance-manager/PBB-AGO-26/contestacao_policy_manager.md` com o texto pronto pra submeter no Policy Manager, explicando que a Brabo Concursos não presta serviço financeiro (é curso preparatório pro concurso do Banco do Brasil) e listando os 14 anúncios afetados.
- **Validação adicional pedida pelo usuário:** pesquisei documentação oficial do Google sobre o impacto de CPA fragmentado por grupo de anúncios (item 13) — confirmado que o próprio Google desaconselha ("this isn't recommended as it can restrict Smart Bidding") e recomenda pelo menos 30 conversões/mês por grupo pra estabilidade, o que a maioria dos grupos Frio/Específico não atinge quando fragmentados. Fontes citadas no chat (Google Ads Help + Google Ads API docs + Display Smart Bidding Guide).
- **Status:** ✅ texto pronto, pendente de submissão por quem tem acesso admin.

### 15. Descoberta de 3 campanhas novas do Google não cobertas pela automação — "new-ads"
- **O que:** usuário confirmou ter criado 3 campanhas de teste em 05/08 (`[GA][captação][quente][principal][new-ads]` id `24107222834`, `[GA][captação][frio][principal][new-ads]` id `24112230952`, `[GA][captação][específico][principal][new-ads]` id `24101539167`), fora da automação do item 11.
- **Regra definida:** dentro de cada clima, a fatia que ia só pra "principal" agora se divide **70% principal original / 30% principal new-ads**. Potencial não muda.
- **Aplicado:** `performance-manager/PBB-AGO-26/orcamento_diario.json` regravado com 9 chaves no Google (era 6) pra todos os dias de 03/08 a 17/08; `scripts/apply_daily_budget.py` não precisou de nenhuma alteração de código — já é genérico, lê as chaves que existirem no JSON.
- **Testado:** rodado manualmente pro dia de hoje (06/08), 21/21 campanhas (12 Meta + 9 Google) aplicadas com sucesso via API.
- **Valores de hoje (06/08), Google:** Quente Principal R$2.859,24 / Quente Principal New-ads R$1.225,39 / Quente Potencial R$1.791,85 / Frio Principal R$991,38 / Frio Principal New-ads R$424,88 / Frio Potencial R$557,29 / Específico Principal R$1.750,12 / Específico Principal New-ads R$750,05 / Específico Potencial R$992,99.
- **Status:** ✅ aplicado e commitado.

## Pendências gerais (não esquecer)
- **Combinar com a diretoria** que os ajustes manuais de CPA ficam pausados nas 6 campanhas de captação do Google por alguns dias, pra não desfazer a consolidação do item 13 de novo.
- Avaliar se a automação de orçamento diário (item 11) está contribuindo pra manter as campanhas em `LEARNING` permanente — considerar suavizar a variação % dia a dia se confirmado, depois que o efeito da consolidação de CPA puder ser isolado.
- Submeter a contestação do item 14 no Policy Manager — pendente de quem tem acesso admin na conta.
- Reavaliar CPL das 6 campanhas em 2-3 dias pra medir o efeito da consolidação total de CPA.
- Acompanhar as 3 campanhas "new-ads" (item 15) — ainda sem histórico de performance pra avaliar.
- P-Max do Google ainda não existe — projeção de verba já calculada (baseada na proporção histórica do PBB-JUN-26), falta criar a campanha.

## 2026-08-06 (continuação)

### 16. Faixa etária 22-55 em todos os grupos de anúncio do Facebook (captação)
- **O que:** a pedido do usuário, alterada a segmentação de idade pra **22 a 55 anos** nos 48 grupos de anúncio das 12 campanhas de captação (quente/frio/específico × principal/potencial/teste/reels).
- **Obstáculo real — Advantage+ Audience:** o Meta bloqueia `age_max` abaixo de 65 em grupos que usam expansão de público, com o erro `error_subcode 1870189`. A causa não era só `targeting_relaxation_types` (custom_audience/lookalike) — o campo decisivo era `targeting_automation.individual_setting.age` e `.gender`, que precisavam ir pra **0** (estavam em 1, o que sinaliza "configuração individual relaxada" e ativa o Advantage+ de fato). Descoberto via busca na documentação/blog de desenvolvedores do Meta sobre a atualização de comportamento do Advantage+ audience (jun/2026).
- **Payload final que funcionou:** manter todo o `targeting` original (públicos, geo, posicionamentos) e só sobrescrever `age_min:22`, `age_max:55`, `targeting_relaxation_types: {custom_audience:0, lookalike:0}` e `targeting_automation: {advantage_audience:0, individual_setting:{age:0, gender:0}}`.
- **Obstáculo à parte:** a conta de anúncios bateu o limite de chamadas da API (`error code 17`) várias vezes durante a tarefa — não é o mesmo limite do app (que está com folga, confirmado pelo usuário via painel "Limitação de volume no nível do aplicativo"). É um throttle no nível da conta de anúncios, que ficou instável ao longo da tarde. Contornado processando em lotes menores com pausa entre chamadas, e usando o MCP como caminho alternativo quando a chamada direta travava.
- **Status:** ✅ 48/48 grupos de anúncio confirmados com idade 22-55, sem alterar nenhum outro parâmetro de segmentação (públicos, geo, posicionamentos mantidos idênticos).

### 17. Verba de Quente dividida entre 2 contas — Felipe Graton (40%) + Criadora de Públicos 2 (60%)
- **Contexto:** usuário ativou 2 campanhas na conta `act_1175937361058463` ("CA - Criadora de Públicos 2", mesmo Business Manager do Felipe Graton) — campanhas antigas do PBB-JUN-26 reaproveitadas e renomeadas com `[OLD]`:
  - `[MA][cadastro][captação][quente][principal][OLD][PBB-AGO-26]` (id `120245854010630549`)
  - `[MA][cadastro][captação][quente][potencial][OLD][PBB-AGO-26]` (id `120246130520210549`)
- **Regra definida:** dentro do total diário de "Quente", **60% vai pras 2 campanhas da Criadora de Públicos** (proporção 70/20 entre principal/potencial reescalada pra somar 60%) e **40% fica nas 4 campanhas do Felipe Graton** (principal/potencial/teste/reels, mesma proporção 70/20/5/5 de sempre, agora valendo 40% do total).
- **Aplicado:** `orcamento_diario.json` regravado com 6 chaves de "quente" no Meta (era 4) pra todos os dias de 03/08 a 17/08. Script não precisou de alteração — a API do Meta aceita atualizar campanha por ID direto, funciona entre contas diferentes sem mudança de lógica.
- **Testado:** rodado manualmente pra hoje (06/08), 14/14 campanhas Meta (incluindo as 2 novas) + 9/9 Google, 23/23 sucesso via API.
- **Valores de hoje (06/08):** Quente Principal (Felipe Graton) R$1.160,44 / Quente Potencial R$331,55 / Quente Teste R$82,89 / Quente Reels R$82,89 / Quente Principal [OLD] (Criadora) R$1.934,07 / Quente Potencial [OLD] (Criadora) R$552,59.
- **Status:** ✅ aplicado e commitado.

## 2026-08-07

### 18. Migração das 12 campanhas de captação — Felipe Graton → Criadora de Públicos 2
- **Contexto:** usuário pediu pra migrar todas as campanhas de captação de `act_438212624024216` (Felipe Graton) pra `act_1175937361058463` (Criadora de Públicos 2), cópia exata (segmentação, públicos, anúncios, URLs, UTMs) — abordagem campanha por campanha, confirmando cada uma antes de seguir pra próxima.
- **Preparação:**
  - Pausadas as 2 campanhas `[OLD]` (leftover do PBB-JUN-26) na Criadora de Públicos, a pedido do usuário.
  - Confirmado que a campanha `[MA][cadastro][captação][quente][principal][PBB-AGO-26]` (id `120249399615500549`) já tinha sido criada e montada manualmente pelo usuário na Criadora de Públicos — 7 grupos + anúncios completos, não precisou de migração.
  - **Achado técnico**: públicos customizados (custom audiences) são compartilháveis entre contas do mesmo Business Manager (confirmado via `/adaccounts` do público) — não precisam ser recriados. **Criativos (vídeo/imagem) não são compartilhados automaticamente** — vídeos funcionam direto pelo `video_id` (mesma Business Manager), mas imagens (`image_hash`) precisam ser baixadas da conta de origem e re-enviadas na conta de destino, gerando um hash novo por imagem.
  - Criado `meta_migrate_helpers.py` (scratchpad) com função reutilizável de remapeamento de `image_hash` (cache em `image_hash_map.json`) e criação de anúncio (`create_ad`), cobrindo vídeo único, imagem única e carrossel (`child_attachments`).
  - **Obstáculo recorrente**: a conta segue em `development_access` (ver item de upgrade abaixo) — bateu rate limit várias vezes durante a migração, contornado com pausas entre chamadas e uso do MCP como caminho alternativo quando a chamada direta falhava.
- **Quente Potencial** (`120249422483500549`): 2 de 7 grupos concluídos (00, 01) com 14 anúncios completos — os outros 5 dependiam de públicos ainda não compartilhados na época. Retomar depois que os públicos abaixo forem confirmados.
- **Quente Teste, Frio Teste, Específico Teste** — **concluídas 100%**:
  - Quente Teste (`120249423617300549`), Frio Teste (`120249423618410549`), Específico Teste (`120249423620760549`).
  - 12 grupos de anúncio criados, 72 anúncios criados (6 por grupo), **72/72 sucesso**, incluindo carrosséis com re-upload de imagem.
  - **5 públicos identificados como bloqueio** (apareciam como `excluded_custom_audiences` em todos os grupos que falhavam na primeira tentativa): `[IG]`/`[FB] - Envolvimento Todos [Felipe Graton] - 180D` e `- 60D`, e `[SITE] Visitou Brabo Concursos - 180D`. Resolvido assim:
    - Os dois "180D" foram **recriados** (não compartilhados) pelo usuário diretamente na Criadora de Públicos — IDs novos: `120233186165430549` ([IG]) e `120233186192980549` ([FB]).
    - Os dois "60D" foram efetivamente **compartilhados** (mesmo ID funciona nas duas contas): `120212923212150520` ([IG]) e `120212923214490520` ([FB]).
    - `[SITE] Visitou Brabo Concursos - 180D`: já existia um público **com o mesmo nome, ID diferente**, criado anteriormente e nativo da conta Criadora de Públicos (`120204080799680754`) — usado no lugar do original (`120232395096280695`, que pertence a uma terceira conta, `718198002133850`, e segue sem compartilhamento).
- **Status:** 🟡 em andamento — 4 campanhas concluídas (Quente Principal, Quente Teste, Frio Teste, Específico Teste), 1 parcial (Quente Potencial), 7 pendentes (Quente Reels, Frio Principal/Potencial/Reels, Específico Principal/Potencial/Reels).

### 19. Upgrade de Marketing API Access Tier (`ads_management`) — submetido para análise
- **Contexto:** confirmado via header `x-business-use-case-usage` da própria resposta da API que a conta `act_438212624024216` está em `ads_api_access_tier: development_access` — nível com teto de chamadas baixo, causa raiz dos travamentos recorrentes de rate limit (`error code 17`) durante toda a sessão de hoje. Não tem relação com o app estar "Publicado" — é uma permissão separada, específica pra `ads_management`.
- **Requisito de qualificação** (documentação oficial do Meta): 500+ chamadas de Marketing API nos últimos 15 dias, taxa de erro abaixo de 15%. Confirmado como "Concluída" na tela de submissão do app (`MKT Brabo Concursos`, App ID `1695645641374745`).
- **Processo seguido:** App Dashboard → Casos de uso → Criar e gerenciar anúncios → Permissões e recursos → linha "Marketing API Access Tier" ("Acesso limitado") → submissão formal de Análise do App, cobrindo: motivo da solicitação, configurações do app (ícone, categoria "Educação", corrigido URL de Termos de Serviço e Exclusão de dados que apontavam erroneamente pro facebook.com), Tratamento de dados (RGPD/LGPD — responsável legal informado: Aprovasim Cursos Treinamentos e Coaching LTDA, CNPJ 30.704.315/0001-80; Supabase Inc. declarado como operador de dados, categoria "TI/armazenamento em nuvem", países Brasil + Estados Unidos, banco hospedado em `sa-east-1`), plataforma Website (`https://braboconcursos.com.br/`) e instruções de teste (integração server-to-server, sem Facebook Login).
- **Status:** ✅ enviado para análise do Meta em 07/08/26. Aguardando aprovação (sem prazo divulgado) — assim que aprovado, o teto de `development_access` deixa de existir nessa conta.

## Pendências gerais (atualizado 07/08)
- Continuar migração das 7 campanhas restantes (Quente Reels, Frio Principal/Potencial/Reels, Específico Principal/Potencial/Reels) pra Criadora de Públicos 2.
- Retomar os 5 grupos pendentes de Quente Potencial assim que possível.
- Depois que as 12 campanhas estiverem migradas: decidir se as originais em Felipe Graton são pausadas/arquivadas, e atualizar `orcamento_diario.json` + `scripts/apply_daily_budget.py` pra apontar pra conta nova.
- Acompanhar aprovação do Marketing API Access Tier (item 19).
