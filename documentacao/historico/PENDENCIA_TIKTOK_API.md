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

## Campos esperados

- `date`
- `campaign_name`
- `adgroup_name`
- `ad_name`
- `spend`
- `impressions`
- `clicks`
- `ctr`
- `cpc`
- `cpm`
- `conversions`
- `cost_per_conversion`
- `lancamento_codigo`

## Observação importante

Hoje o projeto já está em modelo:

`Plataforma/API -> ETL -> banco -> app`

Para TikTok, seguir exatamente esse padrão.

## Status

- Pendente
- Não iniciar agora
- Retomar depois da frente atual
