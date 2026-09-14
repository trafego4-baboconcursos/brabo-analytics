---
titulo: "Arquitetura do Brabo Analytics — 2026-09-14"
area: sistema
status: vigente
atualizado: 2026-09-14
responde:
  - "como o sistema funciona por dentro"
  - "fluxo de dados"
  - "responsabilidade de cada arquivo"
  - "onde fica o calendario e por que"
  - "cache, scheduler, seguranca"
relacionados:
  - "[[METODOLOGIA_EXTRACAO_DADOS]]"
  - "[[DESIGN_SYSTEM]]"
---

# Arquitetura do Brabo Analytics — 2026-09-14

<!-- SUMARIO:INICIO -->

> [!abstract]- Sumario - 12 itens (gerado por `scripts/check_docs.py --atualizar-mapa`)
>
>
> **Estrutura de Arquivos**
>
>
> **God Module Split — Progresso (concluído em 2026-07-01)**
>
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
> **Testes (90 testes, 0 dependência de DB)**
>
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
> **Documentação como sistema (2026-09-14)**
>
>
> **Egress do Supabase — cruzamento de telefone dos grupos otimizado (2026-09-14)**
>

<!-- SUMARIO:FIM -->

Estado atual da arquitetura após as sessões de refatoração de 2026-06-23, 2026-06-25 e o God Module Split (Sessions 1–9, concluído em 2026-07-02).

---

## Estrutura de Arquivos

```
workspace-mmm/
├── frontend/
│   ├── app.py                  ← Ponto de entrada FastAPI (~125 linhas)
│   ├── core.py                 ← Estado compartilhado: cache de launches, _base_ctx, _compute_launch_defaults (~339 linhas)
│   ├── auth.py                 ← Auth HMAC, sessão, rate limiting, ROUTE_PERMISSIONS
│   ├── cache.py                ← Cache TTL em memória (_get_cached, _set_cached, _invalidate)
│   ├── database_reader.py      ← Shim de re-exportação (~314 linhas); contém apenas read_comparativo + read_youtube_aulas
│   ├── utils.py                ← Helpers compartilhados (_norm_text, _extract_launch_code, _safe_date, etc.)
│   ├── models.py               ← Dataclasses de retorno (VendasSummary, MetaSummary, LeadsSummary, etc.)
│   ├── db.py                   ← Engines SQLAlchemy (_get_engine, _get_users_engine, _READONLY_TABLES)
│   ├── formatters.py           ← fmt_brl, fmt_num, fmt_pct (filtros Jinja2)
│   ├── services/
│   │   ├── __init__.py
│   │   ├── attribution.py      ← _classify_campaign, _extract_ad_code, _utm_score, _sales_attribution, _creative_overview, _creative_insights
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

## God Module Split — Progresso (concluído em 2026-07-01)

O `database_reader.py` original tinha **4.180 linhas e 74 funções** em um único arquivo. O split incremental preservou 100% de compatibilidade: `database_reader.py` re-exporta tudo, então nenhum caller (especialmente `core.py`) precisou ser alterado.

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

**Estado final do `database_reader.py`:** 314 linhas. Contém apenas `read_comparativo` (que chama múltiplos readers, ficou como orquestrador) e `read_youtube_aulas` (stub — ETL YouTube não conectado).

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
frontend/db_readers/*.py        (leitores de domínio: sales, leads, ads_meta, ads_google, typeform, launches, users)
frontend/database_reader.py  (shim de re-exportação; contém apenas read_comparativo)
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

## Testes (90 testes, 0 dependência de DB)

| Arquivo | O que testa |
|---------|-------------|
| `test_core.py` | `fmt_brl/num/pct`, `_norm_text`, `_extract_ad_code`, `_classify_campaign`, `_classify_google_campaign_type`, `_utm_score`, `_inc_sales`, `find_previous_launch`, `resolve_launch` |
| `test_csv_utils.py` | Detecção de delimitador, fallback de Sniffer, encoding |
| `test_etl_validation.py` | `validate_dataframe()`: happy path, DataFrame vazio, colunas ausentes, nulos excessivos |
| `test_launch_discovery.py` | `FOLDER_PATTERN` regex, `PRODUCT_BY_PREFIX` |

```bash
python -m pytest tests/ -v   # roda todos os 90 testes
```

---

## Bugs Corrigidos (2026-06-25)

### `SyntaxError` no parâmetro array da query TMB
**Causa:** A query `_query_tmb` em `frontend/database_reader.py` usava `ANY(:product_ids::int[])` com SQLAlchemy `text()`. O parser de parâmetros do SQLAlchemy não consegue separar `:product_ids` do `::int[]` que vem imediatamente após — o parâmetro permanecia literal no SQL e o PostgreSQL recebia `:product_ids::int[]` como texto puro, causando `SyntaxError`.

**Fix:** Substituído por f-string formatando os IDs diretamente no SQL: `ANY(ARRAY[{ids_literal}]::int[])`. Seguro contra injection porque cada valor passa por `int()` antes da interpolação. Padrão alinhado com a query equivalente do Hotmart.

**Localização:** `frontend/database_reader.py`, função `_query_tmb` (~linha 2141).

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
**Localização:** `frontend/database_reader.py`, linha ~3182.

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
**Localização:** `frontend/database_reader.py`, função `read_vendas` (~linha 2169).

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
