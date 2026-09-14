---
titulo: "Design System — Brabo Analytics"
area: sistema
status: vigente
atualizado: 2026-09-14
responde:
  - "tokens, componentes e temas do dashboard"
  - "onde mexer no CSS"
  - "como funciona o gerador de temas"
relacionados:
  - "[[ARQUITETURA]]"
---

# Design System — Brabo Analytics

Como o design system do dashboard funciona por dentro: tokens, componentes compartilhados,
temas e o gerador de temas. Tudo vive em `frontend/templates/base.html` (um único arquivo,
~2700+ linhas) e é herdado por todo template via `{% extends "base.html" %}`.

**Não confundir com** `frontend/design-system.html` — é uma página de referência visual (HTML
solto, fora do fluxo de rotas) que mostra os componentes isolados. Ela desatualiza com
frequência porque não é gerada a partir do CSS real; trate como esboço, não como fonte da
verdade. A fonte da verdade é sempre `base.html`.

## Tokens (`:root`, `base.html` linha ~15)

Custom properties CSS, prefixo `--bs-`:

| Categoria | Tokens |
|---|---|
| Texto | `--bs-ink`, `--bs-ink-muted`, `--bs-ink-subtle` |
| Fundo | `--bs-bg` (página), `--bs-surface`, `--bs-card` (superfície elevada — tabelas, cards) |
| Borda | `--bs-border`, `--bs-border-s` |
| Semântico | `--bs-success`/`-bg`, `--bs-warning`/`-bg`, `--bs-danger`/`-bg`, `--bs-info`/`-bg` |
| Marca | `--bs-accent` (setado via Jinja `{{ accent }}`, cor do lançamento), `--bs-accent-2`, `--bs-accent-bg` |
| Sidebar | `--bs-sidebar`, `--bs-sidebar-dark` (gradiente do menu lateral) |
| Sombra | `--bs-sh-sm/md/lg/xl` |
| Raio | `--bs-r-sm/md/lg/xl/2xl` |
| Espaço/fonte | `--s1..--s10`, `--fs-2xs..--fs-4xl` |
| Plataforma (fixos, não tematizáveis) | `--meta-color`, `--google-color`, `--yt-color`, `--search-color`, `--pmax-color`, `--display-color` |
| Temperatura de lead (fixos) | `--temp-quente/morno/frio/especifico/outros` |

**Regra de uso**: qualquer cor de texto/fundo/borda em um template deve referenciar um
`var(--bs-*)`, nunca um hex literal — só assim a cor acompanha o tema ativo (incluindo temas
gerados pelo usuário, ver abaixo). Exceções aceitas: cores de plataforma (Meta azul, Google
vermelho), badges auto-contidos onde fundo+texto são hardcoded juntos, e séries de gráfico
categóricas.

**Pegadinha do Canvas**: `Chart.js`/`<canvas>` não resolve `var(--bs-token)` — precisa ler o
valor computado antes de montar o config: `getComputedStyle(document.documentElement).getPropertyValue('--bs-accent').trim()`.
Todo gráfico do sistema já segue esse padrão; se adicionar um novo, replicar.

## Componentes compartilhados

- **`.section` / `.section-title`** — bloco de conteúdo colapsável (accordion). É o padrão
  atual; usado na maioria das páginas de análise. Suporta drag-and-drop de ordem, ocultar/
  mostrar, tags de etapa auto-detectadas e "visualizações" salvas nomeadas (igual ao
  gerenciador de colunas do Google Ads) — tudo implementado numa IIFE única no fim de
  `base.html` (`SKIP_PAGES`, `TAG_DEFS`, `detectTag`, `applyState`, `renderSecPanel`,
  `renderViewsPanel`). Roda em toda página automaticamente por detectar o markup — não
  precisa registrar nada por template, exceto páginas na lista `SKIP_PAGES` (`settings`,
  `login`, `invite`, `index`) e o modo apresentação/PDF do debriefing (`?modo=slides`, guardado
  via `document.documentElement.classList.contains('bs-slides')`).
- **`.highlight-box`** (dentro de um `.highlights { display:grid; ... }`) — card titulado
  dentro de um grid de 2-3 colunas (ex.: "Top 5 Criativos" / "Melhores CPL" / "Piores CPL" lado
  a lado no dashboard, ou o card de perfil do Instagram). **Não é uma versão antiga do
  `.section`** — é um componente à parte, pra painéis pequenos que vivem em grade, não pra
  conteúdo de página inteira. Não faz sentido convertê-lo em accordion (perderia o layout em
  grade e ganharia controles de recolher/arrastar/tag que não fazem sentido num card pequeno).
- **`.info-box`** — usado só dentro de `debriefing.html`, sempre **aninhado dentro de um
  `.dbf-section` já existente** (sub-painel de uma seção que já é colapsável, não uma seção
  órfã). Mesma lógica do `.highlight-box`: é um componente de sub-painel, não débito de
  migração. *(Uma auditoria anterior, 14/09/26, chegou a marcar esses dois componentes como
  "padrão antigo em 13 páginas" — checado com mais cuidado depois, é engano: ver
  `projetos/LEVANTAMENTO_DESIGN_SYSTEM_2026-09-14.md`, no vault local.)*
- **`.table-wrap` + `table`** — wrapper padrão de tabela: fundo `var(--bs-card)`, borda,
  scroll horizontal em mobile, zebra striping. Toda tabela de dado deve ficar dentro de um
  `.table-wrap`; tabelas soltas não herdam esse tratamento.
- **`.tp-kpi` / `.tp-kpi-grid`** — cards de KPI.
- **`.bs-pill`** — badges/pills.
- **Modal de preview de vídeo** — `openVideoModalFromEl(this)` lido a partir de atributos
  `data-preview`, `data-title`, `data-gasto`, `data-leads`, `data-cpl`, `data-vendas`,
  `data-roas`, `data-cpm`, `data-ctr`, `data-hook`, `data-hold`, `data-body` na `<img>` da
  thumbnail. **Nunca** usar a chamada antiga de 2 argumentos `openVideoModal(preview, title)`
  — ela derruba silenciosamente o painel de métricas (hook rate/hold rate).

## Temas

Dois mecanismos:

1. **Temas pré-definidos** (`html[data-bs-theme="X"] { --bs-*: ... }` em `base.html`,
   linha ~1405 em diante) — valores conhecidos em tempo de build, aplicados via atributo no
   `<html>`. Lista atual (`BS_THEME_LABELS`, linha ~2657):

   | valor | rótulo | observação |
   |---|---|---|
   | `a` | Colorful | tema padrão |
   | `brabo` | Orange's New Black | cores oficiais da marca, extraídas do SVG real da logo |
   | `b` | Deep Lagoon | |
   | `c` | Slate Teal | |
   | `d` | Midnight Indigo | |
   | `outatime` | Outatime | easter egg De Volta para o Futuro; fonte + loading (relógio) próprios |
   | `predador` | Predador | easter egg Predador (1987); fonte + loading (mira/retícula) próprios |
   | `spidey` | Amigão da Vizinhança | easter egg Homem-Aranha (Raimi); fonte + loading (teia) próprios |
   | `aranhaverso` | Aranhaverso | easter egg Homem-Aranha no Aranhaverso (Miles Morales); fonte + loading (teia) próprios |
   | `springfield` | Springfield | easter egg Simpsons |

   Cada tema easter egg também troca a fonte (Google Fonts: Manrope, Archivo Black, Orbitron,
   Black Ops One, Bangers, Bungee, Luckiest Guy — todas carregadas num `@import` só) e a lista
   de frases da tela de loading (`BF_QUOTES`/`PD_QUOTES`/`SM_QUOTES`/`SV_QUOTES`/`BS_QUOTES`,
   lidas por `activeQuotes()`).

2. **Temas gerados pelo usuário** ("Gerador de Temas", em `/settings`) — o usuário escolhe 15
   cores base + fonte, salva com um nome; os tokens não são conhecidos em build-time, então são
   aplicados via JS (`document.documentElement.style.setProperty`, função
   `bsApplyCustomTokens`) e persistidos em `localStorage` (`bs-custom-themes`). Tokens
   derivados (ex.: `--bs-success-bg`) são calculados com `color-mix(in srgb, ...)` a partir das
   15 cores base para evitar exigir dezenas de seletores de cor. `--bs-info` sempre reusa a cor
   `accent` escolhida (não é configurável separadamente); as 4 sombras são derivadas só de
   `ink` — a UI do gerador documenta os dois. Calcula contraste WCAG ao vivo pra 4 pares
   críticos (ink×bg, ink×card, ink-muted×card, card×bg) e avisa inline se algum ficar ilegível.

O script anti-flash no `<head>` de `base.html` aplica o tema salvo (incluindo tokens
customizados) antes do primeiro paint, pra evitar flash de tema errado.

**Repintura de gráficos ao trocar de tema**: como Chart.js não resolve `var()`, trocar de tema
em runtime não repinta gráficos já desenhados sozinho — existe `bsRetintCharts(before, after)`
que percorre as instâncias Chart.js já montadas e troca os hex antigos pelos novos direto no
config/data, evitando reload de página inteira.

## Onde estão as coisas

| O quê | Onde |
|---|---|
| Tokens, temas, componentes CSS, acessórios JS (modal, accordion, gerador) | `frontend/templates/base.html` |
| UI do gerador de temas | `frontend/templates/settings.html` (seção "Gerador de Temas") |
| Página de referência visual (desatualizada, tratar com cautela) | `frontend/design-system.html` |

## Débito conhecido

A maior parte da auditoria de 14/09/26 (`projetos/LEVANTAMENTO_DESIGN_SYSTEM_2026-09-14.md`, no vault local) já foi
corrigida no mesmo dia (tokens inexistentes, contraste do modal de atalhos, falta de
`:focus-visible`, cores hardcoded restantes, drift do `design-system.html` de referência, e a
falta de aviso de contraste no gerador de temas). O único item de baixa prioridade que ficou em
aberto — `var(--bs-warning)` como cor de ícone isolado em 3 lugares — é cosmético e de baixo
risco.
