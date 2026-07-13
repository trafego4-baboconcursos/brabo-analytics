# Evoluções registradas em 2026-06-17

## Escopo geral

Consolidação de ajustes no dashboard e na camada de leitura de dados para lançamentos, com foco principal em `PBB-ABR-26`, `PBB-JUN-26` e na análise Typeform.

## Dados e banco

- Importação solicitada de leads a partir de:
  - `analises/[PBB-JUN-26]/active campaign/active-campaign-pbb-jun-26.csv`
- Diretriz operacional alinhada:
  - puxar o máximo possível direto das plataformas;
  - manter no banco principalmente os leads, por serem o volume mais pesado.
- Registro do ponto pendente:
  - vendas aguardando finalização do TI no banco.

## Meta Ads e Google Ads

- Revisão dos custos do Meta Ads para o lançamento `PBB-ABR-26`.
- Correção do entendimento do referencial de campanha:
  - o filtro correto é pela tag do lançamento no nome da campanha, por exemplo `PBB-ABR-26`.
- Ajuste/checagem de apresentação monetária no dashboard:
  - investimento total com `R$` e separador de milhar;
  - receita total com `R$` e separador de milhar.
- Verificação adicional solicitada para Google Ads, com a mesma lógica de tag por lançamento.

## Vendas, Hotmart e regras de receita

- Revisão da receita total do `PBB-ABR-26`, com correção da ordem de grandeza esperada.
- Alinhamento de regra de negócio para Hotmart:
  - em compras parceladas, somar todas as parcelas;
  - considerar a parcela 1 como referência temporal de entrada no mês.
- Diretriz estendida para aplicar o mesmo tratamento aos demais lançamentos.

## Typeform: base e consistência

- Correção da leitura do Typeform no backend para não misturar respostas de outros lançamentos no mesmo período.
- Ajuste aplicado em `frontend/database_reader.py`:
  - filtro por intervalo de datas;
  - filtro por `form_id = launch_code` na leitura de `typeform_respostas`.
- Ajuste complementar em `discover_launches()`:
  - `has_typeform` passou a respeitar o mesmo critério por `form_id`.
- Verificação de volume do `PBB-ABR-26`:
  - conferência da contagem de respostas entre exportação e análise da página.

## Typeform: estabilidade da página

- Diagnóstico e estabilização do endpoint:
  - `/typeform?launch_code=PBB-ABR-26`
- Identificado comportamento inconsistente ao subir com `uv run uvicorn`.
- Validado funcionamento com:
  - `.\.venv\Scripts\python.exe -m uvicorn frontend.app:app --host 127.0.0.1 --port 8000 --reload`

## Typeform: redesign visual do funil

- Substituição do gráfico anterior por um funil visual proporcional.
- Iterações realizadas no layout:
  - barras com formato de trapézio;
  - conteúdo interno centralizado;
  - cores em progressão do frio para o quente;
  - informações secundárias movidas para dentro das barras;
  - badges de destaque dentro de cada etapa;
  - remoção dos blocos intermediários abaixo das barras;
  - correção de CSS quebrado no template.
- Ajustes de geometria:
  - cada barra inferior deve ser sempre menor que a superior;
  - depois, endurecimento da escala para parecer efetivamente um funil de dashboard.

## Typeform: encoding e textos

- Correções no template para resolver textos quebrados/sem acentuação.
- Estratégia aplicada:
  - limpeza de trechos corrompidos;
  - uso de entidades HTML em pontos críticos para reduzir dependência do encoding do arquivo.

## Typeform: geografia

- Identificado motivo da seção vazia em:
  - `Distribuição geográfica`
  - `Top 10 estados geral`
  - `Top 10 estados compradores`
- Causa:
  - a leitura dependia de coluna de estado disponível no payload reconstruído do banco.
- Correção aplicada em `frontend/database_reader.py`:
  - fallback para CSV local de Typeform;
  - cruzamento por e-mail;
  - preenchimento de `top_estados_geral` e `top_estados_comp` a partir da exportação local quando necessário.

## Typeform: confronto entre duas pesquisas

- Levantada hipótese de existirem duas pesquisas por lançamento:
  - uma de `Projeto` / captação;
  - outra de `Alunos`.
- Implementada estrutura de comparação entre exportações locais de Typeform:
  - volume de respondentes únicos por pesquisa;
  - interseção por e-mail;
  - exclusivos de cada base;
  - insights automáticos.
- Arquivos alterados:
  - `frontend/database_reader.py`
  - `frontend/templates/typeform.html`

## Resultado do teste em PBB-ABR-26

- As duas exportações locais atuais:
  - `typeform-pesquisa-pbb-abr-26.csv`
  - `typeform-pbb-abr-26.csv`
  aparentam ser o mesmo dataset.
- Resultado validado:
  - `11.103` e-mails únicos em cada uma;
  - interseção total `11.103`;
  - exclusivos `0`.
- Conclusão:
  - a estrutura de comparação ficou pronta, mas neste lançamento específico os dois arquivos hoje não geram contraste analítico real.

## Arquivos principais alterados nesta frente

- [frontend/database_reader.py](/abs/path-placeholder)
- [frontend/templates/typeform.html](/abs/path-placeholder)

## Pendências e próximos passos (Atualizado - Concluído)

- [x] Validar visualmente a nova seção comparativa do Typeform no navegador.
- [x] Generalizar a identificação de `Projeto` vs `Alunos` para outros lançamentos (implementado mapeamento por tags no título do formulário via API/Supabase).
- [x] Integrar API da Typeform e Supabase para consulta direta na plataforma em vez de depender de exportações locais (implementado e validado).

---

## ⚡ Evoluções do Período da Tarde (Typeform API Datalake & Frontend V2)

Nesta tarde de 17 de junho de 2026, consolidamos a migração total para o banco de dados e a API, eliminando os CSVs locais, implementando segurança de sessão e aprimorando significativamente a inteligência do dashboard.

### 1. Migração Total para Datalake e API (Sem CSVs)
- **Resolvedor de FormId**: O backend resolve de forma dinâmica os IDs de formulários da API da Typeform que contêm a tag do lançamento (ex: `PBB-ABR-26`), diferenciando a pesquisa de captação (`"Projeto"`) e a de compradores (`"Alunos"`).
- **Mapeamento de Metadados da API**: Criamos um cache dinâmico de definições (`_get_typeform_fields`) para ler a estrutura de perguntas do formulário no Typeform. Isso resolve a ausência de títulos de perguntas no payload de respostas da API.
- **Normalização de String e Match por Substring**: Implementamos busca robusta por substrings com normalização de acentos em Pandas. Isso resolve a diferença de formato de múltipla escolha (que na API vem em uma célula de texto única com itens separados por vírgula) e garante retrocompatibilidade com estruturas explodidas.

### 2. Autenticação e Área Logada
- **Sessão Segura**: Middleware enforçando login obrigatório para visualização das análises, salvando os tokens via cookies HTTP-only encriptados.
- **Login/Logout**: Interface premium escura de login e rota `/logout` para limpar a sessão.

### 3. Layout Demográfico em Linhas
- Reorganizamos a seção de Perfil Demográfico no template HTML para melhorar o fluxo de leitura visual:
  - **Linha Superior**: Tabela de Gênero e Tabela de Faixa Etária (lado a lado).
  - **Linha Inferior**: Tabela de Situação Profissional e Tabela de Nível nos Estudos (lado a lado).

### 4. Ranking de Atribuição por Anúncios (`utm_content`)
- Alteramos a tabela de campanhas da pesquisa para fazer agregação por **Anúncio (utm_content)** e não mais por *source* genérico.
- Agora o dashboard lista os criativos e anúncios específicos (ex: `AD113 - ...`) que mais converteram leads respondentes em vendas, facilitando a análise de ROAS do criativo.

### 5. Seção de Voz dos Alunos (Fatores de Conversão)
- **Fatores Decisivos de Compra**: Agrupamos e contamos as opções da pergunta de influência de compra do formulário de alunos. Descobrimos que a **Apostila Física (77.6%)** e a **Plataforma LOOP (72.8%)** são os ganchos de maior peso de decisão.
- **Depoimentos Reais por Abas**: Criamos um bloco com abas interativas via JavaScript para ler as respostas abertas de motivação e convencimento de compra. Implementamos um filtro no Python para remover respostas curtas ou lixo de testes e ordenar por riqueza de conteúdo (tamanho do texto).

### 6. Seção de Diagnósticos e Recomendações de IA
- Implementamos um bloco de diagnóstico analítico inteligente gerado dinamicamente com base nos dados consolidados de perfil demográfico, obstáculos e drivers de compra, gerando insights automatizados de negócios para a equipe de tráfego e copy.

### 7. Transparência de Origem (Bases Utilizadas)
- Atualizamos o rodapé para refletir o uso de 5 bases distintas, integrando a tabela `dim_lancamentos` no mapeamento do relatório analítico do Typeform.

---

## 📂 Arquivos Alterados e Criados
- [frontend/database_reader.py](file:///c:/Users/trafe/OneDrive/Desktop/workspace-mmm/frontend/database_reader.py) — Adicionadas lógicas de API, normalizações, IA insights, atalho de anúncios e depoimentos.
- [frontend/templates/typeform.html](file:///c:/Users/trafe/OneDrive/Desktop/workspace-mmm/frontend/templates/typeform.html) — Novo layout demográfico, abas qualitativas, bloco de IA e tabela de rodapé.
- [documentacao/EVOLUCOES_2026-06-17.md](file:///c:/Users/trafe/OneDrive/Desktop/workspace-mmm/documentacao/EVOLUCOES_2026-06-17.md) — Este registro de evoluções atualizado.

---

## 🎯 Seção de Ganchos e Scripts de Criativos de Anúncio

Adicionada nova seção **"Roteiros e Ganchos de Copy Recomendados"** no template do Typeform, posicionada imediatamente abaixo do bloco de Diagnóstico de IA.

### Ganchos de Copy (5 ideias com dados reais)

Cada gancho é gerado dinamicamente via variáveis Jinja2 do banco de dados — os percentuais se adaptam automaticamente a cada lançamento:

1. **Apostila Física (Driver #1)** — usa `tf.top_influence_factors[0].pct`
2. **Método de Estudos (Obstáculo #1)** — usa `tf.obstaculos_comp_pct['Não sei estudar do jeito certo']`
3. **Circuito LOOP (Driver #2)** — usa `tf.top_influence_factors[1].pct`
4. **Perfil Iniciante** — usa `tf.nivel_comp_pct['Sou Iniciante']`
5. **Procrastinação** — usa `tf.obstaculos_comp_pct['Procrastinação']`

### Scripts de Criativos de Anúncio (5 roteiros completos)

Organizados em acordeão interativo (JS vanilla) com 3 blocos por roteiro: `[Hook]`, `[Body]`, `[CTA]`:

1. **Script 1**: Apostila Física na Mesa vs PDF na Tela
2. **Script 2**: O Segredo de Saber Estudar
3. **Script 3**: Acabando com a Procrastinação no Cronograma
4. **Script 4**: O Que Fazer com o Primeiro Salário? (emocional)
5. **Script 5**: Criativo "Eu Sou Iniciante, Dá Tempo?"

### Propagação para todos os lançamentos

O template `typeform.html` é **único e compartilhado** via Jinja2. Todas as melhorias são automaticamente aplicadas a qualquer lançamento com `has_typeform=True` no banco de dados:

| Lançamento | Typeform ativo |
| :--- | :---: |
| PI-JAN-26 | ✅ |
| PES-JAN-26 | ✅ |
| PBB-FEV-26 | ✅ |
| PES-MAR-26 | ✅ |
| PI-ABR-26 | ✅ |
| PBB-ABR-26 | ✅ |
| PES-MAI-26, PBB-JUN-26 e demais | ⏳ (dados ainda não na base) |

### Arquivos alterados nesta etapa

- [frontend/templates/typeform.html](file:///c:/Users/trafe/OneDrive/Desktop/workspace-mmm/frontend/templates/typeform.html) — Nova seção de ganchos e scripts com CSS, HTML e JS integrados.
