# Metodologia de Extração e Atribuição de Dados por Lançamento

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
> - **Meta Ads / Google Ads / Typeform / Active Campaign** já podem entrar por API no banco.
> - O **frontend** ainda lê, em regra, das tabelas já materializadas no banco.
> - A exceção parcial hoje é o **Typeform**, onde o app também consulta a API para metadados de formulários/campos quando necessário.

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
| **Typeform** | `etl_typeform.py` | Tabela `typeform_respostas` | Respostas completas das pesquisas de lançamento |
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

*Documento revisado e atualizado para englobar os novos módulos de conexão MCP, as rotinas diárias em SQLAlchemy e a evolução para a V2.*
