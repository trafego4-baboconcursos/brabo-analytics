# Projetos — implementações pendentes

Backlog do que foi acordado e ainda não está em produção. Cada item diz **onde está o plano**.

> ⚠️ Muitos itens abaixo foram combinados em conversa e **nunca viraram doc no repositório** —
> estavam só na memória do Claude. Estão marcados como `sem doc`. Ao pegar um desses,
> escreva o plano aqui antes de implementar.

Última revisão: 14/09/2026.

---

## 🔴 Com prazo / risco de perder a janela

| projeto | situação | plano |
|---|---|---|
| **Standard Access da Google Ads API** | enviado 01/09/26, resposta esperada ~15/09/26 pelo e-mail de contato do API Center — **é amanhã**, conferir a caixa | `sem doc` |
| **Cron de orçamento do PBB-AGO-26** | `scripts/apply_daily_budget.py` lê JSON de pasta gitignorada; quebra se reativarem o workflow | [[INDICE_PERFORMANCE]], seção Pendências |

## 🟠 Rastreamento e atribuição

| projeto | situação | plano |
|---|---|---|
| **Meta CAPI + GTM server-side** | nenhuma abordagem em produção; Lead via AC→n8n→CAPI, Purchase via webhook Hotmart, dedup por `event_id` | [[SERVER_SIDE_TRACKING]] |
| **Click IDs → conversão offline** | `gclid`/`fbclid` já são capturados nos leads; falta devolver as vendas pro Google (offline conversions) e Meta (CAPI Purchase) | `sem doc` |
| **UTM do Google por sufixo automático** | ideia: script que grava `final_url_suffix` por grupo (slug do nome + `vk_adset_id`/`vk_ad_id` dinâmicos) | `sem doc` |

## 🟡 Fontes de dado que faltam

| projeto | situação | plano |
|---|---|---|
| **TikTok Ads** | sem fonte de dado (só placeholder vazio). Quando ligar, precisa somar em Investimento/Leads/ThruViews de Captação e Pré-Quali, e nos slots já reservados do debriefing | [[PENDENCIA_TIKTOK_API]] |
| **GA4** | conectado 01/09/26 (token e `property_ids` das 2 LPs no `.env`); **ETL definitivo ainda por construir** | `sem doc` |
| **Sorteios das aulas** | feitos no Google Forms — não estão no Typeform/backup nem no sistema novo; precisa da planilha de respostas ou da API | `sem doc` |
| **Hotmart recorrente** | não se sabe distinguir venda recorrente (valor de parcela) de parcelada normal (valor total) — afeta ticket médio e receita. `quantidade_de_cobrancas` e `codigo_do_assinante` já testados e descartados | `sem doc` |

## 🟢 Produto / dashboard

| projeto | situação | plano |
|---|---|---|
| **Melhorias do debriefing** | 4 seções novas entregues; restam itens ❌ (coleta nova) e 🟡 (derivável, falta construir) | [[LEVANTAMENTO_DEBRIEFING_MELHORIAS_2026-08-25]] |
| **Blocos pendentes do debriefing** | "Liberação de Curso/Bônus+Mentoria" (falta o nome do produto na Hotmart) e "Anteriores" por lançamento (dado perdido — `leads` só guarda o cadastro mais recente) | `sem doc` |
| **Debriefing em PDF** | botão "Gerar PDF" e `?modo=slides` funcionam; falta o caminho 2 (renderizar com Playwright no servidor) | `sem doc` |
| **Thumbnails via Meta API** | hoje funciona via Google Drive; o plano é trocar pela Marketing API e eliminar o upload manual | [[PLANO_META_CRIATIVOS_THUMBNAILS]] |
| **Relatório diário de gasto no Slack (9h)** | spec acordada: orçamento por etapa/bucket no wizard, curva %/dia, consulta ao vivo, contingência sem parcial | `sem doc` |
| **Melhorias do design system** | auditoria de 14/09/26: 3 itens de alta prioridade (tokens inexistentes, modal de atalhos ilegível em tema escuro, falta de `:focus-visible`), 9 médios, 3 baixos | [[LEVANTAMENTO_DESIGN_SYSTEM_2026-09-14]], doc de referência [[DESIGN_SYSTEM]] |

## 🔵 Arquitetura, segurança e escala

Avaliação de 03/09/26. **Top 3 priorizado:**

1. revogação de sessão
2. negar-por-default nas rotas
3. role Postgres somente-leitura

Depois: índice/consolidação do Typeform, camada `domain/`, snapshot do debriefing, e Redis só se passar de 1 worker. — `sem doc`

## ⚪ Tráfego

| projeto | situação | plano |
|---|---|---|
| **Migração Meta do Felipe Graton** | campanhas always-on Meta/Google; migração do Meta pendente | [[DISTRIBUICAO_FELIPE_GRATON]] |

---

## Como usar esta pasta

- Plano de algo **ainda não implementado** → `projetos/`
- Quando entregar → mova o doc pra `historico/` (ou atualize o doc de sistema correspondente)
  e tire a linha daqui
- Registro de reunião, status com data, plano já executado → `historico/`, não aqui
