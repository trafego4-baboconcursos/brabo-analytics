# Brabo Analytics — Defesa Técnica e Estratégica

> Documento atualizado em: 2026-09-03  
> Última versão do sistema: botão "Gerar PDF" no Debriefing — exporta a apresentação completa em slides 1920x1080 (capa + uma seção por slide, tabelas longas quebradas automaticamente) via "Salvar como PDF" do navegador

---

## O problema que resolvemos

Antes desta plataforma, o time de marketing operava com **dados fragmentados em quatro sistemas distintos** — Meta Ads, Google Ads, Active Campaign e Hotmart/TMB — sem nenhuma visão unificada. Cada análise exigia exportar CSVs manualmente, cruzar planilhas no Excel e construir um relatório do zero. O resultado era previsível: decisões atrasadas, métricas inconsistentes entre analistas e nenhuma capacidade de resposta em tempo real durante um lançamento.

Um lançamento durava semanas. A análise chegava depois.

---

## O que construímos

**Brabo Analytics** é uma plataforma de inteligência de marketing construída internamente, 100% sob controle da Brabo Concursos, que entrega em uma única tela o que antes levava dias para compilar.

### Cobertura completa de dados

A plataforma conecta e unifica automaticamente:

| Fonte | O que extrai |
|-------|-------------|
| **Meta Ads** | Investimento, impressões, leads, CPL, hook rate, hold rate por anúncio e por dia |
| **Google Ads** | Investimento, conversões, CPA por campanha (Search, P-Max, Display, YouTube) |
| **Active Campaign** | Base de leads com qualidade, temperatura, canal de origem e etapa |
| **Hotmart + TMB** | Vendas confirmadas, receita bruta, reembolsos |
| **Pesquisas de lançamento** | Typeform (histórico, até ago/26) + sistema de formulários interno (a partir do PBB-AGO-26) — mais de 140.000 respostas coletadas de inscritos, combinadas automaticamente na mesma tela por lançamento |

### Histórico de lançamentos cobertos

| Lançamento | Produto | Período |
|------------|---------|---------|
| PI-JAN-26 | INSS | Nov/25 – Jan/26 |
| PES-JAN-26 | TJ-SP | Jan/26 – Fev/26 |
| PBB-FEV-26 | Banco do Brasil | Jan/26 – Fev/26 |
| PES-MAR-26 | TJ-SP | Fev/26 – Mar/26 |
| PI-ABR-26 | INSS | Mar/26 – Abr/26 |
| PBB-ABR-26 | Banco do Brasil | Mar/26 – Abr/26 |
| PES-MAI-26 | TJ-SP | Abr/26 – Mai/26 |
| PBB-JUN-26 | Banco do Brasil | Mai/26 – Jun/26 |

---

## 9 visões analíticas distintas

| Página | Descrição |
|--------|-----------|
| **Dashboard** | Visão executiva: ROAS, receita, investimento, highlights de criativos, performance diária por plataforma |
| **Funil** | Taxa de conversão em cada etapa por plataforma (Meta vs Google) |
| **Criativos** | Ranking de anúncios por CPL com atribuição de venda por código de AD |
| **Meta Ads** | Performance detalhada Meta com thumbnails e preview dos vídeos |
| **Google Ads** | Performance detalhada Google (Search, P-Max, Display, YouTube) com thumbnails |
| **Vendas** | Hotmart vs TMB, consolidado por lançamento |
| **Leads (CRM)** | Qualidade da base por canal, etapa e temperatura; série histórica de 90 dias |
| **Comparativo** | Dois lançamentos lado a lado em todas as métricas — investimento, ROAS, funil, top criativos |
| **Debriefing** | Fechamento do lançamento: matrículas, resumo executivo vs anterior, alocação por etapa, públicos, top ads, dia a dia, aulas, vendas — com botão **Gerar PDF** que monta a apresentação em slides 1920x1080 |
| **Insights** | Consolidação rápida para briefings |

---

## Diferenciais técnicos que merecem atenção

### 1. Atribuição de vendas por criativo

Cada anúncio carrega um código único no formato `ADxxx`. Esse código percorre toda a jornada do lead: do clique no anúncio até a venda confirmada. A plataforma cruza automaticamente Meta Ads + Google Ads + Active Campaign + Hotmart/TMB e responde à pergunta que toda equipe de tráfego quer saber: **qual anúncio gerou venda de verdade?**

Isso transforma a tomada de decisão de "achismo de CPL" para alocação de verba baseada em ROAS real por criativo.

### 2. Thumbnails e preview de vídeos integrados

Direto no ranking de anúncios, é possível ver a thumbnail do vídeo e assistir ao criativo sem sair da plataforma. Os vídeos são puxados do Google Drive via autenticação segura por service account. A coluna de criativo aparece automaticamente quando a pasta Drive está configurada para o lançamento — zero atrito para o gestor de tráfego.

### 3. Pipeline de dados automático

O ETL roda a cada hora em segundo plano. O gestor acorda e os dados do dia anterior já estão consolidados. Em modo CSV (quando a API não está disponível), basta colocar o arquivo na pasta certa — o sistema detecta e importa sozinho.

### 4. Acesso multi-usuário com controle por produto

Cada usuário vê apenas o que precisa:

| Role | Acesso |
|------|--------|
| **Admin** | Total: dados + gerência de usuários e lançamentos |
| **Analista** | Leitura completa dos dados, sem gestão de usuários |
| **Tráfego** | Dados de mídia paga do seu produto específico |
| **Leitura** | Visão somente leitura, ideal para diretoria |

O convite é por link com prazo de expiração. Sem cadastro manual, sem compartilhamento de senha.

O acesso é **segmentado por produto**: um gestor de tráfego do PBB não vê dados do PES ou do PI.

### 5. Comparativo histórico entre lançamentos

Qualquer dois lançamentos lado a lado, com todas as métricas comparadas — investimento, ROAS, CPL, funil, top criativos. Isso é memória institucional que antes se perdia entre planilhas desatualizadas.

### 6. Wizard de configuração de lançamento

Ao iniciar um novo lançamento, o admin preenche um modal de 3 passos dentro da plataforma — sem tocar em código, sem acessar banco de dados. O sistema passa a reconhecer e exibir o novo lançamento automaticamente.

### 7. Debriefing em PDF com um clique

O botão **Gerar PDF** na aba Debriefing abre a mesma página em modo apresentação (`/debriefing?modo=slides`): capa com os KPIs do lançamento e um slide 1920x1080 por seção, na ordem da aba. Seções que não cabem num slide são divididas automaticamente (tabelas quebram por linha, com cabeçalho repetido) e os gráficos são congelados em imagem de alta resolução. O PDF sai pelo "Salvar como PDF" do Chrome, sem dependência no servidor — o deck de fechamento que antes era montado à mão sai pronto em segundos.

---

## Escala e confiabilidade

- **Dois bancos de dados Supabase** com isolamento entre dados analíticos e operacionais — falha em um não afeta o outro.
- **Cache em memória** no servidor — o dashboard carrega rápido mesmo com grande volume de dados.
- **Guard de escrita** nos dados de vendas — impossível sobrescrever `hotmart_clean_oficial` ou `tmb_clean_oficial` por acidente.
- **Webhook de alerta** — falhas no ETL disparam notificação automática no Discord/Slack.
- **Sessões assinadas com HMAC-SHA256** — nenhuma sessão pode ser forjada ou adulterada.
- **Auto-descoberta de lançamentos** — novos lançamentos aparecem no menu lateral automaticamente ao detectar a pasta no sistema de arquivos.

---

## O que isso representa para o negócio

| Antes | Agora |
|-------|-------|
| Relatório manual de 1-2 dias após o lançamento | Dashboard em tempo real durante o lançamento |
| Cada analista com sua própria planilha | Uma única fonte de verdade para todo o time |
| Decisão de verba baseada em CPL de anúncio | Decisão baseada em ROAS e venda atribuída por criativo |
| Histórico perdido entre ciclos | Comparativo de qualquer lançamento a qualquer momento |
| Acesso irrestrito por senha compartilhada | Acesso granular por função e por produto |
| Criativos avaliados por número na planilha | Thumbnail + preview do vídeo diretamente no ranking |

---

## Infraestrutura atual

- **Backend:** FastAPI (Python) + Jinja2
- **Banco de dados:** Supabase (PostgreSQL) — dois ambientes isolados
- **ETL:** Scripts Python com suporte a API e CSV, scheduler horário
- **Autenticação:** HMAC-SHA256, bcrypt, roles hierárquicos
- **Mídia:** Google Drive API com service account, cache de thumbnails em dois níveis
- **Deploy:** Docker-ready, configurado via `.env`

---

## Próximos passos naturais

1. **Alertas automáticos** — notificação se CPL ou ROAS sair do intervalo esperado durante o lançamento
2. **API pública interna** — permitir que ferramentas externas (planilhas, BI) consumam os dados via endpoint autenticado
3. **Dashboard mobile** — layout responsivo para acompanhamento durante eventos ao vivo

---

> A Brabo Analytics não é uma ferramenta de relatório. É a infraestrutura de inteligência que permite à Brabo Concursos tomar decisões de marketing com a velocidade que lançamentos digitais exigem.
