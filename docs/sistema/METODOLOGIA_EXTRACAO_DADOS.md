---
titulo: "Metodologia de Extração e Atribuição de Dados por Lançamento"
area: sistema
status: vigente
atualizado: 2026-10-27
responde:
  - "como e medido o carregamento da pagina dos anuncios"
  - "o que e landing page view"
  - "como ler a velocidade das landing pages"
  - "o que e crux lcp inp cls"
  - "como cada metrica e extraida"
  - "regras de atribuicao lead-venda"
  - "o que mudou com o fim do Typeform"
  - "como as metricas das aulas do YouTube sao extraidas sem API"
  - "por que o roas de um lancamento fechado cai sozinho"
  - "por que o debriefing de um lancamento antigo muda de numero"
  - "por que compradores somem da atribuicao"
relacionados:
  - "[[ARQUITETURA]]"
---

# Metodologia de Extração e Atribuição de Dados por Lançamento

<!-- SUMARIO:INICIO -->

> [!abstract]- Sumario - 21 itens (gerado por `scripts/check_docs.py --atualizar-mapa`)
>
>
> **1. Visão Geral da Arquitetura (2.0 vs 1.0)**
>
> - [[METODOLOGIA_EXTRACAO_DADOS#Arquitetura 2.0 (Atual / Automatizada)|Arquitetura 2.0 (Atual / Automatizada)]]
> - [[METODOLOGIA_EXTRACAO_DADOS#Arquitetura 1.0 (Legado / Baseado em CSV)|Arquitetura 1.0 (Legado / Baseado em CSV)]]
>
> **2. Fontes de Dados e Integração (2.0)**
>
>
> **3. Metodologia de Cálculo (Atribuição)**
>
> - [[METODOLOGIA_EXTRACAO_DADOS#3.1 Atribuição de Leads (UTM Content)|3.1 Atribuição de Leads (UTM Content)]]
> - [[METODOLOGIA_EXTRACAO_DADOS#3.2 Cruzamento Vendas vs. Leads|3.2 Cruzamento Vendas vs. Leads]]
> - [[METODOLOGIA_EXTRACAO_DADOS#3.3 Métricas Derivadas na View|3.3 Métricas Derivadas na View]]
>
> **4. Limitações Conhecidas e Gaps Sistemáticos**
>
> - [[METODOLOGIA_EXTRACAO_DADOS#4.1 Leads: subcontagem de ~26% em relação aos Pixels|4.1 Leads: subcontagem de ~26% em relação aos Pixels]]
> - [[METODOLOGIA_EXTRACAO_DADOS#4.2 Vendas: subcontagem de ~32%|4.2 Vendas: subcontagem de ~32%]]
> - [[METODOLOGIA_EXTRACAO_DADOS#4.3 Confiabilidade das Fontes|4.3 Confiabilidade das Fontes]]
>
> **5. Como Iniciar um Novo Lançamento (Modelo 2.0)**
>
>
> **7. Status Atual e Evolução da V2 (Junho 2026)**
>
>
> **8. Marcos Concluídos na V2 (Junho 2026)**
>
>
> **9. Correções Críticas no Pipeline ETL (2026-06-25)**
>
> - [[METODOLOGIA_EXTRACAO_DADOS#9.1 `sys.path` invertido nos scripts ETL|9.1 `sys.path` invertido nos scripts ETL]]
> - [[METODOLOGIA_EXTRACAO_DADOS#9.2 `import pandas` ausente no `etl_meta_ads.py`|9.2 `import pandas` ausente no `etl_meta_ads.py`]]
> - [[METODOLOGIA_EXTRACAO_DADOS#9.3 Typeform deletava todos os dados do form no upsert|9.3 Typeform deletava todos os dados do form no upsert]]
> - [[METODOLOGIA_EXTRACAO_DADOS#9.4 Active Campaign API varrendo toda a conta para buscar UTMs|9.4 Active Campaign API varrendo toda a conta para buscar UTMs]]
> - [[METODOLOGIA_EXTRACAO_DADOS#9.5 Campos UTM do Active Campaign não configurados no `.env`|9.5 Campos UTM do Active Campaign não configurados no `.env`]]
> - [[METODOLOGIA_EXTRACAO_DADOS#Status após correções|Status após correções]]
>
> **10. Desligamento do Typeform e migração pro sistema de pesquisa interno (2026-08-31)**
>
>
> **11. Métricas das aulas no YouTube sem API (2026-09-15)**
>
> - [[METODOLOGIA_EXTRACAO_DADOS#Os três exports do Studio medem coisas diferentes (2026-09-15)|Os três exports do Studio medem coisas diferentes (2026-09-15)]]
>
> **12. Metricas das aulas no YouTube via API (2026-09-22)**
>
>
> **13. A atribuição de lançamento fechado apaga sozinha (2026-10-07)**
>
> - [[METODOLOGIA_EXTRACAO_DADOS#13.1 A trava (07/10/26, mesmo dia)|13.1 A trava (07/10/26, mesmo dia)]]
> - [[METODOLOGIA_EXTRACAO_DADOS#13.1b As leituras passaram a vir do estado (08/10/26)|13.1b As leituras passaram a vir do estado (08/10/26)]]
> - [[METODOLOGIA_EXTRACAO_DADOS#13.2 Recuperação pelo export do AC da época + trava diária|13.2 Recuperação pelo export do AC da época + trava diária]]
> - [[METODOLOGIA_EXTRACAO_DADOS#13.2b O que isso significa para a decisão de criativo (08/10/26)|13.2b O que isso significa para a decisão de criativo (08/10/26)]]
> - [[METODOLOGIA_EXTRACAO_DADOS#13.3 A tag do AC já guardava o histórico|13.3 A tag do AC já guardava o histórico]]
>
> **14. Carregamento da página — `landing_page_views` e LP por anúncio (2026-10-10)**
>
>
> **15. Receita líquida da Hotmart: o que cada coluna significa em cada origem (2026-10-20, corrigido no mesmo dia)**
>
> - [[METODOLOGIA_EXTRACAO_DADOS#15.1 Regras por produto para parcelas (2026-10-20)|15.1 Regras por produto para parcelas (2026-10-20)]]
>
> **16. Faturamento total da empresa no ano (2026-10-21)**
>
>
> **17. Alcance, retenção e engajamento do Meta; "% Viram 50%" (23/10/26)**
>
>
> **18. Topo do funil da pesquisa: aberturas e inícios, não "quem recebeu" (23/10/26)**
>

<!-- SUMARIO:FIM -->

**Última atualização:** Junho de 2026 (Transição para Análises 2.0)
**Aplicável a:** PBB-ABR-26, PBB-FEV-26, PES-JAN-26, PES-MAI-26 e lançamentos futuros

---

> [!IMPORTANT]  
> **TRANSIÇÃO PARA ARQUITETURA 2.0 (API DIRECTA)**  
> O projeto de análises está migrando de um modelo baseado em exportação manual de CSVs para um pipeline automatizado usando APIs diretas (Meta, Active Campaign, Typeform) integradas a um *Data Warehouse* centralizado no **Supabase**.

## 1. Visão Geral da Arquitetura (2.0 vs 1.0)

Nosso pipeline de análise usa **atribuição baseada em UTM + e-mail** para medir o desempenho de criativos. Isso difere da atribuição por pixel do Google Ads / Meta Ads usada nas plataformas, garantindo que o ROAS seja calculado em cima de vendas reais e confirmadas no banco.

### Arquitetura 2.0 (Atual / Automatizada)
Neste novo modelo, os scripts em Python consultam as APIs periodicamente (ex: a cada 1 hora) e injetam os dados diretamente no banco Supabase:

```
Active Campaign API (Leads/UTMs)     Hotmart/TMB via TI (Vendas reais)
      ↓ Supabase Tabela 'leads'            ↓ Supabase Tabela 'vendas'
      └───────────────> VIEW DE ATRIBUIÇÃO <────────────────┘
                                ↑
Meta Ads / Google Ads API (Investimento)
      ↓ Supabase Tabela 'meta_ads_daily' / 'google_ads_daily'
```

**Scripts Orquestradores:** Pasta `etl/` (ex: `run_all.py`, `etl_meta_ads.py`)

> [!NOTE]
> **Diferença entre "extração direta" e "leitura direta"**
>
> Hoje o projeto já usa **extração direta das plataformas para o banco** em várias fontes, mas o **app FastAPI ainda consome majoritariamente o Supabase**, e não as APIs em tempo real.
>
> Fluxo atual dominante:
>
> `Plataforma/API -> ETL -> Supabase -> App`
>
> Em outras palavras:
> - **Meta Ads / Google Ads / Active Campaign** já podem entrar por API no banco.
> - O **frontend** ainda lê, em regra, das tabelas já materializadas no banco.
> - **Typeform foi desligado em agosto de 2026** (conta cancelada) — ver seção 10. A partir do `PBB-AGO-26`, as pesquisas de lançamento rodam no sistema de formulários interno (`formularios`/`perguntas`/`submissoes`/`respostas`), não mais no Typeform.

### Arquitetura 1.0 (Legado / Baseado em CSV)
Anteriormente, o processo dependia de exportações manuais depositadas nas pastas `analises/[LANCAMENTO]/`.
**Scripts Legados de referência:** `scripts-python/generate_analises_por_plataforma.py`

---

## 2. Fontes de Dados e Integração (2.0)

| Fonte | Método Atual (API) | Destino (Supabase) | O que contém |
| :--- | :--- | :--- | :--- |
| **Active Campaign** | `etl_active_campaign.py` | Tabela `leads` | Leads capturados + UTMs customizados (Campaign, Source, Content, etc) |
| **Meta Ads** | `etl_meta_ads.py` | Tabela `meta_ads_daily` | Investimento (Spend), Impressões e Cliques por *Ad* (breakdown diário) |
| **Google Ads** | `etl_google_ads.py` | Tabela `google_ads_daily` | Custo e conversões por anúncio |
| **Typeform** (até PI/PES-AGO-26, legado) | `etl_typeform.py` (desligado do pipeline automático em ago/2026) | Tabelas `typeform_respostas` + backups `typeform_respostas_backup`/`_2`, `typeform_forms`/`_2` | Respostas históricas das pesquisas via Typeform — ver seção 10 |
| **Sistema de pesquisa interno** (PBB-AGO-26 em diante) | Formulário web próprio (fora do escopo do `etl/`) | Tabelas `formularios`, `perguntas`, `submissoes`, `respostas` | Respostas das pesquisas de lançamento, substituindo o Typeform |
| **Hotmart / TMB** | Integração via TI | Tabelas da Hotmart/TMB | Receita real validada (`faturamento`, `email`, `status_transacao`) |

---

## 3. Metodologia de Cálculo (Atribuição)

Todo o cálculo pesado que antes era feito nos DataFrames (ex: `cruzamento_perpetuo_limpo.py`) agora está consolidado na **View do Supabase** (`view_atribuicao`).

### 3.1 Atribuição de Leads (UTM Content)
O código de criativo (ex: `AD092`) é extraído via expressão regular do campo `utm_content` no banco de dados.

### 3.2 Cruzamento Vendas vs. Leads
A View cruza a tabela de vendas (Hotmart/TMB) com a tabela de `leads` usando o campo **`email`** em minúsculas (trim+lower).
- **Filtros aplicados nas vendas (Hotmart):** Apenas status `Aprovado` ou `Completo`. Ignora-se cobranças do tipo `Recuperador Inteligente` — exceto quando `Quantidade de cobranças == 1`, onde o faturamento líquido × parcelas totais é usado.
- **Filtros (TMB):** Nenhum filtro por situação aplicado — todas as linhas são consideradas para garantir paridade com os totais do dashboard. Filtrar por `Vigente` reduz o total em ~3 vendas e quebra a paridade.

### 3.3 Métricas Derivadas na View

| Métrica | Fórmula na Base |
| :--- | :--- |
| CPL | `investimento_total / leads` |
| CPA (Custo por venda) | `investimento_total / vendas` |
| Faturamento | `SUM(faturamento)` de Hotmart + TMB |
| ROAS | `faturamento_total / investimento_total` |
| Taxa de conversão | `vendas / leads` |

---

## 4. Limitações Conhecidas e Gaps Sistemáticos

### 4.1 Leads: subcontagem de ~26% em relação aos Pixels
**Por que nosso número de CRM é menor que os relatórios nativos das plataformas:**
- O Active Campaign só captura leads que completaram o formulário E sincronizaram.
- O pixel nativo (GA/Meta) conta todo evento de conversão na LP (inclui bounces, cliques rápidos sem sync real e e-mails falsos/inválidos).
- Alguns UTMs podem ser perdidos (redirecionamentos, Safari ITP, ad blockers).

### 4.2 Vendas: subcontagem de ~32%
**Por que nosso número por E-mail é menor:**
- Comprador pode usar um e-mail para baixar a isca/cadastrar e um e-mail *diferente* na hora de passar o cartão na Hotmart.
- O Pixel das plataformas atribui a conversão ao último clique, mesmo que o usuário não tenha passado pelo CRM.

### 4.3 Confiabilidade das Fontes
Para a tomada de decisão (aumentar ou diminuir budget), optamos por seguir a nossa metodologia via E-mail, pois ela usa **receita real confirmada** livre de chargebacks ou pagamentos recusados.

---

## 5. Como Iniciar um Novo Lançamento (Modelo 2.0)

1. Garantir que as tags UTM estão configuradas corretamente nos anúncios (Padrão: `ADXXX - Nome`).
2. Configurar o arquivo `.env` com a data do lançamento nas *flags* do orquestrador.
3. Rodar `python etl/run_all.py --since [DATA_INICIO] --until [DATA_FIM]`.
4. Os dados populam o Supabase em tempo real. O Dashboard/HTML puxará da View atualizada.
5. Em caso de *fallback* (API falhar), o `run_all.py` possui o parâmetro `--csv-mode` para importar os dados antigos depositados nas pastas.

---

## 7. Status Atual e Evolução da V2 (Junho 2026)

Durante a transição para a Arquitetura 2.0, os seguintes marcos foram concluídos:

1. **Ajuste de Conectividade (IPv6 Bypass):** Corrigido o erro de DNS do Supabase em redes IPv4 utilizando o Connection Pooler da AWS (`aws-1-sa-east-1.pooler.supabase.com:5432`) no arquivo `.env`.
2. **Schema com Métricas de Vídeo:** Tabelas `meta_ads_daily` e `google_ads_daily` no Supabase foram expandidas com campos específicos de vídeo (views, 25%, 50%, 75%, 100%, ThruPlays e Outbound Clicks).
3. **Views de Performance Avançada:** Criação e deploy das views `view_meta_performance_criativos` e `view_google_performance_criativos` no Supabase para cálculo automático de **Hook Rate** (Gancho) e **Hold Rate** (Retenção).
4. **Agendador Automatizado (`scheduler.py`):** Criada a rotina em Python que roda o pipeline de hora em hora em uma janela móvel de 3 dias (`hoje - 2` até `hoje`) para capturar conversões tardias.
5. **Autenticação Meta Ads:** Implementado o token de acesso de longa duração (User Access Token) válido até **14 de agosto de 2026**.
6. **Validação de Carga Inicial:** Testado com sucesso o orquestrador (`run_all.py --only meta_ads`) gerando a inserção correta de dados e computação de métricas nas views.

---

## 8. Marcos Concluídos na V2 (Junho 2026)

Todos os itens abaixo foram implementados e estão em produção:

1. **Credenciais Google Ads** — configuradas no `.env`; refresh token gerado via `etl/etl_google_ads.py --get-token`.
2. **Tabelas de Vendas (Hotmart / TMB)** — `hotmart_clean_oficial` e `tmb_clean_oficial` no banco operacional (`SUPABASE_USERS_URL`); guard de escrita SQLAlchemy ativo.
3. **View de Atribuição** — `view_atribuicao` deployada no Supabase com joins reais nas tabelas de produção.
4. **Histórico Retroativo** — 8 lançamentos importados (PI-JAN-26 a PBB-JUN-26); +113.000 respostas Typeform; dados Meta e Google por API.
5. **Scheduler em Produção** — `etl/scheduler.py` com APScheduler rodando a cada hora em janela móvel de 3 dias.

---

## 9. Correções Críticas no Pipeline ETL (2026-06-25)

Durante a primeira execução real do pipeline via API (pós-encerramento do PBB-JUN-26), foram identificados e corrigidos os seguintes bugs:

### 9.1 `sys.path` invertido nos scripts ETL
**Problema:** Os 4 scripts (`etl_meta_ads.py`, `etl_google_ads.py`, `etl_active_campaign.py`, `etl_typeform.py`) faziam dois `sys.path.insert(0, ...)` em sequência: primeiro `etl/`, depois `src/`. Como o segundo insert empurra o primeiro para baixo, `src/db/` era encontrado antes de `etl/db.py`, causando `ImportError: cannot import name 'get_engine'` em todos os scripts.

**Correção:** Ordem invertida — `src/` inserido antes, `etl/` inserido por último (posição 0).

### 9.2 `import pandas` ausente no `etl_meta_ads.py`
**Problema:** O módulo `pandas` era usado mas não importado, causando `NameError: name 'pd' is not defined` ao processar os dados da API.

**Correção:** Adicionado `import pandas as pd` na seção de imports.

### 9.3 Typeform deletava todos os dados do form no upsert
**Problema:** A função `upsert()` do Typeform fazia `DELETE FROM typeform_respostas WHERE form_id = :fid` antes de inserir — apagando **todo o histórico** do form e reinserindo apenas o período recém-buscado. Na primeira execução real, 12.971 respostas foram perdidas e precisaram ser restauradas.

**Correção:** O delete agora é filtrado por `submitted_at::date BETWEEN :since AND :until`, preservando dados fora do range importado. A função `upsert()` recebe os parâmetros `since` e `until` opcionais; sem eles, mantém o comportamento de limpeza total (útil para reimportação completa).

### 9.4 Active Campaign API varrendo toda a conta para buscar UTMs
**Problema:** A função `fetch_field_values_by_field()` paginava **todos** os field values da conta (72k+ contatos × 5 campos UTM) para filtrar só os do período. Isso tornava o modo API inviável — estimativa de horas por execução.

**Correção:** Eliminada a função `fetch_field_values_by_field()`. Agora os field values vêm embutidos na resposta de contatos via parâmetro `include=fieldValues` na chamada de paginação. Um único loop busca contatos e UTMs juntos, em ~8 minutos para uma janela de 3 dias.

### 9.5 Campos UTM do Active Campaign não configurados no `.env`
**Problema:** As variáveis `AC_FIELD_UTM_*` estavam em branco, fazendo os UTMs serem ignorados no modo API.

**Correção:** Executado `python etl/etl_active_campaign.py --api --discover-fields` para descobrir os IDs e configurados no `.env`:
- `AC_FIELD_UTM_CAMPAIGN=3`
- `AC_FIELD_UTM_SOURCE=4`
- `AC_FIELD_UTM_MEDIUM=5`
- `AC_FIELD_UTM_CONTENT=6`
- `AC_FIELD_UTM_TERM=7`

### Status após correções

| Fonte | Modo API | Tempo (janela 3 dias) |
|-------|----------|-----------------------|
| Meta Ads | ✓ funcional | ~35s |
| Google Ads | ✓ funcional | ~15s |
| Typeform | ✓ funcional | ~5s |
| Active Campaign | ✓ funcional | ~8 min |

O scheduler pode ser ativado — nenhuma fonte depende mais de CSV para operação normal.

---

## 10. Desligamento do Typeform e migração pro sistema de pesquisa interno (2026-08-31)

A conta do Typeform foi cancelada. Antes do cancelamento, um backup completo de duas contas Typeform foi feito para o mesmo Supabase (`SUPABASE_DB_URL`):

| Tabela | Conteúdo |
| :--- | :--- |
| `typeform_forms` / `typeform_forms_2` | `form_id → título` de todos os formulários das duas contas |
| `typeform_respostas_backup` / `typeform_respostas_backup_2` | Respostas completas das duas contas (mesmo schema de `typeform_respostas`) |
| `typeform_respostas` | Tabela viva sincronizada pela ETL (`etl_typeform.py`) — cobre só os lançamentos mais recentes antes do cancelamento; tinha 3 form_id que ainda não estavam nos backups |

**Mudanças no código (`frontend/db_readers/typeform.py`):**
- Nenhuma chamada à API do Typeform sobrevive. `_get_typeform_forms()` lê `typeform_forms`/`typeform_forms_2`; `_get_typeform_fields()` (mapeamento field_id → título da pergunta) não tem fonte de backup — retorna vazio, então colunas de perguntas de pesquisas antigas cujo `field.title` não veio salvo no JSON aparecem com o ID cru do campo em vez do texto da pergunta. Isso é uma perda de legibilidade conhecida, sem solução até recuperar esse mapeamento de outra fonte.
- Toda leitura de respostas passou a usar uma fonte unificada (`_tf_source`) que faz `UNION ALL` das 3 tabelas de respostas (`typeform_respostas` + os 2 backups), deduplicada por `response_id` (mantém a versão mais recente por `updated_at` quando o mesmo id aparece em mais de uma tabela). O filtro (form_id ou período) é aplicado dentro de cada tabela antes do `UNION`, não depois — senão o `DISTINCT ON` teria que varrer ~1M linhas a cada chamada.
- `etl/run_all.py` não roda mais `etl_typeform.py` no modo API (removido do dict `scripts` em `run_api_mode`) — o `scheduler.py`, que chama `run_all.py` a cada 30 min, não bate mais na API do Typeform. O script `etl_typeform.py` continua no repo pra uso manual pontual.

**Sistema de pesquisa interno (substituto, a partir do `PBB-AGO-26`):**

Schema normalizado, sem o gap de field-title do Typeform (`perguntas.titulo` já é o texto legível da pergunta):

```
formularios (1 por lançamento, titulo contém "[CODIGO-LANCAMENTO]")
      ↓
perguntas (1 linha por pergunta: id, formulario_id, tipo, titulo, ordem)
      ↓
submissoes (1 linha por resposta enviada: id, formulario_id, created_at)
      ↓
respostas (1 linha por pergunta respondida: submissao_id, pergunta_id, valor jsonb)
```

`valor` (jsonb) guarda a resposta em uma destas chaves, dependendo do tipo da pergunta: `texto` (texto curto/longo, telefone, e-mail, nome), `opcao` (múltipla escolha de uma opção, com `texto_outro` opcional quando a opção é "Outro"), `opcoes` (lista, múltipla escolha de várias opções).

Formulários já criados nesse sistema: `[PBB-AGO-26] Pesquisa - Projeto Banco do Brasil` (id 9) e `[PES-SET-26] Pesquisa - Projeto TJ-SP` (id 13).

**Integração no frontend:** `frontend/db_readers/typeform.py` resolve o(s) `formulario_id` cujo título contém o código do lançamento (`_resolve_novo_sistema_formulario_ids`) e converte o formato normalizado pra tabela larga (`email_norm` + uma coluna por `pergunta.titulo`) via `_read_novo_sistema_respostas`/`_read_novo_sistema_emails` — mesmo formato que o Typeform já produzia. As 4 funções de leitura (`read_typeform_count`, `read_typeform`, `read_perfil_por_anuncio`, `read_pesquisa_engajamento`) combinam (concat/union por e-mail) o resultado do Typeform com o do sistema novo, então cada lançamento usa automaticamente a fonte certa sem configuração manual — Typeform pros lançamentos antigos, sistema novo do `PBB-AGO-26` em diante.

---

*Documento revisado e atualizado para englobar os novos módulos de conexão MCP, as rotinas diárias em SQLAlchemy e a evolução para a V2.*


## 11. Métricas das aulas no YouTube sem API (2026-09-15)

Sem a API do YouTube conectada, as métricas das aulas vêm do **relatório pós-transmissão**
exportado à mão no YouTube Studio (`etl/etl_youtube_csv.py`). Isso muda o que cada número
significa — não é o mesmo recorte que a API devolve.

**O que o export mede:**

| Métrica | Como é extraída | Cuidado na leitura |
|---|---|---|
| `peak_concurrent` | máximo da coluna "Espectadores simultâneos" da curva | é o pico **ao vivo**, não o total de pessoas que assistiram |
| `viewers_fim` | simultâneos no último ponto da curva | quem ainda estava ao vivo quando a transmissão encerrou |
| `retencao_live_pct` | `viewers_fim / peak_concurrent` | **não** é a retenção média da API (`avg_view_pct`), que é tempo assistido ÷ duração. É "quantos dos que chegaram no pico ficaram até o fim" |
| `duration_sec` | último ponto da curva | duração da *transmissão*, não do vídeo publicado depois |
| `chat_msgs` / `reacoes` | soma da curva minuto a minuto | só interações **ao vivo**; comentários do replay não entram |

**O que o export não mede:** views totais, watch time, retenção média, likes, comentários,
split live vs replay e `video_id`. Esses campos ficam zerados até a API rodar ou até entrar o
export do **Modo avançado** do Studio.

**Por que a hierarquia importa no debriefing:** a barra de retenção usa `avg_view_pct` quando
existe e cai para `retencao_live_pct` quando não — e troca o rótulo junto ("Retenção média"
vs "Retenção ao vivo (fim/pico)"), porque comparar os dois como se fossem a mesma coisa
inflaria ou deprimiria o número sem aviso. Pelo mesmo motivo os KPIs do rodapé trocam de
métrica em vez de mostrar zero.

**Comparação entre lançamentos:** só compare retenção entre aulas com a **mesma** fonte.
PBB-JUN-26 tem dado de API (`avg_view_pct`); PI-AGO-26 tem dado de CSV
(`retencao_live_pct`). A coluna `fonte` de `youtube_aulas_stats` existe para essa checagem.

### Os três exports do Studio medem coisas diferentes (2026-09-15)

| Export | O que mede | Cuidado |
|---|---|---|
| Transmissões ao vivo | a **live**, minuto a minuto (simultâneos, chat, reações) | só o ao vivo; o replay não entra |
| Retenção de público | o **vídeo**, por posição (0-100%), com replay | outra população: pode dar menos views que o pico simultâneo da mesma aula |
| Conteúdo | views/watch time/impressões **do período escolhido no export** | inútil se o período não cobrir a data da live |

**Nunca somar o primeiro com o segundo.** No PI-AGO-26 a Aula 3 teve pico simultâneo de
10.118 ao vivo e 9.302 visualizações no relatório de retenção — se fossem a mesma população,
isso seria impossível. Por isso `visualizacoes_video` tem esse nome e a página mostra as duas
coisas em seções separadas, cada uma com a janela de datas do seu export.

**Origem do tráfego.** O Studio responde isso em dois níveis: "orgânico vs pago" (dentro do
relatório de retenção) e "Fontes de tráfego" (notificações, pesquisa, externo…). Nenhum dos
dois quebra por campanha ou por `ADxxx` — atribuição por criativo continua vindo do Google
Ads, e só para campanha de vídeo cujo destino seja o próprio vídeo.

## 12. Metricas das aulas no YouTube via API (2026-09-22)

Com a integracao da YouTube Analytics API (etl/etl_youtube_analytics.py), as metricas oficiais de engajamento das lives e replays passam a ser coletadas automaticamente:

- **Identificacao de Videos**: A API mapeia os IDs dos videos das aulas atraves dos arquivos YAML de configuracao do lancamento (config/lancamentos/{launch_code}.yaml).
- **Metricas Coletadas**:
  - iews / estimatedMinutesWatched: visualizacoes totais e minutos assistidos.
  - verageViewDuration / verageViewPercentage: tempo medio e retencao percentual media real da aula.
  - Curva de retencao percentual segundo a segundo (0% a 100% da duracao do video), persistida em youtube_video_retencao.
- **Roteamento Multi-Token**:
  - Cada expert possui um canal proprio e uma conta Google responsavel. O ETL direciona automaticamente:
    - PI-* -> YOUTUBE_REFRESH_TOKEN_PI (Canal Mateus Andrade)
    - PES-* -> YOUTUBE_REFRESH_TOKEN_PES (Canal Ivan Neto / Brabo Concursos)
    - PBB-* -> YOUTUBE_REFRESH_TOKEN (Canal Felipe Graton)

---

## 13. A atribuição de lançamento fechado apaga sozinha (2026-10-07)

**Sintoma:** o teste de caracterização de `_sales_attribution` quebrou em dois lançamentos
fechados. O PI-AGO-26, que fechou em 24/08, passou de **2.051 para 1.680** compradores
rastreados — o ROAS caiu de **2,36x para 1,97x** sem uma venda nova ter entrado. Nenhuma linha
de código de atribuição tinha mudado.

**Causa:** a tabela `leads` guarda **uma linha por contato** — conferido: os 2.501 compradores
do PI-AGO-26 têm 2.501 linhas, nenhum tem duas. O lançamento vive numa coluna só,
`lancamento_codigo`, e um processo externo reescreve a tabela inteira periodicamente (todas as
linhas dos compradores do PI-AGO-26 têm `updated_at` em outubro/26, inclusive as 1.450 que ainda
dizem PI-AGO-26).

Quando a pessoa se cadastra num lançamento novo, a linha dela é reescrita com o código novo. O
`_sales_attribution` casa comprador com lead por
`WHERE lancamento_codigo = :code` — então **o comprador some da atribuição do lançamento
antigo**, junto com a UTM que dizia qual anúncio o trouxe.

**Para onde foram os 1.027 compradores do PI-AGO-26 que não têm mais linha dele:**

| destino | compradores |
|---|---|
| `NULL` | 479 |
| **BV-26** (a Black, captando agora) | **387** |
| PBB-AGO-26 | 94 |
| outros 9 lançamentos | 67 |

**Não é um caso isolado — todo lançamento fechado já perdeu de um terço a 40%:**

| lançamento | compradores | ainda com linha própria | perdidos | % |
|---|---|---|---|---|
| PI-AGO-26 | 2.501 | 1.474 | 1.027 | **41,1%** |
| PBB-JUN-26 | 698 | 424 | 274 | 39,3% |
| PES-SET-26 | 1.524 | 942 | 582 | 38,2% |
| PI-ABR-26 | 3.074 | 1.990 | 1.084 | 35,3% |
| PBB-AGO-26 | 532 | 353 | 179 | 33,6% |
| PBB-ABR-26 | 545 | 370 | 175 | 32,1% |

**Consequências:**
- O ROAS de um lançamento fechado **cai sozinho com o tempo**, e hoje está subestimado em
  ~1/3 em todos eles. O debriefing de um lançamento fechado dá um número diferente a cada vez
  que é aberto.
- A erosão **acelera enquanto um lançamento novo capta**: a Black levou 387 compradores do
  PI-AGO-26 e 320 do PI-ABR-26 só nas últimas semanas.
- Não dá pra remendar na leitura: a linha reescrita carrega a UTM do lançamento **novo**, não a
  do antigo. O dado antigo não está escondido — **foi sobrescrito**.

**O que resolve, em ordem:**
1. **Fora do nosso código (o conserto de verdade):** `leads` precisa de uma linha por
   (contato, lançamento), ou de uma coluna de origem imutável, gravada na primeira captura e
   nunca sobrescrita. É com quem mantém o upsert externo.
2. **Dentro do nosso código:** congelar a atribuição quando o carrinho fecha — persistir
   comprador + UTM escolhida numa tabela por lançamento e ler dali, em vez de recalcular
   sobre uma `leads` que muda. Preserva daqui pra frente; **não recupera** o que já foi
   sobrescrito.
3. Enquanto nenhum dos dois existir, **todo ROAS histórico é piso**, e comparar o ROAS de um
   lançamento fechado com o de um lançamento em curso é comparar uma medida erodida com uma
   intacta.

**Enquanto isso, o baseline de caracterização não deve ser regravado** nesses dois serviços: ele
é hoje o único alarme que existe pra essa erosão.

### 13.1 A trava (07/10/26, mesmo dia)

O caminho 2 foi implementado: `atribuicao_congelada` guarda a **melhor UTM já observada** por
(lançamento, comprador) e entra em `_sales_attribution` **antes** da leitura ao vivo — o dado de
hoje só a substitui com score maior. Gravação monotônica, então rodar de novo nunca piora.

Congelado no mesmo dia: **11 lançamentos, 12.904 pares comprador×UTM**. Detalhe das peças e a
decisão em aberto (de quanto em quanto tempo rodar) em [[CONGELAR_ATRIBUICAO_LANCAMENTO]].

**O número parou de cair; não voltou.** O que foi sobrescrito antes de 07/10/26 está perdido.

### 13.1b As leituras passaram a vir do estado (08/10/26)

Os leitores por lançamento (atribuição, vendas × CRM, contagens, UTM dos compradores, typeform) leem agora
`lead_utm_lancamento` — uma linha por (contato, lançamento) —, não a `leads`. Detalhe, lista do que ficou na
`leads` e conferência em [[ARQUITETURA]]. Efeito na atribuição dos 10 lançamentos fechados: **12.467 →
13.698 compradores rastreados**, igual ao da trava; contagens de leads no CRM sobem pelos contatos recuperados
(PI-AGO-26 267.200 → 272.076) e nunca descem.

**Quem credita a venda:** cada lançamento lê as UTMs do seu próprio lançamento; a venda é do lançamento em
cujo carrinho a compra aconteceu. Na Black, o comprador com linha nas duas trilhas é creditado pela da
**Vitalícia** (a captação da oferta vendida), com a Base Forte de reserva.

### 13.2 Recuperação pelo export do AC da época + trava diária

Os CSVs em `analises/[LANC]/Active Campaign/` guardam a UTM como estava no dia do export.
`scripts/recuperar_utms_export_ac.py` recuperou **1.216 compradores em 10 lançamentos**, só
os que têm UTM nomeando o lançamento (o resto seria crédito chutado ou errado), marcados
`origem = 'export_ac'`. O PI-AGO-26 voltou de 1.680 para 2.003 compradores atribuídos.

A trava passou a rodar sozinha, **diária às 4h10, a partir da primeira live de cada
lançamento** (job `congelar_atribuicao` no `etl/scheduler.py`). Detalhes em
[[CONGELAR_ATRIBUICAO_LANCAMENTO]].

### 13.2b O que isso significa para a decisão de criativo (08/10/26)

Medição no PI-AGO-26, detalhada no item 54 do [[MUDANCAS_PI-AGO-26]]: a erosão atinge **1,9% dos leads mas
18,1% dos compradores** (quem se perde compra 11,6x mais). O ranking de criativos por CPA é estável (correlação
0,96), mas o CPA individual muda mais de 15% em 24 de 34 criativos. Por isso as páginas `/criativos`, `/meta` e
`/google` passaram a mostrar a **faixa de cobertura** (vendas que chegam a um criativo × total), e o ROAS vale como
**piso** e o custo por venda como **teto**.

**Quem decide o quê, num cadastro em vários lançamentos:** a venda pertence ao lançamento em que a compra
aconteceu (produto + janela do carrinho). Dentro dele, o criativo creditado é o que captou a pessoa **naquele
lançamento** (a última UTM, regra do Michel). Os cadastros em lançamentos anteriores são leads que não converteram
na época e não recebem crédito. A origem do cliente na vida toda (primeiro lançamento em que apareceu) é uma lente
**separada**, que o histórico `lead_utm_lancamento` já permite montar por ter uma linha por lançamento.

### 13.3 A tag do AC já guardava o histórico

`etl_active_campaign.py` grava **`lead_lancamentos`** (contato × lançamento) a partir das tags
do AC, que são **cumulativas** — o contato nunca perde a tag do lançamento anterior. É a origem
imutável que falta na `leads`, e ninguém estava usando pra isso. Recupera **quem** era do
lançamento (PI-AGO-26: 2.125 compradores contra 1.474 pela `leads`), mas **não guarda UTM**,
então não diz qual anúncio creditar. Ver [[CONGELAR_ATRIBUICAO_LANCAMENTO]], frente 1.

## 14. Carregamento da página — `landing_page_views` e LP por anúncio (2026-10-10)

- **Página aberta** = `actions[landing_page_view]` dos insights do Meta (o pixel disparou PageView depois do clique), em `meta_ads_daily.landing_page_views`. Existe desde **23/09/26**; antes disso a coluna é 0 e não deve ser lida como "0% carregou".
- **Abriu / clicou** = landing_page_views ÷ link_clicks. **Lead / página** = leads ÷ landing_page_views.
- **LP do anúncio** = primeiro link do criativo (asset_feed_spec, link_data ou CTA do vídeo), sem query, em `ad_landing_pages`. É a URL **atual**: o anúncio que teve o link trocado no lugar leva o histórico inteiro para a LP nova.
- **Subcontagem conhecida:** as LPs da Black 2026 adiam GTM/pixel até a 1ª interação ("delay JS"). Quem abre e sai sem tocar não vira página aberta, então a taxa não mede só velocidade. As LPs a partir do PI-NOV-26 vêm sem esse atraso (decisão do usuário com o desenvolvedor, 10/10/26).
- Google não tem métrica equivalente na API: a seção é só do Meta.

- **Página:** desde 11/10/26 a leitura está em /landing-pages, junto da velocidade e do GA4:
  - **Laboratório (PageSpeed, celular em 4G lento):** nota, LCP, FCP, CLS, TBT (proxy do INP), TTFB, Speed Index, peso e requisições. Mede a página em condição controlada; serve para comparar versões.
  - **Usuários reais (CrUX):** p75 dos últimos 28 dias no Chrome. Uma LP de lançamento quase nunca tem visitas suficientes sozinha, então em geral o número é do domínio inteiro (a página avisa).
  - **Faixas:** LCP ≤ 2,5 s bom / > 4 s ruim; INP ≤ 200 / > 500 ms; CLS ≤ 0,1 / > 0,25; TBT ≤ 200 / > 600 ms; FCP ≤ 1,8 / > 3 s; TTFB ≤ 800 / > 1.800 ms; nota ≥ 90 / < 50 (`src/landing_pages.FAIXAS_CWV`).
  - **GA4 por LP:** sessões, taxa de engajamento (sessão ≥ 10 s, 2+ páginas ou conversão), tempo médio e eventos-chave por sessão. **Eventos-chave não é taxa de conversão**: um cadastro dispara mais de um (lead e lead qualificado). A página de obrigado não serve de contagem no `ga4_daily`, porque lá ela só aparece quando a sessão começa nela.
  - **Envios do form (AC)** = `entries` do formulário, total desde a criação (não por período).


## 15. Receita líquida da Hotmart: o que cada coluna significa em cada origem (2026-10-20, corrigido no mesmo dia)

`hotmart_clean_oficial` tem duas origens com semânticas **diferentes** na mesma coluna:

- **Linhas antigas (export CSV):** trazem `faturamento_liquido`. Nelas `valor_de_compra_sem_impostos` é *antes* da taxa de processamento e `faturamento_liquido = sem_impostos - taxa_de_processamento` (99,3% de 96,9 mil linhas).
- **Linhas do webhook/API (2026):** `faturamento_liquido` vem vazio e `valor_de_compra_sem_impostos` **já é o faturamento líquido do produtor**: `com_impostos - taxa de parcelamento - taxa de processamento`. Prova: a venda de cartão 12x do export da Hotmart (pago 1.898,64; parcelamento 274,67; processamento 65,96; líquido 1.558,01) existe no banco com `com=1898.64`, `sem=1558.01`, `taxa=65.96`; no BV-26 inteiro, Pix e boleto têm "sobra" (com − sem − taxa) ≈ 0 e o cartão parcelado concentra os R$ 286 mil.

O leitor usa `faturamento_liquido` quando existe e, senão, o valor sem impostos. **Isso está certo para as duas origens.** Em 20/10/26 foi feito (e revertido no mesmo dia) um ajuste que descontava `taxa_de_processamento` também das linhas de 2026 — descontava a taxa duas vezes e derrubava a receita do BV-26 em 4,5% (R$ 2,00 mi em vez de R$ 2,10 mi). A extrapolação partiu das linhas antigas, onde a regra vale, sem testar as novas. Antes de mexer: comparar com a linha real do export.

O debriefing mostra a ponte **pago → líquido** (só Hotmart): `hotmart_receita_bruta` (o que o cliente pagou), `hotmart_parcelamento` (= pago − líquido − taxa), `hotmart_taxa` (taxa de processamento) e o líquido (`hotmart_receita`). BV-26: 2.477.143 − 286.665 − 93.660 = 2.096.819; BV-25: 5.803.942 − 545.637 − 220.430 = 5.037.875. A "Receita Líquida" do topo soma Hotmart + TMB.

**Receita contratada, não caixa:** `hotmart_receita` projeta o contrato completo das vendas gravadas por parcela (valor da parcela × nº de parcelas; regra de `_parcela_unica_info`, validada contra o export do PI-AGO-26). O "Faturamento líquido" do painel da Hotmart conta só o que já foi cobrado (no cartão mês a mês, boleto parcelado e 24x, só a 1ª parcela). Por isso o painel da Hotmart fica abaixo do dashboard e **não serve de prova do total**. Conferências que valem: (1) uma venda específica (ex.: HP0729340238, cartão 12x) deve mostrar R$ 1.558,01 de líquido; (2) a soma **sem projetar** (uma cobrança por linha: R$ 992.909 em 20/10 para os 3 produtos do BV-26) deve ficar perto do "Faturamento líquido" do painel.

### 15.1 Regras por produto para parcelas (2026-10-20)

A regra geral de `_parcela_unica_info` (webhook com `quantidade_de_cobrancas` presente ⇒ valor da parcela ⇒ multiplica pelas parcelas) foi validada no PI-AGO-26, mas erra em produtos cujo webhook manda `quantidade_de_cobrancas = 1` em TODA venda. Exceções ficam em `_REGRAS_POR_PRODUTO` (`_vendas_comum.py`), com `codigo_do_produto` e `codigo_do_preco` nas consultas dos leitores:

- **8743334 ("Black Vitalícia 2026 - AC"):** (a) cartão 12x de R$ 1.198,80 grava o **total** do contrato (12 × R$ 99,90), não a parcela — `total_se_parcelado` impede o ×12 (eram 39 vendas contadas como R$ 11.800 líquidos cada, ~R$ 411 mil a mais); (b) ofertas com código de preço terminado em **DRP** são a cobrança mensal recorrente de R$ 99,90 em **24x** (confirmado pelo time) — `drp_parcelas: 24` (o payload manda 1 parcela e só R$ 94,90 por venda entrava). Segunda cobrança da mesma assinatura continua sendo repetição e não conta como venda.
- Efeito no BV-26 (20/10, líquido projetado): R$ 2.114.741 → R$ 1.760.447; pago R$ 2.499.662 → R$ 2.058.304.
- Para um produto novo com o mesmo defeito: testar `com × parcelas` contra o preço da oferta antes de aceitar a regra geral.

## 16. Faturamento total da empresa no ano (2026-10-21)

`/lancamentos` mostra, no Resumo Executivo, a conta da **empresa inteira**, não só dos lançamentos. Fonte: `frontend/db_readers/empresa.py` (`read_empresa_ano`) + `read_perpetuo_ano`.

- **Total vendido** = tudo que a Hotmart e a TMB venderam no ano civil, com a regra de valor de `read_vendas` (líquido; venda por parcela projetada; cobrança repetida e e-mail de teste fora).
- **Lançamentos** = a venda dentro do carrinho (soma dos cartões). **Perpétuo** = produtos das verticais (`VERTICALS`), líquido de venda aprovada. **Setor de vendas** = o que sobra: `total vendido − lançamentos − perpétuo` (mentorias, apostilas e cursos vendidos fora da janela do carrinho). Nunca fica negativo.
- **Distribuição** não tem venda ligada (só anúncio) e entra só no investimento: gasto Meta + Google de `DISTRIBUICAO-*` e de campanhas sem código com "distribui" no nome; o perpétuo entra com `PERPETUO-*`.
- 2026 em 21/10: R$ 33,76 mi = lançamentos R$ 31,20 mi (92,4%) + setor de vendas R$ 2,47 mi (7,3%) + perpétuo R$ 0,09 mi (0,3%); investimento R$ 10,17 mi (lançamentos 9,02 + distribuição 1,08 + perpétuo 0,07).
- **Perpétuo nunca conta dentro de um lançamento:** os IDs Hotmart do perpétuo (`HOTMART_IDS_PERPETUO` em `_vendas_comum.py`, de onde `perpetuo.py` monta as verticais) são excluídos de `read_vendas`, do dia 1, da página `/hotmart` e de afiliados quando o filtro do lançamento é por projeto (o nome do produto tem "INSS"/"TJ"/"BB"). Lançamento com `hotmart_produto_ids` explícito não precisa. Em 21/10/26 isso mexeu só no PES-MAI-26 (−R$ 2.090, 11 matrículas); a soma lançamentos + setor de vendas + perpétuo agora não tem sobreposição.
- **Perpétuo corrigido:** a página `/perpetuo` e o "Mês a mês" somavam `valor_de_compra_com_impostos` (o que o cliente pagou) de **qualquer status**, inclusive reembolso e cancelamento. Agora somam o líquido de venda aprovada, como o resto do sistema; os números do perpétuo ficam menores.
- A meta anual (R$ 38 mi) passou a medir o **total da empresa**.

## 17. Alcance, retenção e engajamento do Meta; "% Viram 50%" (23/10/26)

`meta_ads_daily` ganhou, por anúncio e dia: `reach` (alcance), `video_avg_time_watched` (segundos, média do dia), `video_views_30s`, `post_engagement`, `post_reactions`, `post_comments`, `post_shares`, `post_saves` (do campo `actions` já baixado). **Sem DEFAULT**: linha anterior à coleta (antes de 22/10/26) é NULL, não zero. Os leitores calculam percentuais só sobre as linhas com alcance.

- **% Viram 50% (Meta)** = viu 50% (`video_views_50`) ÷ alcance, só nos dias com alcance. Igual à planilha de controle da pré-quali. O alcance é "pessoas únicas do dia"; somar dias e anúncios conta a mesma pessoa mais de uma vez (a planilha também soma) — vale como indicador comparativo, não como número exato de pessoas.
- **% Viram 50% (Google)** = (visualizações TrueView × taxa de 50%) ÷ visualizações. O `video_views_50` gravado do Google é impressões × taxa; a taxa de cada linha volta de `video_views_50 ÷ impressões`.
- **Tempo médio assistido** é média do dia: para agregar, ponderar pelas visualizações de 3s (`video_views_3s`), nunca média simples.
- **Quando a coleta vale:** o scheduler (janela móvel de 3 dias) passa a preencher sozinho; o histórico anterior só ganha os campos com recarga (`etl/etl_meta_ads.py --since --until --launch-code`; a CA2 exige janelas de 7 dias).

## 18. Topo do funil da pesquisa: aberturas e inícios, não "quem recebeu" (23/10/26)

**Quem recebeu a pesquisa não existe no banco.** O disparo é template de WhatsApp (`pesquisa_24x`, `pesquisa_alunos_black`…, planejados em `bflow_disparos`, que não tem contagem), e `whatsapp_messages_daily` só guarda enviados/entregues **por dia e por número**, misturando todos os templates. O AC também não tem. Ter o número real exige um ETL das estatísticas por template da Meta (WhatsApp Business) — não feito.

O topo do funil do /pesquisas usa o contador do próprio formulário (`_contar_aberturas`):

- **Abriram a pesquisa** = `formularios.visualizacoes` (sistema novo, soma dos formulários do lançamento) + `typeform_insights(_2).total_visits` (backup do Typeform). Conta **abertura**, não pessoa: quem reabriu conta de novo.
- **Começaram a responder** = `formularios.inicios`. O Typeform não guardou inícios; no sistema novo só ~1/4 dos formulários tem o campo preenchido. Zero vira "sem dado".
- **Abriu → Respondeu** = respondentes únicos ÷ aberturas.

Exemplo PES-NOV-26 (form 487): 215 aberturas → 190 inícios → 148 envios → 147 respondentes únicos.

## Código do anúncio na atribuição de vendas da Black (27/10/26)

A venda é ligada ao anúncio pelo código encontrado nas UTMs do lead (`utm_term`/`utm_content` e demais). Para lançamentos
`BV-*` o código segue a convenção da Black (`AD-TR35`, `ADC-MA38`, `ADL…`, `UGC…`) e é extraído com
`src/ad_codes.extract_ad_code(…, launch_code)`, normalizado como `ADC-MA38`. Nos outros lançamentos continua `ADxxx`. Antes de
27/10/26 a Black não tinha nenhuma venda atribuída a anúncio por causa disso ([[ARQUITETURA]]).
