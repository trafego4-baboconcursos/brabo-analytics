/* Extraído de frontend/templates/base.html em 21/09/2026.
   Carregado com <script> síncrono, na mesma ordem em que estava inline.
   Estes arquivos dependem dessa ordem (ex.: tema.js define bsThemeTokens,
   usado depois). Não adicionar defer/async sem revisar as dependências. */
/* troca de tema, tokens customizados, repintura dos gráficos */

/* ── Seletor de tema (em teste) ────────────────────────────────────────
   Troca os tokens --bs-* globalmente via atributo data-bs-theme no <html>
   (ver <style id="brabo-theme-variant"> no <head>). Persiste só no
   navegador (localStorage) por enquanto — cada pessoa escolhe o seu. ── */
/* Lê o valor atual de todos os custom properties (--*) declarados nos
   <style> inline da página — é o conjunto de tokens que os gráficos
   copiam na hora do draw. Snapshot antes/depois de trocar o atributo
   diz exatamente qual cor virou qual. */
function bsThemeTokens() {
  var names = {};
  var sheets = document.styleSheets;
  for (var i = 0; i < sheets.length; i++) {
    var rules;
    try { rules = sheets[i].cssRules; } catch (e) { continue; }  /* cross-origin */
    if (!rules) continue;
    for (var j = 0; j < rules.length; j++) {
      var st = rules[j].style;
      if (!st) continue;
      for (var k = 0; k < st.length; k++) {
        if (st[k].indexOf('--') === 0) names[st[k]] = 1;
      }
    }
  }
  var cs = getComputedStyle(document.documentElement);
  var out = {};
  Object.keys(names).forEach(function(n) { out[n] = cs.getPropertyValue(n).trim(); });
  return out;
}

/* Gráficos Chart.js copiam a cor dos tokens no momento da criação
   (canvas não escuta mudança de CSS custom property). Em vez de recarregar
   a página — que no debriefing custa uma requisição inteira ao servidor —
   troca, dentro da config de cada gráfico vivo, toda cor antiga pela nova
   (mantendo sufixo de alpha tipo "#f9731622") e manda o Chart.js redesenhar. */
function bsRetintCharts(before, after) {
  if (typeof Chart === 'undefined' || !Chart.instances) return;
  var pairs = [];
  Object.keys(before).forEach(function(n) {
    var o = before[n], nw = after[n];
    if (!o || !nw || o === nw) return;
    if (!/^(#|rgb|hsl)/i.test(o) || o.length < 4) return;  /* só cores */
    pairs.push([o.toLowerCase(), nw]);
  });
  if (!pairs.length) return;
  pairs.sort(function(a, b) { return b[0].length - a[0].length; });  /* mais longa primeiro (#rrggbb antes de #rgb) */
  function swap(s) {
    var low = s.toLowerCase();
    for (var i = 0; i < pairs.length; i++) {
      if (low.indexOf(pairs[i][0]) === 0) return pairs[i][1] + s.slice(pairs[i][0].length);
    }
    return s;
  }
  var seen = typeof WeakSet !== 'undefined' ? new WeakSet() : null;
  function walk(obj, depth) {
    if (!obj || typeof obj !== 'object' || depth > 12) return;
    if (seen) { if (seen.has(obj)) return; seen.add(obj); }
    if (obj instanceof HTMLElement || obj instanceof CanvasRenderingContext2D) return;
    var keys = Object.keys(obj);
    for (var i = 0; i < keys.length; i++) {
      var k = keys[i], v = obj[k];
      if (typeof v === 'string') { var nv = swap(v); if (nv !== v) obj[k] = nv; }
      else if (v && typeof v === 'object') walk(v, depth + 1);
    }
  }
  Object.keys(Chart.instances).forEach(function(id) {
    var ch = Chart.instances[id];
    if (!ch) return;
    try {
      /* v4: config._config é o objeto cru passado em new Chart(); data/options
         resolvidos derivam dele no update(). Anda nos dois pra cobrir v3/v4. */
      walk(ch.config && ch.config._config ? ch.config._config : ch.config, 0);
      walk(ch.data, 0);
      ch.update('none');
    } catch (e) {}
  });
}

window.bsSetTheme = function(v) {
  try { localStorage.setItem('bs-theme-variant', v); } catch (e) {}
  try {
    var before = bsThemeTokens();
    if (v === 'a') document.documentElement.removeAttribute('data-bs-theme');
    else document.documentElement.setAttribute('data-bs-theme', v);
    bsRetintCharts(before, bsThemeTokens());
    bsThemeSyncActive();
    document.querySelectorAll('.bs-launch-picker.open').forEach(function(p) { p.classList.remove('open'); });
  } catch (e) {
    /* Qualquer imprevisto: cai no comportamento antigo, que sempre funciona. */
    location.reload();
  }
};
/* Tema gerado em /settings — mesma ideia do bsSetTheme, mas as cores vêm
   de localStorage (bs-custom-themes), setadas direto como --bs-* no
   <html> (não dá pra usar html[data-bs-theme="x"] pré-escrito porque o
   nome/cores só existem em runtime). Todo tema custom compartilha o
   marcador data-bs-theme="custom"; qual deles está ativo vem do prefixo
   "custom:" salvo em bs-theme-variant. */
/* Aplica um conjunto de tokens "base" (os 15 escolhidos no gerador) mais
   os companheiros derivados via color-mix() — mesma fórmula usada na
   prévia ao vivo do gerador em /settings, pra não desalinhar as duas. */
function bsApplyCustomTokens(t) {
  var root = document.documentElement.style;
  Object.keys(t).forEach(function (k) {
    if (k === 'font') root.setProperty('--bs-custom-font', t.font);
    else root.setProperty('--bs-' + k, t[k]);
  });
  root.setProperty('--bs-accent-bg', 'color-mix(in srgb, ' + t['accent'] + ' 12%, ' + t['card'] + ')');
  root.setProperty('--bs-success-bg', 'color-mix(in srgb, ' + t['success'] + ' 15%, ' + t['card'] + ')');
  root.setProperty('--bs-warning-bg', 'color-mix(in srgb, ' + t['warning'] + ' 15%, ' + t['card'] + ')');
  root.setProperty('--bs-danger-bg', 'color-mix(in srgb, ' + t['danger'] + ' 15%, ' + t['card'] + ')');
  root.setProperty('--bs-info', t['accent']);
  root.setProperty('--bs-info-bg', 'color-mix(in srgb, ' + t['accent'] + ' 12%, ' + t['card'] + ')');
  root.setProperty('--bs-sh-sm', '0 1px 3px color-mix(in srgb, ' + t['ink'] + ' 10%, transparent)');
  root.setProperty('--bs-sh-md', '0 4px 12px color-mix(in srgb, ' + t['ink'] + ' 12%, transparent)');
  root.setProperty('--bs-sh-lg', '0 12px 30px color-mix(in srgb, ' + t['ink'] + ' 14%, transparent)');
  root.setProperty('--bs-sh-xl', '0 20px 60px color-mix(in srgb, ' + t['ink'] + ' 20%, transparent)');
}
window.bsSetCustomTheme = function(name) {
  try {
    var themes = JSON.parse(localStorage.getItem('bs-custom-themes') || '{}');
    var t = themes[name];
    if (!t) return;
    var before = bsThemeTokens();
    localStorage.setItem('bs-theme-variant', 'custom:' + name);
    document.documentElement.setAttribute('data-bs-theme', 'custom');
    bsApplyCustomTokens(t);
    bsRetintCharts(before, bsThemeTokens());
    bsThemeSyncActive();
    document.querySelectorAll('.bs-launch-picker.open').forEach(function(p) { p.classList.remove('open'); });
  } catch (e) {
    location.reload();
  }
};
var BS_THEME_LABELS = { a: 'Colorful', brabo: "Orange's New Black", b: 'Deep Lagoon', c: 'Slate Teal', d: 'Midnight Indigo', outatime: 'Outatime', predador: 'Predador', spidey: 'Amigão da Vizinhança', aranhaverso: 'Aranhaverso', springfield: 'Springfield', boss: 'Boss' };
function bsRenderCustomThemeOpts() {
  var menu = document.getElementById('bs-custom-theme-opts');
  if (!menu) return;
  var themes = {};
  try { themes = JSON.parse(localStorage.getItem('bs-custom-themes') || '{}'); } catch (e) {}
  var names = Object.keys(themes).sort();
  menu.innerHTML = '';
  if (!names.length) return;
  var sep = document.createElement('div');
  sep.className = 'bs-launch-picker-sep';
  menu.appendChild(sep);
  var group = document.createElement('div');
  group.className = 'bs-launch-picker-group';
  group.textContent = 'Meus temas (Configurações)';
  menu.appendChild(group);
  names.forEach(function(name) {
    var btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'bs-theme-opt';
    btn.dataset.themeVal = 'custom:' + name;
    var dotColor = (themes[name] && themes[name].accent) || '#374151';
    btn.innerHTML = '<span class="bs-theme-dot" style="background:' + dotColor + '"></span> ' + String(name).replace(/</g, '&lt;');
    btn.addEventListener('click', function () { bsSetCustomTheme(name); });
    menu.appendChild(btn);
  });
}
window.bsThemeSyncActive = function() {
  bsRenderCustomThemeOpts();
  var current = document.documentElement.getAttribute('data-bs-theme') || 'a';
  var variant = '';
  try { variant = localStorage.getItem('bs-theme-variant') || ''; } catch (e) {}
  var activeVal = current === 'custom' ? variant : current;
  document.querySelectorAll('#bs-theme-picker .bs-theme-opt').forEach(function(b) {
    b.classList.toggle('active', b.dataset.themeVal === activeVal);
  });
  var badge = document.getElementById('bs-theme-badge');
  var label = document.getElementById('bs-theme-badge-label');
  var btn = document.getElementById('bs-theme-btn');
  if (badge && label) {
    label.textContent = current === 'custom' ? variant.slice(7) : (BS_THEME_LABELS[current] || current);
    badge.style.display = '';
  }
  if (btn) btn.classList.add('bs-has-badge');
};
document.addEventListener('DOMContentLoaded', bsThemeSyncActive);
