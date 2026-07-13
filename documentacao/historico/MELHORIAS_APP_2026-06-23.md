# Melhorias de Maturidade do App — 2026-06-23

Sessão de refatoração abrangente do Brabo Analytics para elevar a confiabilidade, segurança e manutenibilidade do projeto em produção.

---

## Resumo das Melhorias

| # | Área | O que foi feito |
|---|------|----------------|
| 1 | Logging centralizado | `src/logger.py` com RotatingFileHandler; substituiu todos os `print()` |
| 2 | Error handling | Todos os `except: pass` substituídos por `logger.exception()` |
| 3 | Health check | Endpoint `GET /health` com status dos dois bancos |
| 4 | Session timeout | `SESSION_MAX_AGE` lido do `.env` |
| 5 | Retry HTTP (ETL) | `etl/http_retry.py` com tenacity — 3 tentativas, backoff exponencial |
| 6 | Validação ETL | `etl/validation.py` — valida DataFrames antes do upsert |
| 7 | Facade readers | `frontend/readers/` — namespace por domínio sem quebrar imports |
| 8 | Testes automatizados | 29 testes unitários com pytest (sem dependência de DB) |
| 9 | CI / lint | `.pre-commit-config.yaml` + `pyproject.toml` com ruff |
| 10 | Bug circuit breaker | `discover_launches()` sem try/except causava 500 quando DB caia |
| 11 | Cache de launches | `get_launches()` com TTL de 60s — para de hammar o DB a cada request |
| 12 | Cache invalidation | `save_launch_config` reseta o cache de launches automaticamente |
| 13 | Env validation | App loga erro no startup se `SUPABASE_DB_URL`/`SUPABASE_USERS_URL` ausentes |
| 14 | Banner DB down | Template base exibe aviso vermelho quando o banco está indisponível |
| 15 | /health com cache | TTL de 30s no health check — evita conexões DB a cada poll de monitoramento |
| 16 | Cache com TTL | `_CACHE` de leituras CSV/DB expiram em 30 min (antes: nunca expiravam) |
| 17 | Rate limit no login | Máx 10 tentativas por IP em 5 min com limpeza automática de memória |
| 18 | Cookie seguro | `COOKIE_SECURE` via env var; `samesite=lax` já existia |
| 19 | Rota duplicada | `/crm-campanhas` estava registrada duas vezes — versão antiga removida |
| 20 | `/debug-path` protegido | Requer autenticação admin (antes: público) |
| 21 | pyrightconfig.json | Configuração do Pyright para reconhecer `.venv` e `src/` |

---

## Novos Arquivos Criados

```
src/logger.py                        ← factory get_logger() com RotatingFileHandler
etl/http_retry.py                    ← http_get() / http_post() com retry via tenacity
etl/validation.py                    ← validate_dataframe() para checagem pré-upsert
frontend/readers/__init__.py         ← re-exporta tudo de database_reader (facade)
frontend/readers/launches.py         ← re-exporta funções de lançamentos
frontend/readers/ads_meta.py         ← re-exporta readers Meta Ads
frontend/readers/ads_google.py       ← re-exporta readers Google Ads
frontend/readers/leads.py            ← re-exporta readers de leads/AC/Typeform
frontend/readers/sales.py            ← re-exporta readers de vendas/Hotmart/TMB
frontend/readers/users.py            ← re-exporta gestão de usuários
tests/__init__.py                    ← marcador de pacote de testes
tests/conftest.py                    ← fixtures compartilhadas (DataFrames, tmp_dir)
tests/test_csv_utils.py              ← testes para src/ingest/csv_utils.py
tests/test_etl_validation.py         ← testes para etl/validation.py
tests/test_launch_discovery.py       ← testes para src/readers/launch_discovery.py
.gitignore                           ← logs/, .env, .venv/, __pycache__, etc.
.pre-commit-config.yaml              ← hooks ruff + ruff-format
pyproject.toml                       ← config ruff (line-length=100) + pytest
pyrightconfig.json                   ← config Pyright: venv + src/ como extraPath
.vscode/settings.json                ← aponta interpretador para .venv (VS Code)
```

---

## Arquivos Modificados

### `frontend/app.py`
- Importa `get_logger("frontend")`; todos os `print()` viram `logger.info/exception`
- `SESSION_MAX_AGE` lido do `.env` (padrão 7 dias)
- `COOKIE_SECURE` lido do `.env` (padrão `false`)
- Validação de env vars críticas no startup com log de erro
- `get_launches()` com cache de 60s e flag `_LAUNCHES_DB_OK`
- `_base_ctx()` passa `db_ok` para todos os templates
- `_CACHE` agora armazena `(valor, expires_at)` — TTL de 30 min
- Rate limiting no `/login`: 10 tentativas / 5 min por IP, com limpeza automática
- `_set_session_cookie()` e `delete_cookie()` com `secure=COOKIE_SECURE`
- `GET /health` com cache de 30s
- Rota `/crm-campanhas` duplicada removida
- `GET /debug-path` protegido — exige role `admin`

### `frontend/database_reader.py`
- Importa `get_logger("db")`; todos os except bare viram `logger.exception()`
- `discover_launches()`: query do DB analytics envolvida em try/except — retorna `[]` em vez de levantar (era causa dos 500 quando o Supabase caía)

### `frontend/templates/base.html`
- Banner vermelho exibido quando `db_ok == false`

### `etl/etl_meta_ads.py`
- Usa `get_logger("etl.meta")`, `http_get()` e `validate_dataframe()`
- Remove import `requests` direto

### `etl/etl_google_ads.py`
- Usa `get_logger("etl.google")`, `http_post()` e `validate_dataframe()`

### `etl/etl_active_campaign.py`
- Usa `get_logger("etl.ac")`, `http_get()` e `validate_dataframe()`

### `etl/etl_typeform.py`
- Usa `get_logger("etl.typeform")`, `http_get()` e `validate_dataframe()`

### `etl/run_all.py`
- Usa `get_logger("etl.run_all")`; substitui separadores `print()` por logs

### `requirements.txt`
- Adicionados: `tenacity>=8.2`, `pytest>=8.0`, `pytest-mock>=3.12`, `ruff>=0.4`, `pre-commit>=3.7`

### `.env.example`
- Adicionados: `SUPABASE_USERS_URL`, `SECRET_KEY`, `SESSION_MAX_AGE`, `COOKIE_SECURE`, `BRABO_USER`, `BRABO_PASS`, `ERROR_WEBHOOK_URL`

---

## Como Rodar

### Testes
```bash
python -m pytest tests/ -v
# Resultado esperado: 29 passed
```

### Lint
```bash
ruff check .
ruff format .
```

### Instalar hooks de pre-commit
```bash
.venv/Scripts/pre-commit install
# A partir daí, ruff roda automaticamente em cada git commit
```

### Health check
```bash
# Com o app rodando:
curl http://127.0.0.1:8000/health
# Resposta esperada:
# {"status":"ok","uptime_seconds":42,"db_analytics":"ok","db_operational":"ok","launches_cached":3}
```

### App
```bash
python -m uvicorn frontend.app:app --reload
```

---

## Configuração de Produção

Variáveis de ambiente adicionais a configurar no servidor:

```env
COOKIE_SECURE=true          # exige HTTPS para o cookie de sessão
SECRET_KEY=<chave-forte>    # mínimo 32 chars aleatórios
SESSION_MAX_AGE=86400       # 1 dia (ajustar conforme política)
ERROR_WEBHOOK_URL=<url>     # Discord/Slack — já implementado no scheduler.py
```

---

## Arquitetura de Logging

Todos os módulos usam `src/logger.py`:

```
src/logger.py → get_logger(name)
  ├── StreamHandler (stdout)
  └── RotatingFileHandler → logs/app.log (5MB, 3 backups)

Loggers em uso:
  "frontend"      → app.py
  "db"            → database_reader.py
  "etl.meta"      → etl_meta_ads.py
  "etl.google"    → etl_google_ads.py
  "etl.ac"        → etl_active_campaign.py
  "etl.typeform"  → etl_typeform.py
  "etl.run_all"   → run_all.py
  "scheduler"     → scheduler.py (logger próprio, formato compatível)
```

---

## Estrutura de Cache (frontend)

| Cache | TTL | Invalidação |
|-------|-----|-------------|
| `_LAUNCHES_CACHE` | 60s | Automática ao expirar; manual via `_LAUNCHES_CACHE_AT = 0` após `save_launch_config` |
| `_CACHE[launch::reader]` | 30 min | Automática ao expirar; manual via `_invalidate(launch_code)` |
| `_HEALTH_CACHE` | 30s | Automática ao expirar |

---

## Segurança

| Proteção | Implementação |
|----------|--------------|
| Brute force no login | 10 tentativas / 5 min por IP; limpeza de memória a cada 5 min |
| Cookie de sessão | `httponly=True`, `samesite=lax`, `secure` configurável via env |
| `/debug-path` | Requer role `admin` |
| Validação de env | Log de erro no startup se DB URLs ausentes |
| Chave fraca | Warning se `SECRET_KEY` usar valor padrão |
| Writes em tabelas read-only | Guard via SQLAlchemy event em `_make_engine()` |
