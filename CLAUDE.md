# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project: Brabo Analytics

Marketing analytics dashboard for digital product launches (concurso público courses). Three products:
- **PBB** — Banco do Brasil
- **PES** — TJ-SP (Tribunal de Justiça de São Paulo)
- **PI** — INSS

## Key Commands

### Run the dashboard
```bash
python -m uvicorn frontend.app:app --reload
# Access: http://127.0.0.1:8000
```

### ETL — via API (automated)
```bash
# Full run (all sources)
python etl/run_all.py --since 2026-04-01 --until 2026-04-30

# Single source (meta_ads | google_ads | active_campaign)
python etl/run_all.py --since 2026-04-01 --until 2026-04-30 --only meta_ads

# Continuous scheduler (runs every hour)
python etl/scheduler.py
```

### ETL — via CSV (plano B, não o fluxo normal)
Todo lançamento novo entra pela API. Este modo existe para quando a API de uma
plataforma está fora no meio de um lançamento e o dado precisa subir pelo export
manual — foi assim que o projeto começou, e continua disponível por isso.
Lançamentos a partir de PBB-JUN-26 não têm CSV nas pastas de `analises/`.
```bash
python etl/run_all.py --csv-mode --campaign-folder "analises/[PBB-ABR-26]" --period 2026-04
```

### ETL — legendas dos criativos
Ingere `analises/[LANCAMENTO]/Legendas/*.txt` (transcrição com minutagem por `ADxxx`).
Fora do scheduler de propósito. Base da página "Análise de Copys" — ver
`docs/projetos/PLANO_ANALISE_COPYS.md`.
```bash
python etl/etl_legendas.py --launch PES-SET-26
python etl/etl_legendas.py --launch PES-SET-26 --dry-run   # parseia e relata, não grava
python etl/etl_legendas.py --all
```

### ETL — copy escrito dos anúncios (Meta)
Puxa da Marketing API o texto **escrito** no anúncio (`message`/`title`/`description`/`cta`
+ cards do carrossel) → `ad_copy_textos`. Complementa as legendas, que são o que é **falado**.
Indispensável para carrossel/imagem, que não têm fala nenhuma.
```bash
python etl/etl_copy_meta.py --launch PES-SET-26
python etl/etl_copy_meta.py --launch PES-SET-26 --dry-run
python etl/etl_copy_google.py --launch PES-SET-26   # headlines/descriptions do Google
```

### ETL — transcrição automática dos vídeos
Baixa o mp4 do criativo pela Marketing API e transcreve com `faster-whisper` (CPU, sem
ffmpeg). Exige `pip install -r requirements-transcricao.txt` — a dependência fica fora do
`requirements.txt` porque pesa ~200 MB e o ETL nunca roda no servidor. Grava `fonte_tipo='corte_final'` + `hook_confiavel=True`, porque o vídeo do
criativo **é** o anúncio publicado — minutagem real, diferente dos `.txt` de filmagem crua.
```bash
python etl/etl_transcrever_meta.py --launch PES-SET-26 --so-faltantes
python etl/etl_transcrever_meta.py --launch PES-SET-26 --pasta "C:/dump"  # dump manual
```
A API **não libera `source`** de vídeo em criativo dinâmico (`asset_feed_spec`) — devolve 200
sem o campo. Para esses, use `--pasta`: casa por `ADxxx` no nome do arquivo e, no que sobrar,
por duração. Não rode com `| grep`: mascara o exit code.

### One-time setup
```bash
# Apply DB schema (run in Supabase > SQL Editor)
# file: etl/schema.sql

# Discover Active Campaign UTM field IDs
python etl/etl_active_campaign.py --discover-fields

# Generate Google Ads OAuth refresh token
python etl/etl_google_ads.py --get-token
```

## Architecture

### Data Flow
```
APIs / CSV exports
      ↓
etl/ (ETL scripts)
      ↓
Supabase (two DBs)
      ↓
frontend/db_readers/*.py (one module per domain)
      ↓
frontend/app.py (FastAPI + Jinja2 → HTML pages)
```

### Two Supabase Databases
- **Analytics DB** (`SUPABASE_DB_URL`): `meta_ads_daily`, `google_ads_daily`, `leads`, `typeform_respostas`, `dim_lancamentos`, audiences/demographics tables
- **Operational DB** (`SUPABASE_USERS_URL`): `hotmart_clean_oficial`, `tmb_clean_oficial`, `users`, `launch_config`, `invites`

### Launch System
Launches are identified by code `[PREFIX]-[MON]-[YY]` (e.g. `PBB-ABR-26`). Each launch has:
- A folder under `analises/[PBB-ABR-26]/` containing CSV exports per source (subfolder names: `Meta Ads/`, `Google Ads/`, `Active Campaign/`, `Hotmart/`, `TMB/`, `Typeform/`)
- An optional YAML config in `config/launches/pbb-abr-26.yaml`
- A row in the `launch_config` table in the operational DB (configured via the Settings wizard)

The frontend auto-discovers launches by querying `dim_lancamentos` in the analytics DB, cross-referencing which tables (`meta_ads_daily`, `google_ads_daily`, `leads`, hotmart/tmb, `typeform_respostas`) have rows for each launch code (`frontend/db_readers/launches.py::discover_launches`).

### Frontend (`frontend/`)
- `app.py` — FastAPI app: routes, auth middleware, session signing, data aggregation logic
- `db_readers/` — all DB queries, one module per domain (sales, hotmart, tmb, leads, ads_meta,
  ads_google, typeform, launches, comparativo, …); returns typed dataclasses to routes.
  `database_reader.py` was removed on 2026-09-15 — import from `frontend.db_readers`
- `calendar_parser.py` — parses launch calendar HTML
- O frontend lê tudo do banco. A única exceção é um fallback em
  `db_readers/typeform.py`, que recupera o estado do respondente do CSV local em 6
  lançamentos de jan–mai/26 (ver `docs/projetos/BACKFILL_ESTADO_TYPEFORM.md`)
- `templates/` — Jinja2 HTML templates (one per page)

Session auth uses HMAC-signed cookies. Roles: `admin > analista > trafego > leitura`. Product-scoped access (each user sees only their assigned products).

### ETL (`etl/`)
- `run_all.py` — orchestrator, accepts API mode or CSV mode (CSV = plano B, see above)
- `etl_meta_ads.py`, `etl_google_ads.py`, `etl_active_campaign.py` — individual ETL scripts, each supports `--since/--until` (API mode) or `--from-csv` (CSV mode)
- `etl_typeform.py` — no longer wired into `run_all.py`/`scheduler.py` (Typeform account was cancelled); `typeform_respostas` reads now come from a one-time Supabase backup (`typeform_respostas_backup`, `typeform_respostas_backup_2`, `typeform_forms`, `typeform_forms_2`) via `frontend/db_readers/typeform.py`. The script still exists for a manual one-off run if the token is ever valid again.
- `scheduler.py` — runs `run_all.py` every hour with a rolling 3-day window
- `schema.sql` — full DB schema + Supabase views (run once)
- `etl_legendas.py` — transcrições dos criativos → `ad_transcricoes` / `ad_transcricao_linhas` /
  `ad_copy_atributos`. Só `fonte_tipo='corte_final'` tem `hook_confiavel=True`: a maioria dos
  arquivos é filmagem crua, não o corte publicado — toda análise temporal precisa filtrar por
  essa coluna (ver `docs/sistema/ARQUITETURA.md`)
- `db.py` — SQLAlchemy engine factory (reads `SUPABASE_DB_URL` from `.env`)

### Shared Modules (`src/`)
- `src/db_engine.py` — shared SQLAlchemy engine factory (pool tuning, statement timeout, read-only guard); used by both `etl/db.py` and `frontend/db.py`
- `src/db/` — legacy SQLite layer (`outputs/analysis.db`), predates the two-Supabase-DB architecture
- `src/ingest/` — CSV utilities
- `src/reports/`, `src/transforms/` — report generators and data transforms
- `src/constants.py` — shared constants (`PRODUCT_BY_PREFIX`, launch accent/name/short lookups)

### Key DB Views (defined in `etl/schema.sql`)
- `view_atribuicao` — lead → sale attribution with ROAS/CPA per ad code
- `view_meta_performance_criativos` / `view_google_performance_criativos` — hook rate, hold rate, completion rate per ad
- `view_investimento_total_por_ad` — combined Meta + Google spend per `ADXXX` code

### Ad Code Convention
All ads are named `ADxxx - Description...` (e.g. `AD110 - Banco do Brasil 2 - ...`). The prefix `ADXXX` is the shared attribution key across Meta, Google, Active Campaign UTMs, and sales data. Regex used everywhere: `^(AD\d+).*`.

### `analises/` Folder Structure
```
analises/
  index.html               ← landing page listing all launches
  [PBB-ABR-26]/
    Meta Ads/              ← CSV export from Meta Ads Manager
    Google Ads/            ← CSV export from Google Ads
    Active Campaign/       ← CSV export from AC
    Hotmart/               ← CSV export from Hotmart
    TMB/                   ← CSV export from TMB
    Typeform/              ← CSV export from Typeform
    INDEX_[PBB-ABR-26].html   ← v1 static report (legacy)
    ANALISE_*.html            ← v1 static reports (legacy)
  [PES-MAI-26]/
    ...
```

These CSVs are the exports from the launch's era. The v2 dashboard reads from the database,
not from here — the single exception is the Typeform state fallback noted above. v1 static
HTML reports are legacy and served as-is via the `/analises` static mount.

## Documentation (`docs/`)

`docs/` is an Obsidian vault. It is the project's long-term memory: **a conversation that
changed something and was not written here did not happen.**

### How to find something — do NOT read the whole vault

1. Read `docs/README.md` first. Its **Mapa de roteamento** is a generated `question -> file`
   table. Open only what it points at.
2. Still unsure? Read just the frontmatter of candidates (`head -14`), never whole files:
   ```bash
   head -14 docs/**/*.md          # titulo / area / status / atualizado / responde
   grep -rl "responde" docs/ | xargs grep -l "palavra-chave"
   ```
3. Follow `relacionados:` to hop between docs instead of scanning directories.
4. **Never read a launch diary whole.** `MUDANCAS_PES-SET-26.md` alone is 240 KB / 130 items.
   Each doc over 30 KB carries a generated `<!-- SUMARIO -->` callout listing every item.
   Read the summary (~10% of the file), then pull only the section you need:
   ```bash
   grep -n "^### 47\." docs/performance/lancamentos/PES-SET-26/MUDANCAS_PES-SET-26.md
   sed -n '1688,1710p'  docs/performance/lancamentos/PES-SET-26/MUDANCAS_PES-SET-26.md
   ```
   To append a new item, read the last section for the numbering — not the whole file.

Reading three whole docs to answer one question means the routing failed — fix the
`responde:` keys of the doc that should have matched.

### Frontmatter contract (every `.md` in `docs/` has it)

```yaml
---
titulo: "..."                  # H1 of the doc
area: sistema|negocio|operacao|performance|lancamento|projeto|analise|historico|indice
status: vigente|pendente|arquivado
atualizado: YYYY-MM-DD         # bump on every edit
responde:                      # routing keys: questions this doc answers
  - "..."
relacionados:                  # optional, "[[WIKILINK]]" entries
  - "[[OUTRO_DOC]]"
---
```

A new doc without frontmatter, or not linked from an index, **fails validation**.

### Structure
```
docs/
  README.md                    <- vault home: routing map + where-to-write table
  sistema/                     <- ARQUITETURA, METODOLOGIA_EXTRACAO_DADOS, DESIGN_SYSTEM
  negocio/                     <- BRABO_ANALYTICS_APRESENTACAO_EXEC, BRIEFING_BRABO
  operacao/                    <- CHECKLIST_DEPLOY_SEGURANCA, RESTAURAR_MAQUINA_NOVA
  performance/                 <- ad-ops; index in INDICE_PERFORMANCE.md
    lancamentos/[LAUNCH]/      <- MUDANCAS_[LAUNCH].md + one-offs for that launch
    playbooks/                 <- reusable methods
    perpetuo/                  <- always-on campaigns, outside any launch
                                  (there is no separate analises/ folder: every analysis
                                   lives with the launch it is about, or in playbooks/)
  projetos/                    <- agreed but NOT yet implemented; index INDICE_PROJETOS.md
  historico/                   <- archived; index INDICE_HISTORICO.md
    codigo-legado/             <- retired code
```

### Registering a conversation — where the outcome goes

Do this **in the same turn** as the change, not "later". Each row is a trigger:

| what happened in the conversation | write it to |
|---|---|
| ad-ops action or analysis for a launch (via API **or** done by hand in the platform) | `performance/lancamentos/[LAUNCH]/MUDANCAS_[LAUNCH].md` — new dated item |
| a method that will repeat on other launches | `performance/playbooks/` (new doc or update existing) |
| a decision covered by a rule | cite the rule ID (`ORC-2`, `META-3`…) from `REGRAS_DECISAO.md` in the item |
| a rule proved wrong, or a new rule emerged | fix/add it in `performance/playbooks/REGRAS_DECISAO.md` with the incident that taught it |
| a launch closed (carrinho fechou) | run `performance/playbooks/FECHAMENTO_LANCAMENTO.md` — measure actions with `scripts/efeito_acao.py`, then write the `## Fechamento — aprendizado` section |
| system behaviour changed (code, data flow, a fixed bug) | `sistema/ARQUITETURA.md` + bump the date in `negocio/BRABO_ANALYTICS_APRESENTACAO_EXEC.md` |
| how a metric is extracted/attributed changed | `sistema/METODOLOGIA_EXTRACAO_DADOS.md` |
| something agreed but not built yet | new doc in `projetos/` + a row in `INDICE_PROJETOS.md` |
| a `projetos/` item shipped | move the doc to `historico/`, drop its row from `INDICE_PROJETOS.md`, and document the result where the table above says |
| decision/investigation that changes nothing yet | the `MUDANCAS_` of the launch it concerns, else a dated doc in `historico/` |

Analyses count, not just actions: if the user asked for an analysis, it becomes an item in the
launch's `MUDANCAS_` — a chat answer alone is not a record.

### Rules
- Never create a new doc without checking whether an existing one should be updated instead.
- Edit in place. Never create a second file with a date in the name to "version" a doc.
- Filenames must be unique across the whole vault (`[[links]]` resolve by name, not path) and
  must not contain `[` or `]` — brackets break wikilink syntax. Keep the launch code in the
  filename even inside `lancamentos/[LAUNCH]/`.
- Every new doc: frontmatter + linked from the index of its area.
- Never archive an open plan in `historico/` — that is how the TikTok/CAPI plans got lost.
- `BRABO_ANALYTICS_APRESENTACAO_EXEC.md` must always reflect the current state of the system.
- Module-level `README.md` (`frontend/`, `config/launches/`) stay next to their code.
- After touching `docs/`, run:
  ```bash
  python scripts/check_docs.py --atualizar-mapa
  ```
  It validates frontmatter, unique names, wikilinks and reachability, and regenerates both the
  routing map and the `SUMARIO` of every doc over 30 KB. Treat a non-zero exit as a broken build.

## Environment Variables (`.env`)
See `.env.example` for the full list. Key vars:
- `SUPABASE_DB_URL` / `SUPABASE_USERS_URL` — direct PostgreSQL connection strings
- `META_ACCESS_TOKEN` / `META_AD_ACCOUNT_ID` — Meta Marketing API (comma-separated account IDs)
- `GOOGLE_ADS_*` — Google Ads API credentials
- `AC_API_URL` / `AC_API_KEY` — Active Campaign
- `TYPEFORM_TOKEN` / `TYPEFORM_FORM_ID` — Typeform
- `BRABO_USER` / `BRABO_PASS` — legacy admin credentials (fallback when DB unavailable)
- `SECRET_KEY` — HMAC session signing key (change in production)
- `ERROR_WEBHOOK_URL` — optional Discord/Slack webhook for ETL failure alerts
- `FRONTEND_URL` / `ETL_REFRESH_TOKEN` — after each successful ETL run, `scheduler.py` POSTs to `/api/etl/refresh` on the dashboard so it re-warms the in-memory cache of active launches in place (`frontend/services/prewarm.py`); without the token the call is skipped and the cache expires on its own (1h)

## Debriefing snapshot
`/debriefing` reads a pre-computed context from the `debriefing_snapshot` table (analytics DB, one JSONB row per launch) and renders in ~0.2s. The row is written by the warm-up (`frontend/services/prewarm.py` → `frontend/services/debriefing_build.py::refresh_debriefing_snapshot`) at boot, after every ETL run, and on its own every `PRE_WARM_INTERVAL_MIN` minutes (default 30); a build with failed blocks never overwrites an existing snapshot. Without a snapshot the route computes live (heavy sections lazy-loaded via `/debriefing/secao/<nome>`); `?ao_vivo=1` forces the live path. The header shows "dados de DD/MM HH:MM" when a snapshot is used.
