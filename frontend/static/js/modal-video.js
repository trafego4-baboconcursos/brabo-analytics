/* Extraído de frontend/templates/base.html em 21/09/2026.
   Carregado com <script> síncrono, na mesma ordem em que estava inline.
   Estes arquivos dependem dessa ordem (ex.: tema.js define bsThemeTokens,
   usado depois). Não adicionar defer/async sem revisar as dependências. */
/* modal de preview de vídeo do Drive */

var BS_VIDEO_METRIC_META = {
  gasto:  { label: 'Gasto',  icon: 'ti-currency-real',  color: '#34d399' },
  leads:  { label: 'Leads',  icon: 'ti-users',          color: '#60a5fa' },
  cpl:    { label: 'CPL',    icon: 'ti-target-arrow',   color: '#fbbf24' },
  vendas: { label: 'Vendas', icon: 'ti-shopping-cart',  color: '#f472b6' },
  roas:   { label: 'ROAS',   icon: 'ti-chart-line',     color: '#a78bfa' },
  cpm:    { label: 'CPM',    icon: 'ti-currency-dollar', color: '#fb923c' },
  ctr:    { label: 'CTR',    icon: 'ti-click',          color: '#ec4899', suffix: '%' }
};
var BS_VIDEO_RATE_META = {
  hook: { label: 'Hook Rate', color: '#8b5cf6' },
  hold: { label: 'Hold Rate', color: '#3b82f6' },
  body: { label: 'Body Rate', color: '#06b6d4' }
};
var BS_VIDEO_STAT_KEYS = ['gasto', 'leads', 'cpl', 'vendas', 'roas', 'cpm', 'ctr'];
var BS_VIDEO_RATE_KEYS = ['hook', 'hold', 'body'];

function bsBuildVideoMetricsHtml(m) {
  var stats = BS_VIDEO_STAT_KEYS.filter(function (k) { return m[k]; });
  var rates = BS_VIDEO_RATE_KEYS.filter(function (k) { return m[k]; });
  if (!stats.length && !rates.length) return '';

  var html = '<div class="vm-eyebrow">Métricas do anúncio</div>';
  if (stats.length) {
    html += '<div class="vm-stats-grid">';
    stats.forEach(function (k) {
      var meta = BS_VIDEO_METRIC_META[k];
      html += '<div class="vm-stat">' +
                '<div class="vm-stat-icon" style="background:' + meta.color + '22;color:' + meta.color + ';"><i class="ti ' + meta.icon + '"></i></div>' +
                '<div><div class="vm-stat-label">' + meta.label + '</div><div class="vm-stat-value">' + m[k] + (meta.suffix || '') + '</div></div>' +
              '</div>';
    });
    html += '</div>';
  }
  if (stats.length && rates.length) html += '<div class="vm-divider"></div>';
  if (rates.length) {
    html += '<div class="vm-rates">';
    rates.forEach(function (k) {
      var meta = BS_VIDEO_RATE_META[k];
      var pct = Math.max(0, Math.min(100, parseFloat((m[k] + '').replace(',', '.')) || 0));
      html += '<div class="vm-rate-row">' +
                '<div class="vm-rate-top"><span>' + meta.label + '</span><b>' + m[k] + '%</b></div>' +
                '<div class="vm-bar-track"><div class="vm-bar-fill" style="width:' + pct + '%;background:' + meta.color + ';"></div></div>' +
              '</div>';
    });
    html += '</div>';
  }
  return html;
}

/* ── Visualizador do criativo ───────────────────────────────────────────────
   Imagem → <img>; carrossel → quadros com setas; vídeo → player (Drive/YouTube) com as versões (Feed/Story).
   Abre na hora com a URL que a tabela já tem (data-preview) e, em seguida, pede a mídia completa do anúncio em
   /api/creative-media/<lançamento>/<ADxxx> (frontend/services/criativo_midia.py) e troca o título pelo nome completo.
   O iframe só serve para players externos: imagem do próprio site em iframe cai no X-Frame-Options: DENY. */
var BS_MODAL = { token: 0, itens: [], idx: 0, tipo: '' };
var BS_AD_RE = /\bAD[A-Z]{0,3}-?[A-Z]{0,3}\d+\b/i;
var BS_IFRAME_RE = /(^|\/\/)(www\.)?(drive\.google\.com|docs\.google\.com|youtube\.com|youtube-nocookie\.com|youtu\.be)\//i;

function bsModalEl(id) { return document.getElementById(id); }
function bsEhPlayer(item) { return item.kind === 'drive_video' || item.kind === 'youtube'; }

function bsRotuloItem(item, i, tipo) {
  if (item.rotulo) return item.rotulo;
  if (item.kind === 'youtube') return 'YouTube';
  var n = item.nome || '';
  if (item.kind === 'drive_video') {
    var m = n.match(/\((feed|story|reels?)\)|\b(feed|story|reels?)\b/i);
    return m ? (m[1] || m[2]).replace(/^./, function (c) { return c.toUpperCase(); }) : 'Vídeo ' + (i + 1);
  }
  return tipo === 'carrossel' ? String(i + 1) : (/meta/i.test(n) ? 'Imagem' : 'Imagem ' + (i + 1));
}

function bsMostrarItem(i) {
  var itens = BS_MODAL.itens;
  if (!itens.length) return;
  BS_MODAL.idx = (i + itens.length) % itens.length;
  var item = itens[BS_MODAL.idx];
  var img = bsModalEl('video-modal-img'), frame = bsModalEl('video-modal-frame'), aviso = bsModalEl('video-modal-aviso');
  aviso.style.display = 'none';
  if (bsEhPlayer(item)) {
    img.style.display = 'none'; img.removeAttribute('src');
    frame.style.display = 'block'; frame.src = item.src;
  } else {
    frame.style.display = 'none'; frame.src = '';
    img.style.display = 'block'; img.src = item.src;
  }
  bsModalEl('video-modal-viewer').classList.toggle('vm-alto', !bsEhPlayer(item));
  var carrossel = BS_MODAL.tipo === 'carrossel' && itens.length > 1;
  bsModalEl('video-modal-prev').style.display = bsModalEl('video-modal-next').style.display = carrossel ? 'flex' : 'none';
  var cont = bsModalEl('video-modal-count');
  cont.style.display = carrossel ? 'block' : 'none';
  cont.textContent = (BS_MODAL.idx + 1) + ' / ' + itens.length;
  var chips = bsModalEl('video-modal-chips').children;
  for (var k = 0; k < chips.length; k++) chips[k].classList.toggle('ativo', k === BS_MODAL.idx);
}

function bsMontarSeletor() {
  var box = bsModalEl('video-modal-chips');
  box.innerHTML = '';
  var itens = BS_MODAL.itens;
  box.style.display = itens.length > 1 ? 'flex' : 'none';
  if (itens.length < 2) return;
  itens.forEach(function (item, i) {
    var b = document.createElement('button');
    b.type = 'button';
    b.className = 'vm-chip' + (BS_MODAL.tipo === 'carrossel' ? ' vm-chip-num' : '');
    b.textContent = bsRotuloItem(item, i, BS_MODAL.tipo);
    b.title = item.nome || '';
    b.onclick = function () { bsMostrarItem(i); };
    box.appendChild(b);
  });
}

function bsAplicarItens(itens, tipo) {
  BS_MODAL.itens = itens; BS_MODAL.tipo = tipo || '';
  bsMontarSeletor();
  bsMostrarItem(0);
}

function bsAvisoModal(msg) {
  var a = bsModalEl('video-modal-aviso');
  a.textContent = msg; a.style.display = 'flex';
}

window.openVideoModal = function (previewUrl, title, metrics, opts) {
  opts = opts || {};
  var token = ++BS_MODAL.token;
  var overlay = bsModalEl('video-modal-overlay');
  var tituloEl = bsModalEl('video-modal-title');
  tituloEl.textContent = title || ''; tituloEl.title = title || '';
  var panel = bsModalEl('video-modal-metrics');
  var html = metrics ? bsBuildVideoMetricsHtml(metrics) : '';
  panel.innerHTML = html;
  panel.style.display = html ? 'flex' : 'none';
  overlay.style.display = 'flex';

  // 1) o que a tabela já sabe, para abrir sem espera
  BS_MODAL.itens = []; BS_MODAL.tipo = '';
  bsModalEl('video-modal-chips').innerHTML = '';
  bsModalEl('video-modal-chips').style.display = 'none';
  bsModalEl('video-modal-prev').style.display = bsModalEl('video-modal-next').style.display = 'none';
  bsModalEl('video-modal-count').style.display = 'none';
  if (previewUrl) {
    bsAplicarItens([{ kind: BS_IFRAME_RE.test(previewUrl) ? 'drive_video' : 'image', src: previewUrl, nome: title }], '');
  } else {
    bsModalEl('video-modal-img').style.display = 'none';
    bsModalEl('video-modal-frame').style.display = 'none';
    bsAvisoModal('Carregando o criativo…');
  }

  // 2) a mídia completa do anúncio (carrossel, versões do vídeo, nome completo)
  var achado = (title || '').match(BS_AD_RE) || (previewUrl || '').match(BS_AD_RE);
  var ad = (opts.ad || (achado ? achado[0] : '') || '').toUpperCase();
  var launch = opts.launch || overlay.dataset.launch || '_';
  if (!ad) return;
  fetch('/api/creative-media/' + encodeURIComponent(launch) + '/' + encodeURIComponent(ad), { credentials: 'same-origin' })
    .then(function (r) { return r.ok ? r.json() : { ok: false }; })
    .then(function (d) {
      if (token !== BS_MODAL.token) return;               // o modal já foi fechado ou aberto em outro criativo
      if (d && d.ok && d.itens && d.itens.length) {
        if (d.nome) { tituloEl.textContent = d.nome; tituloEl.title = d.nome; }
        bsAplicarItens(d.itens, d.tipo);
      } else if (!previewUrl) {
        bsAvisoModal('Sem imagem ou vídeo para este anúncio.');
      }
    })
    .catch(function () {
      if (token === BS_MODAL.token && !previewUrl) bsAvisoModal('Não foi possível carregar o criativo.');
    });
};
window.openVideoModalFromEl = function (el) {
  var metrics = {
    gasto: el.dataset.gasto, leads: el.dataset.leads, cpl: el.dataset.cpl,
    vendas: el.dataset.vendas, roas: el.dataset.roas, cpm: el.dataset.cpm,
    ctr: el.dataset.ctr, hook: el.dataset.hook, hold: el.dataset.hold, body: el.dataset.body
  };
  window.openVideoModal(el.dataset.preview, el.dataset.title, metrics, { ad: el.dataset.ad, launch: el.dataset.launch });
};
window.closeVideoModal = function () {
  BS_MODAL.token++;
  bsModalEl('video-modal-frame').src = '';
  bsModalEl('video-modal-img').removeAttribute('src');
  bsModalEl('video-modal-overlay').style.display = 'none';
};
document.addEventListener('keydown', function (e) {
  if (e.key === 'Escape') closeVideoModal();
  var ov = bsModalEl('video-modal-overlay');
  if (ov && ov.style.display === 'flex' && BS_MODAL.tipo === 'carrossel') {
    if (e.key === 'ArrowRight') bsMostrarItem(BS_MODAL.idx + 1);
    if (e.key === 'ArrowLeft') bsMostrarItem(BS_MODAL.idx - 1);
  }
});
