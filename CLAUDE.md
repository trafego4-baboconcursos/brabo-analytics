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

# Single source (meta_ads | google_ads | active_campaign | typeform)
python etl/run_all.py --since 2026-04-01 --until 2026-04-30 --only meta_ads

# Continuous scheduler (runs every hour)
python etl/scheduler.py
```

### ETL — via CSV (manual exports)
```bash
python etl/run_all.py --csv-mode --campaign-folder "analises/[PBB-ABR-26]" --period 2026-04
```

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
frontend/database_reader.py (reads DB + CSVs)
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
- `database_reader.py` — all DB queries and CSV reads; returns typed dataclasses to routes
- `calendar_parser.py` — parses launch calendar HTML
- `templates/` — Jinja2 HTML templates (one per page)

Session auth uses HMAC-signed cookies. Roles: `admin > analista > trafego > leitura`. Product-scoped access (each user sees only their assigned products).

### ETL (`etl/`)
- `run_all.py` — orchestrator, accepts API mode or CSV mode
- `etl_meta_ads.py`, `etl_google_ads.py`, `etl_active_campaign.py`, `etl_typeform.py` — individual ETL scripts, each supports `--since/--until` (API mode) or `--from-csv` (CSV mode)
- `scheduler.py` — runs `run_all.py` every hour with a rolling 3-day window
- `schema.sql` — full DB schema + Supabase views (run once)
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

The v2 dashboard reads CSVs directly from these subfolders; v1 static HTML reports are legacy and served as-is via `/analises` static mount.

## Documentation (`documentacao/`)

### Required structure
```
documentacao/
  BRABO_ANALYTICS_APRESENTACAO_EXEC.md   ← executive presentation, always up to date
  ARQUITETURA.md                          ← system architecture reference
  CHECKLIST_DEPLOY_SEGURANCA.md
  METODOLOGIA_EXTRACAO_DADOS.md
  BRIEFING_BRABO.md
  HOW_TO_CONTINUE.md
  HANDOFF_CRIATIVOS_REUTILIZAVEL.md
  analises/        ← data analyses for specific launches
  historico/       ← old files; never delete, only archive here
```

### Rules — follow these whenever touching documentation
- Never create a new documentation file without checking if an existing one should be updated instead.
- Session logs, one-off plans, and date-stamped status files go in `historico/` — never in the root.
- When updating existing documentation, edit the file in place — do not create a new file with a date in the name.
- `BRABO_ANALYTICS_APRESENTACAO_EXEC.md` must always reflect the current state of the system; update the date in its header on every edit.
- When asked to "update the documentation", always update `BRABO_ANALYTICS_APRESENTACAO_EXEC.md` and any other relevant existing file — do not create new files.

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
