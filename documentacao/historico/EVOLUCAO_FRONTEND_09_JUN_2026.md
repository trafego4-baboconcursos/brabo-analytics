# Evolução do Frontend — 09/06/2026

Este documento registra a evolução realizada no painel FastAPI/HTML do Brabo Analytics no dia 09/06/2026, com o objetivo de assegurar que o sistema dinâmico funcione de forma idêntica e correta para todos os lançamentos locais adicionados pelo usuário.

---

## 1. Objetivo da Iteração

Tornar o front-end dinâmico resiliente às particularidades estruturais e de dados de cada pasta de lançamento (`analises/`), permitindo que a visualização de funil, criativos, mídias e vendas atinja a paridade perfeita que foi aprovada no lançamento de referência `PBB-ABR-26`.

---

## 2. Mudanças Principais

### A. Detecção Tolerante de Subpastas de Lançamento
**Problema:** Pastas locais de campanhas anteriores e novas possuíam divergências de digitação e de maiúsculas/minúsculas (ex: `Googole Ads` no `PES-JAN-26`, `active-campaing` no `PBB-FEV-26`, subpastas em minúsculas, etc.), impedindo o app de localizar os dados CSV e gerando telas vazias ou erros no servidor.
- **Solução:** Criado o utilitário [`src/readers/path_helper.py`](file:///c:/Users/trafe/OneDrive/Desktop/workspace-mmm/src/readers/path_helper.py) com a função `find_subfolder()`. Ela busca subpastas por palavras-chave com comparação de case-insensitive e tolerância a erros comuns.
- **Refatoração:** Modificados os seguintes arquivos para utilizar a descoberta flexível:
  - [`src/readers/launch_discovery.py`](file:///c:/Users/trafe/OneDrive/Desktop/workspace-mmm/src/readers/launch_discovery.py) (para detecção de flags de dados no menu lateral)
  - [`src/readers/meta_reader.py`](file:///c:/Users/trafe/OneDrive/Desktop/workspace-mmm/src/readers/meta_reader.py) (leitor do Meta Ads)
  - [`src/readers/google_reader.py`](file:///c:/Users/trafe/OneDrive/Desktop/workspace-mmm/src/readers/google_reader.py) (leitor do Google Ads)
  - [`src/readers/vendas_reader.py`](file:///c:/Users/trafe/OneDrive/Desktop/workspace-mmm/src/readers/vendas_reader.py) (leitor de Vendas e CRM)
  - [`frontend/app.py`](file:///c:/Users/trafe/OneDrive/Desktop/workspace-mmm/frontend/app.py) (verificação de Typeform e Active Campaign)

### B. Lógica Auto-Ajustável para o Topo do Funil
**Problema:** Em lançamentos como o `PES-MAI-26`, o usuário não exportou a coluna de visualizações no CSV do Google Ads. Isso fez com que as visualizações do YouTube caíssem em um fallback incorreto de "Conversões" (71), gerando taxas de conversão absurdas de mais de 700.000% na relação "Topo -> Clique" do funil.
- **Solução:** Implementado um ajuste inteligente no template [`frontend/templates/funil.html`](file:///c:/Users/trafe/OneDrive/Desktop/workspace-mmm/frontend/templates/funil.html).
- **Lógica:** Se o volume acumulado de ThruPlays + Views do YouTube for nulo ou menor que o volume total de cliques da campanha, o sistema dinamicamente adota as **Impressões (Meta + Google)** como topo do funil e altera o rótulo da primeira barra do funil para refletir esse dado de forma transparente.
- **Resultado:** O funil do `PES-MAI-26` agora soma corretamente as `82.949.541` impressões como topo, normalizando todas as taxas subsequentes com exatidão matemática e visual.

### C. Consolidação Global de Criativos (Meta Ads)
**Problema:** A rota `/criativos` e a seção de criativos do funil estavam duplicando registros de criativos que rodavam em conjuntos de anúncios diferentes devido ao agrupamento por `conjunto || anuncio`.
- **Solução:** Alterado o agrupamento do leitor do Meta Ads ([`src/readers/meta_reader.py`](file:///c:/Users/trafe/OneDrive/Desktop/workspace-mmm/src/readers/meta_reader.py)) para consolidar os dados de investimentos, cliques, leads e faturamento unicamente pela tag do criativo (`anuncio`). Isso unificou a leitura dos rankings e facilitou a avaliação de escala de peças de vídeo e imagem.

### D. Integração e Tratamento das Visualizações do YouTube
**Problema:** Havia inconsistência na exibição do volume de visualizações reais do YouTube na seção de Pré-Qualificação do Google Ads.
- **Solução:** Atualizado o [`google_reader.py`](file:///c:/Users/trafe/OneDrive/Desktop/workspace-mmm/src/readers/google_reader.py) para extrair o dado de `Visualizações do TrueView` a partir do CSV de performance de anúncios e repassá-lo na agregação de campanhas e etapas. O template do funil foi atualizado para exibir as taxas com cores correspondentes aos blocos do funil principal (Topo, Clique, Lead, etc.).

---

## 3. Validações Realizadas

1. **Invalidação de Cache:** Executada a limpeza de cache geral no FastAPI via chamada ao endpoint `/api/clear-cache` para garantir a imediata re-leitura de todos os CSVs locais recém-adicionados nas pastas.
2. **Navegação em Lote no Painel:** O frontend foi validado usando o navegador de testes para diversos códigos de campanha:
   - `PBB-FEV-26`: Carrega com sucesso todos os dados de Meta/Google Ads e Vendas (mesmo a pasta do Google estando grafada em minúsculas).
   - `PES-JAN-26`: Renderiza com sucesso os dados de Meta Ads e Vendas (mesmo com a pasta grafada `Googole Ads`).
   - `PES-MAI-26`: Funil e criativos normalizados com o novo ajuste do Topo do Funil por Impressões.
