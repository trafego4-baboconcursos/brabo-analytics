# Status PBB-JUN-26 - 2026-06-16

## O que foi feito

- `PBB-JUN-26` já existia em `dim_lancamentos`.
- Período cadastrado no banco: `2026-05-11` a `2026-06-22`.
- Rodada de ETL via API até `2026-06-16`:
  - Meta Ads: `etl/run_all.py --since 2026-05-11 --until 2026-06-16 --only meta_ads`
  - Google Ads: `etl/run_all.py --since 2026-05-11 --until 2026-06-16 --only google_ads`
  - Typeform: `etl/run_all.py --since 2026-05-11 --until 2026-06-16 --only typeform`
- Leads ActiveCampaign foram importados por CSV local, não pela API, por volume/performance:
  - Arquivo: `analises/[PBB-JUN-26]/active campaign/active-campaign-pbb-jun-26.csv`
  - Comando:
    ```bash
    python etl/etl_active_campaign.py --from-csv "analises\[PBB-JUN-26]\active campaign\active-campaign-pbb-jun-26.csv" --launch-code PBB-JUN-26
    ```
- Cache do painel local foi limpo para `PBB-JUN-26`.

## Esclarecimento importante sobre "extração direta"

Para `PBB-JUN-26`, já começamos a operar no modelo de **extração direta das plataformas para o banco** em parte relevante do pipeline.

Isso significa:

- **Meta Ads**: extraído via API e gravado em `meta_ads_daily`
- **Google Ads**: extraído via API e gravado em `google_ads_daily`
- **Typeform**: extraído via API e gravado em `typeform_respostas`

Mas o **dashboard ainda não consome essas plataformas em tempo real**. O fluxo atual é:

1. Plataforma/API
2. ETL (`etl/`)
3. Supabase / banco
4. App FastAPI lê do banco

Ou seja: o projeto já está em **extração direta para o banco**, mas ainda não em **leitura direta da plataforma pelo frontend**.

### Estado por fonte no app atual

- **Meta Ads**: app lê do banco (`meta_ads_daily`)
- **Google Ads**: app lê do banco (`google_ads_daily`)
- **Leads / Active Campaign**: app lê do banco (`leads`)
- **Typeform**: app lê principalmente do banco (`typeform_respostas`), com apoio pontual da API para metadados dos formulários
- **Hotmart**: app lê do banco (`hotmart_clean_oficial`)
- **TMB**: app lê do banco (`tmb_clean_oficial`)

### Observação específica de PBB-JUN-26

No caso de `PBB-JUN-26`, a impressão de que "já está vindo direto da plataforma" está correta no sentido do **ETL**. A aplicação, porém, continua consultando as tabelas já populadas no Supabase.

## Ajustes técnicos feitos

- `etl/etl_active_campaign.py`
  - `extract_launch_code` agora trata valores nulos em `utm_campaign`.
  - Adicionado fallback para inferir o código do lançamento pelo caminho do arquivo.
  - Adicionado argumento `--launch-code` para filtrar a carga e evitar importar UTMs antigas misturadas no CSV.

## Totais validados após carga

- Meta Ads:
  - Leads pixel: `19.496`
  - Spend atual: `R$ 87.241,78`
- Google Ads:
  - Conversões: `35.971`
  - Custo: `R$ 202.646,05`
- Leads CRM:
  - `72.235`
- Typeform:
  - `12.982`
- Vendas:
  - Ainda vazio no painel.
  - Aguardando TI finalizar/popular Hotmart/TMB no banco.

## Atenção: custo Meta Ads possivelmente fora do escopo esperado

Foi revisada a documentação antiga sobre problemas de valores:

- `documentacao/README_ANALISE.md`
  - Registra o erro antigo: valores `100x` inflados.
  - Regra correta documentada: não dividir por `100` quando o valor já vem em reais.
  - Para CSV Meta/Facebook, `Valor usado (BRL)` deve ser convertido como decimal direto.
- `documentacao/ATUALIZACAO_12_MAIO_2026.md`
  - Reforça que o erro antigo era manipulação monetária incorreta.
  - Também registra a separação Facebook vs YouTube por plataforma.

No ETL atual de API (`etl/etl_meta_ads.py`), o campo `spend` do Graph API está sendo gravado diretamente como BRL, sem dividir por `100`. Isso está alinhado com a documentação antiga.

O ponto suspeito agora não parece ser escala monetária `100x`, e sim escopo de classificação:

- O regex atual extrai `PBB-JUN-26` de nomes como `PRE-PBB-JUN-26`.
- Assim, campanhas de pré-lançamento estão entrando no lançamento `PBB-JUN-26`.
- Top spends atuais incluem:
  - `AD013 - ... PRE-PBB-JUN-26`: `R$ 8.833,80`
  - `AD021 - ... PRE-PBB-JUN-26`: `R$ 6.133,85`
  - `AD005 - ... PRE-PBB-JUN-26`: `R$ 5.520,67`
  - `AD020 - ... PRE-PBB-JUN-26`: `R$ 3.248,41`

Esses itens de `PRE-*` somam aproximadamente `R$ 23,7k` só entre os maiores criativos listados. Antes de corrigir dados no banco, decidir se `PRE-PBB-JUN-26` deve:

1. Entrar no consolidado de `PBB-JUN-26`, por ser pré-lançamento do mesmo produto.
2. Virar um código separado, por exemplo `PRE-PBB-JUN-26`.
3. Ser excluído das telas principais e usado apenas em análises de topo/pre-aquecimento.

## Próximo passo recomendado

Não alterar valores monetários ainda. Primeiro validar regra de negócio para campanhas `PRE-*`.

Se `PRE-*` deve ser separado, alterar `extract_launch_code` dos ETLs de Meta/Google/ActiveCampaign para reconhecer prefixo `PRE-` como parte do código ou classificá-lo em campo auxiliar de fase.
