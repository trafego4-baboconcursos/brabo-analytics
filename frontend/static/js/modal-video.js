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

window.openVideoModal = function (previewUrl, title, metrics) {
  document.getElementById('video-modal-title').textContent = title || '';
  document.getElementById('video-modal-frame').src = previewUrl;
  var panel = document.getElementById('video-modal-metrics');
  var html = metrics ? bsBuildVideoMetricsHtml(metrics) : '';
  panel.innerHTML = html;
  panel.style.display = html ? 'flex' : 'none';
  document.getElementById('video-modal-overlay').style.display = 'flex';
};
window.openVideoModalFromEl = function (el) {
  var metrics = {
    gasto: el.dataset.gasto, leads: el.dataset.leads, cpl: el.dataset.cpl,
    vendas: el.dataset.vendas, roas: el.dataset.roas, cpm: el.dataset.cpm,
    ctr: el.dataset.ctr, hook: el.dataset.hook, hold: el.dataset.hold, body: el.dataset.body
  };
  window.openVideoModal(el.dataset.preview, el.dataset.title, metrics);
};
window.closeVideoModal = function () {
  document.getElementById('video-modal-frame').src = '';
  document.getElementById('video-modal-overlay').style.display = 'none';
};
document.addEventListener('keydown', function (e) {
  if (e.key === 'Escape') closeVideoModal();
});
