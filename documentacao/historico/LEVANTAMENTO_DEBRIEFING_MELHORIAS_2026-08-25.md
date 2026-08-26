# Levantamento — Melhorias do Debriefing (reunião 25/08/2026)

Mapeamento da pauta da reunião contra o que já existe no banco/API do Brabo Analytics,
o que é derivável dos dados atuais (só falta construir a análise/tela) e o que exige
coleta nova.

Legenda: ✅ temos | 🟡 derivável (dado existe, falta cruzar/exibir) | ❌ falta coletar

> **Atualização 25/08/2026 (tarde):** primeiros 4 itens deriváveis implementados:
> 1. ✅ Detalhamento dos públicos por categoria (Cadastrados, Envolvimento 30/60/180D, Vídeo, Lista, Semelhante...) por clima — seção nova no Debriefing (`por_publico_captacao` no reader Meta)
> 2. ✅ Compradores dentro × fora dos grupos (cruzamento por telefone) — seção "Compradores × Grupos" na página Grupos de WhatsApp. PI-AGO-26: 95,6% dos compradores estavam nos grupos
> 3. ✅ Compradores lead novo × lead antigo (created_at do contato AC vs início do lançamento) — seção nova no Debriefing. PI-AGO-26: 29,5% dos compradores já estavam na base antes do lançamento
> 4. ✅ Perfil do lead por anúncio top 5 × pesquisa (utm_term ADxxx × Typeform por e-mail) — seção nova no Debriefing. Descoberta importante: o código do anúncio vem no **utm_term** (utm_content traz o adset)
>
> **Atualização 26/08/2026:** mais 3 itens deriváveis concluídos:
> 5. ✅ Pesquisa — taxa de resposta da base (47.136 respostas, 14,6% da base no PI-AGO-26); "quem recebeu" segue pendente dos disparos WhatsApp. `etl_ac_campaigns` entrou no `run_all` (estava parado desde 23/06)
> 6. ✅ Vendas Comercial × IA × Orgânico via `codigo_sck` Hotmart (ana, HOTMART_SALES_AGENT, agente_ia) + `utm_source` TMB (COMERCIAL, IA). PI-AGO-26: 63 comercial (R$ 114k) + 15 IA (R$ 28k)
> 7. ✅ Abertura do carrinho hora a hora × lançamento anterior (reusa `read_dia1_sales` do /comparativo)
>
> Com isso, TODOS os itens deriváveis dos dados existentes estão no ar. O que resta na pauta exige coleta nova (ver lista priorizada no fim).

---

## 1. Estratégia — Planejado × Executado

| Item | Status | Fonte / o que falta |
|---|---|---|
| Executado por plataforma (Meta/YouTube) | ✅ | `meta_ads_daily`, `google_ads_daily` |
| Executado por público (Quente/Frio/Específico) | ✅ | Já no debriefing (`por_temperatura`, derivado do nome de campanha/adset) |
| % de gasto por etapa e plataforma | ✅ | `por_etapa` (Pré-Quali, Captação, sub-etapas de Remarketing) |
| **Planejado** por etapa | 🟡 | `launch_config.etapas` (verba por etapa do wizard, usada pelo `budget_alert`) — existe por etapa, **não** por plataforma×público |
| Planejado por plataforma × público | ❌ | Estender o wizard/`launch_config` pra registrar o plano nesse grão |

## 2. Pré-Qualificação

| Item | Status | Fonte / o que falta |
|---|---|---|
| Investimento por plataforma | ✅ | `por_etapa["Pré-Qualificação"]` Meta + Google |
| Detalhamento de anúncios | ✅ | daily por ad |
| Pessoas que assistiram 50% + custo por 50% | ✅ | `video_views_50` (Meta exato; Google estimado pela API) |
| Cadastrados relacionados à pré-quali | ❌ | Lead só entra na Captação via UTM; pré-quali não gera cadastro rastreável hoje. Precisa UTM/lista própria da pré-quali no AC |
| Vídeos antigos × novos (invest. + qualificação) | ❌ | Não existe flag "antigo/novo" por ADxxx. Gasto por ad existe; falta uma tabela/YAML de metadata do criativo (novo × reutilizado, lançamento de origem) |
| Top 5 por plataforma | ✅ | já derivável do daily + creative_data |

## 3. Captação — Performance + Qualidade

| Item | Status | Fonte / o que falta |
|---|---|---|
| Detalhamento de público e de anúncios | ✅ | mantém o que já existe |
| Antigos × novos | ❌ | mesma flag de metadata do item 2 |
| Qualidade por plataforma com **REGIÃO+CIDADE** | ❌ | Comprador tem cidade/UF (`hotmart_clean_oficial.cidade/estado_provincia`, `tmb.cidade/estado`) ✅, mas **lead não** (AC só traz nome/email/phone/UTMs) e os breakdowns de mídia são só age/gender (`meta_ads_demographics_daily`, `google_ads_demographics_daily`). Precisa: breakdown `region` no ETL Meta + `user_location_view` no Google, e/ou UF/cidade na página de captura |
| Detalhamento dos públicos (Env. 30d/180d, Vídeo, Lista) | 🟡 | Google: `google_ads_audiences_daily` ✅. Meta: o público está no **nome do adset** (cascateamento 00-06) — falta parser/agrupamento por público |
| Mapear testes: carrossel, com/sem título | ❌ | Detectável via API (`object_story_spec`/`asset_feed_spec` do criativo) — falta estender o ETL de criativos pra salvar formato e presença de título |
| Perfil do lead por anúncio (top 5) × pesquisa | 🟡 | `leads.utm_content` (ADxxx) + `typeform_respostas` por e-mail — cruzamento possível hoje, falta a análise/tela |
| IA nos anúncios (criativo + copy + métricas) | 🟡 | Imagem ✅ (`ad_creatives` com bytes), métricas ✅; **copy (texto/título/descrição) não é salva** — estender ETL Meta/Google pra guardar body/headline |
| Foram para a live ← de qual anúncio | ❌ | YouTube não identifica viewer. Caminho: cruzar sorteio da live / janela WhatsApp / pesquisa com a base de leads |

## 4. WhatsApp + Pesquisa + Sorteio

| Item | Status | Fonte / o que falta |
|---|---|---|
| Grupos: total, entradas, taxa, normal×VIP, saídas | ✅ | tabelas `[CODE]_API` / `[CODE]_VIP_API` (página nova de Grupos) |
| Compradores dentro × fora dos grupos | 🟡 | cruzável por telefone (grupos × vendas) — falta a tela/consulta |
| Pesquisa: quem **respondeu** | ✅ | `typeform_respostas` |
| Pesquisa: quem **recebeu** + taxa de resposta | 🟡 | `etl_ac_campaigns.py` já coleta envios/aberturas/cliques por campanha (`ac_campaigns`) — se o disparo da pesquisa for por e-mail/AC dá pra fechar; disparo por WhatsApp depende do item de disparos abaixo |
| Sorteio da live (participantes, % da base, cruzamentos) | ❌ | Sem fonte. Precisa export/planilha dos participantes com telefone/e-mail pra cruzar com plataforma/público/anúncio/dia |
| Abriu janela com "SORTEIO" (domingo) | ❌ | Dado da ferramenta de WhatsApp API (Utily) — precisa export/API |
| Páginas de captura A×B | ❌→🟡 | **GA4 em andamento**: `etl/get_ga4_token.py` + `etl/ga4_discover.py` já criados; falta o ETL de pageviews/conversão por página |
| Página de Obrigado A×B (visitas → ação WhatsApp → conversão) | ❌ | mesmo caminho GA4 + evento de clique no botão do WhatsApp |
| Disparos dos grupos (Utily × MKT, valor gasto, janelas abertas, engajamento) | ❌ | Escopo novo: API/export da plataforma de WhatsApp. Nada no banco hoje |
| Qtde entrando na pré-quali e captação (grupos) | 🟡 | `GRUPO DA CAMPANHA` nas tabelas de grupos — se a nomenclatura separar pré-quali de captação, é só agrupar |

## 5. Aulas ao Vivo

| Item | Status | Fonte / o que falta |
|---|---|---|
| Pico simultâneo, média, views, retenção, tempo médio, comparativo | ✅ | `youtube_aulas_stats` (ETL YouTube Analytics já rodando por launch) |
| **Chat analisado por IA** | ❌ | O chat da live some depois do encerramento. Precisa coletor rodando **durante** a live (YouTube Live Chat API) ou export manual. Escopo novo — agendar por aula |

## 6. Vendas

| Item | Status | Fonte / o que falta |
|---|---|---|
| Vendas por dia, horário do 1º dia | ✅ | timeline + leitura hora-a-hora do dia 1 |
| Formas de pagamento (detalhado) | ✅ | `metodo_de_pagamento` / `forma_pagamento` |
| TMB × Hotmart | ✅ | duas tabelas oficiais |
| VIP × normal | 🟡 | comprador × grupos VIP por telefone — cruzável, falta tela |
| Comercial × orgânico | 🟡 | Hotmart tem `codigo_src`/`codigo_sck`/`ferramenta_de_venda` — se o comercial usar src próprio no link, dá pra marcar. Precisa padronizar o src do comercial |
| Comparativo com anterior (horários) | 🟡 | dado existe, falta comparativo hora-a-hora no debriefing |
| Recuperação de carrinho (modelo João) | ❌ | Boletos gerados×pagos existem parcialmente; falta a definição do modelo + dados de recusa/abandono (Hotmart tem `motivo_de_recusa_de_cartao`) |
| Leads antigos compraram agora? | 🟡 | leads de lançamentos anteriores × compradores atuais por e-mail — dado existe, análise falta |
| IA de recuperação (valor gasto, recuperação, taxa) | ❌ | dados da ferramenta do comercial — escopo novo |

## 7. Caminho do Comprador (base unificada por pessoa)

Todos os elos têm chave de junção (e-mail e/ou telefone):

| Elo | Fonte | Chave |
|---|---|---|
| Origem/anúncio + data cadastro | `leads` (utm_content, created_at) | e-mail, telefone |
| Normal ou VIP | tabelas `_API` / `_VIP_API` | telefone |
| Respondeu pesquisa | `typeform_respostas` | e-mail |
| Participou sorteio/live | ❌ falta fonte (item 4) | — |
| Comprou | hotmart/tmb | e-mail, telefone |
| Orgânico ou Comercial | 🟡 via `codigo_src` (item 6) | — |

**Conclusão: a base unificada é construível HOJE para ~70% do funil** (view/tabela
`caminho_comprador` juntando por e-mail/telefone, regras de matching já definidas —
só e-mail/telefone, sem nome). Os elos faltantes são sorteio e presença na live.

## 8. Público Comprador + Pesquisa Pós-Compra

- ❌ Não há pesquisa pós-compra no pipeline hoje. O ETL Typeform já suporta múltiplos
  forms por lançamento (`typeform_resolve`) — basta criar o form e cadastrar o ID.
- Ação: revisar/criar o questionário (perfil, momento, histórico, dificuldade,
  objetivos, motivo, objeções) e apontar o ETL pro novo form.

## 9. Mapear Testes (guia INSS, 19:30, carrossel, preço boleto, desconto à vista)

- 🟡 Preço do boleto (179,90 × 169,90) e desconto à vista: distinguíveis por
  `nome_deste_preco`/`codigo_do_preco`/`codigo_de_cupom` na Hotmart.
- ❌ Não existe registro estruturado de testes (hoje só nos .md do performance-manager).
  Precisa de uma tabela/registro de testes: data, hipótese, variantes, ads envolvidos.

---

## Resumo das novas coletas necessárias (ordem sugerida de esforço/valor)

1. **Copy + formato dos criativos** — estender ETL Meta/Google (base pra IA de anúncios, carrossel, com/sem título). Baixo esforço, API já integrada.
2. **Região/cidade nos breakdowns** — breakdown `region` Meta + `user_location_view` Google. Baixo esforço.
3. **Flag antigo×novo por ADxxx** — tabela de metadata de criativo (ou campo no YAML). Baixo esforço, destrava 2 seções.
4. **GA4 (páginas de captura + obrigado)** — já encaminhado (token + discover prontos); falta o ETL. Médio.
5. **Base unificada "caminho do comprador"** — só engenharia sobre dados existentes. Médio.
6. **Disparos WhatsApp (Utily): envios, janelas, gasto, engajamento** — API/export da ferramenta. Escopo novo, médio/alto.
7. **Chat das lives** — coletor Live Chat API rodando durante a aula. Escopo novo, precisa rodar ao vivo.
8. **Sorteio da live** — definir export dos participantes (com telefone/e-mail).
9. **Pesquisa pós-compra** — criar form + cadastrar no ETL Typeform.
10. **Padronizar src do comercial** — pra separar comercial × orgânico nas vendas.
11. **Registro estruturado de testes** — tabela simples de testes por lançamento.
