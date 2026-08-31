# AGENTS.md

Instructions for Codex and other coding agents working in this repository.

## Project

This repository is **Brabo Analytics**, a marketing analytics dashboard for digital product launches focused on public exam courses.

Core products:

- **PBB**: Banco do Brasil
- **PES**: TJ-SP
- **PI**: INSS

The system consolidates media spend, leads, survey answers, and sales into a launch-oriented dashboard and analysis workflow.

## Working Language

- Prefer Portuguese when communicating with the project owner.
- Keep code, commands, identifiers, and environment variable names exactly as implemented.
- Do not expose secrets from `.env` or logs in summaries, commits, docs, or chat.
- Before editing or diagnosing a file, read the actual file contents. Do not infer structure from filenames or old memory.
- If an API/tool call fails, report the error promptly and ask how to proceed instead of retrying silently in loops.

## Primary Commands

Run the dashboard:

```powershell
python -m uvicorn frontend.app:app --reload
```

Local URL:

```text
http://127.0.0.1:8000
```

Run full ETL via APIs:

```powershell
python etl/run_all.py --since 2026-04-01 --until 2026-04-30
```

Run one ETL source:

```powershell
python etl/run_all.py --since 2026-04-01 --until 2026-04-30 --only meta_ads
```

Accepted `--only` sources:

- `meta_ads`
- `google_ads`
- `active_campaign`

(`typeform` was removed from the automated pipeline in 2026-08 — Typeform account cancelled; `etl/etl_typeform.py` still runs standalone if ever needed again.)

Run scheduler:

```powershell
python etl/scheduler.py
```

Run ETL from manual CSV exports:

```powershell
python etl/run_all.py --csv-mode --campaign-folder "analises/[PBB-ABR-26]" --period 2026-04
```

One-time setup references:

- Apply `etl/schema.sql` in Supabase SQL Editor.
- Discover Active Campaign UTM field IDs with:

```powershell
python etl/etl_active_campaign.py --discover-fields
```

- Generate Google Ads OAuth refresh token with:

```powershell
python etl/etl_google_ads.py --get-token
```

## Architecture

High-level data flow:

```text
APIs / CSV exports
  -> etl/
  -> Supabase
  -> frontend/database_reader.py
  -> frontend/app.py
  -> FastAPI + Jinja2 dashboard
```

There are two Supabase databases:

- **Analytics DB** via `SUPABASE_DB_URL`
  - Tables include `meta_ads_daily`, `google_ads_daily`, `leads`, `typeform_respostas`, `dim_lancamentos`, and audience/demographic tables.
- **Operational DB** via `SUPABASE_USERS_URL`
  - Tables include `hotmart_clean_oficial`, `tmb_clean_oficial`, `users`, `launch_config`, and `invites`.

Important DB views are defined in `etl/schema.sql`:

- `view_atribuicao`: lead-to-sale attribution with ROAS/CPA per ad code.
- `view_meta_performance_criativos`: Meta creative performance.
- `view_google_performance_criativos`: Google creative performance.
- `view_investimento_total_por_ad`: combined Meta + Google spend per `ADXXX` code.

## Launch System

Launches are identified by codes in this pattern:

```text
[PREFIX]-[MON]-[YY]
```

Examples:

- `PBB-ABR-26`
- `PES-JAN-26`
- `PI-AGO-26`

Each launch may have:

- A folder under `analises/[LAUNCH-CODE]/`.
- A YAML config in `config/launches/<launch-code-lowercase>.yaml`.
- A row in the operational DB table `launch_config`.
- Rows in analytics tables such as `dim_lancamentos`, `meta_ads_daily`, `google_ads_daily`, `leads`, and `typeform_respostas`.

Expected local CSV folder structure:

```text
analises/
  [PBB-ABR-26]/
    Meta Ads/
    Google Ads/
    Active Campaign/
    Hotmart/
    TMB/
    Typeform/
```

Legacy static HTML reports under `analises/` are served as-is through the `/analises` static mount.

## Attribution And Naming Rules

Ads use the convention:

```text
ADxxx - Description...
```

The `ADXXX` prefix is the shared attribution key across:

- Meta Ads
- Google Ads
- Active Campaign UTMs
- Sales data
- Analysis reports

The common regex is:

```regex
^(AD\d+).*
```

When changing attribution or analysis code, preserve this convention unless the user explicitly asks for a migration.

Campaign names use this general convention:

```text
[PLATFORM][type][stage][temperature][bucket][LAUNCH-CODE][start-date]
```

Platform tags:

- `[MA]`: Meta Ads
- `[GA]`: Google Ads

Campaign naming rules:

- The date in the campaign name is the real campaign/ad set start date, not the date the object was created.
- If a campaign starts earlier or later than the nominal launch calendar stage, use the real go-live date.
- Confirm dates with the user before naming campaigns when timing is unclear.
- Ad copy dates usually refer to live class/event dates, not media campaign start/end dates.
- Parse `replay` before `aula`; replay campaigns often contain both terms.
- Lembrete, Replay, and Aulas campaigns may not use `AD\d+`; the ETL should generate a synthetic slug ID when no `ADXXX` exists.

Known CSV naming:

- Meta preferred export: `analises/[LAUNCH-CODE]/Meta Ads/Campanhas-Completas-LAUNCH.csv`.
- Google ads export: `analises/[LAUNCH-CODE]/Google Ads/Performance dos anúncios-LAUNCH.csv`.
- Google campaign export: `analises/[LAUNCH-CODE]/Google Ads/Performance da campanha-LAUNCH.csv`.

## Performance Manager And Ad Creation

Operational ad work lives mainly in:

- `performance-manager/PLAYBOOK_DUPLICAR_LANCAMENTO_META_ADS.md`
- `performance-manager/CASCATEAMENTO_PUBLICOS_META_ADS.md`
- `performance-manager/MUDANCAS_*.md`
- launch-specific folders under `performance-manager/[LAUNCH-CODE]/`

Before creating, duplicating, pausing, activating, renaming, or changing ads/campaigns:

- Confirm the exact account, product, launch code, campaign type, and scope.
- Distinguish `captação`, `pré-qualificação`, `quente`, `frio`, `específico`, `principal`, `potencial`, `teste`, `reels`, `old-ads`, and `new-ads`; do not apply a change across these boundaries unless explicitly confirmed.
- Ask for destination URLs; never infer LP URLs.
- Ask whether ad copy changes beyond event dates.
- Confirm whether videos/images are already in the media library or must be uploaded.
- If several healthy source ads are candidates for the same slot, ask which one to use; prefer ads without approval/policy problems.
- For bulk creation, create in one ad set first when risk is meaningful, wait for user review/approval, then duplicate to the remaining ad sets.
- Create new ads paused unless the user explicitly asks to activate them immediately.
- After any mutation via API, verify the affected objects by ID and report counts.
- Every Meta ad created via API must include `tracking_specs=[{"action.type":"offsite_conversion","fb_pixel":"<PIXEL_ID>"}]`, even for engagement campaigns. This is separate from the ad set `promoted_object`.

Meta Ads campaign duplication rules:

- Use shallow copy for campaigns: `/copies` with `deep_copy=false`, `status_option=PAUSED`, and `rename_options={"rename_strategy":"NO_RENAME"}`.
- Do not use `deep_copy=true` for campaign duplication with more than a couple of child objects; the API commonly refuses it.
- For ad sets, prefer recreating from fetched targeting instead of using `/{adset_id}/copies` when positioning validation is likely to fail.
- Preserve `promoted_object` with pixel and `custom_event_type=LEAD`, the account attribution spec, `optimization_goal=OFFSITE_CONVERSIONS`, and `billing_event=IMPRESSIONS`.
- Use new launch `start_time` and `end_time`; do not inherit dates from the old launch.
- If `instagram_positions` includes `explore_home`, include `explore` as well.
- For Reels variants, restrict placements to IG Story, IG Reels, FB Story, and FB Reels unless the user asks otherwise.
- If future scheduling matters, avoid campaign-level budget/CBO. Meta may freeze `start_time` at creation time and later return `success:true` without applying the intended date. Use ad set budgets with explicit `daily_budget`, `bid_strategy=LOWEST_COST_WITHOUT_CAP`, `start_time`, and `end_time`.
- For `OUTCOME_ENGAGEMENT` / `THRUPLAY` ad sets, include `promoted_object={"page_id": ...}`, `destination_type="ON_VIDEO"`, and `targeting.targeting_automation.advantage_audience`.
- `promoted_object` is effectively immutable after ad set creation; if it is wrong or missing, recreate the ad set.
- For new videos without a thumbnail hash, fetch `picture` from the video and use it as `image_url` if needed.

Meta Ads creative rules:

- Put the standard UTM in the creative `url_tags`, not inside `asset_feed_spec`:

```text
utm_source=facebook&utm_medium=paid_social&utm_campaign={{campaign.name}}&utm_content={{adset.name}}&utm_term={{ad.name}}&vk_source=paid_metaads&vk_ad_id={{ad.id}}
```

- For Feed + Story video creatives, use `asset_feed_spec` with `call_to_action_types` as a plural array of strings, `ad_formats: AUTOMATIC_FORMAT`, and `asset_customization_rules` with Story priority before the catch-all/feed rule.
- For one-video Reels creatives, `object_story_spec.video_data` is usually enough.
- For Feed + Story image creatives, use the same DCO pattern as video, using `images` and `image_label`.
- For carousel creatives, use `object_story_spec.link_data.child_attachments`, one image per attachment, same link and CTA unless the user specifies otherwise.
- Warn the user that Meta may create an extra carousel highlight card that needs manual review/removal.
- Use resumable upload for large videos via `upload_phase=start/transfer/finish` on `/act_{account}/advideos`.
- Do not assume video files can be renamed in Meta's Media Library via API; ad names can be correct even if the raw media title is not.
- Some older creatives contain deprecated fields such as `degrees_of_freedom_spec`; if `/copies` fails because of this, recreate the ad manually from clean creative fields.
- Do not put CTA data in `asset_feed_spec.call_to_actions` for Feed + Story video; this creates but fails at ad publish. Use `call_to_action_types` as shown above.

Meta Ads audience cascade rules for capture campaigns:

- Groups `00` to `06` represent a cascade from colder/broader audiences to more qualified audiences.
- Group `00 - Cadastrados Antigos` targets accumulated old registrants and excludes people registered in the current launch.
- Groups `01` to `06` should exclude buyers, current-launch registrants, and audiences that are further down the current funnel.
- When duplicating to a new launch, replace every old `[SITE] Cadastrados/Caiu Pág. Captura [OLD-LAUNCH]` exclusion with the current-launch version, checking all old launch references, not only the immediately previous one.
- Add the previous launch's registrant list to group `00` targeting and as an exclusion in groups `01` to `06`.
- Video-view audiences for the new launch may not exist until new videos have run; keep previous-launch video audiences temporarily and record the follow-up.
- Confirm scope before touching pre-qualification audiences, because they are conceptually different from capture audiences even inside an `específico` campaign.
- Rename ad sets that still mention the old launch.

Segment `específico` rules:

- `Específico` uses only the `principal` variant by default; do not create Reels, Potencial, or Imagem variants unless the user explicitly changes this rule.
- `Específico` should run in the product owner's dedicated/new ad account after pixel and audiences are shared through Business Manager.
- For pre-qualification, prioritize new ads in warm audiences before replicating to the rest.
- In PES-SET-26 and similar structure, `específico` may be conceptually part of Pré-Qualificação even if older naming/templates resemble Captação. Confirm classification before reporting totals.

After ads are approved or published:

- Complement video-view audiences only when the new video is associated with a Page post.
- If Meta returns error `1713216` about missing Page or New Page Experience association, ask the user to add it manually in Ads Manager.
- For very old audiences, `GET /{audience_id}?fields=rule` may return server errors; do not keep retrying blindly.

Google Ads and policy care:

- For PBB/Banco do Brasil campaigns, be careful with financial-services policy classification. The product is an education/course product for a public exam, not a financial service.
- If ads are limited by Financial Services Verification, use Policy Manager first; if no contest button is available, open Google Ads support and explain that "Banco do Brasil" refers to the public exam, not banking products.
- Copy dates should refer to the live classes/event dates, not necessarily campaign start/end dates.
- Start times for campaigns/ad sets should be explicit; do not rely on old/default dates when launches move.

## Advertising Accounts And Budget Work

Current launch ad accounts tracked by ETL:

- Meta Ads: `act_1407542209639031`, `act_438212624024216`, `act_1175937361058463`.
- Google Ads MCC: `9335944411`.
- Google Ads customer IDs: `6482320788`, `1450466453`.

Known account ownership:

- Felipe Graton / PBB uses `act_438212624024216`, `act_1175937361058463`, and Google customer `1450466453`.
- Ivan Neto / PES and Mateus Andrade / PI historically shared `act_1407542209639031` and Google customer `6482320788`.
- PES is migrating to Ivan's dedicated Meta account `act_1572917053349409`; confirm pixel/audience sharing and `.env`/ETL coverage before assuming dashboard ingestion.
- Perpétuo uses separate accounts and should not be mixed with launch-funnel data.

Budget diligence rules:

- Budget work is high stakes. Before reporting spend totals, projections, or applying cuts/increases, search by launch tag across all relevant accounts and include active and paused campaigns.
- Never trust a fixed list of campaign IDs for current totals; campaigns can be created manually outside the list.
- Confirm the current date before any "até hoje" calculation.
- Ask the user before treating a spend/budget number as final if it will drive allocation decisions.
- When ETL data is stale, say so and either refresh ETL or explicitly use live platform API data.
- For recent/current conversions, spend, delivery, approval status, or tracking checks, consult Meta Ads / Google Ads directly first. Use the database/dashboard only as secondary support or historical context.

## Frontend

Main frontend files:

- `frontend/app.py`: FastAPI app, routes, auth middleware, session signing, and orchestration.
- `frontend/database_reader.py`: DB and CSV reads, returning typed data to routes.
- `frontend/calendar_parser.py`: launch calendar HTML parsing.
- `frontend/templates/`: Jinja2 templates.
- `frontend/routes/`: route modules by domain when present.

Auth:

- Uses HMAC-signed cookies.
- Role order: `admin > analista > trafego > leitura`.
- Product-scoped access means users should only see assigned products.

When editing frontend behavior:

- Preserve product access filtering.
- Avoid leaking launch data across product scopes.
- Keep dashboard pages data-dense and operational, not marketing-style.
- Check relevant templates and route data together; many bugs come from route/template contract drift.
- Use platform CSS variables: `--meta-color` for Meta and `--google-color` for Google; avoid hardcoded alternate blues/reds.
- Global table CSS can override `<thead>` backgrounds. If platform table headers need colors, apply background to each `<th>` or use the existing scoped table classes.
- The sidebar header should not be animated with transforms; sticky header plus transform can break z-index behavior against the fixed sidebar.
- For Drive thumbnails, store/cache `file_id`, not the temporary `thumbnailLink` URL. Serve via `/api/drive-thumb/{file_id}` with a fresh Drive lookup and 302 redirect.
- Thumbnails are intentionally Drive-backed. Do not replace with Meta API thumbnails unless the user explicitly reopens that architecture.

## Auth And Users

Auth uses:

- FastAPI + Jinja2.
- `passlib/bcrypt`.
- HMAC-SHA256 signed session cookies.
- Invite links at `/invite/{token}`.

Access rules:

- Roles: `admin`, `analista`, `trafego`, `leitura`.
- Product scope is based on launch code prefixes: `PBB`, `PES`, `PI`, `PERPETUO`, `ALL`.
- Do not expose admin bootstrap credentials or password values in docs or chat.

Database routing:

- Analytics queries use the analytics DB engine from `SUPABASE_DB_URL`.
- Users, invites, launch config, Hotmart, and TMB use the operational DB engine from `SUPABASE_USERS_URL`.
- Cross-database joins do not work directly; fetch launch/product context separately before querying operational sales tables.
- `hotmart_clean_oficial` and `tmb_clean_oficial` are operational/external sales tables. Treat them as read-only unless the user explicitly authorizes writes/imports.

## ETL

Main ETL files:

- `etl/run_all.py`: ETL orchestrator for API mode or CSV mode.
- `etl/etl_meta_ads.py`: Meta Ads ETL.
- `etl/etl_google_ads.py`: Google Ads ETL.
- `etl/etl_active_campaign.py`: Active Campaign ETL.
- `etl/etl_typeform.py`: Typeform ETL.
- `etl/scheduler.py`: hourly scheduler with rolling window.
- `etl/schema.sql`: database schema and views.
- `etl/db.py`: SQLAlchemy engine factory for ETL.

Shared DB utilities:

- `src/db_engine.py`: shared SQLAlchemy engine factory, pool tuning, statement timeout, and read-only guard.

Current source-of-truth direction:

```text
Platform/API -> ETL -> Supabase -> App
```

CSV mode exists as a fallback and for historical imports.

ETL rules:

- Prefer Google Ads API imports for new work; CSV imports miss some P-Max and YouTube `video_id` details.
- For Google Ads API launch imports, use `--launch-code`; it deletes existing rows for that launch before insert and avoids duplicate imports.
- Google Ads P-Max uses `asset_group`, not `ad_group_ad`; keep the separate P-Max query path.
- Do not delete Google campaigns just because their names contain `[MA]`; users may have incorrectly named real Google campaigns with `[MA]`.
- Avoid aggregated Google CSV rows like `[GA][total-campanhas]`; use campaign/ad-level exports.
- `etl/scheduler.py` runs a rolling 3-day window and writes `etl/scheduler.log`; if the machine restarts, verify whether it is still running.
- Running frontend modules outside uvicorn may require `PYTHONPATH=<repo>\\src`.
- Typeform account is cancelled (since 2026-08); `_get_typeform_forms()`/`read_typeform()` in `frontend/db_readers/typeform.py` read from Supabase backup tables (`typeform_forms`, `typeform_forms_2`, `typeform_respostas_backup`, `typeform_respostas_backup_2`) instead of the API. Launches from `PBB-AGO-26` onward use a separate internal survey system (`formularios`/`perguntas`/`submissoes`/`respostas` tables) instead of Typeform; both sources are merged transparently by the same reader functions. The user-facing page is `/pesquisas` (`/typeform` redirects there for legacy links).

## External APIs

The project uses these API families when credentials are present:

- Meta Marketing API
- Google Ads API
- Active Campaign API
- Google Drive API for media/thumbnails in parts of the system
- Hotmart/TMB data through the operational database or imported exports

Key environment variables are documented in `.env.example`.

Important variable names:

- `SUPABASE_DB_URL`
- `SUPABASE_USERS_URL`
- `META_ACCESS_TOKEN`
- `META_AD_ACCOUNT_ID`
- `GOOGLE_ADS_*`
- `AC_API_URL`
- `AC_API_KEY`
- `TYPEFORM_TOKEN`
- `TYPEFORM_FORM_ID`
- `BRABO_USER`
- `BRABO_PASS`
- `SECRET_KEY`
- `ERROR_WEBHOOK_URL`

Rules:

- Never paste real tokens, URLs with credentials, or passwords into documentation or chat.
- Prefer reading `.env.example` for variable names.
- Read `.env` only when needed to run or debug locally, and never disclose values.
- If an API call or dependency install fails because of restricted network access, request permission before retrying with elevated access.

Google Drive media rules:

- The Drive folder for creatives is configured per launch in `launch_config.drive_folder_url`.
- The Drive folder must be shared with the configured service account.
- File names should contain the `ADXXX` code so thumbnails/previews map to creative rows.

## Analysis System

Analysis work usually lives in:

- `documentacao/analises/`
- `analises/[LAUNCH-CODE]/`
- `scripts-python/`
- `performance-manager/`

Important reusable analysis docs:

- `documentacao/analises/HANDOFF_CRIATIVOS_REUTILIZAVEL.md`
- `documentacao/analises/README_ANALISE.md`
- `documentacao/METODOLOGIA_EXTRACAO_DADOS.md`
- `documentacao/ARQUITETURA.md`

When producing or changing analyses:

- Check whether the current flow is DB/API-backed or CSV-backed before changing code.
- Preserve the distinction between lead data, survey answers, media platform metrics, and confirmed sales.
- Treat ROAS and CPA as attribution metrics based on real sales joined through UTMs/email, not only platform-reported conversions.
- Validate launch code handling across PBB, PES, and PI instead of hardcoding one launch when making reusable logic.
- Keep generated or historical reports in the existing launch folder structure.
- For `PES-MAI-26` and later, treat `utm_term` as the primary creative/ad field when present; older launches may rely more on `utm_content`.
- When matching creative performance, search all available UTM fields before declaring attribution missing.
- Typeform "do zero" analysis should deduplicate by email using the latest response before joining with CRM when following the validated historical rule.

## Documentation Rules

Documentation lives under `documentacao/`.

Required root docs include:

- `documentacao/BRABO_ANALYTICS_APRESENTACAO_EXEC.md`
- `documentacao/ARQUITETURA.md`
- `documentacao/CHECKLIST_DEPLOY_SEGURANCA.md`
- `documentacao/METODOLOGIA_EXTRACAO_DADOS.md`
- `documentacao/BRIEFING_BRABO.md`

Rules:

- Never create a new documentation file before checking whether an existing one should be updated.
- Session logs, one-off plans, and date-stamped status files go in `documentacao/historico/`.
- Do not delete historical docs; archive or update in place.
- When updating existing docs, edit the existing file instead of creating a new dated copy.
- When asked to "update the documentation", update `documentacao/BRABO_ANALYTICS_APRESENTACAO_EXEC.md` and any other relevant existing file.
- When editing `BRABO_ANALYTICS_APRESENTACAO_EXEC.md`, update the date in its header.

## Coding Guidelines

- Read the surrounding code before making changes.
- Follow existing module boundaries and local patterns.
- Keep edits scoped to the requested behavior.
- Do not refactor unrelated code while fixing a specific issue.
- Prefer structured parsing and existing helper APIs over ad hoc string manipulation.
- Add focused tests when behavior changes, especially for attribution, launch discovery, auth, or ETL transformations.
- Do not revert user changes unless explicitly asked.
- Avoid destructive git or filesystem commands unless the user clearly requested them.
- Never commit `.env`, Google client secret JSON files, YouTube tokens, CSV exports under `analises/` or `active-campaign/`, or files containing lead/customer PII.
- Official workspace path is `C:\dev\workspace-mmm`; if a session opens in an old OneDrive path, stop and switch to this workspace before committing or running operational changes.

## Known Current Launch Notes

Use these as context, then verify against current DB/docs before acting:

- `PBB-AGO-26` was previously misregistered as `PBB-OUT-26`; treat residual `PBB-OUT-26` references as likely stale unless the user says otherwise.
- `PBB-AGO-26` dates were corrected on 2026-08-05: Pré-Qualificação 2026-07-20 to 2026-08-14, Captação 2026-08-03 to 2026-08-17, live classes/event 2026-08-17 to 2026-08-20.
- `PES-SET-26` confirmed calendar: Pré-Qualificação 2026-08-17 00:00 to 2026-09-11 18:00, Captação 2026-08-31 00:00 to 2026-09-14 18:00, live classes 2026-09-14 to 2026-09-17, cart 2026-09-17 to 2026-09-28.
- `PI-AGO-26` pre-qualification real end was confirmed as 2026-08-07, even if older `launch_config` data says otherwise.

## Verification

Choose verification based on the change:

- Frontend route/template changes: run or import the FastAPI app where practical and manually check the affected route.
- ETL changes: run the relevant ETL command on a narrow date range or with a small CSV fixture.
- DB query changes: validate against expected table/view names and failure modes when Supabase is unavailable.
- Docs-only changes: no test run required, but check links and file placement.

Common commands:

```powershell
python -m pytest
```

```powershell
python -m uvicorn frontend.app:app --reload
```

## Claude Memory Migration

This file was created from repository-visible Claude guidance, project documentation, and the exported Claude memory files under `claude-memory-export/`.

The durable rules from the export have been incorporated here. The export folder itself is local/private context and should not be committed.

Good candidates to migrate:

- Stable business rules.
- API usage assumptions.
- Launch naming and folder conventions.
- Analysis methodology.
- Known gotchas that repeatedly affected the project.
- Operational runbooks.

Do not migrate:

- Secrets.
- Temporary chat history.
- One-off debugging notes that are no longer true.
- Personal/private data that is not required for project work.
