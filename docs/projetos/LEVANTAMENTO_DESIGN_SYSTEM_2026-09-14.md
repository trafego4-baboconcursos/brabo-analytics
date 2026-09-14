---
titulo: "Levantamento — Design System (14/09/2026)"
area: projeto
status: pendente
atualizado: 2026-09-14
responde:
  - "problemas abertos do design system"
  - "tokens inexistentes e inconsistencias de CSS"
relacionados:
  - "[[DESIGN_SYSTEM]]"
  - "[[INDICE_PROJETOS]]"
---

# Levantamento — Design System (14/09/2026)

Auditoria pedida pra achar melhorias na estrutura do design system (tokens, componentes,
temas) descrita em [[DESIGN_SYSTEM]]. Achados abaixo, com prioridade. Ao corrigir um item,
risque/mova pra `historico/` (ou apague daqui se for trivial) e tire a linha do
[[INDICE_PROJETOS]] quando tudo estiver feito.

## 🔴 Alta prioridade

- [x] **H1 — tokens inexistentes `var(--muted)`/`var(--border)`** em
  `frontend/templates/google_audiences.html` (linhas 166, 175, 186, 210, 222) e
  `frontend/templates/meta_audiences.html` (linhas 194, 205, 229, 241). Os tokens reais são
  `--bs-ink-muted`/`--bs-border`; como os nomes usados não existem, a declaração de `color`
  cai silenciosamente pro valor herdado e a de `border-top` fica inválida. Corrigido renomeando
  nos 9 pontos. *(commit `52831b6`)*
- [x] **H2 — modal de atalhos de teclado ilegível em todo tema escuro**
  (`frontend/templates/base.html:1042`, `.bs-sh-row { color:var(--bs-sidebar); }`, dentro de
  `#bs-sh-modal { background:var(--bs-card); }` linha 1022). Trocado pra `var(--bs-ink)`;
  achados mais 2 casos do mesmo padrão (`kbd`, badge de role da conta) e corrigidos junto.
  *(commit `52831b6`)*
- [x] **H3 — sem `:focus-visible` em nenhum controle interativo**. Adicionado
  `:focus-visible { outline: 2px solid var(--bs-accent); outline-offset: 2px; }` genérico em
  `base.html`. *(commit `52831b6`)*

## 🟠 Média prioridade

- [x] **M1** — `.kpi-funil-layout .kpi-lbl`/`.kpi-sub` com cinza hardcoded, agora
  `var(--bs-ink-muted)`/`var(--bs-ink-subtle)`. *(commit `38d33bf`)*
- [x] **M2** — `.funil-rate` agora `color:var(--bs-ink-muted)`. *(commit `38d33bf`)*
- [x] **M3** — `.criativos-title.validado`/`.novo` agora `var(--bs-success)`/`var(--bs-warning)`.
  *(commit `38d33bf`)*
- [x] **M4** — banner de dado desatualizado agora `background:var(--bs-warning)` com texto
  escuro fixo (contraste, já que warning é sempre claro em todo tema). *(commit `38d33bf`)*
- [x] **M5** — `.dbf-table .roas-ok` agora `var(--bs-warning)`. *(commit `38d33bf`)*
- [x] **M6** — `design-system.html` resincronizado com os tokens reais do `base.html`
  (`--bs-bg`, `--bs-sidebar`/`-dark`, `--bs-r-sm`, tokens `-bg`/`--bs-info` que faltavam) +
  comentário avisando que os apelidos curtos (`--muted`, `--card`...) só existem nessa página
  de demo. *(commit `38d33bf`)*
- [x] **M7** — `.dbf-table`/`.day-table` ganharam `background:var(--bs-card)` direto (sem
  precisar reestruturar o markup em `.table-wrap`, o que arriscaria o modo slides/PDF).
  *(commit `38d33bf`)*
- [x] **M8 — CORRIGIDO/RECLASSIFICADO: não é débito de migração.** Este item original estava
  errado — conflava dois componentes distintos sob "padrão antigo":
  - `.highlight-box` (as 45 ocorrências nas 12 páginas fora do debriefing) é um **card dentro
    de um grid** (`.highlights { display:grid; ... }`), usado pra 2-3 painéis lado a lado (ex.:
    "Top 5 Criativos"/"Melhores CPL"/"Piores CPL" no dashboard, card de perfil no
    `instagram.html`). Não é uma seção de página — converter pra `.section`/`.section-title`
    quebraria o layout em grade e criaria accordion/drag/tag sem sentido em cards pequenos.
  - `.info-box` (as 5 ocorrências, só em `debriefing.html`, linhas 678/743/798/853/2641) estão
    **todas aninhadas dentro de um `.dbf-section` já existente** (603/847/2613) — sub-painel de
    uma seção que já é colapsável, não seção órfã.

  Decisão 14/09/26 (depois de checar os usos com mais cuidado, antes de converter 13 arquivos
  às cegas): manter os dois componentes como estão, só corrigir a documentação
  ([[DESIGN_SYSTEM]]). Nenhum template foi alterado por este item.
- [x] **M9 — gerador de temas sem validação de contraste**. Adicionado cálculo de contraste
  WCAG ao vivo pra 4 pares críticos (ink×bg, ink×card, ink-muted×card, card×bg), calibrado
  contra os 10 temas reais pra não dar falso positivo; UI também documenta que `--bs-info` e as
  sombras reusam accent/ink. *(commit `3cfe242`)*

## 🟢 Baixa prioridade

- [x] **L1** — série "VIP" do gráfico WhatsApp agora usa `cssVar('--temp-especifico', ...)`.
  *(commit `38d33bf`)*
- [ ] **L2** — `var(--bs-warning)` usado como cor de ícone isolado sobre fundo claro
  (`comparativo.html:161`, `comparativo_v1_v2.html:57`, `debriefing.html:34`) — legibilidade
  limítrofe, baixo risco por ser ícone e não texto. Não corrigido ainda (baixa prioridade,
  risco maior que benefício por ora).
- [x] **L3** — divisor `.bs-sh-row` corrigido junto do H2 (`var(--bs-border)`).
  *(commit `52831b6`)*

## Já auditado e sólido (não precisa reauditar sem motivo)

- Resolução de cor em Chart.js/Canvas — todos os gráficos já resolvem `var()` via
  `getComputedStyle(...)` antes de montar o config.
- Wiring do modal de preview de vídeo — os 12 casos de `openVideoModal()` de 2 argumentos
  corrigidos anteriormente seguem corrigidos; nenhum caso novo apareceu.
- Estilo central do `.table-wrap` (fundo, borda, zebra) — consistente e tokenizado; o único
  gap é o M7 acima (tabelas do debriefing que não usam o wrapper).
