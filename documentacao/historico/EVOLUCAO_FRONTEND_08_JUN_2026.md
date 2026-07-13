# Evolução do Frontend - 08/06/2026

Este documento registra a evolução feita no painel FastAPI/HTML do Brabo Analytics para evitar perda de contexto.

## Objetivo

Melhorar a experiência das páginas abertas no editor:

- `frontend/templates/funil.html`
- `frontend/templates/vendas.html`
- `frontend/templates/meta_audiences.html`
- `frontend/templates/google_audiences.html`
- `frontend/templates/base.html`
- `frontend/app.py`
- `src/readers/launch_discovery.py`

O trabalho teve dois focos:

1. Melhorar a leitura analítica das páginas de funil, vendas e audiências.
2. Reorganizar o menu lateral por produto, porque hoje existem 3 produtos:
   - INSS: lançamentos com prefixo `PI`
   - TJ-SP: lançamentos com prefixo `PES`
   - Banco do Brasil: lançamentos com prefixo `PBB`

## Estado anterior

O seletor de lançamentos da sidebar mostrava uma lista plana:

- `ABR`
- `FEV`
- `JAN`
- `MAI`
- `MAR`
- `PI-ABR`
- `PI-JAN`

Isso misturava produto e mês no mesmo nível. O usuário precisava inferir que:

- `PES` representa TJ-SP
- `PBB` representa Banco do Brasil
- `PI` representa INSS

Também havia páginas com blocos analíticos mais simples, pouco diagnóstico e algumas mensagens de "CSV não encontrado" que pareciam erro de tela mesmo quando o lançamento realmente não tinha aquele tipo de dado.

## Mudanças principais

### 1. Menu lateral por produto

Arquivos:

- `src/readers/launch_discovery.py`
- `frontend/app.py`
- `frontend/templates/base.html`

Foi adicionada a noção de produto no objeto `Launch`:

- `product`
- `product_name`
- `product_order`

Mapeamento atual:

| Prefixo | Produto | Nome completo | Ordem |
| :--- | :--- | :--- | ---: |
| `PI` | INSS | Instituto Nacional do Seguro Social | 1 |
| `PES` | TJ-SP | Tribunal de Justiça de São Paulo | 2 |
| `PBB` | Banco do Brasil | Banco do Brasil | 3 |

O `frontend/app.py` agora cria `launch_groups` no contexto base dos templates. O `base.html` usa esse agrupamento para renderizar o switcher assim:

- INSS
  - JAN
  - ABR
- TJ-SP
  - JAN
  - MAR
  - MAI
- Banco do Brasil
  - FEV
  - ABR

Dentro de cada produto, o botão mostra apenas o mês. O produto já esta no cabecalho do grupo.

Também foi ajustado o link do switcher para manter a página atual ao trocar de lançamento:

```jinja2
href="{{ request.url.path }}?launch_code={{ l.code }}"
```

Antes, trocar de lançamento sempre voltava para o dashboard.

### 2. `launch_discovery.py` foi normalizado

O arquivo estava com textos em mojibake no terminal. Ele foi reescrito em ASCII para reduzir problemas de encoding e facilitar manutencao.

Comportamento preservado:

- Descobre pastas no padrão `[CODIGO-MES-ANO]`.
- Calcula flags:
  - `has_meta`
  - `has_google`
  - `has_vendas`
  - `has_ac`
  - `has_typeform`
- Mantem `get_launch()`.

Comportamento novo:

- Adiciona metadados de produto.
- Mantem a lista principal de lançamentos sem reordenar, para não mudar o lançamento padrão escolhido pelo app.
- A ordenacao por produto acontece apenas no agrupamento visual criado em `frontend/app.py`.

### 3. Página de funil

Arquivo:

- `frontend/templates/funil.html`

Melhorias:

- KPIs consolidados:
  - investimento total
  - receita total
  - ROAS
  - leads + conversoes
  - cliques totais
  - vendas totais
- Funil visual com etapas:
  - ThruPlays Meta + Cliques Google
  - Cliques totais
  - Leads Meta + Conversoes Google
  - Vendas Hotmart + TMB
- Taxas destacadas:
  - TP para clique
  - clique para lead/conversao
  - lead para venda
  - ROAS
- Diagnóstico de investimento:
  - mix de verba Meta vs Google
  - gargalos principais
- Tabelas por etapa:
  - Meta Ads por etapa
  - Google Ads por etapa

Importante: a página usa apenas dados que já vinham do backend (`meta`, `google`, `vendas`, `receita`, `invest`, `roas`). Não houve mudanca nos readers de Meta/Google/Vendas para essa tela.

### 4. Página de vendas

Arquivo:

- `frontend/templates/vendas.html`

Melhorias:

- KPIs:
  - receita total
  - vendas totais
  - Hotmart
  - TMB
- Metodos de pagamento Hotmart com barras percentuais.
- Distribuição de receita Hotmart vs TMB.
- Novo bloco "Diagnóstico Comercial":
  - ticket medio por plataforma
  - mix de vendas por plataforma

Também foram trocados emojis por icones Tabler em varios pontos.

### 5. Página Meta Audiências

Arquivo:

- `frontend/templates/meta_audiences.html`

Melhorias:

- KPIs adicionais:
  - investimento Meta
  - leads totais
  - cliques
  - impressoes
- Tabela por temperatura de público.
- Leitura rapida:
  - maior alocacao de verba
  - melhor CPL
- Tabela por bucket de campanha.

Observação: a página depende de `meta.por_temperatura` e `meta.por_bucket`, gerados pelo `src/readers/meta_reader.py`.

### 6. Página Google Audiências

Arquivo:

- `frontend/templates/google_audiences.html`

Melhorias:

- KPIs:
  - custo Google
  - segmentos ativos
  - cliques
  - conversoes
- Destaques:
  - segmento com maior investimento
  - conversoes dos públicos listados
- Tabela de públicos com:
  - posicao
  - segmento
  - campanha
  - custo
  - percentual da lista
  - cliques
  - conversoes
  - CPC
  - CTR

Observação: essa página depende de `google.públicos`. Se o CSV de públicos não existir ou não for lido, ela mostra estado vazio.

## Diagnóstico sobre PI-ABR-26

Foi investigado por que varias telas exibiam mensagens como:

```text
CSV Meta Ads não encontrado
Adicione o export em analises/[PI-ABR-26]/Meta Ads/*.csv
```

Resultado do discovery:

```text
PI-ABR-26 meta=False google=False vendas=True ac=True
```

Ou seja:

- A pasta `[PI-ABR-26]` existe.
- As subpastas `Meta Ads` e `Google Ads` existem.
- Mas não foram encontrados CSVs dentro dessas subpastas.
- Ha arquivos em `Active Campaign` e `Vendas`.

Portanto, para `PI-ABR-26`, as páginas que dependem de Meta/Google vao mostrar estado vazio ate que existam CSVs nas pastas:

```text
analises/[PI-ABR-26]/Meta Ads/*.csv
analises/[PI-ABR-26]/Google Ads/*.csv
```

Isso não foi causado pela mudanca visual. E um estado real dos dados detectados.

## Validações feitas

### Sintaxe Jinja

Foi validada a sintaxe dos templates com os filtros usados pelo app:

- `brl`
- `num`
- `pct`

Templates validados:

- `funil.html`
- `vendas.html`
- `meta_audiences.html`
- `google_audiences.html`
- `base.html`
- `dashboard.html`

### Renderização com dados de teste

Os templates principais foram renderizados com objetos mockados para capturar erros de runtime Jinja.

Resultado:

```text
OK funil.html
OK vendas.html
OK meta_audiences.html
OK google_audiences.html
```

### Renderização via FastAPI

Foi iniciado um servidor temporario em porta alternativa e validada a URL:

```text
/funil?launch_code=PI-ABR-26
```

Resultado:

```text
STATUS=200
HAS_INSS=True
HAS_TJSP=True
HAS_BB=True
```

Isso confirmou que o menu agrupado por produto renderiza corretamente.

## Como testar localmente

A partir da pasta `frontend`:

```powershell
python -m uvicorn app:app --host 127.0.0.1 --port 8012
```

Abrir:

```text
http://127.0.0.1:8012/
http://127.0.0.1:8012/funil?launch_code=PI-ABR-26
http://127.0.0.1:8012/vendas?launch_code=PI-ABR-26
http://127.0.0.1:8012/meta-audiences?launch_code=PBB-ABR-26
http://127.0.0.1:8012/google-audiences?launch_code=PBB-ABR-26
```

Se já houver servidor antigo rodando, reiniciar para carregar os arquivos alterados.

## Pendencias e proximos passos recomendados

1. Melhorar os estados vazios por tipo de dado.
   - Hoje a mensagem e correta, mas pode ficar mais contextual:
     - "Este lançamento ainda não tem CSV de Meta Ads"
     - "Dados disponíveis neste lançamento: Vendas, Active Campaign"

2. Verificar CSVs faltantes de `PI-ABR-26`.
   - Meta Ads: pasta existe, mas sem CSV detectado.
   - Google Ads: pasta existe, mas sem CSV detectado.

3. Revisar nomês exibidos nos lançamentos.
   - O mapeamento foi corrigido para:
     - `PES` = TJ-SP
     - `PBB` = Banco do Brasil
     - `PI` = INSS

4. Padronizar textos com acento depois.
   - Alguns arquivos foram mantidos em ASCII para evitar novos problemas de encoding no Windows/PowerShell.

5. Melhorar a responsividade do menu em telas menores.
   - O switcher esta melhor hierarquizado, mas ainda pode ganhar colapso/accordion se a quantidade de lançamentos crescer.

## Atualizacao: Comparador V1/V2

Foi implementada a primeira versao da página:

```text
/comparativo-v1-v2
```

Objetivo:

- Validar a V2 dinâmica contra a V1 estática antes de evoluir mais a interface.
- Mostrar disponibilidade de dados V2 por lançamento.
- Mostrar quais relatórios V1 existem para o lançamento ativo.
- Abrir V1 e V2 lado a lado para conferencia manual.

Arquivos alterados:

- `frontend/app.py`
- `frontend/templates/base.html`
- `frontend/templates/comparativo_v1_v2.html`

Comportamento:

- A página exibe KPIs V2 principais:
  - investimento
  - receita
  - ROAS
  - leads/conversoes
- A página mostra saúde dos dados:
  - Meta Ads
  - Google Ads
  - Vendas
  - Active Campaign
  - Typeform
- A matriz de comparacao lista:
  - Dashboard / Índice
  - Funil
  - Meta Ads
  - Google Ads
  - Vendas
  - Meta Audiências
  - Google Audiências
- Links V1 so aparecem quando o HTML existe no disco.
- Links V2 sempre apontam para a página dinâmica correspondente com `launch_code`.
- Ainda não ha parsing automático dos HTMLs V1; a validação e assistida/manual.

Validações executadas:

```text
/comparativo-v1-v2?launch_code=PBB-ABR-26 -> 200
/comparativo-v1-v2?launch_code=PI-ABR-26  -> 200
```

Resultados esperados confirmados:

- `PBB-ABR-26` mostra links V1 disponíveis.
- `PI-ABR-26` mostra CSVs ausentes para Meta/Google quando não ha dados.
- `PI-ABR-26` mostra "Sem HTML V1" quando o relatório estático não existe.
- O menu lateral ganhou o item `Comparar V1/V2` na seção `Versoes`.

## Atualizacao: Funil V2 alinhado a V1

A página `/funil` foi realinhada para seguir a hierarquia da V1 `ANALISE_FUNIL_[CODIGO].html`.

Mudanças principais:

- Corrigido parsing numérico nos readers de Meta, Google e Vendas.
  - Valores com decimal `6.31` continuam como decimal.
  - Valores com milhar `114.586` passam a ser tratados como `114586`.
  - Valores BR `29.564,65` continuam como `29564.65`.
- O funil passou a usar `Leads CRM` do Active Campaign quando disponível.
- Adicionado contador simples de respostas Typeform para a etapa `Responderam a pesquisa`.
- A ordem das secoes passou a seguir a V1:
  - KPIs do Funil Completo
  - Meta Ads por etapa de funil
  - Google Ads por etapa de funil
  - Distribuição de verba Meta Captação vs Meta Estrategica
  - Performance por temperatura de público
  - Pré-Qualificação
  - Criativos Validados vs Novos
  - Comparativo de canais
  - Curva Diária - Meta Ads (Fases do Lançamento)
  - Diagnóstico e recomendações

Atualizacao complementar:

- `meta_reader.py` passou a gerar `meta.por_dia`.
- `meta.por_dia` agrega por data:
  - gasto
  - leads
  - thruplays
  - cliques
  - distribuição por etapa
  - CPL diário
- A seção `9. Curva Diária - Meta Ads (Fases do Lançamento)` foi adicionada ao funil.
- O diagnóstico foi renumerado para seção 10.

Atualizacao de vendas/faturamento:

- `vendas_reader.py` passou a normalizar nomês de colunas com acentos antes de detectar campos.
- Hotmart passou a aplicar a regra especial de `Recuperador Inteligente`:
  - `Quantidade de cobranças == 1` entra como nova venda.
  - nesses casos, o valor e multiplicado por `Quantidade total de parcelas`.
  - demais recorrencias de RI ficam fora do total.
- TMB passou a somar todas as linhas com `Ticket do pedido` positivo para seguir a paridade do funil V1.
- A regra e global para todos os lançamentos Hotmart; não ha exceção fixa por código de lançamento.
- No `PBB-ABR-26`, a regra global reproduz a paridade da V1:
  - Hotmart: 378 vendas, R$ 598.854,30
  - TMB: 170 vendas, R$ 279.237,80
  - Total: 548 vendas, R$ 878.092,10

Validação executada:

```text
http://127.0.0.1:8026/funil?launch_code=PBB-ABR-26 -> 200
R$ 878.092,10 -> presente
Hotmart: R$ 598.854,30 | TMB: R$ 279.237,80 -> presente
Hotmart: 378 | TMB: 170 -> presente
R$ 1.602,36 -> presente
```

## Atualizacao: tabelas do funil com vendas, faturamento e ROAS

Depois da paridade dos totais de vendas, as tabelas da página `/funil` passaram a incluir métricas comerciais rastreadas por UTM/Active Campaign.

Mudanças principais:

- `frontend/app.py` passou a gerar `sales_attr`.
- `sales_attr` cruza:
  - compradores Hotmart/TMB por e-mail
  - leads do Active Campaign por e-mail
  - UTMs do lead (`utm_source`, `utm_medium`, `utm_campaign`, `utm_content`)
- O cruzamento gera agregacoes para:
  - canal: Meta Ads, Google Ads, Outros
  - etapa: Captação, Pré-Qualificação, RMK/Engajamento, Pitch/ROAS, Outros
  - bucket Meta: Principal, Potencial, Reels, Novos Ads, Outros
  - temperatura Meta: Quente, Frio, Especifico, Outros
  - criativo por `ADxxx`, extraido de `utm_content`
- `src/readers/vendas_reader.py` passou a manter `receita_por_email`, permitindo somar faturamento por dimensão rastreada.

Tabelas atualizadas:

- Meta Ads por etapa:
  - vendas
  - faturamento
  - ROAS
- Google Ads por etapa:
  - vendas
  - faturamento
  - ROAS
- Distribuição de verba Meta por bucket:
  - vendas
  - faturamento
  - ROAS
- Temperatura de público:
  - vendas
  - faturamento
  - ROAS
- Comparativo Meta vs Google:
  - vendas
  - faturamento
  - ROAS
- Criativos Validados vs Novos:
  - layout vertical: Validados em cima, Novos embaixo
  - vendas por `ADxxx`
  - faturamento por `ADxxx`
  - ROAS por `ADxxx`

Observação importante:

- As métricas comerciais por tabela representam apenas vendas rastreadas por UTM/Active Campaign.
- Portanto, podem não somar 100% das vendas totais do lançamento.
- Para `PBB-ABR-26`, a validação atual encontrou:
  - 406 compradores rastreados por UTM/Active
  - Meta Ads: 199 vendas, R$ 320.420,43, ROAS 1,80x
  - Google Ads: 205 vendas, R$ 331.230,25, ROAS 1,76x
  - Outros: 2 vendas, R$ 2.952,08

## Atualizacao: layout e acentuacao

Mudanças visuais recentes:

- A seção `1. KPIs do Funil Completo` foi redesenhada:
  - funil visual a esquerda
  - cards de KPI a direita
  - funil em barras trapezoidais coloridas
  - chips de taxas de conversao abaixo do funil
- As tabelas do funil receberam:
  - `colgroup` para larguras fixas
  - cabeçalhos numéricos alinhados a direita
  - `table-layout: fixed`
  - overflow horizontal em telas menores
- Titulos e rótulos visíveis foram acentuados:
  - Análise -> Análise
  - Segmentacao -> Segmentação
  - Diagnóstico -> Diagnóstico
  - Distribuição -> Distribuição
  - Captação -> Captação
  - Pré-Qualificação -> Pré-Qualificação
  - Público -> Público
  - Métrica -> Métrica
  - Lançamento -> Lançamento
  - Recomendações -> Recomendações
- Menu lateral:
  - `V1 Índice Geral` virou `V1 Índice Geral`
  - `V1 Lançamento` virou `V1 Lançamento`

Porta oficial de validação atual:

```text
http://127.0.0.1:8026/funil?launch_code=PBB-ABR-26
```

## Atualizacao: página de criativos

A página `/criativos` passou a ter uma leitura própria de ranking por criativo, diferente da leitura por temperatura/bucket do funil.

Mudanças principais:

- A seção `2. Ranking Geral` agora consolida todos os ADs de captação por código `ADxxx`.
- O mesmo AD rodando em varias campanhas deixa de aparecer quebrado por temperatura ou bucket.
- O ranking principal une Meta Ads + Google/YouTube quando o código `ADxxx` e igual.
- O ranking principal não mostra coluna de origem e não repete `ADxxx` separado do nome; a linha exibe apenas o nome completo do criativo.
- Foram incluidos no overview:
  - investimento
  - leads
  - CPL
  - CTR
  - CPM
  - vendas rastreadas
  - faturamento rastreado
  - ROAS rastreado
- Abaixo do ranking principal, a página traz recortes separados:
  - somente Meta Ads
  - somente Google/YouTube
- Esses recortes usam investimento/leads do proprio canal e vendas/faturamento atribuídos ao canal quando a UTM permite classificar origem.
- O final da página traz um consolidado de rastreabilidade:
  - compradores unicos Hotmart + TMB por e-mail
  - compradores encontrados no Active Campaign com UTM
  - compradores sem UTM confiavel
  - respostas Typeform disponíveis
- Vendas Google rastreadas sem `ADxxx` de Search, PMax e Display entram em tabela própria:
  - `GOOGLE-PMAX`
  - `GOOGLE-SEARCH`
  - `GOOGLE-DISPLAY`
- A atribuição de vendas passou a confrontar todas as UTMs encontradas para o comprador no Active Campaign e escolhe a melhor evidência:
  - prioriza UTM do lançamento ativo
  - prioriza UTM com `ADxxx`
  - considera `utm_source`, `utm_medium`, `utm_campaign`, `utm_content` e `utm_term`
  - classifica Search/PMax/Display mesmo quando não há `ADxxx`
- `utm_term` passou a ser usado para extrair `ADxxx`, porque no Active Campaign parte relevante dos criativos estava nesse campo.
- Regra de versão das UTMs:
  - lançamentos anteriores a `PES-MAI-26` podem seguir o padrão antigo, com `ADxxx` frequentemente em `utm_content` ou em nomenclaturas históricas.
  - a partir de `PES-MAI-26`, o padrão novo passa a ser:
    - Meta/Facebook:
      - `utm_source=facebook`
      - `utm_medium=paid_social`
      - `utm_campaign={{campaign.name}}`
      - `utm_content={{adset.name}}`
      - `utm_term={{ad.name}}`
      - `vk_source=paid_metaads`
      - `vk_ad_id={{ad.id}}`
    - YouTube/Google:
      - `utm_source=google`
      - `utm_medium=cpc`
      - `utm_campaign={_campaignname}`
      - `utm_content={_adgroupname}`
      - `utm_term={_adname}`
      - `vk_source=paid_googleads`
      - `vk_ad_id={creative}`
  - Portanto, para `PES-MAI-26` em diante, `utm_term` deve ser tratado como o campo principal de criativo/anúncio.
- A análise automática usa parâmetros consistentes:
  - volume de vendas rastreadas
  - faturamento atribuído
  - ROAS
  - eficiência de CPL
  - CTR/CPM
  - investimento sem venda rastreada

Arquivos alterados:

- `src/readers/meta_reader.py`
  - adicionou `captacao_por_ad`, consolidando captação Meta por `ADxxx`.
- `src/readers/google_reader.py`
  - adicionou `anuncios_por_ad`, lendo o export `performance-dos-anuncios` e consolidando Google/YouTube por `ADxxx`.
- `frontend/app.py`
  - adicionou `_creative_overview`.
  - adicionou `por_criativo_canal` em `_sales_attribution`.
  - adicionou `google_sem_ad_por_tipo` para classificar vendas Google sem `ADxxx`.
  - adicionou seleção da melhor UTM do comprador antes de atribuir venda.
  - rota `/criativos` passou a enviar `creative_overview`, `sales_attr`, `vendas` e `typeform_count`.
- `frontend/templates/criativos.html`
  - redesenhou a página com ranking unificado, diagnóstico final e recortes por canal.

Validação executada:

```text
http://127.0.0.1:8026/criativos?launch_code=PBB-ABR-26 -> 200
Ranking Geral -> presente
Google / YouTube -> presente
AD050 -> presente

http://127.0.0.1:8030/criativos?launch_code=PES-MAI-26 -> 200
GOOGLE-PMAX -> presente
GOOGLE-SEARCH -> presente
GOOGLE-DISPLAY -> presente
GOOGLE-GERACAO-DEMANDA -> presente
```

## Mapa rápido de arquivos

| Arquivo | Papel |
| :--- | :--- |
| `src/readers/launch_discovery.py` | Descobre lançamentos e atribui produto, cor, nome e flags de dados |
| `src/readers/vendas_reader.py` | Lê vendas Hotmart/TMB, aplica regra RI global e guarda receita por e-mail |
| `src/readers/meta_reader.py` | Lê Meta Ads e consolida criativos de captação por AD |
| `src/readers/google_reader.py` | Lê Google Ads e consolida anúncios de captação por AD |
| `frontend/app.py` | Monta contexto global, cria `launch_groups`, calcula atribuição de vendas por UTM |
| `frontend/templates/base.html` | Sidebar, switcher por produto, navegação global, CSS base e estilos das tabelas |
| `frontend/templates/funil.html` | Análise consolidada de funil, investimento, vendas, faturamento e ROAS |
| `frontend/templates/criativos.html` | Ranking unificado de criativos Meta + Google/YouTube por AD, vendas, faturamento e ROAS |
| `frontend/templates/vendas.html` | Análise comercial Hotmart + TMB |
| `frontend/templates/meta_audiences.html` | Audiências Meta por temperatura e bucket |
| `frontend/templates/google_audiences.html` | Públicos Google por investimento e performance |
