# Brabo Analytics — Documentação

Home do vault. Toda a documentação do projeto mora aqui; o código tem `README.md` próprio
ao lado de cada módulo (`frontend/`, `config/launches/`), que é onde eles devem ficar.

## 🏗 Sistema — `sistema/`
Como o Brabo Analytics funciona por dentro.

- [[ARQUITETURA]] — **comece por aqui.** Fluxo de dados, os dois bancos Supabase, ETL, frontend, views
- [[METODOLOGIA_EXTRACAO_DADOS]] — como cada métrica é extraída e atribuída por lançamento
- [[DESIGN_SYSTEM]] — tokens, componentes, temas e gerador de temas do frontend

## 💼 Negócio — `negocio/`
- [[BRABO_ANALYTICS_APRESENTACAO_EXEC]] — apresentação executiva; sempre reflete o estado atual do sistema
- [[BRIEFING_BRABO]] — produtos (PBB/PES/PI), público, objetivos

## 🚀 Operação — `operacao/`
- [[CHECKLIST_DEPLOY_SEGURANCA]] — conferir antes de subir pra produção
- [[RESTAURAR_MAQUINA_NOVA]] — reinstalar o projeto do zero (par do `scripts/backup-workspace.ps1`)

## 📈 Performance — `performance/`
Tráfego pago: o que foi feito em cada lançamento, playbooks e metodologias.
Índice detalhado em [[INDICE_PERFORMANCE]].

- `performance/lancamentos/[CÓDIGO]/` — diário vivo de cada lançamento
  - [[MUDANCAS_PES-SET-26]] · [[MUDANCAS_PI-AGO-26]] · [[MUDANCAS_PBB-AGO-26]]
- `performance/playbooks/` — reutilizáveis, valem pra qualquer lançamento
  - [[PLAYBOOK_DUPLICAR_LANCAMENTO_META_ADS]] · [[CASCATEAMENTO_PUBLICOS_META_ADS]] · [[CPA_DOS_AND_DONTS_GOOGLE_ADS]]
- `performance/perpetuo/` — campanhas always-on, fora de lançamento
  - [[DISTRIBUICAO_FELIPE_GRATON]] · [[LEVANTAMENTO_PERPETUO_DISTRIBUICAO]]

## 🛠 Projetos — `projetos/`
O que foi acordado e **ainda não está em produção**.

- [[INDICE_PROJETOS]] — **backlog completo**, com o estado de cada um
- [[SERVER_SIDE_TRACKING]] · [[PENDENCIA_TIKTOK_API]] · [[PLANO_META_CRIATIVOS_THUMBNAILS]] · [[LEVANTAMENTO_DEBRIEFING_MELHORIAS_2026-08-25]]

## 🔍 Análises — `analises/`
Análises de dados sobre lançamentos específicos.

- [[README_ANALISE]] — índice das análises
- [[HANDOFF_CRIATIVOS_REUTILIZAVEL]] — handoff de criativos, reutilizável
- [[ANALISE_META_ADS_MMM]] · [[ANALISE_GOOGLE_ADS_MMM]] · [[ANALISE_LEADS_CONFRONTO_FINAL_V2]]

## 🗄 Histórico — `historico/`
Nada é apagado, só arquivado. Logs de sessão, planos pontuais, status com data e ideias já
implementadas vão pra lá. Vale como registro, não como referência do estado atual.
`historico/codigo-legado/` guarda código aposentado (readers antigos, backups `.bak`).

---

## Onde criar documento novo

| tipo | vai pra |
|---|---|
| doc do sistema / metodologia | `sistema/` |
| produto, público, posicionamento | `negocio/` |
| deploy, backup, restauração | `operacao/` |
| ação ou análise de tráfego num lançamento | `performance/lancamentos/[CÓDIGO]/MUDANCAS_[CÓDIGO].md` (item novo, não arquivo novo) |
| método de tráfego que serve pra qualquer lançamento | `performance/playbooks/` |
| análise de dados de um lançamento | `analises/` |
| plano de algo **ainda não implementado** | `projetos/` (e linkar no [[INDICE_PROJETOS]]) |
| log de sessão, plano **já executado**, status com data | `historico/` |
| "como rodar este módulo" | `README.md` dentro da pasta do módulo, não aqui |

Regras: antes de criar arquivo novo, confira se não é caso de **atualizar um existente** — é
quase sempre o caso. Ao editar o [[BRABO_ANALYTICS_APRESENTACAO_EXEC]], atualize a data do
cabeçalho. Nomes de arquivo devem ser **únicos no vault inteiro** (os wikilinks do Obsidian resolvem
por nome, não por caminho) — por isso o código do lançamento entra no nome, mesmo
já estando na pasta.
