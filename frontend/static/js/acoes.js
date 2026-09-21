/* Extraído de frontend/templates/base.html em 21/09/2026.
   Carregado com <script> síncrono, na mesma ordem em que estava inline.
   Estes arquivos dependem dessa ordem (ex.: tema.js define bsThemeTokens,
   usado depois). Não adicionar defer/async sem revisar as dependências. */
/* subnav, menu de conta, rodar ETL, atalhos de teclado */

/* ── Subnav horizontal (modo Funis, desktop) — clique abre/fecha ─────── */
window.bsSubnavToggle = function(btn) {
  var group = btn.closest('.bs-subnav-group');
  if (!group) return;
  var open = group.classList.contains('open');
  document.querySelectorAll('.bs-subnav-group.open').forEach(function(g) { g.classList.remove('open'); });
  group.classList.toggle('open', !open);
};
document.addEventListener('click', function(e) {
  if (!e.target.closest('.bs-subnav-group')) {
    document.querySelectorAll('.bs-subnav-group.open').forEach(function(g) { g.classList.remove('open'); });
  }
});
document.addEventListener('keydown', function(e) {
  if (e.key === 'Escape') {
    document.querySelectorAll('.bs-subnav-group.open').forEach(function(g) { g.classList.remove('open'); });
  }
});

/* ── Account dropdown ───────────────────────────────────────────────── */
window.bsAcctToggle = function() {
  var menu = document.getElementById('bs-acct-menu');
  var btn  = document.getElementById('bs-acct-btn');
  if (!menu) return;
  var open = menu.classList.contains('open');
  menu.classList.toggle('open', !open);
  btn.classList.toggle('open', !open);
};
document.addEventListener('click', function(e) {
  if (!e.target.closest('#bs-acct-wrap')) {
    var menu = document.getElementById('bs-acct-menu');
    var btn  = document.getElementById('bs-acct-btn');
    if (menu) menu.classList.remove('open');
    if (btn)  btn.classList.remove('open');
  }
});

/* ── Disparo manual do ETL ──────────────────────────────────────────── */
window.bsRunEtl = function() {
  var btn = document.getElementById('bs-run-etl-btn');
  var msgEl = document.getElementById('bs-etl-last-sync');
  if (!btn || btn.disabled) return;
  if (!confirm('Rodar o ETL agora (últimos 3 dias)? Pode levar alguns minutos.')) return;
  var original = btn.innerHTML;
  var originalMsg = msgEl ? msgEl.innerHTML : '';
  var originalColor = msgEl ? msgEl.style.color : '';
  btn.disabled = true;
  btn.innerHTML = '<span class="bs-nav-icon"><i class="ti ti-loader-2"></i></span>Disparando...';
  fetch('/api/run-etl', { method: 'POST' })
    .then(function(r) { return r.json(); })
    .then(function(data) {
      if (!msgEl) return;
      if (data.error) {
        msgEl.style.color = 'var(--bs-danger)';
        msgEl.textContent = data.error;
      } else {
        msgEl.style.color = 'var(--bs-success)';
        msgEl.textContent = data.message || 'ETL disparado com sucesso.';
      }
    })
    .catch(function() {
      if (msgEl) {
        msgEl.style.color = 'var(--bs-danger)';
        msgEl.textContent = 'Falha ao disparar o ETL — tente novamente.';
      }
    })
    .finally(function() {
      btn.disabled = false;
      btn.innerHTML = original;
      if (msgEl) {
        setTimeout(function() {
          msgEl.style.color = originalColor;
          msgEl.innerHTML = originalMsg;
        }, 15000);
      }
    });
};

/* ── Keyboard shortcuts modal ───────────────────────────────────────── */
window.bsShortcuts = function() {
  var existing = document.getElementById('bs-sh-overlay');
  if (existing) { existing.remove(); return; }
  var menu = document.getElementById('bs-acct-menu');
  var btn  = document.getElementById('bs-acct-btn');
  if (menu) menu.classList.remove('open');
  if (btn)  btn.classList.remove('open');
  var overlay = document.createElement('div');
  overlay.id = 'bs-sh-overlay';
  overlay.onclick = function(e) { if (e.target === overlay) overlay.remove(); };
  overlay.innerHTML = [
    '<div id="bs-sh-modal">',
    '  <div class="bs-sh-header">',
    '    <span>Atalhos de Teclado</span>',
    '    <button onclick="document.getElementById(\'bs-sh-overlay\').remove()" style="background:none;border:none;cursor:pointer;color:var(--bs-ink-muted);font-size:18px;line-height:1">&#x2715;</button>',
    '  </div>',
    '  <div class="bs-sh-body">',
    '    <div class="bs-sh-group">',
    '      <div class="bs-sh-group-title">Navegação</div>',
    '      <div class="bs-sh-row"><span>Abrir atalhos</span><kbd>?</kbd></div>',
    '      <div class="bs-sh-row"><span>Fechar modal</span><kbd>Esc</kbd></div>',
    '    </div>',
    '    <div class="bs-sh-group">',
    '      <div class="bs-sh-group-title">Lançamento</div>',
    '      <div class="bs-sh-row"><span>Trocar lançamento</span><kbd>L</kbd></div>',
    '    </div>',
    '  </div>',
    '</div>'
  ].join('');
  document.body.appendChild(overlay);
};
document.addEventListener('keydown', function(e) {
  if (e.key === '?' && !e.target.matches('input,textarea,select')) bsShortcuts();
  if (e.key === 'Escape') {
    var o = document.getElementById('bs-sh-overlay');
    if (o) o.remove();
  }
});
