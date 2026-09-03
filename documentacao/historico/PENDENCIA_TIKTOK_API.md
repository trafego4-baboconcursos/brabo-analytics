# Pendência: integração TikTok Ads API

## Objetivo

Adicionar extração direta do TikTok Ads no mesmo padrão já usado para:

- Meta Ads
- Google Ads
- Typeform
- Active Campaign

## Decisão registrada

- **Não contar com MCP** para TikTok neste projeto.
- O caminho esperado é **API própria do TikTok Ads** + **ETL dedicado** + **banco** + **leitura pelo app**.

## Arquitetura desejada

1. `TikTok Ads API`
2. `etl_tiktok_ads.py`
3. tabela no Supabase, sugestão: `tiktok_ads_daily`
4. leitura no app via `frontend/database_reader.py`

## Status da conta (31/08/26)

- Já existe conta de anúncios TikTok Ads ativa (advertiser).
- **Falta criar o app no TikTok for Business Developers** (App ID/Secret) e gerar o access token.

## Plano de implementação (acordado em 31/08/26)

### 1. Setup de credenciais (App Developer)

1. Acessar [TikTok for Business Developers](https://business-api.tiktok.com/portal) com a conta que administra o Business Center.
2. Criar um **App** → gera `App ID` e `App Secret`.
3. Vincular o app ao(s) **Advertiser ID(s)** da Brabo (um por produto/responsável, igual já fazem com Meta — Felipe/Ivan/Mateus; ver [[project_ad_accounts]]).
4. Rodar o fluxo de autorização (Authorization Code → `access_token`) — criar `etl/get_tiktok_token.py`, mesmo padrão do `get_google_ads_token.py`: abre o browser, captura o `auth_code` via redirect local, troca por `access_token`. Token do TikTok não expira automaticamente enquanto a permissão do app estiver ativa.

### 2. Variáveis de ambiente novas (`.env`)

```bash
TIKTOK_APP_ID
TIKTOK_APP_SECRET
TIKTOK_ACCESS_TOKEN       (gerado via --get-token)
TIKTOK_ADVERTISER_ID      (um ou mais, comma-separated — igual META_AD_ACCOUNT_ID)
```

### 3. Endpoint da API (Reporting)

TikTok Marketing API → `POST /v1.3/report/integrated/get/` com `data_level=AUCTION_AD`, `dimensions=[ad_id, stat_time_day]`, e métricas:

- **Básico/atribuição**: `spend`, `impressions`, `clicks`, `conversion` (evento de lead configurado no pixel TikTok)
- **Vídeo (hook/hold)**: `video_watched_2s`, `video_watched_6s`, `video_views_p25/p50/p75/p100`, `average_video_play`
- **Demografia/público**: endpoint separado `data_level=AUCTION_AUDIENCE` com `dimensions=[age, gender, ac]` — mesmo padrão do `google_audience`/`meta_demographics` que já existe

Escopo confirmado: puxar as três coisas (performance diária, vídeo, demografia), não só o essencial de atribuição.

### 4. Novo script `etl/etl_tiktok_ads.py`

Seguindo o padrão de `etl_meta_ads.py`/`etl_google_ads.py`:

- `--since/--until` (modo API) e `--from-csv` (fallback manual)
- `extract_launch_code()` reaproveitando a regex `(PBB|PES|PI)-\w{3}-\d{2}` do nome da campanha
- Extração do `ADXXX` do nome do anúncio (**pendente confirmar**: TikTok tem limite de caracteres menor no nome do anúncio — precisa validar se `ADxxx - Descrição` cabe)
- Grava em `tiktok_ads_daily`, upsert por `(ad_id, date, lancamento_codigo)`

### 5. Campos da tabela `tiktok_ads_daily` (`etl/schema.sql`)

Espelhando `meta_ads_daily`, com nomenclatura de vídeo do TikTok:

- `date`, `ad_id`, `ad_name`, `adgroup_id`, `adgroup_name`, `campaign_id`, `campaign_name`
- `spend`, `impressions`, `clicks`, `ctr`, `cpc`, `cpm`
- `conversions`, `cost_per_conversion` (leads)
- `video_watched_2s`, `video_watched_6s`, `video_views_p25`, `video_views_p50`, `video_views_p75`, `video_views_p100`
- `lancamento_codigo`
- `UNIQUE (ad_id, date, lancamento_codigo)`

### 6. Integração

- `etl/run_all.py`: adicionar `"tiktok_ads"` ao dict de scripts do `run_api_mode` e ao modo CSV
- `frontend/database_reader.py`: incluir TikTok nas queries de investimento total (`view_investimento_total_por_ad` precisa de `UNION` com `tiktok_ads_daily`)
- Pasta `analises/[LAUNCH]/TikTok Ads/` para exports manuais, seguindo a convenção existente

## Pontos em aberto antes de iniciar a implementação

- **Pixel/evento de conversão**: qual evento do pixel TikTok mapeia pra "lead"? (equivalente ao pixel tracking_specs do Meta — ver [[feedback_pixel_tracking_specs]])
- **Nomenclatura de anúncio**: confirmar se `ADxxx - ...` cabe no limite de caracteres do TikTok
- **Quantas contas de anunciante**: confirmar se Felipe/Ivan/Mateus todos terão conta TikTok própria, ou se começa com uma conta só

## Status

- Plano detalhado, aguardando decisão de início
- Próximo passo sugerido: criar o app no TikTok for Business Developers (passo 1) para desbloquear o resto
