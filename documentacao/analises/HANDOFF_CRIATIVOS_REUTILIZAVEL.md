# Handoff: Criativos Reutilizavel

## Objetivo

Este documento resume o estado atual da analise de criativos, as regras de dados validadas e como evoluir o gerador em outro chat sem depender do historico anterior.

Escopo principal desta entrega:
- validar se os dados de `ANALISE_CRIATIVOS_[PBB-ABR-26].html` saem dos CSVs
- revisar o Python para reaproveitamento em outros lancamentos
- manter a pagina final atual intacta

## Arquivos principais

HTML final atual, com reorganizacao manual e ajustes visuais:
- `analises/[PBB-ABR-26]/ANALISE_CRIATIVOS_[PBB-ABR-26].html`

HTML de teste gerado pelo novo pipeline reutilizavel:
- `analises/[PBB-ABR-26]/ANALISE_CRIATIVOS_TESTE_[PBB-ABR-26].html`

Novo gerador reutilizavel:
- `scripts-python/generate_analise_criativos_launch.py`

Geradores antigos ou especificos por campanha:
- `scripts-python/generate_analise_criativos_abr_v2.py`
- `scripts-python/generate_analise_criativos_pes_mai.py`
- `scripts-python/generate_analise_criativos_FINAL.py`

Resolver de nomes de CSV:
- `scripts-python/csv_resolver.py`

## O que foi validado

A pagina atual de criativos do PBB-ABR-26 esta baseada em CSVs. O que era manual era a composicao visual do HTML final, nao os numeros.

KPIs principais validados contra os CSVs:
- vendas totais: `548`
- vendas rastreadas: `407`
- vendas nao rastreadas: `141`
- leads totais: `86.025`
- leads com UTM: `84.228`
- faturamento total: `R$ 878.092,10`
- investimento total: `R$ 360.405,75`
- meta: `R$ 175.523,24`
- google: `R$ 184.882,51`

Top criativos por vendas tambem bateu com os CSVs, incluindo:
- `AD050`: 55 vendas
- `AD092`: 53 vendas
- `AD113`: 52 vendas
- `AD110`: 44 vendas
- `AD054`: 38 vendas

Bloco `Pesquisa + Captacao / do zero` tambem foi validado e ficou alinhado com a pagina atual.

## Regra real dos dados

### 1. Leads CRM

Fonte:
- pasta `analises/[campanha]/Active Campaign/`

Regra:
- usar o CSV mais recente da pasta
- normalizar `Email` para lowercase e trim
- considerar apenas linhas com `*Utm_content` preenchido para atribuicao por criativo
- extrair `ADXXX` de `*Utm_content`

Importante:
- para paridade com o dashboard validado, nao usar fallback para `utm_term` nesse fluxo
- quando o gerador abriu demais esse criterio, os leads com UTM subiram de `84.228` para `86.025` e a paridade foi perdida

### 2. Hotmart

Fonte:
- `analises/[campanha]/Vendas/hotmart-<campanha>.csv`
- aliases antigos tambem sao suportados

Regra:
- normalizar email do comprador
- excluir `Recuperador Inteligente`, exceto quando `Quantidade de cobrancas == 1`
- nesses casos, usar `Faturamento liquido do(a) Produtor(a) * Quantidade total de parcelas`

Essa e a regra que reproduziu os totais da pagina validada.

### 3. TMB

Fonte:
- `analises/[campanha]/Vendas/tmb-<campanha>.csv`
- aliases antigos tambem sao suportados

Regra para paridade com a pagina atual:
- ler todas as linhas
- nao filtrar por status `Vigente`
- normalizar email e converter `Ticket do pedido`

Importante:
- quando o gerador filtrou TMB por `Vigente`, o total caiu de `548` para `545`

### 4. Meta Ads

Fonte:
- `analises/[campanha]/Meta Ads/`

Regra:
- carregar campanhas completas
- filtrar criativos de captacao pelo nome da campanha contendo `capta`
- extrair `ADXXX` de `Nome do anuncio`
- usar `Cliques (todos)` e fallback para `Cliques no link` quando necessario

### 5. Google Ads

Fonte:
- `analises/[campanha]/Google Ads/google-ads-performance-dos-anuncios-<campanha>.csv`

Regra:
- carregar export por anuncios com `skiprows=2`
- extrair `ADXXX` de `Nome do anuncio`
- somar `Custo` por criativo
- esse valor entra no investimento total e no ROAS consolidado

Importante:
- quando o gerador ignorou Google Ads, o investimento total caiu para `R$ 151.066,91`

### 6. Typeform e bloco `do zero`

Fonte:
- `analises/[campanha]/Typeform/typeform-pesquisa-<campanha>.csv`

Pergunta usada:
- `Em relacao aos estudos para concursos publicos, voce se considera?`

Classificacao de `do zero`:
- resposta exata `Estou do zero`

Regra de deduplicacao que bate com a pagina atual:
- deduplicar o Typeform por email usando a ultima resposta do email
- so depois fazer o join com CRM por email
- em seguida quebrar por `ad_id`

Se essa deduplicacao for feita de outro jeito, aparecem pequenas diferencas de 1 a 5 respostas por criativo.

## Estado do codigo

### Arquivo recomendado para evolucao

Use este arquivo como base daqui para frente:
- `scripts-python/generate_analise_criativos_launch.py`

Ele ja faz:
- configuracao via argumentos de linha de comando
- resolucao de nomes canonicos e aliases de CSV
- leitura de CRM, Hotmart, TMB, Meta e Google
- classificacao `Validado` vs `Novo`
- cruzamento Typeform + CRM + vendas para bloco `do zero`
- geracao de HTML reutilizavel por campanha

### Arquivos antigos

Os scripts antigos continuam uteis como referencia, mas nao sao a melhor base para evolucao:
- `generate_analise_criativos_FINAL.py`: muito fixo em PBB-ABR-26
- `generate_analise_criativos_abr_v2.py`: bom historico de regra, mas ainda campaign-specific
- `generate_analise_criativos_pes_mai.py`: tentativa previa de reaproveitamento, ainda com hardcodes e substituicoes manuais

## Comando validado

Comando usado para validar o pipeline reutilizavel sem sobrescrever a pagina final manual:

```powershell
& .\.venv\Scripts\python.exe .\scripts-python\generate_analise_criativos_launch.py \
  --campaign-code PBB-ABR-26 \
  --campaign-folder [PBB-ABR-26] \
  --product-name "Banco do Brasil" \
  --period-label "Abril de 2026" \
  --reference-folder [PBB-FEV-26] \
  --output-filename ANALISE_CRIATIVOS_TESTE_[PBB-ABR-26].html
```

Saida validada:
- `analises/[PBB-ABR-26]/ANALISE_CRIATIVOS_TESTE_[PBB-ABR-26].html`

## Como usar em outro lancamento

Exemplo generico:

```powershell
& .\.venv\Scripts\python.exe .\scripts-python\generate_analise_criativos_launch.py \
  --campaign-code PES-MAI-26 \
  --campaign-folder [PES-MAI-26] \
  --product-name "Escrevente TJSP" \
  --period-label "Abril a Maio de 2026"
```

Quando usar `--reference-folder`:
- use quando quiser classificar `Validado` vs `Novo` por sobreposicao de `ADXXX` com uma campanha anterior
- exemplo: `PBB-ABR-26` comparando contra `[PBB-FEV-26]`

Quando nao usar `--reference-folder`:
- o script cai na regra de naming por `[novos-ads]`

## Diferenca entre a pagina final e o gerador novo

A pagina atual em `ANALISE_CRIATIVOS_[PBB-ABR-26].html` foi reorganizada manualmente e tem:
- hierarquia visual especifica
- blocos reorganizados fora da ordem do script antigo
- menu padronizado injetado
- titulos, espacamento e textos finais ajustados manualmente

O gerador novo:
- reproduz os dados centrais e o bloco `do zero`
- gera um HTML reutilizavel e seguro para novos lancamentos
- ainda nao replica 100% o layout final artesanal do PBB-ABR-26

Em outras palavras:
- a base de dados ja esta pronta para reaproveitamento
- a camada visual ainda pode ser evoluida se quiser chegar no mesmo refinamento da pagina atual

## Proximos passos recomendados

### Opcao 1: consolidar o layout final no gerador novo

Objetivo:
- fazer `generate_analise_criativos_launch.py` emitir o mesmo padrao visual do HTML manual atual

Vantagem:
- elimina divergencia entre pagina final e pipeline reutilizavel

### Opcao 2: criar wrappers por campanha

Objetivo:
- adicionar scripts pequenos, por exemplo:
  - `generate_analise_criativos_pbb_abr.py`
  - `generate_analise_criativos_pes_mai.py`
- cada wrapper apenas chama o gerador novo com argumentos fixos

Vantagem:
- operacionalmente mais simples para rodar de novo

### Opcao 3: externalizar configuracao de campanhas

Objetivo:
- mover configuracoes para JSON ou YAML por campanha
- o gerador passa a ler config em vez de varios argumentos CLI

Vantagem:
- facilita escalar para muitas campanhas

## Cuidados para outro chat

Se for continuar em outro chat, informar explicitamente:
- que os dados centrais da pagina de criativos do `PBB-ABR-26` ja foram validados contra CSV
- que o arquivo base de evolucao e `scripts-python/generate_analise_criativos_launch.py`
- que a pagina final manual nao deve ser sobrescrita sem intencao explicita
- que a regra correta do Typeform para `do zero` usa a ultima resposta por email antes do join com CRM
- que Hotmart usa regra especial de `Recuperador Inteligente`
- que TMB nao deve ser filtrado por `Vigente` se o objetivo for paridade com o dashboard atual
- que o investimento total precisa somar Meta + Google

## Resumo curto para colar em outro chat

```text
Ja existe um gerador reutilizavel em scripts-python/generate_analise_criativos_launch.py.
Os dados centrais do dashboard de criativos do PBB-ABR-26 foram validados contra CSV e batem: 548 vendas, 407 rastreadas, 86.025 leads, 84.228 com UTM, R$ 878.092,10 de faturamento e R$ 360.405,75 de investimento total.
A pagina final ANALISE_CRIATIVOS_[PBB-ABR-26].html foi reorganizada manualmente e nao deve ser sobrescrita sem querer.
A regra do bloco do zero usa Typeform deduplicado pela ultima resposta por email antes do join com CRM.
Hotmart usa regra especial para Recuperador Inteligente; TMB nao deve ser filtrado por Vigente se o objetivo for paridade com o dashboard atual.
```
