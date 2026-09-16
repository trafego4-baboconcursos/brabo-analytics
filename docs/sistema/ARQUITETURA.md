---
titulo: "Arquitetura do Brabo Analytics — 2026-09-16"
area: sistema
status: vigente
atualizado: 2026-09-16
responde:
  - "como o sistema funciona por dentro"
  - "fluxo de dados"
  - "responsabilidade de cada arquivo"
  - "onde fica o calendario e por que"
  - "cache, scheduler, seguranca"
  - "salvei no wizard e nao apareceu no debriefing"
  - "por que a verba configurada demora pra aparecer"
  - "quais campos o wizard grava em launch_config"
  - "por que o previsto do WhatsApp aparece zerado"
  - "quando subir o SNAPSHOT_VERSION"
  - "por que o debriefing quebrou depois de mexer no dbf"
  - "como regravar o baseline de caracterizacao sem perder o resto"
  - "por que read_launch_config e volatil no teste"
relacionados:
  - "[[METODOLOGIA_EXTRACAO_DADOS]]"
  - "[[DESIGN_SYSTEM]]"
---

# Arquitetura do Brabo Analytics — 2026-09-14

<!-- SUMARIO:INICIO -->

> [!abstract]- Sumario - 41 itens (gerado por `scripts/check_docs.py --atualizar-mapa`)
>
>
> **Estrutura de Arquivos**
>
>
> **God Module Split (S1–S9 em 2026-07-01; encerrado em 2026-09-15)**
>
> - [[ARQUITETURA#S10 — fim do shim (2026-09-15)|S10 — fim do shim (2026-09-15)]]
>
> **Fluxo de Dados**
>
>
> **Responsabilidades por Arquivo**
>
> - [[ARQUITETURA#`frontend/app.py` (~125 linhas)|`frontend/app.py` (~125 linhas)]]
> - [[ARQUITETURA#`frontend/auth.py`|`frontend/auth.py`]]
> - [[ARQUITETURA#`frontend/cache.py`|`frontend/cache.py`]]
> - [[ARQUITETURA#`frontend/services/fetch.py` (~348 linhas)|`frontend/services/fetch.py` (~348 linhas)]]
> - [[ARQUITETURA#`frontend/core.py` (~339 linhas)|`frontend/core.py` (~339 linhas)]]
> - [[ARQUITETURA#`frontend/services/debriefing.py` (~363 linhas)|`frontend/services/debriefing.py` (~363 linhas)]]
> - [[ARQUITETURA#`frontend/formatters.py`|`frontend/formatters.py`]]
> - [[ARQUITETURA#`frontend/services/attribution.py`|`frontend/services/attribution.py`]]
> - [[ARQUITETURA#`frontend/routes/*.py`|`frontend/routes/*.py`]]
>
> **Cache (frontend)**
>
>
> **ETL Scheduler**
>
>
> **Segurança**
>
>
> **Testes**
>
> - [[ARQUITETURA#1. Unitários — sem banco, rodam sempre|1. Unitários — sem banco, rodam sempre]]
> - [[ARQUITETURA#2. Fumaça (`-m smoke`) — precisa de banco|2. Fumaça (`-m smoke`) — precisa de banco]]
> - [[ARQUITETURA#3. Caracterização (`-m caracterizacao`) — precisa de banco|3. Caracterização (`-m caracterizacao`) — precisa de banco]]
>
> **Rodar os testes escrevia no banco de producao (2026-09-16)**
>
> - [[ARQUITETURA#Reincidiu no mesmo dia, com três servidores (2026-09-16)|Reincidiu no mesmo dia, com três servidores (2026-09-16)]]
> - [[ARQUITETURA#O escritor que não estava nesta máquina — a tabela virou monotônica (2026-09-16)|O escritor que não estava nesta máquina — a tabela virou monotônica (2026-09-16)]]
>
> **A rede congelou o bug que existia para pegar (2026-09-16)**
>
>
> **Os dois modos da rede de caracterização — e qual vale de fato (2026-09-16)**
>
>
> **A rede de caracterização precisou distinguir rede ruim de regressão (2026-09-16)**
>
>
> **S12 — sales.py dividido por plataforma (2026-09-15)**
>
>
> **S11 — attribution.py dividido por responsabilidade (2026-09-15)**
>
>
> **/debriefing em 500 — campo removido do contexto, mantido no template (2026-09-15/16)**
>
>
> **Ordem não determinística em listas ordenadas por contagem (2026-09-15)**
>
> - [[ARQUITETURA#O mesmo defeito em `read_hotmart_recompra`|O mesmo defeito em `read_hotmart_recompra`]]
> - [[ARQUITETURA#A regra|A regra]]
>
> **Bugs Corrigidos (2026-06-25)**
>
> - [[ARQUITETURA#`SyntaxError` no parâmetro array da query TMB|`SyntaxError` no parâmetro array da query TMB]]
> - Internal Server Error por falhas no banco de dados (sessão 2026-06-25 #2)
>
> **Bugs Corrigidos (2026-06-24)**
>
> - [[ARQUITETURA#`DatetimeFieldOverflow` no Hotmart e TMB|`DatetimeFieldOverflow` no Hotmart e TMB]]
>
> **Desligamento do Typeform e sistema de pesquisa interno (2026-08-31)**
>
>
> **Calendário de lançamentos — fonte das datas-padrão (2026-09-14)**
>
>
> **Calendário — linha do tempo editável (vis-timeline, 2026-09-16)**
>
>
> **Documentação como sistema (2026-09-14)**
>
>
> **Egress do Supabase — cruzamento de telefone dos grupos otimizado (2026-09-14)**
>
>
> **Egress do Supabase — os cruzamentos que baixavam a base inteira (2026-09-14)**
>
> - [[ARQUITETURA#O que foi feito, por ordem de impacto|O que foi feito, por ordem de impacto]]
> - [[ARQUITETURA#Como validar mudança de reader sem regressão|Como validar mudança de reader sem regressão]]
>
> **Histórico de lançamentos por lead — tags do Active Campaign (2026-09-14)**
>
>
> **Atribuição por criativo — o sorteio do UTM e as vendas "sem veiculação" (2026-09-14)**
>
> - [[ARQUITETURA#O sorteio do UTM representante|O sorteio do UTM representante]]
> - [[ARQUITETURA#Pré-Qualificação aparecendo como "sem veiculação"|Pré-Qualificação aparecendo como "sem veiculação"]]
> - [[ARQUITETURA#O que sobra: renomeação de campanha/anúncio|O que sobra: renomeação de campanha/anúncio]]
>
> **Eventos de tráfego — a juncão entre o diário e a métrica (2026-09-14)**
>
> - [[ARQUITETURA#Como conferir se as correções de egress estão valendo|Como conferir se as correções de egress estão valendo]]
> - [[ARQUITETURA#Anotações no gráfico (`/verba`)|Anotações no gráfico (`/verba`)]]
> - [[ARQUITETURA#Contexto medido por evento|Contexto medido por evento]]
>
> **Dados das aulas no YouTube — duas fontes, uma tabela (2026-09-15)**
>
> - [[ARQUITETURA#Página `/aulas-ao-vivo`|Página `/aulas-ao-vivo`]]
>
> **Código de anúncio e imagem de criativo (15/09/26)**
>
> - [[ARQUITETURA#Convenção de nome por lançamento|Convenção de nome por lançamento]]
> - [[ARQUITETURA#De onde vem a imagem do criativo|De onde vem a imagem do criativo]]
>
> **Egress — contagens de e-mail que desciam como lista (2026-09-15)**
>
> - [[ARQUITETURA#Pendência: `read_typeform` do PI-AGO-26 falha ~50% das vezes|Pendência: `read_typeform` do PI-AGO-26 falha ~50% das vezes]]
>
> **Saúde do Lançamento — nota 0-100 no Debriefing (2026-09-15/16)**
>
>
> **Wizard de Configurações — o que era gravado, e o que a página via (2026-09-16)**
>
> - [[ARQUITETURA#1. `/debriefing` não lê `launch_config` — lê o snapshot|1. `/debriefing` não lê `launch_config` — lê o snapshot]]
> - [[ARQUITETURA#2. O save era overwrite da linha inteira, não patch|2. O save era overwrite da linha inteira, não patch]]
> - [[ARQUITETURA#3. Número inválido virava `NULL` em silêncio|3. Número inválido virava `NULL` em silêncio]]
> - [[ARQUITETURA#4. Escrita de config sem checagem de papel|4. Escrita de config sem checagem de papel]]
> - [[ARQUITETURA#5. A etapa "WhatsApp" não existia no wizard|5. A etapa "WhatsApp" não existia no wizard]]
>
> **Preview de landing page via thum.io (2026-09-16)**
>
>
> **`SNAPSHOT_VERSION`: por que virou teste (2026-09-16)**
>
> - [[ARQUITETURA#O teste que cobra|O teste que cobra]]
> - [[ARQUITETURA#O outro lado: campo que ninguém produz|O outro lado: campo que ninguém produz]]
> - [[ARQUITETURA#Previsto e realizado tinham que somar as mesmas coisas (2026-09-16)|Previsto e realizado tinham que somar as mesmas coisas (2026-09-16)]]
> - [[ARQUITETURA#Resumo do que protege o quê|Resumo do que protege o quê]]
>
> **Mobile: scroll horizontal em vez de esconder colunas (2026-09-16)**
>
>
> **Accordion: título em 2 linhas, ícone maior — mudança única, ~30 páginas (2026-09-16)**
>
>
> **Título sem "Captação/Pré-Quali/Meta/Google/YouTube/TikTok" no texto — vira badge (2026-09-16)**
>
>
> **plat_badge() migrou pra fora do Debriefing + extensão pra 11 páginas (2026-09-16/17)**
>

<!-- SUMARIO:FIM -->

Estado atual da arquitetura após as sessões de refatoração de 2026-06-23 e 2026-06-25, o God Module Split
(S1–S9, 2026-07-02) e a remoção do shim `database_reader.py` (S10, 2026-09-15).

---

## Estrutura de Arquivos

```
workspace-mmm/
├── frontend/
│   ├── app.py                  ← Ponto de entrada FastAPI (~125 linhas)
│   ├── core.py                 ← Estado compartilhado: cache de launches, _base_ctx, _compute_launch_defaults (~339 linhas)
│   ├── auth.py                 ← Auth HMAC, sessão, rate limiting, ROUTE_PERMISSIONS
│   ├── cache.py                ← Cache TTL em memória (_get_cached, _set_cached, _invalidate)
│   ├── utils.py                ← Helpers compartilhados (_norm_text, _extract_launch_code, _safe_date, etc.)
│   ├── models.py               ← Dataclasses de retorno (VendasSummary, MetaSummary, LeadsSummary, etc.)
│   ├── db.py                   ← Engines SQLAlchemy (_get_engine, _get_users_engine, _READONLY_TABLES)
│   ├── ad_accounts.py          ← Descoberta das contas de anúncio por API + listas KNOWN_* de fallback
│   ├── formatters.py           ← fmt_brl, fmt_num, fmt_pct (filtros Jinja2)
│   ├── services/
│   │   ├── __init__.py
│   │   ├── attribution.py      ← _sales_attribution (casa venda↔lead e decide anúncio/campanha/etapa)
│   │   ├── classificadores.py  ← puros, sobre UTM: _classify_campaign, _extract_ad_code, _utm_score, _inc_sales
│   │   ├── criativos.py        ← _creative_overview, _creative_insights (ranking de ADxxx, Validados × Novos)
│   │   ├── fetch.py            ← _launch_cfg, leitores com cache (_meta, _google, etc.), _fetch_all_data, _fetch_prev_for_debriefing
│   │   └── debriefing.py       ← _CLIMA_ORDER, _build_clima_breakdown, _attach_clima_*, _build_leads_detail_table, _build_rmkt_adsets, _compute_debriefing_ctx
│   ├── calendar_parser.py      ← Parser do HTML de calendário
│   ├── readers/                ← Módulos de domínio com implementações reais
│   │   ├── __init__.py
│   │   ├── launches.py         ← discover_launches, get_launch, read_launch_config, save_launch_config, get_etl_status
│   │   ├── ads_meta.py         ← read_meta, get_historico_ad_codes
│   │   ├── ads_google.py       ← read_google, read_daily_breakdown, _classify_google_type
│   │   ├── typeform.py         ← read_typeform, _resolve_typeform_ids, _build_typeform_comparison
│   │   ├── leads.py            ← read_leads, read_ac_leads_for_attribution, read_ac_campaigns
│   │   ├── sales.py            ← read_vendas, read_hotmart_details, read_tmb_details, read_vendas_consolidado
│   │   └── users.py            ← get_user_by_email, create_user, create_invite, bootstrap_admin, etc.
│   ├── routes/                 ← Routers FastAPI por domínio
│   │   ├── __init__.py
│   │   ├── auth.py             ← /login, /logout, /invite
│   │   ├── analytics.py        ← /, /funil, /insights, /calendario, /comparativo, /comparativo-v1-v2
│   │   ├── media.py            ← /meta, /google, /criativos, /meta-audiences, /google-audiences
│   │   ├── leads.py            ← /leads, /typeform, /crm-campanhas
│   │   ├── vendas.py           ← /vendas, /hotmart, /tmb
│   │   ├── settings_router.py  ← /settings
│   │   └── api.py              ← /api/*, /health, /debug-path, redirects legados
│   └── templates/              ← Templates Jinja2 (um por página)
├── etl/
│   ├── scheduler.py            ← APScheduler (substitui while/sleep)
│   ├── run_all.py              ← Orquestrador ETL
│   ├── etl_meta_ads.py
│   ├── etl_google_ads.py
│   ├── etl_active_campaign.py
│   ├── etl_typeform.py
│   ├── http_retry.py           ← http_get/http_post com retry via tenacity
│   ├── validation.py           ← validate_dataframe() pré-upsert
│   ├── db.py                   ← Engine SQLAlchemy para o ETL
│   └── schema.sql              ← Schema completo + views Supabase
├── src/
│   ├── logger.py               ← get_logger() com RotatingFileHandler
│   ├── readers/
│   │   └── launch_discovery.py ← Descobre pastas [CÓDIGO] em analises/
│   ├── ingest/
│   │   └── csv_utils.py        ← Utilitários de leitura de CSV
│   └── reports/, transforms/   ← Geradores de relatório e transforms
├── tests/
│   ├── conftest.py
│   ├── test_core.py            ← 61 testes: formatadores, classificação, atribuição, launches
│   ├── test_csv_utils.py       ← Testes de detecção de delimitador e encoding
│   ├── test_etl_validation.py  ← Testes de validate_dataframe()
│   └── test_launch_discovery.py← Testes de regex e PRODUCT_BY_PREFIX
└── analises/
    └── [PBB-ABR-26]/           ← Pastas de lançamento com CSVs por fonte
```

---

## God Module Split (S1–S9 em 2026-07-01; encerrado em 2026-09-15)

O `database_reader.py` original tinha **4.180 linhas e 74 funções** em um único arquivo. O split incremental
preservou 100% de compatibilidade porque `database_reader.py` seguiu re-exportando tudo — nenhum caller
(especialmente `core.py`) precisou mudar durante as sessões S1–S9. Em S10 o shim foi removido e os callers
passaram a importar de `frontend.db_readers`.

| Sessão | O que foi extraído | Resultado |
|--------|--------------------|-----------|
| **S1** | `frontend/models.py` — todos os dataclasses de retorno | Tipos isolados, importáveis sem carregar DB |
| **S1** | `frontend/db.py` — engines SQLAlchemy e `_READONLY_TABLES` | Pool de conexão isolado; `_make_engine` centralizado |
| **S2** | `frontend/utils.py` — `_norm_text`, `_extract_launch_code`, `_safe_date`, `_safe_div`, `_delta`, `_normalize_product_ids` | Helpers compartilhados sem dependência circular |
| **S3** | `frontend/db_readers/users.py` — funções de autenticação e convites | Zero dependência com o pipeline analítico |
| **S3** | `frontend/db_readers/launches.py` — discovery, config, ETL status | Inclui `discover_launches`, `read_launch_config`, `get_etl_status` |
| **S4** | `frontend/db_readers/typeform.py` — reader de pesquisas com cache de formulários | Deferred import de `read_vendas` evita circular |
| **S4** | `frontend/db_readers/ads_meta.py` — `read_meta`, `get_historico_ad_codes` | Deferred import de `read_vendas` evita circular |
| **S4** | `frontend/db_readers/ads_google.py` — `read_google`, `read_daily_breakdown` | Deferred import de `read_vendas` evita circular |
| **S5** | `frontend/db_readers/sales.py` — `read_vendas`, `read_hotmart_details`, `read_tmb_details`, `read_vendas_consolidado` | SQL com raw strings (resolve SyntaxWarning de `\d`); strings PT corrigidas |
| **S5** | `frontend/db_readers/leads.py` — `read_leads`, `read_ac_leads_for_attribution`, `read_ac_campaigns` | Strings PT corrigidas (Pré-Qualificação, Captação, etc.) |
| **S6** | `frontend/formatters.py` — `fmt_brl`, `fmt_num`, `fmt_pct` | Zero deps; registrados em `templates.env.filters` em core.py |
| **S6** | `frontend/services/attribution.py` — classificadores puros + `_sales_attribution`, `_creative_overview`, `_creative_insights` | `_sales_attribution` usa deferred imports de core.py para config; `_norm_text` vem de utils.py |
| **S7** | `frontend/cache.py` — `_get_cached`, `_set_cached`, `_invalidate`, `_CACHE*` | Zero deps; `attribution.py` atualizado para importar de `frontend.cache` |
| **S7** | `frontend/auth.py` — auth HMAC, sessão, rate limiting, `ROUTE_PERMISSIONS` | Importa `Launch` de `frontend.models`; `core.py` re-exporta tudo para backward compat |
| **S8** | `frontend/services/fetch.py` — `_launch_cfg`, `_get_global_start/_end`, leitores com cache (`_meta`, `_google`, `_vendas`, `_leads`, `_typeform`, `_hotmart_details`, `_tmb_details`, `_vendas_consolidado`, `_typeform_count`), `_fetch_all_data`, `_fetch_prev_for_debriefing` | `_sales_attribution` importado no topo (sem circular); imports de `database_reader` + `frontend.cache` |
| **S9** | `frontend/services/debriefing.py` — `_CLIMA_ORDER`, `_build_clima_breakdown`, `_attach_clima_sales`, `_attach_clima_variation`, `_clima_raw`, `_sales_raw`, `_build_leads_detail_table`, `_build_rmkt_adsets`, `_compute_debriefing_ctx` | Imports de `fetch.py` (`_launch_cfg`) e `attribution.py` (`_merge_google_tipo_sales`) no topo; `core.py` re-exporta `_compute_debriefing_ctx` |

### S10 — fim do shim (2026-09-15)

O `database_reader.py` **não existe mais**. As três coisas que ainda moravam nele foram para onde pertenciam:

| O que | Foi para |
|---|---|
| `read_comparativo` + `_merge_segmentos` | `frontend/db_readers/comparativo.py` (novo) |
| `read_youtube_aulas` | `frontend/db_readers/youtube_aulas.py` (já existia) |
| `KNOWN_META_ACCOUNTS` / `KNOWN_GOOGLE_ACCOUNTS` | `frontend/ad_accounts.py` — onde a docstring já dizia que era o lugar delas |

`frontend/db_readers/__init__.py` deixou de ser `from frontend.database_reader import *` e passou a listar
explicitamente o que exporta, então `from frontend.db_readers import read_meta` continua funcionando sem
que ninguém dependa do arquivo onde a função mora.

**`frontend/db_readers/nomenclatura.py` (novo).** A classificação de campanha pelo nome (etapa, temperatura,
bucket, segmento) estava duplicada entre `ads_meta.py` e `ads_google.py`: `BUCKET_MAP` e `MODIFIER_MAP` eram
byte a byte idênticos nos dois, e o laço de classificação era quase igual. Os mapas de **etapa** e
**temperatura**, esses sim, diferem de propósito (o Meta casa a chave entre colchetes e lista `aula 1..4`
uma a uma; o Google casa por substring e tem `Performance Max`) — e continuam separados, agora com o motivo
escrito ao lado.

Isso também desfez o ciclo `sales` ↔ `ads_meta`: `sales` importava `_categorize_campaign` de `ads_meta`, que
por sua vez precisava de `read_vendas` de volta. Hoje os dois dependem de `nomenclatura`, que é folha, e
`ads_meta`/`ads_google` importam `sales` normalmente, no topo do módulo.

**Ciclo que continua existindo:** `sales` → `launches` → `typeform` → `sales`. `discover_launches` precisa
saber se o lançamento tem pesquisa (typeform), `typeform` precisa de `read_vendas`, e `sales` precisa de
`read_launch_config`. Essas três dependências seguem importadas dentro das funções, e o motivo está escrito
na docstring de cada uma. Desfazer exigiria tirar `_resolve_typeform_ids` de `typeform.py`.

**Equivalência provada, não presumida:** `tests/test_nomenclatura.py` roda a implementação nova contra uma
fixture gerada com a implementação antiga sobre **todas as 837 campanhas distintas que existem no banco**
(470 Meta × 2 modos de `legacy`, 367 Google). São 1.311 casos; qualquer divergência de classificação em
campanha real derruba o teste.

**Estado de `core.py` após S8:** 689 linhas.

**Estado de `core.py` após S9:** 339 linhas. Restam: cache de lançamentos (`get_launches`, `reset_launches_cache`), resolução de launch (`resolve_launch`, `find_previous_launch`), `_base_ctx`, `_compute_launch_defaults`, caches de health/ETL/thumb. Re-exporta seletivamente de `auth.py`, `cache.py`, `attribution.py`, `fetch.py` e `debriefing.py`.

**Deferred imports:** `typeform.py`, `ads_meta.py` e `ads_google.py` importam `read_vendas` via `from frontend.db_readers.sales import read_vendas` dentro do corpo da função, evitando circular import no carregamento do módulo. `attribution.py._sales_attribution` importa `_get_cached/_set_cached` de `frontend.cache` e `_launch_cfg/_get_global_*` de `frontend.core` por deferred import. `fetch.py` importa `_sales_attribution` de `attribution.py` no topo (sem circular, pois `attribution.py` é carregado antes de `fetch.py` na ordem de imports de `core.py`). `debriefing.py` importa de `fetch.py` e `attribution.py` no topo — ambos são carregados antes de `debriefing.py` em `core.py`.

**Bugs críticos descobertos e corrigidos durante o split:**
- `get_user_by_email` e demais funções de usuário foram extraídas em sessão anterior mas nunca re-exportadas de `database_reader.py` → app crashava no startup. Corrigido adicionando o bloco de re-exportação.
- `read_youtube_aulas` importada por `core.py` mas nunca existiu em nenhum arquivo → crash no startup. Corrigido com stub que retorna `[]`.

---

## Fluxo de Dados

```
APIs / CSV exports
      ↓
etl/ (ETL scripts com retry e validação)
      ↓
Supabase (dois bancos)
      ↓
frontend/db_readers/*.py        (leitores de domínio: sales, leads, ads_meta, ads_google,
                                 typeform, launches, users, comparativo, nomenclatura, …)
      ↓
frontend/services/attribution.py  (atribuição de vendas, overview de criativos)
frontend/formatters.py            (fmt_brl, fmt_num, fmt_pct)
      ↓
frontend/cache.py                  (cache TTL em memória: _get_cached, _set_cached, _invalidate)
frontend/auth.py                   (sessão HMAC, rate limiting, ROUTE_PERMISSIONS)
frontend/services/fetch.py         (leitores com cache, _fetch_all_data, _fetch_prev_for_debriefing)
frontend/services/debriefing.py    (_compute_debriefing_ctx, _build_clima_*, _build_leads_detail_table, _build_rmkt_adsets)
frontend/core.py                   (_base_ctx, _compute_launch_defaults, caches de health/ETL/thumb)
      ↓
frontend/routes/*.py         (handlers FastAPI com APIRouter)
      ↓
frontend/app.py              (inclui routers, middleware, startup)
      ↓
frontend/templates/*.html    (Jinja2 → HTML)
```

---

## Responsabilidades por Arquivo

### `frontend/app.py` (~125 linhas)
- Cria o objeto `FastAPI`
- Registra middleware de autenticação (`auth_middleware`)
- Monta arquivos estáticos (`/analises`, `/img`)
- Registra startup events (`_bootstrap_admin`, `pre_warm_cache`)
- Inclui todos os routers com `app.include_router()`

### `frontend/auth.py`
Auth HMAC e sessão — zero dependência de rotas ou cache:
- Constantes: `BRABO_USER`, `BRABO_PASS`, `SECRET_KEY`, `SESSION_MAX_AGE`, `COOKIE_SECURE`
- Permissões: `ROUTE_PERMISSIONS`, `_ALL`, `_MEDIA`, `_ANLT`, `_DTLD`, `_ADM`
- Senha: `_hash_password`, `_verify_password` (via passlib/bcrypt)
- Sessão HMAC: `_sign_session`, `_decode_session`, `_set_session_cookie`
- Helpers: `_get_current_user`, `_filter_launches_for_user`
- Rate limiting: `_check_login_rate_limit`, `_record_login_attempt`

### `frontend/cache.py`
Cache em memória com TTL — zero dependências além de `time`:
- `_CACHE`, `_CACHE_TTL` (30 min), `_CACHE_MAX_SIZE` (2000 entradas)
- `_cache_key`, `_get_cached`, `_set_cached`, `_invalidate`
- Eviction LRU de 20% ao atingir `_CACHE_MAX_SIZE`

### `frontend/services/fetch.py` (~348 linhas)
Leitores com cache e orquestrador assíncrono:
- `_launch_cfg`, `_get_global_start`, `_get_global_end` — helpers de config que lêem `read_launch_config` com cache TTL
- Leitores com cache: `_meta`, `_google`, `_vendas`, `_leads`, `_typeform`, `_hotmart_details`, `_tmb_details`, `_vendas_consolidado`, `_typeform_count`
- `_fetch_all_data` — orquestrador async com `asyncio.gather`; todos os leitores em paralelo, erros capturados em `_errors`
- `_fetch_prev_for_debriefing` — versão sync para buscar dados do lançamento anterior

### `frontend/core.py` (~339 linhas)
Ponto de coesão do frontend — importado por todos os routers. Re-exporta seletivamente de `auth.py`, `cache.py`, `attribution.py`, `fetch.py` e `debriefing.py`. Contém:
- Registro de filtros Jinja2 (`templates.env.filters["brl"] = fmt_brl` etc.)
- Cache de lançamentos com TTL 60s (`get_launches`, `reset_launches_cache`, `_LAUNCHES_DB_OK`)
- Resolução de lançamento (`resolve_launch`, `find_previous_launch`)
- V1 reports: `V1_REPORTS`, `_v1_url_if_exists`, `_v1_reports_for_launch`
- Contexto base (`_base_ctx`) injetado em todos os templates
- Defaults de lançamento (`_compute_launch_defaults`)
- Caches de health check (30s), ETL status (5 min), Drive thumb URL (10 min)

### `frontend/services/debriefing.py` (~363 linhas)
Builders de contexto para `debriefing.html`:
- `_CLIMA_ORDER` — ordem canônica dos climas (Quente/Frio/Específico)
- `_build_clima_breakdown`, `_attach_clima_sales`, `_attach_clima_variation` — breakdown de investimento/leads por clima com variação vs lançamento anterior
- `_clima_raw`, `_sales_raw` — helpers de extração de valores brutos
- `_build_leads_detail_table` — tabela combinada FB/YT × clima com CPL, conversão, ROAS e delta vs período anterior
- `_build_rmkt_adsets` — etapas de remarketing com percentual de gasto
- `_compute_debriefing_ctx` — orquestra todos os builders e retorna o dict de contexto completo para o template

### `frontend/formatters.py`
`fmt_brl`, `fmt_num`, `fmt_pct` — zero dependências. Registrados como filtros Jinja2 em `core.py`.

### `frontend/services/attribution.py`
Lógica de atribuição de vendas e overview de criativos:
- Classificadores puros: `_classify_campaign`, `_extract_ad_code`, `_classify_google_campaign_type`, `_merge_google_tipo_sales`, `_inc_sales`, `_utm_score`, `_find_header_col`
- Atribuição: `_sales_attribution` (lê leads do AC, cruza com buyers, pondera por `_utm_score`)
- Overview: `_creative_overview` (agrega Meta + Google por código AD, calcula hook/hold/body rate)
- Insights: `_creative_insights` (gera frases automáticas sobre top performers e gastos sem retorno)

### `frontend/routes/*.py`
Cada arquivo define um `APIRouter` com as rotas do seu domínio. Importam de `frontend.core` e não contêm lógica de negócio — apenas orquestram dados e renderizam templates.

---

## Cache (frontend)

| Cache | TTL | Invalidação |
|-------|-----|-------------|
| `_CACHE[launch::reader]` | 30 min | Automática ao expirar; manual via `_invalidate(launch_code)` |
| `_LAUNCHES_CACHE` | 60s | Automática; manual via `reset_launches_cache()` após `save_launch_config` |
| `_HEALTH_CACHE` | 30s | Automática ao expirar |
| `_thumb_url_cache` | 10 min | Automática ao expirar |

---

## ETL Scheduler

O `etl/scheduler.py` usa **APScheduler** (`BlockingScheduler`) com:
- `coalesce=True` — se perdeu disparos enquanto ocupado, executa apenas 1
- `misfire_grace_time=300` — tolera até 5 min de atraso antes de marcar como misfire
- `threading.Lock` — impede sobreposição: se o ETL ainda corre, o próximo ciclo é ignorado com log de aviso
- `next_run_time=datetime.now()` — executa imediatamente ao iniciar
- Listener para erros e misfires com alerta via webhook

---

## Segurança

| Proteção | Implementação |
|----------|--------------|
| Sessão HMAC | `_sign_session` / `_decode_session` com SHA-256 |
| Cookie seguro | `httponly=True`, `samesite=lax`, `secure` via `COOKIE_SECURE` env var |
| Brute force | 10 tentativas / 5 min por IP com limpeza automática de memória |
| Permissões por rota | `ROUTE_PERMISSIONS` dict verificado no middleware |
| `/debug-path` | Requer role `admin` |
| Writes em tabelas read-only | Guard via SQLAlchemy event em `_make_engine()` |
| Env vars críticas | Log de erro no startup se `SUPABASE_DB_URL`/`SUPABASE_USERS_URL` ausentes |

---

## Testes

Três camadas, com dependências diferentes de banco.

### 1. Unitários — sem banco, rodam sempre

| Arquivo | O que testa |
|---------|-------------|
| `test_core.py` | `fmt_brl/num/pct`, `_norm_text`, `_extract_ad_code`, `_classify_campaign`, `_classify_google_campaign_type`, `_utm_score`, `_inc_sales`, `find_previous_launch`, `resolve_launch` |
| `test_csv_utils.py` | Detecção de delimitador, fallback de Sniffer, encoding |
| `test_etl_validation.py` | `validate_dataframe()`: happy path, DataFrame vazio, colunas ausentes, nulos excessivos |
| `test_nomenclatura.py` | Classificação de campanha pelo nome, contra **as 837 campanhas reais do banco** (1.311 casos) — ver S10 |
| `test_frontend_smoke.py::test_templates_compilam` | Todos os templates Jinja compilam no ambiente real do app |

### 2. Fumaça (`-m smoke`) — precisa de banco

Loga com as credenciais legadas e confere que cada página autenticada responde 200.
Pega erro de template, de rota e de import; **não** pega número errado.

### 3. Caracterização (`-m caracterizacao`) — precisa de banco

`tests/test_caracterizacao_readers.py` congela num baseline o que cada `read_*` de
`frontend/db_readers/` devolve, para dois lançamentos encerrados (PBB-ABR-26 e PI-AGO-26).
É a rede que permite refatorar leitura sem medo: se um número mudar, o teste cai.

Os readers são descobertos por **introspecção** — `read_*` novo entra na cobertura sozinho,
desde que a assinatura seja `(launch…, **opcionais)`. `test_descobriu_readers` garante que a
introspecção não quebrou e virou um no-op silencioso.

O baseline guarda **digest + esqueleto**, nunca o conteúdo: a saída completa são ~180 MB e
inclui e-mail e telefone de comprador, que não podem entrar no repositório. Quando um teste
cai, a saída inteira é gravada em `tests/baseline/_falhas/` (ignorado pelo git) pra dar o diff.

**Nem todo reader dá pra congelar pelo valor.** Os listados em `VOLATEIS` leem tabelas que
continuam recebendo linhas mesmo depois do carrinho fechar (sendflow/WhatsApp, formulários do
sistema novo, sincronismo do AC) ou devolvem totais globais, não recortados pela janela do
lançamento. Deles o teste cobra só a **forma** da resposta. A lista foi medida, não chutada:
duas execuções a 15 minutos de distância divergiram nesses e em nenhum outro.

`read_launch_config` entrou nessa lista em 16/09 por um motivo **diferente dos outros**: ali não é
dado chegando sozinho, é gente editando. `launch_config` é preenchida à mão no wizard de
Configurações, a qualquer momento e inclusive em lançamento já fechado, e `updated_at` faz parte da
resposta do reader — então todo salvamento muda o digest. Congelado por valor, o teste falhava
sempre que alguém mexia no wizard (foi o que aconteceu quando a oferta do PI-AGO-26 foi preenchida
no meio de uma rodada: mesmas 42 chaves, sha diferente). Nenhuma medição de 15 minutos pega isso —
depende de alguém abrir a tela.

```bash
# unitários (CI, sem banco)
python -m pytest tests/ -m "not smoke and not caracterizacao"

# antes de refatorar: grava a foto do comportamento atual
ATUALIZAR_BASELINE=1 python -m pytest tests/test_caracterizacao_readers.py -m caracterizacao

# depois de refatorar: confere que nada mudou
python -m pytest tests/test_caracterizacao_readers.py -m caracterizacao
```

> ⚠️ **`ATUALIZAR_BASELINE=1` só vale na suíte inteira.** Escopado em alguns test ids, ele reescreve
> o arquivo do lançamento **apenas com as chaves daqueles testes** e apaga as dos outros readers —
> regravar só `read_launch_config` de dois lançamentos custou 2.655 linhas de baseline. Se precisar
> atualizar um reader só, extraia a entrada nova, restaure o arquivo e aplique a chave à mão. E
> restaure com **cópia de backup**, não com `git checkout -- a b c`: basta um dos caminhos não estar
> versionado pra ele abortar sem reverter nada (silenciosamente, se o stderr estiver descartado).

---

## Rodar os testes escrevia no banco de producao (2026-09-16)

`PRE_WARM_CACHE` vem **ligado por padrao** (`os.environ.get("PRE_WARM_CACHE", "true")`). O
aquecimento sobe junto com o app, no evento de startup do FastAPI, e grava `debriefing_snapshot`
— tabela do banco analytics, que **nao** tem guard de somente-leitura (o guard existe so no banco
operacional e cobre duas tabelas: `tmb_clean_oficial` e `hotmart_clean_oficial`).

`tests/test_frontend_smoke.py` carrega o `.env` real e usa `TestClient(app)` como context manager,
o que dispara esse startup. Resultado: **rodar a suite de fumaca reescrevia os snapshots de
producao** com o codigo do checkout. Os testes de caracterizacao ja desligavam; o de fumaca nao.

Corrigido com `os.environ["PRE_WARM_CACHE"] = "false"` antes de importar `frontend.app`. Efeito
colateral bom: `/debriefing` passa a ser exercitado pelo caminho **ao vivo**, que e onde os 500
aparecem — o caminho do snapshot mascarava erro de template quando o snapshot estava velho.

**O que isso revelou, e continua valendo.** Qualquer processo local com o `.env` de producao
escreve nessa tabela sozinho, sem requisicao HTTP nenhuma: basta o app estar de pe. Foi assim que
o diagnostico do 500 do `/debriefing` se perdeu — um servidor de desenvolvimento rodando codigo
novo gravava snapshots no formato novo enquanto o checkout da investigacao, um commit atras, lia
com o template velho.

Das 13 escritas do frontend no banco, **12 exigem acao humana autenticada** (wizard de
lancamento, gestao de usuarios, cache de thumbnails). A do snapshot e a unica autonoma — e por
isso a unica que vaza de um ambiente para o outro sem ninguem perceber.

**Ao rodar o app localmente contra o `.env` de producao, use `PRE_WARM_CACHE=false`** a menos que
queira mesmo regravar os snapshots que todo mundo le.

### Reincidiu no mesmo dia, com três servidores (2026-09-16)

Horas depois, `/debriefing` voltou a dar 500 — e desta vez **ia e voltava sozinho**, o mesmo
lançamento alternando entre carregar e quebrar a cada rodada de aquecimento. Havia **três uvicorn
de pé ao mesmo tempo** contra o `.env` de produção (portas 8000, 8934 e 8291, subidos às 09:11,
09:55 e 10:15), cada um com uma versão diferente do código congelada em memória. Todos gravando
`debriefing_snapshot` a cada ciclo, um por cima do outro. Quem abrisse a página pegava o payload
de quem tivesse gravado por último.

O gatilho foi a Saúde do Lançamento 2.0 ter mudado a forma do `dbf` (`saude_pesos` e os
`saude_score_*` novos) **sem subir `SNAPSHOT_VERSION`** — exatamente o que o comentário em
`frontend/db_readers/debriefing_snapshot.py` já dizia não ser opcional, depois de a mesma coisa ter
acontecido entre 04/09 e 15/09. Subido para `7`.

**A lição que faltava no registro anterior:** subir a versão **não conserta um processo já de pé**.
O Jinja relê o template do disco a cada request, mas o Python fica congelado em memória — o
servidor das 09:11 servia o template novo, que pede `dbf.saude_pesos`, com um código que nunca
calcula esse campo. Por isso ele devolvia 500 em `?ao_vivo=1` de forma determinística, mesmo com o
banco perfeito. Diagnóstico de 500 no `/debriefing` começa por **quantos processos estão de pé e
desde quando**:

```bash
# PowerShell — todo uvicorn vivo, com porta e hora de início
Get-CimInstance Win32_Process -Filter "Name='python.exe'" |
  Where-Object { $_.CommandLine -like '*uvicorn*' } |
  Select-Object ProcessId, CreationDate, CommandLine
```

Um servidor só, reiniciado depois de qualquer mudança no `dbf`.

### O escritor que não estava nesta máquina — a tabela virou monotônica (2026-09-16)

Com um único servidor local de pé, a tabela continuou voltando inteira para a versão 6 a cada
~30 min: uma varredura sequencial pelos 9 lançamentos, o intervalo do `PRE_WARM_INTERVAL_MIN`.
Não era processo local (varredura de `Win32_Process` mostrava só um uvicorn) e não era deploy
remoto (`FRONTEND_URL` aponta pra `127.0.0.1`, não há servidor de produção). Era **outra máquina
com o `.env` de produção e um checkout antigo** — e não deu pra identificar qual: o tráfego do app
passa pelo Supavisor, então `pg_stat_activity.client_addr` devolve o endereço do pooler, não o do
cliente.

Enquanto isso durou, a página ficava **correta e lenta**: o leitor descartava o payload de versão
diferente e recalculava ao vivo, 25-80s por lançamento em vez de 0,2s.

Duas mudanças fecham esse buraco, independentemente de quem seja o escritor:

1. **`write_snapshot` não rebaixa mais a versão.** O `ON CONFLICT DO UPDATE` ganhou
   `WHERE COALESCE((debriefing_snapshot.payload->>'_version')::int, 0) <= :versao`, então um
   processo com código antigo simplesmente não grava por cima de um snapshot mais novo — o upsert
   vira no-op e o processo loga que *ele* é o desatualizado. Regravação na mesma versão (o refresh
   normal) e subida de versão seguem funcionando. **Preço:** rollback de propósito pra uma versão
   anterior não consegue regravar; nesse caso, apagar as linhas da tabela.
2. **Todo snapshot carrega `_writer`** (`hostname#pid`). Da próxima vez, descobrir a origem é uma
   consulta:
   ```sql
   SELECT lancamento_codigo, payload->>'_version', payload->>'_writer', computed_at
   FROM debriefing_snapshot ORDER BY computed_at DESC;
   ```

Desfecho do dia: depois do push da versão 7, as escritas de fora passaram a sair como v7 — a outra
máquina atualizou. O que a sobrevivência dessa tabela não pode depender é disso acontecer.

---

## A rede congelou o bug que existia para pegar (2026-09-16)

O erro mais caro desta refatoracao, e vale escrito por inteiro porque o mecanismo se repete.

**O bug.** `attribution.py` e `orcamento.py` importavam `_categorize_campaign` de `ads_meta` e
`ads_google` **dentro de funcoes** (import diferido, para quebrar ciclo). Ao extrair a
classificacao para `nomenclatura.py`, a funcao saiu daqueles modulos e os 6 pontos de import
ficaram apontando para o vazio. Import dentro de funcao so falha quando a funcao roda — nao no
import do modulo, nao na coleta do pytest, nao numa varredura de imports de topo.

Resultado: o bloco "Atribuicao" do dashboard falhava nos 11 lancamentos com Active Campaign,
mostrando "Falha ao carregar: Atribuicao. Os totais desta pagina podem estar incompletos."
Quem achou foi o usuario, olhando a tela.

**Por que a rede nao pegou — o que importa de verdade.** O teste captura excecao e a registra
como resultado (`{"__excecao__": ...}`), porque excecao tambem e comportamento. Mas o baseline
foi **gerado com o codigo ja quebrado**: o ImportError virou o valor esperado. Todas as
verificacoes seguintes compararam excecao com excecao e passaram. A rede aprovou, repetidamente,
exatamente o bug que existia para pegar.

**As tres correcoes:**

1. Os 6 imports apontam para `nomenclatura` (assinaturas identicas, so mudou nome e modulo).
2. `caracterizacao_util.recusar_excecao_no_baseline` faz `ATUALIZAR_BASELINE=1` **falhar** quando
   a saida e uma excecao capturada. Congelar excecao e sempre suspeito; congelar em silencio e
   o que torna o teste inutil.
3. Varredura de nomes orfaos com `ast` em **todo** o `frontend/`, nao so nos arquivos tocados.
   Ela achou mais dois quebrados pela mesma refatoracao: `_norm_text` em `criativos.py` e
   `read_dia1_sales` em `comparativo.py`. Some-se a verificacao de que todos os 86 imports
   diferidos do `frontend/` resolvem.

**A regra que fica:** ao mover uma funcao de modulo, `grep` pelo nome **em todo o repositorio**,
nao so nos arquivos que voce editou — import diferido nao aparece no topo de nada. E antes de
gravar baseline, confirme que o codigo esta verde por outro meio; um baseline gerado sobre codigo
quebrado e pior que nenhum, porque da a impressao de cobertura.

---

## Os dois modos da rede de caracterização — e qual vale de fato (2026-09-16)

O baseline commitado em `tests/baseline/` **envelhece**, e isso não é defeito: `leads`,
`ga4` e `typeform` continuam recebendo linhas pelo sincronismo do Active Campaign e do GA4
mesmo para lançamento encerrado. Um baseline gerado à noite e verificado no dia seguinte
acusou 9 readers "divergentes" sem nenhuma mudança de código.

Por isso a rede tem dois modos, e é importante não confundi-los:

**Modo A/B (o que vale para aprovar uma refatoração).** Gera o baseline no código **antigo**,
num worktree do commit anterior, e verifica no código novo minutos depois:

```bash
git worktree add "$TEMP/antes" <commit-anterior>
cd "$TEMP/antes" && BASELINE_DIR="$TEMP/base" ATUALIZAR_BASELINE=1     pytest tests/test_caracterizacao_readers.py -m caracterizacao
cd /c/dev/workspace-mmm && BASELINE_DIR="$TEMP/base"     pytest tests/test_caracterizacao_readers.py -m caracterizacao
```

Como as duas leituras acontecem com minutos de diferença, o dado não se move, e **toda**
divergência é do código. Foi assim que S10, S11 e S12 foram validadas — e foi assim que o
bug das constantes de UF órfãs apareceu.

**Modo tripwire (o baseline commitado).** Serve para acusar mudança acidental no dia a dia.
Para os readers que acompanham tabelas vivas ele compara só a forma (`VOLATEIS`), porque
comparar valor contra um baseline de ontem só produziria alarme falso.

**A regra:** divergência no baseline commitado é *suspeita*, não veredicto. Antes de tratar
como regressão, rode o mesmo reader em dois processos separados — se o digest bate, o código
é determinístico e o que mudou foi o dado. Se não bate, achou um bug de ordenação (já
aconteceu duas vezes, ver a seção sobre desempate).

---

## A rede de caracterização precisou distinguir rede ruim de regressão (2026-09-16)

Nas primeiras execuções a rede acusou falha três vezes sem que nada tivesse mudado no código.
Duas causas, ambas defeito do teste, não do sistema:

**1. Timeout do banco contava como "a saída mudou".** Quando o Supabase fica lento, a consulta
estoura o `statement_timeout` e o reader levanta. O teste transformava a exceção em resultado e
comparava com o baseline — acusando regressão onde só houve rede ruim. Numa das noites a suíte
levou 23 minutos contra os ~5 habituais e 35 testes "falharam".

Agora `caracterizacao_util.e_falha_de_infra` percorre a cadeia de causas (o SQLAlchemy embrulha o
erro do psycopg2, e a frase reveladora está duas camadas abaixo) e o teste **pula** quando
reconhece falha de acesso — timeout, conexão fechada, sem slot, deadlock. `KeyError` e
`AttributeError` continuam sendo falha de verdade: são erros de *como o dado é calculado*, não de
*chegar até o dado*.

**2. A comparação por forma trocava de representação sozinha.** `resumir` colapsa um dicionário
assim que ele passa de 30 chaves. Um dicionário aninhado que cruzasse esse limiar por dado novo
mudava de representação sem nenhuma mudança de código, e o teste acusava "mudou de forma".
`_forma` passou a ser deliberadamente raso: nomes dos campos de primeiro nível e a espécie de
cada um.

**Por que isso importa mais do que parece:** uma rede que grita lobo deixa de ser consultada, e
aí não serve para nada. Se ela vai bloquear um commit, precisa errar para o lado de calar a boca
quando o problema não é do código.

---

## S12 — sales.py dividido por plataforma (2026-09-15)

`db_readers/sales.py` tinha 1.341 linhas e misturava a venda do lançamento com o detalhe de
cada plataforma. Virou quatro módulos:

| Módulo | Linhas | Responsabilidade |
|---|---|---|
| `sales.py` | ~660 | `read_vendas` (soma Hotmart + TMB na janela do carrinho), consolidado, qualidade por região, dia 1 |
| `hotmart.py` | ~380 | `read_hotmart_details`, `read_hotmart_recompra` |
| `tmb.py` | ~200 | `read_tmb_details`, `read_forma_pagamento_entrada` |
| `_vendas_comum.py` | ~190 | O que os três consultam: `_parcela_unica_info`, `_hm_data_sql`, `_norm_uf`, `_canal_venda`… |

`sales.py` reexporta os outros, então os imports existentes continuam valendo.

`_vendas_comum.py` não é um "utils" genérico: cada peça está ali porque é usada de dois ou três
lugares, e duplicá-la faria o número da Hotmart divergir do consolidado. O caso mais sensível é
`_parcela_unica_info`, que decide se a linha é venda à vista, parcelada ou assinatura recorrente
— critério usado na contagem, no faturamento e no dia 1.

**Um bug meu, pego pela rede.** Na primeira tentativa, `_norm_uf` foi para `_vendas_comum.py` e
as constantes que ela usa (`_UF_POR_NOME`, `_UFS_VALIDAS`) ficaram em `sales.py`. O teste de
caracterização acusou 35 readers divergentes — `read_vendas` mudava e o erro se propagava para
Meta, Google, Hotmart, TMB e dia 1. Sem a rede isso teria ido para produção como estado de
comprador errado em relatório de região. A varredura de nomes órfãos com `ast` virou parte do
procedimento de qualquer divisão de módulo daqui pra frente.

---

## S11 — attribution.py dividido por responsabilidade (2026-09-15)

`services/attribution.py` tinha 859 linhas e três assuntos diferentes. Virou três módulos:

| Módulo | Linhas | Responsabilidade |
|---|---|---|
| `classificadores.py` | 140 | Funções puras sobre texto de UTM — sem banco, sem estado |
| `attribution.py` | 288 | `_sales_attribution`: casa venda com lead e decide anúncio/campanha/etapa |
| `criativos.py` | 476 | `_creative_overview` e `_creative_insights`: ranking de ADxxx e Validados × Novos |

`attribution.py` reexporta os dois outros, então `from frontend.services.attribution import
_creative_overview` — que `core.py` e outros usam há tempo — continua valendo.

**Não confundir `classificadores.py` com `db_readers/nomenclatura.py`.** O segundo lê o padrão
de colchetes do nome da campanha na plataforma (`[MA][CAPTAÇÃO][QUENTE]…`); o primeiro trabalha
sobre as UTMs que chegam com a venda, onde o texto vem solto e a decisão é por palavra
encontrada. São regras diferentes para perguntas diferentes, e é por isso que continuam
separadas em vez de unificadas.

**Rede usada:** `tests/test_caracterizacao_servicos.py` (novo) congela a saída de
`_sales_attribution`, `_creative_overview` e do contexto do debriefing para PBB-ABR-26 e
PI-AGO-26. Foi gravado **antes** da divisão e verificado depois: as três saídas continuaram
idênticas. Sem isso, mexer em `_creative_overview` — que carrega as correções sutis de escopo
de etapa de 14/09 — seria aposta, não refatoração.

---

## /debriefing em 500 — campo removido do contexto, mantido no template (2026-09-15/16)

**Sintoma:** `/debriefing` (e `?modo=slides`) devolvendo 500 com
`UndefinedError: 'dict object' has no attribute 'total_grupos_vip'`.

**Causa real:** o commit `bf8065c` ("Resumo Executivo: Pessoas nos Grupos vira pico; remove Total
de Grupos") tirou `total_grupos_normais`/`total_grupos_vip` e os `prev_` correspondentes do
`_compute_debriefing_ctx`, e ajustou o primeiro grid de KPIs. Mas o template tinha **dois** blocos
citando esses campos: `kpis_gerais` e um segundo, "Grupos WhatsApp — Normal x VIP", que passou
despercebido e continuou pedindo `dbf.total_grupos_vip`.

**Correção:** o segundo bloco foi removido por inteiro. Era o que o commit pretendia — os dois
cards de "Total" saíram por decisão do usuário (a tabela do Supabase ficava incompleta em alguns
lançamentos) e os dois de "Pessoas" já haviam subido para o grid principal, então o bloco era
duplicata.

**Por que o diagnóstico demorou.** Um servidor de desenvolvimento rodando na máquina com o código
novo já gravava snapshots no formato novo **no banco compartilhado**, enquanto o checkout usado na
investigação estava um commit atrás, com o template velho. O sintoma — "o snapshot não tem o campo
que o template pede" — parecia guard de versão quebrado, quando era só uma árvore desatualizada
lendo snapshot de outra.

**Lição que fica:** um `.env` apontando para o banco compartilhado significa que *qualquer*
servidor local escreve em produção-de-fato. Ao investigar divergência entre snapshot e código,
confirme primeiro em que commit está o processo que **escreveu** o snapshot, não só o que o lê.

**`SNAPSHOT_VERSION` foi para 6 assim mesmo**, e continua valendo: `bf8065c` mudou o *significado*
de `pessoas_grupos_*` (passou a ser o pico histórico, não o número atual). Sem o bump, os snapshots
v5 seguiriam válidos e o dashboard mostraria a semântica antiga até o aquecimento seguinte. A regra
não muda: mexeu nos campos que o template consome do `dbf`, sobe `SNAPSHOT_VERSION` no mesmo commit.

---

## Ordem não determinística em listas ordenadas por contagem (2026-09-15)

**Sintoma:** dois downloads de `/api/caminho-comprador.csv` do mesmo lançamento, sem nenhum
dado novo no meio, saíam com as linhas em ordem diferente — e portanto pareciam ter mudado.
A tabela do Debriefing embaralhava pelo mesmo motivo a cada reinício do servidor.

**Causa:** `read_caminho_comprador` monta as linhas iterando `buyers`, que é um `set` de
e-mails. O Python aleatoriza o hash de string a cada processo, então a ordem de iteração muda.
Existia um `rows.sort(key=receita, reverse=True)`, mas ele **não é uma ordem total**: como o
preço do produto é o mesmo para quase todo mundo, a maioria das linhas empata em receita, e
`sort` é estável — ou seja, preserva entre os empatados exatamente a ordem arbitrária do set.

**Correção:** desempate explícito por e-mail, `rows.sort(key=lambda r: (-r["receita"], r["email"]))`.
Não muda nenhum valor, só torna a ordem reprodutível.

**Como apareceu:** os testes de caracterização (ver seção Testes) acusaram este reader como o
único divergente entre o código antes e depois de S10. A investigação mostrou que o código
**antigo** também divergia de si mesmo entre duas execuções — era defeito pré-existente, não
regressão da refatoração.

### O mesmo defeito em `read_hotmart_recompra`

`por_meio` (Boleto / Pix / Cartão / TMB, na recompra) é montado iterando um `set` de e-mails e
ordenado só por `qtd`. Com "Boleto" e "Pix" empatados em 1, os dois trocavam de posição entre
dois carregamentos da página. Corrigido com o mesmo desempate: `key=lambda x: (-x["qtd"], x["meio"])`.

### A regra

**Ordenação por contagem ou por valor precisa de critério de desempate.** `sorted`/`sort_values`
são estáveis, ou seja, preservam entre os empatados a ordem em que os itens chegaram — e quando
essa ordem veio de iterar um `set` ou um `dict` montado a partir de um `set`, ela muda a cada
processo, porque o Python aleatoriza o hash de string. Empate é a regra, não a exceção: preço
igual, contagem 1, mesma data.

Os dois casos foram achados pelos testes de caracterização, que comparam o resultado inteiro por
digest — nenhum apareceria numa conferência visual do dashboard.

---

## Bugs Corrigidos (2026-06-25)

### `SyntaxError` no parâmetro array da query TMB
**Causa:** A query `_query_tmb` em `frontend/database_reader.py` usava `ANY(:product_ids::int[])` com SQLAlchemy `text()`. O parser de parâmetros do SQLAlchemy não consegue separar `:product_ids` do `::int[]` que vem imediatamente após — o parâmetro permanecia literal no SQL e o PostgreSQL recebia `:product_ids::int[]` como texto puro, causando `SyntaxError`.

**Fix:** Substituído por f-string formatando os IDs diretamente no SQL: `ANY(ARRAY[{ids_literal}]::int[])`. Seguro contra injection porque cada valor passa por `int()` antes da interpolação. Padrão alinhado com a query equivalente do Hotmart.

**Localização:** à época `frontend/database_reader.py`, função `_query_tmb`; hoje `frontend/db_readers/sales.py`.

---

### Internal Server Error por falhas no banco de dados (sessão 2026-06-25 #2)

Múltiplos problemas encadeados que causavam 500 em todas as páginas.

#### 1. Supabase circuit breaker (ECIRCUITBREAKER)
**Causa:** Senha expirada no `.env` — o Supabase bloqueia o projeto após muitas falhas de autenticação consecutivas.  
**Fix:** Credenciais atualizadas para o formato Session Pooler (IPv4-compatível, recomendado para ambientes sem IPv6 nativo):
```
postgresql://postgres.<project_ref>:<senha>@aws-<n>-<region>.pooler.supabase.com:5432/postgres
```
O Session Pooler usa senha gerenciada separadamente do banco (não expira da mesma forma que a senha de banco direto).

#### 2. `SUPABASE_DB_URL` com formato inválido
**Causa:** A variável continha apenas o hostname (`db.xxx.supabase.co`) sem protocolo, usuário ou senha — provavelmente copiada errada de uma tela anterior.  
**Fix:** Substituída pela string completa de conexão do Session Pooler.

#### 3. `read_launch_config` sem tratamento de erro
**Causa:** A função não tinha `try/except` — qualquer falha de conexão ao banco operacional propagava como 500.  
**Fix:** Envolvida em `try/except Exception` retornando `{}` em caso de falha, com `logger.warning`.  
**Localização:** à época `frontend/database_reader.py`; hoje `frontend/db_readers/launches.py::read_launch_config`.

#### 4. `_fetch_all_data` propagando exceções pelo `asyncio.gather`
**Causa:** As corrotinas `f_vendas`, `f_hm`, `f_tmb`, `f_vc` não tinham `try/except` — uma falha em qualquer uma delas cancelava o gather inteiro e causava 500.  
**Fix:** Cada corrotina envolvida em `try/except Exception` retornando `None` em caso de falha.  
**Localização:** `frontend/core.py`, função `_fetch_all_data`.

#### 5. ETL escrevendo vendas no banco analytics (errado)
**Causa:** `etl/db.py` só tinha `get_engine()` (banco analytics). O `etl/import_vendas.py` usava essa engine, mas `hotmart_clean_oficial` e `tmb_clean_oficial` ficam no banco operacional (`SUPABASE_USERS_URL`).  
**Fix:** Adicionada `get_users_engine()` em `etl/db.py`; `import_vendas.py` alterado para usá-la.  
O ETL foi re-rodado para PBB-JUN-26: 536 Hotmart + 307 TMB importados corretamente.

#### 6. `hotmart_receita: nan` no PBB-JUN-26
**Causa:** A coluna `faturamento_liquido` estava NULL no banco (dados importados no banco errado antes da correção). `float(nan or 0.0)` em Python retorna `nan`, não `0.0` — o `or` não funciona com NaN.  
**Fix:** Fallback explícito com verificação `pd.isna()`:
```python
valor = _hm_val(row.get("faturamento_liquido")) \
     or _hm_val(row.get("valor_de_compra_sem_impostos")) \
     or 0.0
```
**Localização:** à época `frontend/database_reader.py`; hoje `frontend/db_readers/sales.py::read_vendas`.

#### 7. TMB retornando 0 vendas para PBB-JUN-26
**Causa:** Três problemas encadeados:

**a) Fallback lógica errada**  
`_query_tmb(use_ids=True)` retornava 0 porque os rows importados tinham `lancamento_id=NULL`. O fallback para produto+data só corria quando `tmb_ids` estava vazio — nunca rodava quando `tmb_ids=['29396']`.  
**Fix:** Fallback agora sempre corre quando a query retorna 0, independente de `tmb_ids`:
```python
# antes:
if tmb_df.empty and not tmb_ids:
    tmb_df = _query_tmb(False)
# depois:
if tmb_df.empty:
    tmb_df = _query_tmb(False)
```

**b) ETL não populava `lancamento_id` ao importar TMB**  
O `import_vendas.py` não lia o `launch_config` para obter o ID do produto TMB, deixando `lancamento_id=NULL` em todos os rows importados.  
**Fix:** Antes de importar cada lançamento, o script consulta `launch_config.tmb_produto_ids` e popula `lancamento_id` no DataFrame antes do `to_sql`.

**c) Parse de `tmb_produto_ids` (tipo `text[]` no PostgreSQL)**  
A coluna `tmb_produto_ids` é `text[]` no PostgreSQL — SQLAlchemy devolve uma `list` Python, não uma string. O parse original usava `str(val).split(',')` que transformava `['29396']` em `"['29396']"` e falhava no `int()`.  
**Fix:** Verificação de tipo antes do parse:
```python
ids_val = cfg_row[0]  # já é list Python
if isinstance(ids_val, list):
    first = ids_val[0] if ids_val else None
else:
    first = str(ids_val).strip().strip("[]'\"")
tmb_lancamento_id = int(first) if first else None
```

**Resultado final PBB-JUN-26:** `tmb_vendas=307`, `tmb_receita=R$568.101`, total `R$1.189.584`.

---

## Bugs Corrigidos (2026-06-24)

### `DatetimeFieldOverflow` no Hotmart e TMB
**Causa:** Campos de data (`data_da_transacao`, `confirmacao_do_pagamento`, `data_efetivado`) às vezes contêm Unix timestamps em milissegundos (ex: `"1781788622000"`). O `CASE WHEN` original só tratava `DD/MM/YYYY` e caía no `::timestamptz::date` genérico, que explode com valores numéricos grandes.

**Fix:** Adicionado WHEN intermediário com regex `^\d{10,13}$` que converte via `to_timestamp(valor_ms / 1000)::date` antes de tentar o cast genérico. Aplicado em 4 queries (2 Hotmart + 2 TMB).

---

## Desligamento do Typeform e sistema de pesquisa interno (2026-08-31)

A conta do Typeform foi cancelada; `frontend/db_readers/typeform.py` não chama mais nenhuma API do Typeform. Detalhes completos (schema das tabelas de backup, schema do sistema de pesquisa interno, o que mudou em cada função) estão em `docs/sistema/METODOLOGIA_EXTRACAO_DADOS.md` (seção 10). Resumo pro contexto de arquitetura:

- **`_get_typeform_forms()` / `_get_typeform_fields()`** — form_id→título agora vem das tabelas `typeform_forms`/`typeform_forms_2` (backup no Supabase); field_id→título da pergunta não tem backup e retorna vazio (gap conhecido, sem solução).
- **`_tf_source()`** — nova função que faz `UNION ALL` de `typeform_respostas` + `typeform_respostas_backup` + `typeform_respostas_backup_2`, deduplicado por `response_id`, com o filtro (form_id/período) empurrado pra dentro de cada branch do UNION por performance.
- **Sistema de pesquisa interno** (tabelas `formularios`/`perguntas`/`submissoes`/`respostas`, fora do `etl/`) — substituiu o Typeform a partir do `PBB-AGO-26`. Novas funções `_resolve_novo_sistema_formulario_ids`, `_read_novo_sistema_respostas`, `_read_novo_sistema_emails` convertem esse schema normalizado pro mesmo formato tabular que o Typeform produzia; as 4 funções públicas do módulo (`read_typeform_count`, `read_typeform`, `read_perfil_por_anuncio`, `read_pesquisa_engajamento`) combinam as duas fontes por e-mail, então cada lançamento usa a fonte certa automaticamente.
- **`etl/run_all.py`** — `typeform` removido do dict `scripts` de `run_api_mode`; `scheduler.py` não roda mais `etl_typeform.py` a cada 30 min.

**Renomeação da UI (2026-08-31):** como a página agora cobre Typeform (legado) + sistema de pesquisa interno, a nomenclatura visível trocou de "Typeform" para "Pesquisas" em todo o sistema — menu lateral, título da página, KPIs e textos em `index.html`, `criativos.html`, `vendas.html`, `comparativo-v1-v2`. A rota mudou de `/typeform` para `/pesquisas`; `/typeform` continua existindo como redirect 307 pra `/pesquisas` (link legado). O template foi renomeado de `typeform.html` para `pesquisas.html`. Nomes internos de código (arquivo `frontend/db_readers/typeform.py`, funções `read_typeform*`, tabelas `typeform_*`) **não** foram renomeados — são detalhes de implementação, não nomenclatura visível ao usuário.


## Calendário de lançamentos — fonte das datas-padrão (2026-09-14)

`frontend/calendar_parser.py::parse_calendar` extrai, por lançamento, o início/fim de cada etapa
(pré-quali, captação, depoimento, aulas, carrinho) direto do HTML do calendário. É o que alimenta
`_compute_launch_defaults` em `core.py`, ou seja, os valores que o wizard de lançamento sugere.

**Local canônico:** `analises/calendario/SISTEMA_CALENDARIO_2026.html`, junto dos CSVs de consulta
(`BASE_CONSULTA_CALENDARIO_2026*.csv`). Fica sob `analises/` de propósito — é a única pasta montada
como estático (`/analises`), então a mesma cópia serve o parser, os relatórios v1 (que linkam
`../calendario/...`) e o navegador. Os dois CSVs têm exceção no `.gitignore`, que por padrão
ignora `analises/**/*.csv`.

**Armadilha já materializada:** o parser varre apenas `analises/`. Enquanto o HTML esteve em
`frontend/static/calendario/` (pasta que **não** é montada), `parse_calendar` caiu em
`get_static_fallback_bounds()` — datas chumbadas no código — **sem logar nada**. As datas gerais
batiam, mas o fallback devolve `stages: {}`, então a Captação virava o range inteiro do lançamento
e pré-quali/carrinho/evento voltavam `None`. Corrigido em 2026-09-14: arquivo movido pro local
canônico e o fallback agora emite `logger.warning`.

**Duas fontes, papeis diferentes:** o HTML do calendário é o *planejado* (sugestão de datas);
`launch_config` (banco operacional) é o *configurado*. Quando divergirem, `launch_config` manda.
Na mesma correção o calendário ainda trazia o `PBB-AGO-26` sob o código antigo `PBB-OUT-26` com
datas de set/out; código e as 5 etapas foram realinhados com o `launch_config`.

**Segunda ocorrência do mesmo caminho quebrado (2026-09-16):** a correção acima trocou o caminho
lido por `calendar_parser.py` (sugestão de datas do wizard), mas `frontend/routes/analytics.py::
_load_calendario_assets` — usado só pela página `/calendario` pra reaproveitar o CSS/JS do HTML
legado (métricas, chips, tabelas) — continuou apontando pra `frontend/static/calendario/`, que já
não existia. O `try/except` engolia o erro e a página rodava sem esse CSS, silenciosamente, por 2
dias. Corrigido pro mesmo caminho canônico (`analises/calendario/`).

## Calendário — linha do tempo editável (vis-timeline, 2026-09-16)

A página `/calendario` ganhou uma visualização tipo Gantt em cima das duas tabelas existentes
(mantidas como estão): 1 linha por lançamento, 1 barra por etapa. Biblioteca
[vis-timeline](https://github.com/visjs/vis-timeline) (MIT/Apache-2.0, via CDN jsdelivr, sem
build step — mesmo padrão do Chart.js/Tabler Icons já usados no resto do sistema).

`frontend/services/calendario.py::_build_timeline` monta os dados: um `group` por lançamento, um
`item` por etapa. Etapa sem data vira um item "fantasma" (`ghost: true`, barra tracejada,
posicionada logo após a última etapa conhecida daquele lançamento) — arrastar/redimensionar
qualquer barra (real ou fantasma) chama `POST /api/launch-config/{code}` só com as 2 colunas
daquela etapa. Esse endpoint já existia pro wizard de Configurações, já faz upsert parcial (não
sobrescreve o resto da config) e já é role-guardado (`admin`/`analista`/`trafego`); a linha do
tempo não precisou de endpoint novo. Quem não tem esses papéis vê a régua em modo leitura (a
trava real é no servidor; o client só evita mostrar um arrastar que ia falhar).

Datas: o servidor manda `"YYYY-MM-DD"` (sem hora); o JS converte pra `Date` local explícito antes
de qualquer coisa (`localDateFromIso`), nunca deixa o parser de string do vis-timeline decidir —
uma string ISO sem timezone é interpretada como UTC meia-noite, que em fuso negativo (BR) vira o
dia anterior na hora local. Salvar recarrega a página inteira em vez de tentar sincronizar o
estado client-side — mais simples, e garante que status/métricas recalculados batem com o banco.

**Padrão visual + grade de mês (2026-09-16):** a página parou de depender do CSS/JS extraído do
HTML estático (`cal_styles`/`cal_script`, `_load_calendario_assets` em `analytics.py` — removido)
e passou a usar os tokens `--bs-*` como o resto do sistema, acompanhando tema. Ganhou também um
toggle "Linha do Tempo" / "Calendário": a segunda opção é uma grade de mês nova (navegação
anterior/próximo/hoje), só leitura — mostra as etapas já datadas num grid de dias; editar
continua sendo exclusivo da Linha do Tempo (arrastar uma barra). As duas visões e as duas tabelas
de baixo (Pipeline Completo / Agenda por Lançamento) reaproveitam o mesmo `cal.timeline_items`.

## Documentação como sistema (2026-09-14)

`docs/` deixou de ser uma pasta de arquivos soltos e virou um vault com roteamento, para que
nem pessoa nem agente precise ler tudo para achar uma coisa. Três camadas:

1. **Frontmatter em todo `.md`** — `titulo`, `area`, `status`, `atualizado` e `responde`
   (as perguntas que aquele doc responde). É o índice legivel por máquina: dá para varrer o
   vault inteiro lendo 14 linhas por arquivo (~570 linhas) em vez das ~6.700 linhas de conteúdo.
2. **Mapa de roteamento** em `docs/README.md`, uma tabela `pergunta -> doc` **gerada** a partir
   desses `responde`. Não editar à mão.
3. **Validador** `scripts/check_docs.py` — confere frontmatter obrigatório, nomes únicos no
   vault, wikilinks quebrados e se todo doc é alcançável a partir do README; com
   `--atualizar-mapa` regenera a tabela. Saída diferente de zero = build quebrado.

```bash
python scripts/check_docs.py --atualizar-mapa
```

**Restrições que isso impõe:** nome de arquivo único no vault (o `[[link]]` do Obsidian resolve
por nome, não por caminho) e sem `[`/`]` no nome — colchete quebra a sintaxe do wikilink; foi
por isso que `VERIFICACAO_GOOGLE_ADS_[PES-JAN-26].md` precisou ser renomeado.

As regras de onde escrever cada tipo de registro estão em `CLAUDE.md`, seção
*Documentation (`docs/`)* — fonte única; `AGENTS.md` só aponta pra lá, depois de as duas
cópias terem divergido.

## Egress do Supabase — cruzamento de telefone dos grupos otimizado (2026-09-14)

`frontend/db_readers/whatsapp_groups.py::_telefones_tabela` (usada em `_compradores_grupos`,
que alimenta `read_vendas_grupos_whatsapp` e `read_leads_x_whatsapp`) e `_fones_com_data`
(usada em `read_compradores_por_dia_grupo`) traziam a coluna `"NÚMERO"` **inteira** das tabelas
`[CODE]_API`/`[CODE]_VIP_API` (até ~410 mil linhas por lançamento) pro Python, só pra cruzar
contra uma lista pequena de compradores (Hotmart+TMB). O mesmo padrão estava duplicado em
`frontend/db_readers/caminho_comprador.py`.

**Impacto real:** via `pg_stat_statements`, essa única consulta (`SELECT DISTINCT "NÚMERO"
FROM "PI_AGO_26_API"`) respondia por ~655 milhões de linhas / ~13% de todo o egress do banco
analytics em 10 dias (04-14/09) — Shared Pooler Egress estourando os 250 GB inclusos do plano
Pro do Supabase, virando custo real de tráfego excedente (~US$0,09/GB acima do limite).

**Fix:** função SQL `norm_phone_brasil(v text)` (criada sob demanda via `_ensure_norm_phone_fn`,
espelha `_norm_phone()` do Python) permite filtrar o telefone **dentro do banco** — a consulta
vira `WHERE norm_phone_brasil("NÚMERO"::text) = ANY(:alvos)`, e só os telefones que batem com
compradores voltam pro Python, não a tabela inteira. Validado contra 3 lançamentos
(PI-AGO-26, PES-SET-26, PBB-AGO-26): resultado idêntico ao método antigo em todos.

**Armadilha do fix:** criar a função via `CREATE OR REPLACE FUNCTION` usando a mesma `conn`
de leitura do chamador (`engine.connect()`, sem commit explícito) a torna visível só dentro
daquela transação — ao fechar a conexão sem commit, o `CREATE FUNCTION` é desfeito e a próxima
conexão (nova transação) não encontra mais a função. `_ensure_norm_phone_fn()` usa
`engine.begin()` próprio (sempre commitado), independente da conexão de quem chama.

## Egress do Supabase — os cruzamentos que baixavam a base inteira (2026-09-14)

Continuação do item anterior. Um relatório técnico apontou ~1 TB de Shared Pooler Egress em
30 dias contra os 250 GB inclusos no plano Pro (US$ 0,09/GB de excedente). A causa é sempre o
mesmo padrão: **baixar a tabela inteira pro Python pra filtrar/agregar em pandas**. O
`pg_stat_statements` confirmou a atribuição antes de mexer em qualquer linha de código.

A regra que saiu disso: quando o resultado é uma contagem, uma soma ou um cruzamento contra
uma lista pequena, o filtro e o `GROUP BY` vão pro SQL. Só volta pro Python o que ele de fato
usa. Passar a lista de compradores como parâmetro é *upload*, que não é cobrado como egress.

### O que foi feito, por ordem de impacto

| Alvo | Egress estimado | O que mudou |
|---|---|---|
| `leads` (9 consultas) | ~288 GB (70%) | `COUNT(*)`/`GROUP BY` no servidor e cruzamento via `= ANY(:lista)` em `ads_meta`, `ads_google`, `typeform`, `sales`, `leads`, `attribution` |
| `respostas`/`submissoes` | ~38 GB | resultado compartilhado entre os quatro readers do Typeform |
| `meta`/`google`/`ga4_daily` | ~29 GB | GA4 agrega por `landing_page` no banco |
| `typeform_respostas` + backups | ~25 GB | índices de expressão + poda de colunas |
| telefones dos grupos WhatsApp | ~25 GB | `norm_phone_brasil()` (seção anterior) |

**`leads`** — `read_leads` agregava em pandas as 269 mil linhas do PI-AGO-26 a cada chamada;
agora o `GROUP BY utm_source, utm_medium, utm_campaign, dia` roda no servidor e só a linha dos
compradores desce. `read_ac_leads_for_attribution` ganhou filtro opcional por e-mail/telefone,
e o mapa `utm_term -> campanha` virou `read_term_campaign_map` (agregação no SQL, com
`ORDER BY termo, n DESC, campanha` replicando o desempate do `idxmax()` do pandas).

**Typeform** — as três tabelas `typeform_respostas*` (~990 mil linhas) caíam em *Seq Scan*
porque o filtro do frontend é `upper(coalesce(form_id, ''))` e os índices eram em `form_id`
puro. Nunca tinham sido analisadas também (`n_live_tup = 0` com 800 mil linhas reais), então o
planejador estimava 1.764 linhas onde vinham 95 mil. Índices de expressão + `ANALYZE`: 32.880
→ 1.889 buffers por chamada. **Isso explica o timeout intermitente de 30s** que derrubava a
seção do PI-AGO-26 — o sintoma aparecia como `SSL connection has been closed unexpectedly`,
não como timeout, o que despistou o diagnóstico por um bom tempo.

**Sistema de pesquisa novo** — o JOIN `submissoes × respostas × perguntas` (912 mil linhas
agregadas em ~27 mil jsonb) rodava duas vezes por lançamento a cada TTL, porque
`read_typeform`, `read_typeform_count`, `read_perfil_por_anuncio` e `read_pesquisa_engajamento`
chamavam o helper direto, cada um sob o cache do seu próprio reader.
`_novo_sistema_respostas_cached` guarda o resultado sob a chave do lançamento, que o
`_invalidate` do ETL já limpa.

**GA4** — `read_landing_pages_por_etapa` e `read_conversao_pagina_captura` baixavam uma linha
por dia por página e somavam em pandas. Etapa e versão são função pura do `landing_page`, então
a agregação subiu pro SQL: 7.511 → 81 linhas no PI-AGO-26, saída byte-idêntica.

`meta_ads_daily`/`google_ads_daily` ficaram como estão: os readers precisam da granularidade
por anúncio e por dia, e depois das correções acima essas consultas não aparecem mais entre as
15 maiores do `pg_stat_statements`.

### Como validar mudança de reader sem regressão

`pg_stat_statements` foi zerado em 14/09/26 (5,0 bilhões de linhas / 13,0 milhões de chamadas
acumuladas), então daqui pra frente ele mede só o código otimizado.

Duas armadilhas que custaram tempo e valem pra qualquer refatoração de leitura:

- **Comparar snapshots só de lançamentos ENCERRADOS.** Usar um lançamento ativo (PES-SET-26)
  polui o diff com centenas de falsos positivos, porque o ETL atualiza as métricas no meio da
  captura.
- **Diferença de 1 a 3 leads entre duas capturas é drift real, não regressão.** Um contato que
  se recadastra tem o `lancamento_codigo` sobrescrito, então ele sai da contagem de um
  lançamento e entra na de outro entre uma rodada e outra.

Quando o diff acusar diferença, isolar com `git stash` dos arquivos alterados e recapturar: se
a diferença persiste com o código antigo, é dado que mudou, não a refatoração.

**O método rigoroso (usado em S10).** `git stash` serve pra um caso pontual, mas a comparação
honesta é gerar o baseline com o código **antigo** e verificar com o **novo**, com poucos
minutos entre as duas — senão o drift de dado se mistura com o efeito da refatoração:

```bash
git worktree add "$TEMP/mmm-head" HEAD
cp .env pyproject.toml "$TEMP/mmm-head/"
cp tests/caracterizacao_util.py tests/test_caracterizacao_readers.py "$TEMP/mmm-head/tests/"

# baseline do código ANTIGO, gravado na árvore de trabalho
cd "$TEMP/mmm-head" && BASELINE_DIR="C:/dev/workspace-mmm/tests/baseline"   ATUALIZAR_BASELINE=1 python -m pytest tests/test_caracterizacao_readers.py -m caracterizacao

# verificação do código NOVO contra ele
cd C:/dev/workspace-mmm && python -m pytest tests/test_caracterizacao_readers.py -m caracterizacao
```

`BASELINE_DIR` existe exatamente pra isso. Em S10 esse método deu 74 de 76 readers idênticos
byte a byte, e as 2 divergências eram não determinismo pré-existente — que só ficou visível
porque o código antigo também divergia **de si mesmo** entre duas execuções.

## Histórico de lançamentos por lead — tags do Active Campaign (2026-09-14)

`leads` guarda só o cadastro **mais recente**: o upsert do ETL sobrescreve
`lancamento_codigo` quando o mesmo contato se cadastra de novo. Por isso "esse lead já
participou de lançamentos anteriores?" não tinha resposta no banco — é a pendência que estava
registrada em `projetos/` como "Anteriores por lançamento específico (dado perdido)".

O dado não estava perdido: está nas tags do Active Campaign. As tags de lançamento seguem
`[PRODUTO] [LANÇAMENTO] [CÓDIGO]` (ex: `[INSS] [LANÇAMENTO] [PI-AGO-26]`), são **cumulativas**
— o contato nunca perde a tag do lançamento anterior — e vão até abr/2024. Das 1.932 tags da
conta, 31 casam, uma por código do sistema. O marcador `[LANÇAMENTO]` é o que separa essas de
tags que só citam o código sem ser cadastro (ex: `[INSS][PDF][PI-AGO-26]`).

**Tabela `lead_lancamentos`** (`contact_id`, `lancamento_codigo`, `tagged_at`) materializa
esse histórico, uma linha por contato × lançamento.

**Coleta:** `etl_active_campaign.py` pede `include=contactTags.tag` de carona na paginação de
contatos que já existia. A alternativa — `/contacts?tagid=N` por tag — significaria varrer 284
mil contatos só no PI-AGO-26. As tags são gravadas **antes** do filtro de UTM, que descarta
contatos sem `utm_content`/`utm_term`: esse contato não entra em `leads`, mas a tag dele vale
pro histórico.

**Leitura:** `read_lancamentos_anteriores(code, emails=None)` devolve
`{email: [códigos anteriores]}` e `read_recorrencia_lancamento(code)` devolve o agregado
(novos vs recorrentes + de qual lançamento vieram). "Anterior" é pela data da tag
(`ant.tagged_at < atual.tagged_at`) — sem isso um lançamento posterior apareceria como passado.

**Backfill:** a conta tem 3,97 milhões de contatos e 3,43 milhões de pares contato × tag de
lançamento. Não existe atalho na API: `filters[tag]` em `/contactTags` é ignorado (devolve os
14,5 milhões de vínculos da conta) e o `limit` trava em 100 — varrer tudo são ~34 mil
requisições. **Não é preciso.** Quando um contato se cadastra num lançamento ele é
*atualizado*, então o ETL normal já o captura com a lista completa de tags: a cobertura dos
próximos lançamentos é automática. O backfill só serve pra leads de lançamentos passados que
não foram tocados desde então, e aí vale a passada direcionada por tag
(`/contacts?tagid=N&include=contactTags.tag`, ~4,3 mil requisições pros três lançamentos em
uso, ver `scratchpad/backfill_tags.py`).

## Atribuição por criativo — o sorteio do UTM e as vendas "sem veiculação" (2026-09-14)

Investigação a partir de um achado do harness de snapshot: o mesmo ADxxx aparecia com
campanha/source diferentes entre duas capturas seguidas, sem nada ter mudado no dado.

### O sorteio do UTM representante

`_sales_attribution` monta `por_criativo_utm[ad_code]` guardando **o primeiro comprador que
chegasse** — e a ordem vem do banco, sem `ORDER BY`. O mesmo ADxxx costuma ter UTMs diferentes
entre compradores (veiculou na Meta e no Google, ou a campanha mudou de nome no meio do
lançamento), então o representante mudava a cada recomputação do cache.

Não era instabilidade de exibição. Em `_creative_overview` o `campaign` do representante é
casado contra os nomes das campanhas do Google pra recuperar gasto/leads/cliques; quando o
sorteado era um UTM da Meta, nenhuma campanha casava, o gasto dava zero e o criativo era
**descartado do ranking principal**, caindo na seção 3. Atingia a maioria dos criativos: 37 de
57 ADs do PI-AGO-26, 27 de 52 do PES-MAI-26, 25 de 31 do PBB-AGO-26 têm mais de uma campanha.

Agora `por_criativo_utm` acumula todas as campanhas vistas (`campaigns`) e a união dos
lançamentos detectados; o representante exibido é a menor tupla
`(source, medium, campaign, content, term)`, estável independente da ordem do banco; e o
casamento com o Google usa **todas** as campanhas observadas do ADxxx — só pode somar
investimento, nunca remover. Recuperou R$ 9.881,75 no ranking do PBB-AGO-26.

### Pré-Qualificação aparecendo como "sem veiculação"

A seção 2 do `/criativos` é declaradamente só de Captação (`captacao_por_ad`), mas as vendas
vêm de qualquer etapa. Criativo que só veiculou na Pré-Qualificação caía na seção 3 sob um
texto que afirmava não haver investimento "nem em `meta_ads_daily`, nem em `google_ads_daily`"
— falso: o AD030 tem R$ 17.443 de gasto no próprio PI-AGO-26, só que na outra etapa.

Somar `preq_por_ad` ao ranking quebraria o sentido da seção 2, então o gasto de Pré-Quali é
levantado à parte (`preq_gasto`) e a seção 3 passa a mostrá-lo. Isso reclassificou 11 dos 14
casos do PI-AGO-26 (R$ 69.492 de faturamento, R$ 144.320 de investimento real) e zerou a seção
no PES-MAI-26.

### O que sobra: renomeação de campanha/anúncio

Os 3 casos restantes do PI-AGO-26 (R$ 165 mil, quase tudo em AD255 e AD267) **não** são lacuna
de ingestão: o gasto da Meta no período bate exatamente entre a API e o banco
(R$ 839.663,31 dos dois lados, 15/07–12/08). Também não é conta de anúncio faltando — das 25
contas visíveis ao token, as 20 fora do ETL não têm nenhum gasto de PI-AGO-26.

É **renomeação**. A campanha do AD255 existe na conta como
`[MA][cadastro][captação][específico][potencial][PI-AGO-26][27.07.26]`, criada em 21/07 e
renomeada depois (a data do lançamento foi empurrada de 20/07 pra 27/07). Os leads captados
antes da renomeação carregam o nome antigo no `utm_campaign`, o banco guarda o nome atual, e o
código deixa de casar. O mesmo vale pros anúncios — há ads no banco chamados
`AD302 - AD043 - Estúdio Brabo - PI-AGO-26`, com dois códigos no nome, sinal de renomeação.

**O conserto estrutural existe e não está funcionando:** `vk_ad_id` carrega o ID real do
anúncio, que não muda com rename. O mapeamento do ETL está correto (campo 10 = `vk_ad_id` na
conta do AC, confirmado via `/fields`), mas o campo está **0% preenchido** nos três lançamentos
ativos — 0 de 269.392 leads no PI-AGO-26, 0 de 70.312 no PBB-AGO-26, 0 de 56.254 no PES-SET-26.
Ou seja, o parâmetro não está chegando ao Active Campaign. Enquanto isso não for resolvido no
lado do tráfego (garantir a UTM padrão completa nos anúncios de captação), toda campanha
renomeada no meio do voo continua órfã das vendas captadas antes da renomeação.

## Eventos de tráfego — a juncão entre o diário e a métrica (2026-09-14)

Os diários (`docs/performance/lancamentos/[CODIGO]/MUDANCAS_*.md`) registram o que foi feito;
`meta_ads_daily`/`google_ads_daily` registram o que aconteceu. Eram dois mundos: o banco não
enxerga markdown, então cruzar ação com resultado dependia de parsear título de seção —
frágil, e inútil pro dashboard.

**`eventos_trafego`** (analytics, DDL em `etl/schema.sql`) é o índice legível por máquina desses
diários. O `.md` continua sendo a narrativa legível por gente; cada item vira uma linha com
`data`, `escopo`, `codigo`, `produto`, `expert`, `plataforma`, `tipo`, `regra` e `resultado`.

O `escopo` usa o mesmo vocabulário de `lancamento_codigo`, então os três mundos convivem:
`lancamento` (PES-SET-26), `perpetuo` (PERPETUO-PMQ-TJSP), `distribuicao` (DISTRIBUICAO-IVAN-NETO).

`scripts/eventos.py` cria a tabela e importa os diários:

```bash
python scripts/eventos.py --criar-tabela
python scripts/eventos.py --importar            # simula
python scripts/eventos.py --importar --aplicar
python scripts/eventos.py --listar PES-SET-26
```

Reimportar não duplica — a chave é `codigo + hash do título`. A data vem do título quando ele
traz `(DD/MM/AA)` (padrão do PES-SET-26) ou do cabeçalho `## YYYY-MM-DD` acima (padrão do
PBB-AGO-26 e PI-AGO-26); sem esse fallback, dois dos três diários ficavam de fora inteiros.

**O que isso destrava:** `JOIN` entre evento e métrica do dia. Exemplo real — o CPA do
PES-SET-26 subiu de R$ 6,74 (01/09) para R$ 12,20 (04/09), e o dia 04/09 concentra **17 ações**
de 7 tipos diferentes. Sem a tabela, associar uma coisa à outra exigia ler 240 KB de markdown.

**Armadilha do DDL:** o bloco tem ponto-e-vírgula dentro de comentário `--`; separar por `;`
sem tirar os comentários antes corta a tabela no meio.

### Como conferir se as correções de egress estão valendo

`python scripts/checar_egress.py` responde as duas perguntas com o mesmo dado:

1. **O deploy pegou?** Código antigo e novo geram formas de consulta inconfundíveis (o GA4
   antigo trazia linha por dia sem `GROUP BY`; o novo agrega no banco). O script checa cada par
   velho/novo — se as novas aparecem e as velhas não, o container está com o código novo.
2. **O egress caiu?** Compara o ritmo de linhas devolvidas com a linha de base do relatório
   técnico (4,93 bilhões de linhas em ~10 dias = ~493 milhões/dia). A meta, na proporção do
   relatório, é ~95 milhões de linhas/dia — o equivalente aos 250 GB inclusos.

Pré-requisito: rodar `SELECT pg_stat_statements_reset()` com o código novo já no ar e esperar
algumas horas. Abaixo de 1 hora o número não significa nada, e **leitura feita da máquina local
entra na mesma estatística** — rodar o dashboard ou o harness durante a janela contamina a
medição. O reset pós-deploy foi feito em 14/09/26.

### Anotações no gráfico (`/verba`)

`frontend/db_readers/eventos.py::read_eventos` lê a tabela e `eventos_por_dia` agrupa pela
chave `dd/mm`, que é exatamente o `data_str` usado no eixo X das curvas de verba. Em
`verba.html`, dia com ação registrada ganha ponto maior na cor do tipo
(`pointRadius`/`pointBackgroundColor` por índice, sem plugin extra), e o `afterBody` do tooltip
lista o que foi feito. Abaixo do gráfico, legenda de cores e a tabela completa em `<details>`.

**O formato da data é o acoplamento frágil:** o agrupamento usa `%d/%m` porque é o que a curva
usa. Se o eixo mudar de formato, as anotações somem em silêncio — nada quebra, só param de
aparecer. Conferir a interseção entre `labels` e as chaves de `evDia` ao mexer em qualquer um
dos dois.

`read_eventos` engole a exceção e devolve lista vazia se a tabela não existir — num ambiente
sem o schema novo o gráfico perde a anotação, mas a página continua de pé.

### Contexto medido por evento

`scripts/eventos.py --medir` preenche `contexto_metrica`: como gasto, conversões e CPA se
moveram numa janela em volta da data (padrão 3 dias antes × 3 dias a partir da data).

**É coluna separada de `resultado` de propósito.** `resultado` é texto escrito por gente — o
que aconteceu *por causa* da ação. `contexto_metrica` é só o que as métricas fizeram no
período; várias ações dividem o mesmo dia, e a janela captura tudo que mudou. Misturar as
duas daria a um número automatizado a autoridade de uma conclusão.

Duas proteções contra número enganoso: janela anterior com menos de R$ 500 ou 10 conversões
vira "sem base de comparação"; variação acima de 300% vira "mudança de patamar" — no início
do lançamento qualquer comparação com quase-zero produzia coisas como "+42570%".

Dos 193 eventos: 123 medidos, 20 mudança de patamar, 18 sem base, 32 sem dado no período.

`scripts/efeito_acao.py --itens` passou a ler a tabela em vez de parsear o markdown — com
isso funciona para distribuição e perpétuo do mesmo jeito que para lançamento.


## Dados das aulas no YouTube — duas fontes, uma tabela (2026-09-15)

A API do YouTube ainda não está conectada. Até lá os dados das aulas entram pelo export
manual do YouTube Studio, e o sistema aceita as duas fontes na mesma tabela.

**`etl/etl_youtube_csv.py`** lê `analises/[LAUNCH]/Youtube/Aula N/` — zip ou CSV solto, como
o Studio baixa — e grava com `fonte='manual'`. É ingestão manual: de propósito **não** está
no `run_all.py` nem no `scheduler.py`.

O export é o relatório da *transmissão ao vivo*: `liveViewership_*.csv` (curva minuto a
minuto) e `liveEngagements_*.csv` (totais por tipo). Ele resolve exatamente o campo que a
API **não** entrega para uma live encerrada — `peak_concurrent`, já que
`liveStreamingDetails.concurrentViewers` da Data API só existe enquanto a transmissão está
no ar. Ou seja: mesmo com a API conectada, o pico de simultâneos continuará vindo daqui.

Em compensação o export não tem views totais, watch time, retenção média, likes, comments,
live vs replay nem o `video_id` — isso é do `etl_youtube_analytics.py` (API) ou do export do
Modo avançado.

**Por isso o upsert de cada script só toca as colunas que ele realmente mede.** Os dois
escrevem na mesma linha de `youtube_aulas_stats` sem zerar o trabalho do outro. Enquanto não
há `video_id` real, o CSV usa a chave estável `manual-aula-N`, que satisfaz o
`UNIQUE(launch_code, video_id)` sem colidir com a linha que a API vai gravar depois.

**Tabelas (banco analytics):**

- `youtube_aulas_stats` — 1 linha por vídeo. Ganhou `viewers_fim`, `chat_msgs`, `reacoes` e
  `fonte` ('api' | 'manual').
- `youtube_live_curva` — 1 linha por (lançamento, aula, segundo). A série minuto a minuto não
  cabe numa tabela de 1 linha por vídeo, e a API não entrega essa curva de jeito nenhum.

`read_youtube_aulas` (`frontend/database_reader.py`) monta as duas coisas: os agregados mais
a curva já convertida para minutos, e calcula `retencao_live_pct` (fim/pico). Isso é **campo,
não property** — o snapshot do debriefing serializa com `dataclasses.asdict`, que ignora
properties, e a página leria `Undefined`.

A seção "Engajamento das Aulas — YouTube" do `/debriefing` renderiza a partir de qualquer uma
das fontes: mostra o que existe e omite o resto, com badge "CSV" no dado manual e sparkline
SVG da curva. Os 4 KPIs do rodapé trocam de métrica conforme a fonte (sem API: chat, reações
e retenção ao vivo no lugar de views e watch time).

**`video_id` e thumbnail.** Os IDs dos vídeos ficam em `config/launches/<launch>.yaml`
(bloco `youtube.aulas`), lidos por `_load_videos` — o mesmo ponto que o ETL da API usa, para
não haver duas listas. Com o ID real, o card renderiza a thumb oficial
(`i.ytimg.com/vi/<id>/maxresdefault.jpg`, com fallback `mqdefault` no `onerror`) e vira link
para o vídeo; sem ele, a linha usa a chave `manual-aula-N` e o card só não mostra thumb. A
thumb não passa por proxy nem por credencial, diferente das thumbnails de criativo do Drive.

### Página `/aulas-ao-vivo`

A seção do debriefing mostra o resumo; a página mostra a curva. `read_aulas_ao_vivo`
(`frontend/db_readers/youtube_aulas.py`) lê `youtube_live_curva` inteira e deriva minuto do
pico, média de simultâneos, régua de retenção a cada 15 min em % do pico, as janelas de maior
queda e a interação por pessoa.

**Ela não passa por `_fetch_all_data` de propósito.** A página depende só das duas tabelas de
YouTube; puxar Meta, Google e vendas junto custaria dezenas de segundos sem alimentar nada do
que ela mostra. Resultado: ~0,4s contra os ~22s do debriefing ao vivo.

Duas decisões de leitura que valem para qualquer lançamento: as janelas de queda só contam
**depois** do pico (antes dele a audiência ainda está entrando, e uma queda ali é ruído), e o
engajamento é dividido pelo pico de audiência — o volume bruto sempre premia a aula mais
cheia.
## Código de anúncio e imagem de criativo (15/09/26)

### Convenção de nome por lançamento

A chave de atribuição é `ADxxx` (`AD` + número), extraída do nome do anúncio. Lançamentos
anteriores à padronização não seguem isso — o BV-25 usa `AD-<iniciais><n>` com prefixo por
etapa (`ADC`/`ADR`/`ADL`) e `UGC`, e o regex corrente reconhecia 7 dos 237 nomes.

`src/ad_codes.py` centraliza a extração e resolve isso **por lançamento**
(`extract_ad_code(ad_name, launch_code)`): só um código listado em `_LEGACY_LAUNCHES` usa o
regex antigo, e para um `ADxxx` normal os dois caminhos devolvem o mesmo valor. A alternativa
— estender o regex global — mexeria na chave de atribuição de todos os lançamentos ativos,
que é justamente o que não se quer tocar.

A classificação de etapa tem o mesmo recorte: `_categorize_campaign` casa a tag entre
colchetes, e na convenção antiga o que está entre colchetes é o *objetivo* da campanha Meta
(`[CADASTRO]`), com a etapa solta no nome. O fallback sem colchetes só roda em lançamento
legado e só quando o match normal falha.

### De onde vem a imagem do criativo

`ad_creatives` guarda os **bytes** da thumb e da imagem cheia (migration 006); as URLs do CDN
do Facebook expiram, os bytes não. Serve por `/api/meta-creative/{launch}/{ad_code}/{kind}`.
Lançamento com `drive_folder_url` no `launch_config` usa as imagens do Drive; sem ele (caso do
BV-25), a origem é o próprio Meta.

O Meta expõe a imagem de quatro formas diferentes, e `_creative_image_url` tenta todas nesta
ordem: `image_url` direto, `object_story_spec` (`video_data`/`link_data`/`photo_data`),
`asset_feed_spec.videos[].thumbnail_url` (Advantage+/dynamic creative) e, por último,
`asset_feed_spec.images[].hash` — que não é URL e precisa ser resolvido em `/adimages`.

Dois cuidados que valem para qualquer backfill de imagem:

- **A URL de `/adimages` é assinada e de vida curta.** A resolução acontece em janelas de
  `_JANELA_HASHES` registros, imediatamente antes do download. Resolver a fila inteira antes
  faz o fim dela chegar expirado.
- **Uma linha só está completa com thumb E imagem.** A thumb do criativo é 64x64, pequena
  demais para a grade; o guard de reprocessamento considera as duas colunas, senão um
  criativo que falhou o download uma vez nunca mais é tentado.

## Egress — contagens de e-mail que desciam como lista (2026-09-15)

Medição pós-deploy (22h de janela limpa): o egress caiu 81%, de ~493 para ~92 milhões de
linhas/dia. Auditando o que sobrou, três consultas ainda seguiam o padrão que o relatório
apontou — **baixar uma lista para contar/cruzar em Python** —, somando 20,6 milhões de linhas
por dia (24% do total) para produzir três números e um teste de pertinência:

| Onde | Antes | Agora |
|---|---|---|
| `read_typeform_count` | baixava ~13 mil e-mails do Typeform + ~27 mil do sistema novo pra fazer `len()` de um set | `UNION` + `count` no servidor: **1 linha** |
| `read_pesquisa_engajamento` | mesma lista, e ainda devolvia como parâmetro `= ANY(:emails)` do cruzamento | os três números (respostas, base, cruzadas) numa consulta só: **1 linha** |
| `caminho_comprador.py` | baixava os ~13 mil respondentes do lançamento pra testar `email in respondentes` contra ~2,5 mil compradores | `AND LOWER(email) = ANY(:buyers)` |

O caso do `caminho_comprador` é instrutivo: o telefone nesse mesmo arquivo já tinha sido
corrigido em 14/09, e o e-mail dez linhas abaixo passou batido. Ao corrigir um cruzamento num
arquivo, vale varrer o resto dele.

Detalhe que precisa ser preservado no `read_typeform_count`: o `if not emails` que decidia o
fallback por data olhava a contagem **crua** do Typeform, não a dos e-mails válidos. Por isso a
consulta devolve duas contagens (`bruto` e o total unido) em vez de só o total.

Validado com o harness de snapshot contra PI-AGO-26, PBB-AGO-26 e PES-MAI-26: zero diferença.

### Pendência: `read_typeform` do PI-AGO-26 falha ~50% das vezes

O `SELECT *` com a coluna `answers` sobre a união deduplicada leva ~33s no PI-AGO-26, contra o
`statement_timeout` de 30s (`src/db_engine.py`) — duas execuções seguidas deram uma OK e uma
`DatabaseError`. Quando passa, os valores batem (`total_tf=47140`, `tf_leads_crm=39314`). É a
mesma consulta que lidera o egress restante (6,5 milhões de linhas em 777 chamadas), então vale
atacar as duas coisas juntas.

## Saúde do Lançamento — nota 0-100 no Debriefing (2026-09-15/16)

Nova seção no topo do `/debriefing`, acima de Matrículas: uma nota 0-100 resumindo o
lançamento. Primeira versão (15/09) reaproveitou o score que já existia no `/insights`
(4 fatores de 25 pts: ROAS, rastreabilidade UTM, CPL médio Meta, % de ads com venda) — só
precisou mover o cálculo pra dentro de `_compute_debriefing_ctx()`
(`frontend/services/debriefing.py`), porque o `/insights` calcula inline no template a partir de
objetos Python (`meta`/`google`/`sales_attr`) que o Debriefing não tem disponíveis quando lê do
snapshot pré-computado (`debriefing_snapshot`, JSONB) — só o dict `dbf`, serializável.

No dia seguinte o usuário trouxe uma proposta própria de pesos ("Saúde do Lançamento 2.0"), que
substituiu os 4 fatores por 7: ROAS (50 pts), Meta de Faturamento (15), CAC/Custo por Venda (10),
Conversão do Funil (10), Eficiência dos Anúncios (5), Volume de Vendas vs lançamento anterior (5)
e Rastreabilidade (5). "Meta de Faturamento" não existia em lugar nenhum do sistema — nova coluna
`launch_config.meta_faturamento` (`src/db/migrations/008_meta_faturamento.sql`) + campo no wizard
de Configurações (pane Vendas). Quando a meta não está cadastrada, ou quando não há lançamento
anterior do mesmo produto (fator Volume), o peso desse fator é redistribuído proporcionalmente
entre os que têm dado — não contar como 0, porque não ter a referência não é "lançamento ruim".

Dois cortes de nota são palpite documentado, não regra validada — ajustar se o usuário achar
errado: CAC pontua cheio em custo-por-venda R$0 e zero a partir do ticket médio (ponto de
empate); Conversão do Funil pontua cheio a partir de 3% leads→vendas.

**Mobile (16/09):** abaixo de 640px, `.dbf-saude` era `flex-wrap` mas continuava `flex-direction:
row` — a nota (bloco estreito) só ocupava parte da primeira linha do wrap, e o primeiro item
(ROAS) entrava na MESMA linha ao lado dela em vez de abaixo; os itens seguintes empilhavam por
baixo dos dois, deixando a nota "flutuando" no meio da pilha em vez de no topo. Fix: nesse
breakpoint `.dbf-saude` vira `flex-direction: column` — nota em cima, ocupando a largura toda,
itens empilhados abaixo. A legenda ("Nota de 0 a 100 combinando 7 fatores...") ganhou `<strong>`
nos nomes dos 7 fatores e em "fora da nota".

## Wizard de Configurações — o que era gravado, e o que a página via (2026-09-16)

Usuário salvou a verba de Captação do PES-SET-26 no wizard e não viu o número no `/debriefing`.
O dado estava gravado desde o primeiro clique; o que faltava era tudo o que acontece **depois**
do `INSERT`. Cinco defeitos distintos no caminho `wizard → launch_config → página`, todos
corrigidos de uma vez.

### 1. `/debriefing` não lê `launch_config` — lê o snapshot

`save_launch_config` invalidava o cache em memória (`_invalidate` + `reset_launches_cache`), e
isso basta pro `/verba`, `/funil` e companhia. Mas o `/debriefing` renderiza a partir de
`debriefing_snapshot`, uma linha JSONB reescrita só pelo aquecimento periódico — nada disparava
a remontagem dela ao salvar. Config nova só aparecia na rodada seguinte: **até
`PRE_WARM_INTERVAL_MIN` minutos (padrão 30)**. No incidente foram 9 minutos, e o usuário olhou
dentro deles.

`POST /api/launch-config/{code}` agora chama `schedule_snapshot_only(launch, launches, force=True)`
depois de invalidar o cache. Medido em produção: save 13:19:35 → snapshot regravado 13:20:46 (71s,
cache frio de propósito — a remontagem vem logo após o `_invalidate`).

O `force` é o detalhe que importa: `schedule_snapshot_only` tem um guard de "um por código por
vez", e sem ele um save que caísse no meio de uma montagem já em curso seria simplesmente
descartado — e essa montagem, que leu a config **antiga**, gravaria o estado velho por cima. Com
`force=True` o código entra em `_SNAPSHOT_REFAZER` e a remontagem é reagendada quando a atual
termina.

### 2. O save era overwrite da linha inteira, não patch

O `INSERT ... ON CONFLICT DO UPDATE` tinha a lista de colunas escrita à mão, e toda coluna
ausente do payload do wizard era reescrita com o valor default. `bonus_oferta` é o caso
materializado: o JS nunca mandou esse campo, então **todo salvamento do wizard zerava a coluna
pra `[]`**. Qualquer coluna nova teria o mesmo destino até alguém lembrar de acrescentá-la no JS.

Agora existe `_CONFIG_COLUNAS`, um dict `coluna -> conversor` que é ao mesmo tempo a allowlist de
escrita e a especificação de tipo. `save_launch_config` monta o SQL só com as colunas presentes em
`config`: o que não for mandado fica como está. Limpar um campo continua funcionando, porque o
wizard manda `""` explicitamente (e `""` vira `NULL`), o que é diferente de não mandar a chave.

Os nomes de coluna do SQL saem sempre de `_CONFIG_COLUNAS`, nunca do payload — a montagem por
f-string não tem como carregar entrada do usuário.

### 3. Número inválido virava `NULL` em silêncio

`_or_int`/`_or_zero` capturavam `ValueError` e devolviam `None`. Digitar um valor que não
converte gravava `NULL` e respondia `{"ok": true}` — o botão dizia "✓ Salvo!" e o campo voltava
vazio depois. Os conversores agora levantam `ConfigInvalida`, e a rota devolve
`{"ok": false, "error": ...}` com o nome do campo.

Isso cobre o cliente não-navegador. No navegador o problema é anterior: num `<input type=number>`,
texto que o browser não consegue parsear (`540.000` digitado no teclado brasileiro) nem chega ao
servidor — `.value` devolve `""`, indistinguível de campo apagado. O único lugar onde esse estado
ainda existe é `validity.badInput`, então `lcSave` checa os inputs numéricos do modal antes de
montar o payload e recusa com a lista de campos.

### 4. Escrita de config sem checagem de papel

`ROUTE_PERMISSIONS` (`frontend/auth.py`) casa **path exato** e só lista páginas, então `/api/*`
passava com qualquer sessão válida: um usuário `leitura` reescrevia a config de qualquer
lançamento. `POST /api/launch-config/{code}` agora exige `admin`/`analista`/`trafego`, o mesmo
conjunto de `POST /api/lancamentos`. Continua sendo um guard por rota, não por default — a
inversão ("negar por default") segue no backlog.

### 5. A etapa "WhatsApp" não existia no wizard

`/debriefing` e `/verba` casam a etapa de orçamento pelo **nome exato** — em
`routes/analytics.py`, literalmente `et.get("nome") == "WhatsApp"`. Mas as etapas padrão do wizard
eram só Lembrete, Depoimento, Aulas no Ar, Replay e Matrículas Abertas. Sem ninguém criar uma
etapa custom grafada exatamente assim, o previsto do WhatsApp era sempre R$ 0 — no PES-SET-26,
contra R$ 8.638,51 de gasto real, que entrava no realizado do Remarketing sem previsto
correspondente.

"WhatsApp" virou etapa padrão. Junto foi corrigido o `lcPopulateEtapas`, que só renderizava as
etapas padrão quando o lançamento **não tinha nenhuma salva** — em config existente, uma etapa
padrão nova nunca apareceria. Agora as padrão entram sempre, e as customizadas do usuário são
acrescentadas depois, sem duplicar. Efeito colateral aceito: etapa padrão removida à mão volta na
próxima abertura, com total 0.

**Os nomes das etapas padrão são chave, não rótulo.** Renomear "WhatsApp" ou "Lembrete" no wizard
zera o previsto da seção correspondente do debriefing, sem erro nenhum.

## Preview de landing page via thum.io (2026-09-16)

"Landing Pages que Mais Converteram" (Pré-Qualificação e Captação, `/debriefing`) ganhou uma
coluna de miniatura da página. Sem infra própria: um `<img>` aponta direto pra
`https://image.thum.io/get/width/500/crop/340/viewportWidth/1440/noanimate/<url-completa-da-lp>` —
serviço público de screenshot, sem chave de API, sem custo. A URL completa é montada com o mesmo
`lp_base_url` já usado pro link da página (`lp.mateusandrade.com.br` pra INSS,
`lp.braboconcursos.com.br` pros demais produtos) — o GA4 só guarda o caminho, não o host.

Testado direto contra o thum.io (fora do preview reduzido do card): devolve JPEG real da página,
~5-17KB, HTTP 200. Sem cache próprio — cada carregamento da página pode disparar uma renderização
nova do lado do thum.io se o cache deles tiver expirado (comportamento deles, fora do nosso
controle). Se o volume de tráfego no debriefing crescer e isso ficar lento/instável, a alternativa
é migrar pra captura própria via Playwright no servidor (mesmo padrão de
`ad_creatives.thumb_data`/`image_data`, ver "Código de anúncio e imagem de criativo" acima) — mais
robusto e sem depender de terceiro, mas exige instalar o binário do Chromium (~300MB) e uma
camada de cache/armazenamento próprias. Decisão registrada 16/09/26: optou-se pelo terceiro
primeiro, por ser zero-infra e já resolver o pedido.

**Ajuste 16/09/26 (mesmo dia):** o card era 64×44px e `width/300/crop/200` sem `viewportWidth` —
o thum.io renderizava a versão responsiva/estreita da LP, então duas variantes diferentes da
mesma página ficavam com preview quase idêntico (dá pra ver isso comparando dois `crop` de LPs
diferentes sem o parâmetro: ambos ficam "escuros e genéricos"). Corrigido com `viewportWidth/1440`
(força o navegador headless do thum.io a renderizar em layout desktop) e ~40% de aumento em
`width`/`crop` e no tamanho exibido do `<img>` (64×44 → 90×62px) — pedido do usuário: "não da para
mostrar a diferença entre uma pagina e outra".

## `SNAPSHOT_VERSION`: por que virou teste (2026-09-16)

Quatro quebras do `/debriefing` em dois dias, todas com a mesma causa: o `dbf` ganhou campo, o
template passou a pedir esse campo, e `SNAPSHOT_VERSION` não subiu junto. O snapshot já gravado
passava no guard de versão, o template pedia o que aquele payload não tinha, a página devolvia 500.

| versão | o que mudou no `dbf` |
|---|---|
| 5 → 6 | `total_grupos_normais/vip` e os `prev_` correspondentes (entre 04 e 15/09) |
| 6 → 7 | Saúde do Lançamento 2.0 — `saude_pesos`, `saude_score_meta_fat/cac/conv` |
| 7 → 8 | Detalhamento de Oferta — `oferta_parcela_cartao`, `oferta_parcela_boleto` |
| 8 → 9 | `oferta_preco_parcelado` |
| 9 → 10 | mesma forma, valores diferentes: previsto de Remarketing passou a incluir o WhatsApp |

O aviso estava escrito em `frontend/db_readers/debriefing_snapshot.py` desde a primeira vez, com
todas as letras, dizendo que subir o número não é opcional. **Quatro vezes não bastou.** Um
comentário não roda.

### O teste que cobra

`tests/test_dbf_contrato.py` lê por AST as chaves do `return` de `_compute_debriefing_ctx` e compara
com `tests/baseline/dbf_manifesto.json`. Mudou a forma sem o bump, falha dizendo qual campo entrou
ou saiu e para qual número subir. Não executa o produtor — precisaria de banco e leva ~1 min por
lançamento, e o que interessa aqui é a *forma*, que é estática. Roda em 0,06s, sem banco, na faixa
rápida do CI.

Só `ATUALIZAR_MANIFESTO=1` escreve o manifesto. Um teste que regrava o próprio gabarito numa rodada
normal esconde exatamente o que ele existe pra denunciar — e, diferente do `ATUALIZAR_BASELINE=1`,
aqui não há risco de escopar e perder o resto: é um arquivo só, reescrito inteiro.

### O outro lado: campo que ninguém produz

O segundo teste do arquivo cobra que todo `dbf.x` lido nos templates exista no produtor. Esse
defeito é mais silencioso que o 500: com guarda no template (`{% if dbf.x %}`), o campo ausente não
quebra nada — só cai no ramo do "não configurado" para sempre.

Foi o caso de `oferta_preco_parcelado`, achado por esse teste na primeira execução: o template lia,
ninguém produzia, e a linha "Preço parcelado" do Detalhamento de Oferta mostrava "não configurado"
mesmo com `produto_preco_parcelado` preenchido no wizard. Corrigido, e é o que levou a versão a 9.

### Previsto e realizado tinham que somar as mesmas coisas (2026-09-16)

Uma constante respondendo a duas perguntas diferentes. `_REMARKETING_SUBETAPAS`
(`Lembrete`, `Depoimento`, `Aulas no Ar`, `Replay`, `Matrículas Abertas`) diz **quais chaves de
`por_etapa` do Meta/Google compõem o gasto** de Remarketing — o WhatsApp não está lá, e com razão:
não é campanha de mídia, o gasto dele entra separado por `wa_gasto`. Mas a mesma lista era usada
para decidir **quais etapas do wizard compõem o orçamento**, e aí o WhatsApp precisa entrar, porque
é uma etapa como as outras.

Resultado: `get_etapa` somava o gasto do WhatsApp no realizado, `_previsto_por_etapa` não somava a
verba dele no previsto. No PI-AGO-26, com R$ 115.024 cadastrados, o Remarketing aparecia como
**previsto R$ 35.076 contra realizado R$ 69.211, ▲97,3%** — um estouro de orçamento que não existia.
Com o WhatsApp no previsto: R$ 150.100, **▼53,9%**, sobra. O Total Investido também mudava de
▲0,7% para ▼6,6%.

A linha do WhatsApp no detalhamento tinha `"previsto": 0.0` cravado, então mostrava "—" mesmo com
verba cadastrada — passa a ler do wizard como as outras, e aparece também quando há verba sem gasto
(orçamento provisionado e não usado é informação, não ausência de dado).

Separado em `_REMARKETING_ETAPAS_ORCAMENTO`. **O sintoma dessa classe de bug é a variação com o
sinal trocado** — quando previsto e realizado não somam o mesmo conjunto, o número não fica só
impreciso, ele inverte a conclusão.

### Resumo do que protege o quê

| risco | quem protege |
|---|---|
| campo novo no `dbf` sem bump de versão | `test_dbf_contrato.py` |
| template lendo campo que ninguém produz | `test_dbf_contrato.py` |
| processo com código velho rebaixando o snapshot | guard de monotonicidade no `write_snapshot` |
| não saber quem gravou um snapshot | `_writer` (`hostname#pid`) no payload |
| processo velho servindo template novo | nada automático — **reinicie o servidor** |

## Mobile: scroll horizontal em vez de esconder colunas (2026-09-16)

`/debriefing` tinha duas formas distintas de "resolver" tabela larga no celular, e as duas
perdiam dado: "Detalhamento de Tráfego" dava `display:none` em Previsto/Realizado/Var/Lanç. Ant.
abaixo de 640px (`.alloc-row-budget`); "Dia a Dia de Captação" e a tabela de "Ebook → Compra" não
tinham wrapper de scroll nenhum, deixavam o navegador encolher as colunas até quebrar "R$" numa
linha e o valor na outra.

Fix: toda tabela larga vira `overflow-x:auto` num wrapper próprio (`.alloc-scroll`,
`.day-table-wrap`, ou o já existente `.table-wrap`), mantendo as colunas todas, em qualquer
largura — rola em vez de esconder. `.dbf-table td` ganhou `white-space:nowrap` (o `th` já tinha),
pra travar o valor numa linha só em vez de reflow.

**A pegadinha:** `overflow-x:auto` no wrapper não bastava. `.cmp-curr`/`.cmp-prev` (os itens do
grid `.cmp-grid`) e os `<div>` de `.day-tables-grid` são itens de grid/flex, que por padrão têm
`min-width: auto` — respeitam o tamanho mínimo intrínseco do conteúdo em vez de encolher pra
largura disponível. Sem `min-width: 0` explícito nesses itens, o wrapper de scroll nunca
"sentia" falta de espaço (nunca ficava menor que o próprio conteúdo) e era a **página inteira**
que ganhava barra de rolagem horizontal, não o card. Medido via
`el.scrollWidth > el.clientWidth` no DevTools/Playwright: antes do `min-width:0`, todo
`.alloc-scroll` reportava `scrollWidth === clientWidth` (não rolava nada, só empurrava a página);
depois, `scrollWidth` (622px) > `clientWidth` (315px) e a página ficou sem overflow.

## Accordion: título em 2 linhas, ícone maior — mudança única, ~30 páginas (2026-09-16)

Usuário mandou print do Debriefing no celular ("Detalhamento por Dia de Captação" com o título
quebrando em parágrafo e cada badge — `PI-AGO-26`, `PI-ABR-26`, `Captação` — pulando pra uma linha
própria, bagunçado) + um desenho à mão do layout que queria: ícone maior, título numa linha,
badges na linha de baixo, sem a palavra "vs" entre lançamentos.

`bsInitAccordion()` (`base.html`) é o motor genérico de accordion — reconhece qualquer
`.section`/`.dbf-section-title` com esse bloco, sem precisar tocar no template de cada página
(comentário original: "generalizado pra qualquer página que já usa o bloco .section/.section-
title"). Isso significa que o problema (e o fix) não é do Debriefing: é de **toda** página que
usa esse padrão — confirmado em ~30 arquivos via grep. A causa raiz é a mesma em qualquer uma:
ícone + texto + badges (o "badge de tag" automático que essa mesma função injeta por
palavra-chave do título, e badges que a própria página já colocava soltas ali, como o
`.dbf-launch-badge` do Debriefing) brigavam pelo mesmo `display:flex; flex-wrap:wrap` — sem
espaço, cada peça quebrava pra uma linha, cada uma na sua, imprevisível.

**Fix, todo dentro de `bsInitAccordion()` + CSS de `.section-title`/`.dbf-section-title`:**
- O ícone (sempre o 1º filho, se houver — nunca é o chevron, que entra por último) sai do bloco
  de texto e vira filho direto do título, sozinho — CSS aumenta pra 26px (~altura de 2 linhas),
  alinhado ao centro do bloco ao lado.
- O resto do conteúdo original — que antes ia tudo pra um `<span class="bs-sec-orig">` só — agora
  é separado nó a nó: texto vai pra `.bs-sec-orig` (linha 1), qualquer **elemento** (badge que a
  página já tinha, ex. `.dbf-launch-badge`) vai pra um novo `<div class="bs-sec-badges">` (linha
  2). A tag automática (`.bs-sec-tag`) entra nesse mesmo `.bs-sec-badges`. Um `.bs-sec-body`
  (`display:flex; flex-wrap:wrap`) envolve as duas linhas — no desktop, com espaço de sobra, as
  duas ainda colam numa linha só (nada muda visualmente); no celular (`max-width:640px`) vira
  `flex-direction:column` e força as duas linhas separadas.
- `.bs-sec-badges` fica `display:none` quando vazio (sem tag automática nem badge da página) —
  `updateBadgesVisibility()`, chamada toda vez que `applyCustom()` roda (inclusive quando o
  usuário edita a tag manualmente no painel "Seções").
- Chevron sempre `position:absolute` no canto (nunca mais dentro do flex) — só existia essa regra
  antes pra celular (`max-width:520px`); virou permanente, então o comportamento é o mesmo em
  qualquer largura, sem depender de breakpoint pra não quebrar.

**Testado nos dois formatos que existem** (a maioria das ~30 páginas não tem ícone no título, só
número + texto — ex. Funil, Verba; um grupo menor tem, ex. Debriefing, Comparativo): Debriefing
(ícone + 2 badges), Funil (sem ícone, com 1 badge), Comparativo (ícone + 1 badge) — mobile (390px)
e desktop (1280px), accordion recolher/expandir e o painel "Seções" continuam funcionando.

De quebra: as duas badges de lançamento do Debriefing (`.dbf-launch-badge`) perderam o "vs" —
"vs PI-ABR-26" virou só "PI-ABR-26" — pedido explícito junto com o desenho.

## Título sem "Captação/Pré-Quali/Meta/Google/YouTube/TikTok" no texto — vira badge (2026-09-16)

Continuação do fix acima: usuário pediu pra tirar a palavra da etapa (Captação/Pré-Qualificação)
e da plataforma (Meta/Google/YouTube/TikTok) do texto de ~19 títulos do Debriefing — a etapa já
tinha tag automática, a plataforma não tinha nada. Sequência final pedida: **etapa → plataforma →
lançamento atual → lançamento anterior**, todas as badges do mesmo tamanho.

**A pegadinha:** a tag automática (`detectTag()`, `bsInitAccordion()`) funciona escaneando
palavra-chave **no texto visível** do título (`title.textContent`). Tirar a palavra do texto
quebra a própria detecção que mostra a tag — sem "Captação" no texto, nada dispara o badge
"Captação". Resolvido com um atributo `data-tag="Captação"` no `<div class="dbf-section-title">`,
que `initAccordion()` agora lê **antes** de cair pra `detectTag(label)`:
```js
var forcedTag = title.getAttribute('data-tag');
return { ..., autoTag: forcedTag || detectTag(label) };
```
Só os ~19 títulos que tiveram a palavra removida ganharam `data-tag` explícito; o resto do
sistema (as outras ~29 páginas) continua 100% por detecção automática, sem tocar em nada.

**Plataforma vira badge** — `plat_badge(nome)` (`debriefing/_macros.html`), logo + nome, mesmo
tamanho de `.dbf-launch-badge`/`.bs-sec-tag` (11px/700/2px 8px/20px, unificado nos três pro pedido
"mesmo tamanho das tag de lançamento"). Usado só nos títulos que tinham a palavra da plataforma
solta no texto (ex.: "Top 5 Melhores Ads — Captação (Meta)" → "Top 5 Melhores Ads" +
`plat_badge("Meta")`). As variantes por plataforma de "Top 5 Melhores Ads" trocaram o ícone
principal de marca (`ti-brand-meta`/`ti-brand-youtube`) por `ti-trophy` genérico — mesmo ícone da
variante combinada (Meta+Google), pra não ter 3 ícones diferentes pra 3 recortes do mesmo
ranking.

**Ordem das badges já saía certa sem esforço extra:** `bsInitAccordion()` insere a tag automática
**antes** do loop que aspira o resto do conteúdo original do título pra `.bs-sec-badges` — como
cada template já escreve `{{ plat_badge(...) }}` antes de `.dbf-launch-badge` (atual) antes de
`.dbf-launch-badge.prev` (anterior), a ordem final bate exatamente com "etapa → plataforma →
lançamento → lançamento anterior" sem precisar de nenhuma lógica de reordenação.

## plat_badge() migrou pra fora do Debriefing + extensão pra 11 páginas (2026-09-16/17)

`plat_badge()` e `_PLAT_BADGE` saíram de `debriefing/_macros.html` pra `_macros_platform.html`
(raiz de `templates/`, sem `{% extends %}`, mesmo padrão de `_macros_verba.html`) — pedido do
usuário de estender a limpeza de título pras outras páginas, e não fazia sentido um macro
genérico morar num caminho com "debriefing". CSS de `.dbf-plat-badge` foi atrás, de
`debriefing.html` pra `base.html` (é usado em páginas que não são o Debriefing agora). Depois,
outra sessão trocou o ícone branco simples por um círculo branco com o ícone colorido dentro
(`.dbf-plat-badge-dot`) e acrescentou WhatsApp/Active Campaign ao dicionário — evolução
coerente, não precisou de ajuste.

Mesma limpeza do Debriefing (tirar "Captação"/"Pré-Qualificação"/"Meta Ads"/"Google
Ads"/"YouTube"/"TikTok" do texto do título, badge no lugar) estendida pra comparativo,
criativos, dashboard, distribuição, funil, google, google-audiences, meta, perpétuo e
pré-qualificação. Três armadilhas que apareceram só fora do Debriefing:

1. **"Meta" é ambíguo em português.** `meta.html` tem "Distribuição de Verba Meta Captação vs
   Meta Estratégica" — aqui "Meta" é a palavra comum (meta estratégica de alocação de verba: 70%
   Principal / 25% Potencial / 5% Reels), não a plataforma. Trocado por badge teria mudado o
   sentido da frase. Deixado sem tocar.
2. **Página 100% de uma plataforma/etapa não precisa do badge redundante.** `meta.html`,
   `google.html`, `meta-audiences`, `google-audiences` já têm "Meta Ads"/"Google Ads" no `<h1>`
   da página — todo badge de plataforma em toda seção seria ruído. Só a etapa (`Captação`) virou
   tag onde fazia sentido; a palavra da plataforma nem foi tocada nesses 4 arquivos. Mesma lógica
   em `pre_qualificacao.html` (h1 já diz "Pré-Qualificação") — a palavra saiu do texto, mas sem
   tag (senão toda seção da página ganharia a mesma tag óbvia).
3. **`funil.html` já tinha um sistema de badge de plataforma próprio** (SVG hardcoded,
   `.platform-badge`/`.section-title.platform-meta`/`.platform-google`, de uma feature anterior a
   este trabalho) — mantido como está (não fazia sentido ter dois sistemas de badge na mesma
   página); só a palavra duplicada ("Meta Ads -", "Google Ads -") saiu do texto do título, que
   antes repetia o que o badge já mostrava.

Testado: as 11 rotas devolvem 200 e a inspeção visual (Playwright, funil/pré-qualificação/
captação) confirma ordem e tamanho consistentes com o Debriefing.
