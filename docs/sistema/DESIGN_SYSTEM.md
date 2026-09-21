---
titulo: "Design System — Brabo Analytics"
area: sistema
status: vigente
atualizado: 2026-09-21
responde:
  - "tokens, componentes e temas do dashboard"
  - "onde mexer no CSS"
  - "como funciona o gerador de temas"
  - "como mudar a ordem padrão das seções de uma página"
  - "onde ficam salvas as visualizações de seções"
  - "como funciona a busca de seções"
relacionados:
  - "[[ARQUITETURA]]"
---

# Design System — Brabo Analytics

Como o design system do dashboard funciona por dentro: tokens, componentes compartilhados,
temas e o gerador de temas. Vive em `frontend/static/` e é herdado por todo template via
`{% extends "base.html" %}`, que carrega os arquivos na ordem certa.

**Até 21/09/2026 tudo isso era inline dentro do `base.html`** — 1.827 linhas de CSS e 2.343 de
JS num arquivo de 5.053 linhas. Foi extraído para arquivos servidos em `/static` (o `base.html`
ficou com 942 linhas, só markup). Nenhuma regra ou função mudou na extração; só saíram de dentro
do HTML. Docs e comentários antigos que dizem "no fim de `base.html`" se referem a este estado
anterior — o mapa atual está em **Onde estão as coisas**, no fim deste doc.

**Não confundir com** `frontend/design-system.html` — é uma página de referência visual (HTML
solto, fora do fluxo de rotas) que mostra os componentes isolados. Ela desatualiza com
frequência porque não é gerada a partir do CSS real; trate como esboço, não como fonte da
verdade. A fonte da verdade é sempre o CSS em `frontend/static/css/`.

## Tokens (`:root`, `frontend/static/css/tokens.css`)

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
  mostrar, tags de etapa auto-detectadas, busca que filtra a página e "visualizações" salvas
  nomeadas (igual ao gerenciador de colunas do Google Ads) — tudo implementado numa IIFE única
  em `frontend/static/js/secoes.js` (`SKIP_PAGES`, `TAG_DEFS`, `detectTag`, `applyState`, `renderSecPanel`,
  `renderViewsPanel`, `aplicarBusca`). Roda em toda página automaticamente por detectar o
  markup — não precisa registrar nada por template, exceto páginas na lista `SKIP_PAGES`
  (`settings`, `login`, `invite`, `index`) e o modo apresentação/PDF do debriefing
  (`?modo=slides`, guardado via `document.documentElement.classList.contains('bs-slides')`).

  **Key da seção** vem do slug do título (`captacao-meta-ads`), não da posição no documento.
  Era `section-<idx>` até 17/09/26 — com as visualizações no banco, índice quebraria em
  silêncio assim que alguém inserisse uma seção no meio do template. `data-sec-key` no título
  fixa a key à mão quando o título for mudar. Estado salvo com as keys antigas continua sendo
  lido (`migrarKeys`).

  **Visualizações** ficam no banco operacional (tabela `section_views`, migration 010), não
  mais só no localStorage:
  - escopo `user` — pessoais, seguem a pessoa entre navegadores;
  - escopo `global` — da equipe; só **admin/analista** escreve. A marcada como `is_padrao` é a
    que qualquer pessoa abre na primeira visita àquela página — é assim que se muda a ordem
    "padrão" sem mexer no HTML.

  Cada visualização guarda `order`, `hidden`, `collapsed` **e** `customs` (apelidos e tags das
  seções). No painel dá pra aplicar, salvar por cima, renomear, excluir e promover a padrão.
  "Ordem original do sistema" continua existindo como saída de emergência: volta pra ordem crua
  do template. O estado *de trabalho* (o que está na tela agora) segue no localStorage — arrastar
  seção não bate no banco a cada gesto. Sem a migration 010, o painel cai de volta no
  localStorage sozinho e avisa na dica do rodapé.

  **Busca** (`.bs-sec-search`, no topo, junto de Recolher/Expandir): filtra a página inteira —
  o que casa fica, o resto some. Título e tag primeiro; conteúdo da seção só entra quando
  **nenhum** título casa, senão procurar "vendas" traria meia página por causa de uma palavra
  solta numa tabela. Ignora acento, expande o que achou e ganha de seção ocultada no painel
  (`.bs-search-hit` vence `.bs-hidden-section`). É efêmera: limpar restaura o estado anterior.
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

1. **Temas pré-definidos** (`html[data-bs-theme="X"] { --bs-*: ... }` em
   `frontend/static/css/temas.css`) — valores conhecidos em tempo de build, aplicados via
   atributo no `<html>`. Lista atual (`BS_THEME_LABELS`, em `static/js/tema.js`):

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
customizados) antes do primeiro paint, pra evitar flash de tema errado. É o único JS que
**continua inline** depois da extração de 21/09/2026, justamente por isso.

**Repintura de gráficos ao trocar de tema**: como Chart.js não resolve `var()`, trocar de tema
em runtime não repinta gráficos já desenhados sozinho — existe `bsRetintCharts(before, after)`
(em `frontend/static/js/tema.js`)
que percorre as instâncias Chart.js já montadas e troca os hex antigos pelos novos direto no
config/data, evitando reload de página inteira.

## Onde estão as coisas

Os arquivos abaixo são carregados pelo `base.html` **nesta ordem**, que é a cascata do CSS e a
ordem de dependência do JS. Reordenar quebra coisas em silêncio — ver o comentário no `<head>`.

| # | CSS (`frontend/static/css/`) | o que tem dentro |
|---|---|---|
| 1 | `tokens.css` | `:root`, os 61 `--bs-*`, reset, `:focus-visible` |
| 2 | `layout.css` | frame, sidebar, seletor de lançamento, mode rail, subnav, nav, barra de progresso, overlay de carregamento (e os easter eggs), main |
| 3 | `componentes.css` | seções recolhíveis, dropdown de seções, busca, métricas grid, KPI, highlights, info-box, tabelas, funil, pills e badges |
| 4 | `utilitarios.css` | animações, hover lift, live badge, menu de conta, modal de atalhos, topbar mobile |
| 5 | `responsivo.css` | todas as media queries |
| 6 | `wizard-lancamento.css` | modal do wizard de lançamento |
| 7 | `temas.css` | os 10 temas (`html[data-bs-theme="X"]`) — sobrescreve os tokens, por isso vem depois |
| 8 | `modal-video.css` | modal de preview de vídeo |

| # | JS (`frontend/static/js/`) | o que tem dentro |
|---|---|---|
| 1 | `carregamento.js` | frases de loading, barra de progresso, overlay de navegação |
| 2 | `tabelas.js` | export CSV de tabela, marcação da linha de total |
| 3 | `nav.js` | menu mobile, `bsSoftNavigate`, pickers da trilha |
| 4 | `tema.js` | `bsSetTheme`, `bsApplyCustomTokens`, `bsRetintCharts` |
| 5 | `secoes.js` | accordion, ordem/visibilidade, visualizações salvas, busca (a IIFE grande) |
| 6 | `acoes.js` | subnav, menu de conta, `bsRunEtl`, atalhos de teclado |
| 7 | `modal-video.js` | `openVideoModalFromEl` e o painel de métricas |
| 8 | `wizard-lancamento.js` | todo o `lc*` — etapas, curva de verba, buckets |

**O que continua inline no `base.html`, de propósito:**

| o quê | por quê |
|---|---|
| `<style id="brabo-accent">` | depende de `{{ accent }}` — a cor é do lançamento aberto |
| script anti-flash no `<head>` | precisa rodar **antes do primeiro paint**; num `<script src>` a rede entraria no caminho crítico e voltaria o flash de tema errado que ele existe pra evitar |
| markup do modal de vídeo e do wizard | é HTML, não CSS/JS |

`secoes.js` lê a página atual de `document.body.dataset.page` (o `<body>` recebe
`data-page="{{ page }}"`); antes era `{{ page }}` interpolado direto no JS.

As URLs saem do helper `static_url()` (`frontend/core.py`), que anexa `?v=<mtime>` — sem isso o
navegador serviria CSS velho depois do deploy, porque o `Cache-Control: no-store` do middleware
só vale para `text/html`.

| Outros | Onde |
|---|---|
| UI do gerador de temas | `frontend/templates/settings.html` (seção "Gerador de Temas") |
| Página de referência visual (desatualizada, tratar com cautela) | `frontend/design-system.html` |

## Débito conhecido

A maior parte da auditoria de 14/09/26 (`projetos/LEVANTAMENTO_DESIGN_SYSTEM_2026-09-14.md`, no vault local) já foi
corrigida no mesmo dia (tokens inexistentes, contraste do modal de atalhos, falta de
`:focus-visible`, cores hardcoded restantes, drift do `design-system.html` de referência, e a
falta de aviso de contraste no gerador de temas). O único item de baixa prioridade que ficou em
aberto — `var(--bs-warning)` como cor de ícone isolado em 3 lugares — é cosmético e de baixo
risco.
