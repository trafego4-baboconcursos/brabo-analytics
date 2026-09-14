# Levantamento — Design System (14/09/2026)

Auditoria pedida pra achar melhorias na estrutura do design system (tokens, componentes,
temas) descrita em [[DESIGN_SYSTEM]]. Achados abaixo, com prioridade. Ao corrigir um item,
risque/mova pra `historico/` (ou apague daqui se for trivial) e tire a linha do
[[INDICE_PROJETOS]] quando tudo estiver feito.

## 🔴 Alta prioridade

- [ ] **H1 — tokens inexistentes `var(--muted)`/`var(--border)`** em
  `frontend/templates/google_audiences.html` (linhas 166, 175, 186, 210, 222) e
  `frontend/templates/meta_audiences.html` (linhas 194, 205, 229, 241). Os tokens reais são
  `--bs-ink-muted`/`--bs-border`; como os nomes usados não existem, a declaração de `color`
  cai silenciosamente pro valor herdado e a de `border-top` fica inválida. Corrigir renomeando
  nos 9 pontos.
- [ ] **H2 — modal de atalhos de teclado ilegível em todo tema escuro**
  (`frontend/templates/base.html:1042`, `.bs-sh-row { color:var(--bs-sidebar); }`, dentro de
  `#bs-sh-modal { background:var(--bs-card); }` linha 1022). `--bs-sidebar` e `--bs-card` ficam
  parecidos em tom em Predador/Outatime/Aranhaverso/Amigão da Vizinhança/Orange's New Black.
  Trocar pra `var(--bs-ink)`.
- [ ] **H3 — sem `:focus-visible` em nenhum controle interativo** (nav, botões de tema,
  cabeçalho de seção) em `base.html`. Adicionar um `:focus-visible { outline: 2px solid
  var(--bs-accent); outline-offset: 2px; }` genérico.

## 🟠 Média prioridade

- [ ] **M1** — `.kpi-funil-layout .kpi-lbl`/`.kpi-sub` com cinza hardcoded (`base.html:719-720`)
  sobrescrevendo o token correto definido 2 blocos acima (linhas 705-706).
- [ ] **M2** — `.funil-rate` com `color:#526176` hardcoded (`base.html:744`).
- [ ] **M3** — `.criativos-title.validado`/`.novo` com `#28a745`/`#ff9800` hardcoded
  (`base.html:807-808`) em vez de `var(--bs-success)`/`var(--bs-warning)`.
- [ ] **M4** — banner de dado desatualizado com `background:#f59e0b` hardcoded
  (`base.html:2066,2072`), inconsistente com o banner irmão logo acima que já usa
  `var(--bs-danger)` (linha 2054).
- [ ] **M5** — `.dbf-table .roas-ok` com `color:#d97706` hardcoded
  (`debriefing.html:191`), enquanto `.roas-good`/`.roas-bad` ao lado já usam
  `var(--bs-success)`/`var(--bs-danger)`.
- [ ] **M6** — `frontend/design-system.html` (página de referência) desatualizado em relação ao
  `base.html` real: `--bs-bg` diferente, `--bs-sidebar`/`-dark` mostrando azul quando o real é
  cinza-chumbo, `--bs-r-sm` errado, faltam `--bs-border-s`, `--bs-success-bg`,
  `--bs-warning-bg`, `--bs-danger-bg`, `--bs-info`, `--bs-info-bg` no `:root` do doc. Decidir:
  atualizar o doc pra refletir `base.html`, ou gerar os tokens dinamicamente a partir dele pra
  nunca mais dessincronizar.
- [ ] **M7** — `.day-table`/`.dbf-table` do debriefing fora do `.table-wrap` compartilhado
  (`debriefing.html:180-215`, usos em 2238/2254/2547) — não herdam fundo `var(--bs-card)`,
  borda nem zebra striping padrão.
- [ ] **M8 — migração `.info-box`→`.section` incompleta em 13 páginas roteadas** (não é só
  débito de páginas órfãs): `hotmart.html` (10 usos), `vendas.html` (8), `index.html` (6),
  `debriefing.html` (5), `criativos.html` (4), `tmb.html` (4), `dashboard.html` (3),
  `google_audiences.html` (2), `insights.html` (2), `instagram_detail.html` (2),
  `meta_audiences.html` (2), `comparativo_v1_v2.html` (1), `instagram.html` (1). Decidir:
  terminar a migração ou aceitar `.info-box` como segundo padrão permanente.
- [ ] **M9 — gerador de temas sem validação de contraste** (`frontend/templates/settings.html`,
  seção "Gerador de Temas"). 15 color pickers sem nenhum aviso se o usuário escolher `ink`
  parecido com `bg`/`card`. `--bs-info` sempre reusa `accent` e as sombras são derivadas só de
  `ink` — não documentado na UI.

## 🟢 Baixa prioridade

- [ ] **L1** — série "VIP" do gráfico WhatsApp com cor hardcoded (`whatsapp.html:447-448`),
  enquanto "Normal" já usa `cssVar()`.
- [ ] **L2** — `var(--bs-warning)` usado como cor de ícone isolado sobre fundo claro
  (`comparativo.html:161`, `comparativo_v1_v2.html:57`, `debriefing.html:34`) — legibilidade
  limítrofe, baixo risco por ser ícone e não texto.
- [ ] **L3** — divisor `.bs-sh-row` com `border-bottom:1px solid #f9fafb` (quase branco),
  invisível em tema escuro. Mesmo local do H2.

## Já auditado e sólido (não precisa reauditar sem motivo)

- Resolução de cor em Chart.js/Canvas — todos os gráficos já resolvem `var()` via
  `getComputedStyle(...)` antes de montar o config.
- Wiring do modal de preview de vídeo — os 12 casos de `openVideoModal()` de 2 argumentos
  corrigidos anteriormente seguem corrigidos; nenhum caso novo apareceu.
- Estilo central do `.table-wrap` (fundo, borda, zebra) — consistente e tokenizado; o único
  gap é o M7 acima (tabelas do debriefing que não usam o wrapper).
