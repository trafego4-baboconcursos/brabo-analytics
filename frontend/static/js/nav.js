/* Extraído de frontend/templates/base.html em 21/09/2026.
   Carregado com <script> síncrono, na mesma ordem em que estava inline.
   Estes arquivos dependem dessa ordem (ex.: tema.js define bsThemeTokens,
   usado depois). Não adicionar defer/async sem revisar as dependências. */
/* menu lateral, soft navigation, pickers da trilha */

/* ── Menu mobile (gaveta) ──────────────────────────────────────────── */
window.bsMenuToggle = function(force) {
  var drawer  = document.getElementById('bs-drawer');
  var overlay = document.getElementById('bs-drawer-overlay');
  if (!drawer) return;
  var open = (typeof force === 'boolean') ? force : !drawer.classList.contains('open');
  drawer.classList.toggle('open', open);
  if (overlay) overlay.classList.toggle('open', open);
  document.body.style.overflow = open ? 'hidden' : '';
  if (!open) {
    /* Fecha a gaveta sempre voltando pro menu principal — reabrir não
       deve pular direto pro drill-down que estava aberto antes. */
    document.querySelectorAll('.bs-launch-picker.open').forEach(function(p) { p.classList.remove('open'); });
    drawer.classList.remove('bs-drilled');
  }
};
document.querySelectorAll('#bs-drawer .bs-nav-link, #bs-drawer .bs-camp-select').forEach(function(el) {
  el.addEventListener('click', function() {
    if (window.innerWidth > 1024) return;
    bsMenuToggle(false);
  });
});
/* Trocar de lançamento/perfil ou abrir uma página pesada do menu mobile
   (Meta Ads, Captação...) costuma esperar 1-3s de banco sem cache — tempo
   suficiente pro navegador abandonar a página atual (com nosso overlay de
   loading) e mostrar tela branca até a resposta chegar, comportamento
   nativo dele em navegação normal, não dá pra evitar só com CSS/JS na
   página que está saindo. Busca o HTML via fetch primeiro, mantendo a
   página (e o overlay) na tela o tempo todo, e só troca quando a resposta
   já chegou — document.write (não innerHTML) porque preserva a execução
   normal dos <script> inline, igual uma navegação de verdade. */
function bsSoftNavigate(url, updateHistory) {
  window.bsStartProgress();
  fetch(url, { credentials: 'same-origin' })
    .then(function(r) { return r.text().then(function(html) { return { html: html, finalUrl: r.url }; }); })
    .then(function(res) {
      if (updateHistory) history.pushState(null, '', res.finalUrl);
      document.open();
      document.write(res.html);
      document.close();
    })
    .catch(function() {
      /* Fetch falhou (rede caiu, CORS, etc) — cai pra navegação normal em
         vez de deixar a pessoa presa com o overlay girando pra sempre. */
      window.location.href = url;
    });
}
document.querySelectorAll('#bs-drawer .bs-launch-picker-item, #bs-drawer .bs-launch-picker-all, #bs-drawer .bs-subnav-link').forEach(function(el) {
  el.addEventListener('click', function(e) {
    if (window.innerWidth > 1024) return;
    var href = el.getAttribute('href');
    if (!href) return;
    e.preventDefault();
    bsMenuToggle(false);
    bsSoftNavigate(href, true);
  });
});
/* pushState não navega de verdade — sem isso, Voltar/Avançar do navegador
   só trocaria a URL da barra, mantendo o conteúdo da página anterior na
   tela. false = não empilha de novo, o histórico já tem essa posição. */
window.addEventListener('popstate', function() {
  bsSoftNavigate(location.href, false);
});
window.addEventListener('resize', function() {
  if (window.innerWidth > 1024) bsMenuToggle(false);
});

/* ── Pickers da trilha (Lançamento/Perpétuo/Distribuição/Redes Sociais) ──
   O menu usa position:fixed (ver CSS) pra escapar do overflow:auto da
   sidebar, então a posição precisa ser calculada em JS a partir do botão
   toda vez que o menu abre (e recalculada em scroll/resize enquanto aberto,
   já que fixed não acompanha o scroll interno da sidebar). ── */
function bsPositionPickerMenu(picker) {
  var btn = picker.querySelector('.bs-launch-picker-btn');
  var menu = picker.querySelector('.bs-launch-picker-menu');
  if (!btn || !menu) return;
  var rect = btn.getBoundingClientRect();
  var top = rect.bottom + 4;
  var left = rect.left;
  menu.style.top = top + 'px';
  menu.style.left = left + 'px';
  var maxLeft = window.innerWidth - menu.offsetWidth - 8;
  if (left > maxLeft) left = Math.max(8, maxLeft);
  var maxTop = window.innerHeight - menu.offsetHeight - 8;
  if (top > maxTop) top = Math.max(8, maxTop);
  menu.style.left = left + 'px';
  menu.style.top = top + 'px';
}
/* No celular (≤1024px) o dropdown vira um painel drill-down ocupando a
   gaveta inteira (ver CSS #bs-drawer.bs-drilled) em vez de flutuar por
   cima do menu principal — abrir um picker esconde o resto do menu. */
function bsIsMobileDrawer() { return window.innerWidth <= 1024; }
window.bsPickerToggle = function(btn) {
  var picker = btn.closest('.bs-launch-picker');
  if (!picker) return;
  var open = picker.classList.contains('open');
  document.querySelectorAll('.bs-launch-picker.open').forEach(function(p) { p.classList.remove('open'); });
  picker.classList.toggle('open', !open);
  var drawer = document.getElementById('bs-drawer');
  if (bsIsMobileDrawer()) {
    if (drawer) drawer.classList.toggle('bs-drilled', !open);
  } else if (!open) {
    bsPositionPickerMenu(picker);
  }
};
document.addEventListener('click', function(e) {
  if (!e.target.closest('.bs-launch-picker')) {
    document.querySelectorAll('.bs-launch-picker.open').forEach(function(p) { p.classList.remove('open'); });
    var drawer = document.getElementById('bs-drawer');
    if (drawer) drawer.classList.remove('bs-drilled');
  }
});
/* Acordeão dos grupos de página (Visão Geral/Mídia Paga/...) dentro do
   painel de Lançamento no celular — expande no próprio painel, não abre
   outro nível de drill-down (só um grupo aberto por vez). */
window.bsPickerSubToggle = function(btn) {
  var sub = btn.closest('.bs-picker-subgroup');
  if (!sub) return;
  var open = sub.classList.contains('open');
  var parent = sub.parentElement;
  if (parent) {
    parent.querySelectorAll('.bs-picker-subgroup.open').forEach(function(s) { s.classList.remove('open'); });
  }
  sub.classList.toggle('open', !open);
};
['scroll', 'resize'].forEach(function(evt) {
  window.addEventListener(evt, function() {
    if (bsIsMobileDrawer()) return;
    var open = document.querySelector('.bs-launch-picker.open');
    if (open) bsPositionPickerMenu(open);
  }, true);
});
window.addEventListener('resize', function() {
  if (!bsIsMobileDrawer()) {
    var drawer = document.getElementById('bs-drawer');
    if (drawer) drawer.classList.remove('bs-drilled');
  }
});
