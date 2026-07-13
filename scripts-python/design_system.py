"""
design_system.py — Basis-inspired Design System CSS for Brabo Analytics.

Exports
-------
DS_FONT   : <link> tag for Inter via Google Fonts CDN (system-font fallback works offline)
DS_CSS    : full CSS string — embed in <style> tag in generated HTML <head>
              Covers: variables, typography, frame layout, sidebar, cards,
                      stat rows, badges, pills, flash messages, tables,
                      + legacy overrides so existing .wrap/.hdr/.section content
                      looks correct inside the new sidebar frame.

Python helpers (for Phase 4 generator updates)
-----------------------------------------------
ds_kpi_row(stats)       : grid of stat cards  → HTML str
ds_stat(label, v, d)    : single stat card     → HTML str
ds_badge(text, variant) : subtle inline badge  → HTML str
ds_pill(text, variant)  : solid colored pill   → HTML str
ds_flash(text, variant) : note / alert block   → HTML str
ds_bar(v, total, color) : progress bar strip   → HTML str
ds_card(title, body)    : white card wrapper   → HTML str (inject accent via --bs-accent)
ds_table_wrap(inner)    : table with DS border → HTML str
"""

# ── Font ──────────────────────────────────────────────────────────────────────

DS_FONT = (
    '<link rel="preconnect" href="https://fonts.googleapis.com">'
    '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
    '<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap"'
    ' rel="stylesheet">'
)

# ── CSS — plain string (no f-string: CSS uses { } everywhere) ─────────────────

DS_CSS = """
/* ── Basis Design System — Brabo Analytics ──────────────────────────── */

@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

:root {
  /* Neutral ink scale */
  --bs-ink:          #1f2330;
  --bs-ink-muted:    #6b7280;
  --bs-ink-subtle:   #9ca3af;

  /* Surfaces */
  --bs-bg:           #eef0f8;
  --bs-surface:      #f6f7fb;
  --bs-card:         #ffffff;
  --bs-border:       #e5e7eb;
  --bs-border-s:     #d1d5db;

  /* Primary */
  --bs-primary:      #2f5ee3;
  --bs-primary-2:    #6aa8ff;
  --bs-primary-bg:   #eef3ff;

  /* Semantic */
  --bs-success:      #31c16c;
  --bs-success-bg:   #f0fdf4;
  --bs-warning:      #f4b740;
  --bs-warning-bg:   #fffbeb;
  --bs-danger:       #f05454;
  --bs-danger-bg:    #fef2f2;
  --bs-info:         #3b82f6;
  --bs-info-bg:      #eff6ff;

  /* Sidebar */
  --bs-sidebar:      #2f5ee3;
  --bs-sidebar-dark: #2347b2;

  /* Campaign accent (overridden inline per campaign) */
  --bs-accent:       #2f5ee3;

  /* Shadows */
  --bs-sh-sm:  0 1px 3px rgba(0,0,0,.08);
  --bs-sh-md:  0 4px 12px rgba(0,0,0,.10);
  --bs-sh-lg:  0 12px 30px rgba(0,0,0,.12);
  --bs-sh-xl:  0 20px 60px rgba(20,26,52,.18);

  /* Radii */
  --bs-r-sm:   6px;
  --bs-r-md:   8px;
  --bs-r-lg:   12px;
  --bs-r-xl:   16px;
  --bs-r-2xl:  20px;

  /* Spacing */
  --s1: 4px;   --s2: 8px;   --s3: 12px;  --s4: 16px;
  --s5: 20px;  --s6: 24px;  --s8: 32px;  --s10: 40px;
}

*, *::before, *::after { box-sizing: border-box; }

html, body {
  margin: 0 !important; padding: 0 !important;
  font-family: 'Inter', 'Segoe UI', system-ui, sans-serif;
  font-size: 14px;
  line-height: 1.5;
  color: var(--bs-ink);
  background: var(--bs-bg);
}

/* ── Frame ───────────────────────────────────────────────────────────── */

#bs-frame {
  display: block;
  min-height: 100vh;
}

/* ── Sidebar / App Drawer ─────────────────────────────────────────────── */

#bs-drawer {
  background: linear-gradient(180deg, var(--bs-sidebar) 0%, var(--bs-sidebar-dark) 100%);
  color: #fff;
  padding: 20px 14px;
  position: fixed;
  top: 0;
  left: 0;
  width: 240px;
  height: 100vh;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 14px;
  scrollbar-width: none;
  z-index: 100;
}
#bs-drawer::-webkit-scrollbar { display: none; }

/* Brand */
.bs-brand {
  display: flex; align-items: center; gap: 10px;
  padding-bottom: 14px;
  border-bottom: 1px solid rgba(255,255,255,.15);
  flex-shrink: 0;
}
.bs-brand a { display: flex; align-items: center; gap: 10px; text-decoration: none; }
.bs-brand img { height: 26px; }
.bs-brand-name { font-size: 12px; font-weight: 700; color: rgba(255,255,255,.9); }

/* Campaign switcher */
.bs-camp-switch {
  display: flex; gap: 5px;
  background: rgba(0,0,0,.2);
  border-radius: var(--bs-r-lg);
  padding: 4px;
  flex-shrink: 0;
}
.bs-camp-btn {
  flex: 1; padding: 6px 6px;
  border: none; border-radius: var(--bs-r-md);
  background: transparent; color: rgba(255,255,255,.6);
  font-size: 11px; font-weight: 700;
  cursor: pointer; text-decoration: none; text-align: center;
  transition: background .15s, color .15s; white-space: nowrap;
  line-height: 1.3;
}
.bs-camp-btn:hover  { background: rgba(255,255,255,.15); color: #fff; }
.bs-camp-btn.active { background: var(--bs-accent); color: #fff; }

/* Nav */
.bs-nav { display: flex; flex-direction: column; gap: 1px; flex: 1; min-height: 0; }

.bs-nav-sep {
  height: 1px; background: rgba(255,255,255,.12);
  margin: 6px 0;
}
.bs-nav-group {
  font-size: 10px; font-weight: 700;
  color: rgba(255,255,255,.4);
  text-transform: uppercase; letter-spacing: .08em;
  padding: 10px 8px 3px;
}
.bs-nav-link {
  display: flex; align-items: center; gap: 8px;
  color: rgba(255,255,255,.75); text-decoration: none;
  padding: 7px 10px; border-radius: var(--bs-r-md);
  font-size: 13px; font-weight: 500;
  transition: background .12s, color .12s;
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
}
.bs-nav-link:hover  { background: rgba(255,255,255,.14); color: #fff; }
.bs-nav-link.active { background: rgba(255,255,255,.22); color: #fff; font-weight: 700; }
.bs-nav-icon { display: flex; align-items: center; flex-shrink: 0; }
.bs-nav-icon i { font-size: 15px; line-height: 1; opacity: .85; }
.bs-comp-link i { font-size: 14px; line-height: 1; vertical-align: middle; }

/* Drawer footer */
.bs-drawer-footer {
  margin-top: auto; padding-top: 10px;
  border-top: 1px solid rgba(255,255,255,.15);
  flex-shrink: 0;
}
.bs-comp-link {
  display: flex; align-items: center; justify-content: center; gap: 6px;
  background: rgba(255,255,255,.14); border: 1px solid rgba(255,255,255,.22);
  color: #fff; text-decoration: none; padding: 9px 12px;
  border-radius: var(--bs-r-lg); font-size: 11px; font-weight: 700;
  transition: background .15s; text-align: center;
}
.bs-comp-link:hover { background: rgba(255,255,255,.24); }

/* ── Main content area ───────────────────────────────────────────────── */

#bs-main {
  background: var(--bs-surface);
  min-width: 0;
  overflow-x: hidden;
  margin-left: 240px;
}

/* ── Legacy override: existing .wrap content inside sidebar layout ────── */

body   { background: var(--bs-bg) !important; padding-top: 0 !important; }

#bs-main .wrap {
  max-width: 100% !important;
  margin: 0 !important;
  border-radius: 0 !important;
  box-shadow: none !important;
  background: transparent !important;
}
#bs-main .hdr {
  border-radius: 0 !important;
  border-bottom: 1px solid var(--bs-border);
  position: sticky; top: 0; z-index: 50;
}
#bs-main .content { padding: 24px 32px; }

/* Accent-aware section titles and table headers */
#bs-main .section-title  { border-bottom-color: var(--bs-accent) !important; }
#bs-main table th        { background: var(--bs-accent) !important; }
#bs-main .kpi-grid,
#bs-main .kpis           { gap: 12px; }
#bs-main .note {
  background: var(--bs-info-bg);
  border-left-color: var(--bs-info);
}

/* ── Design System Components ────────────────────────────────────────── */

/* Stat row */
.bs-stat-row {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(150px, 1fr));
  gap: var(--s3);
  margin-bottom: var(--s4);
}
.bs-stat {
  background: #f7f8fc;
  border-radius: var(--bs-r-lg);
  padding: var(--s4);
  display: flex; flex-direction: column; gap: 4px;
  border-top: 3px solid var(--bs-accent);
}
.bs-stat-label {
  font-size: 11px; color: var(--bs-ink-muted);
  text-transform: uppercase; letter-spacing: .05em; font-weight: 600;
}
.bs-stat-value { font-size: 22px; font-weight: 800; color: var(--bs-ink); line-height: 1.1; }
.bs-stat-delta { font-size: 11px; font-weight: 600; }
.bs-stat-delta.up      { color: var(--bs-success); }
.bs-stat-delta.down    { color: var(--bs-danger); }
.bs-stat-delta.neutral { color: var(--bs-ink-muted); }

/* Card */
.bs-card {
  background: var(--bs-card);
  border-radius: var(--bs-r-xl);
  padding: var(--s5);
  box-shadow: var(--bs-sh-md);
  margin-bottom: var(--s5);
}
.bs-card-title {
  font-size: 14px; font-weight: 700; color: var(--bs-ink);
  border-bottom: 2px solid var(--bs-accent);
  padding-bottom: var(--s2); margin-bottom: var(--s4);
  display: flex; align-items: center; gap: var(--s2);
}

/* Badge */
.bs-badge {
  display: inline-flex; align-items: center; gap: 3px;
  font-size: 11px; padding: 2px 8px; border-radius: 999px;
  background: var(--bs-primary-bg); color: var(--bs-primary);
  font-weight: 600;
}
.bs-badge.success { background: var(--bs-success-bg); color: var(--bs-success); }
.bs-badge.warning { background: var(--bs-warning-bg); color: #92400e; }
.bs-badge.danger  { background: var(--bs-danger-bg);  color: var(--bs-danger); }
.bs-badge.neutral { background: #f3f4f6; color: var(--bs-ink-muted); }

/* Pill */
.bs-pill {
  display: inline-block; padding: 3px 10px; border-radius: 999px;
  font-size: 11px; font-weight: 700; color: #fff; white-space: nowrap;
}
.bs-pill.success { background: var(--bs-success); }
.bs-pill.warning { background: var(--bs-warning); color: #1a1a2e; }
.bs-pill.danger  { background: var(--bs-danger); }
.bs-pill.info    { background: var(--bs-info); }
.bs-pill.neutral { background: var(--bs-border-s); color: var(--bs-ink); }
.bs-pill.accent  { background: var(--bs-accent); }

/* Flash / Alert */
.bs-flash {
  padding: var(--s3) var(--s4);
  border-radius: var(--bs-r-md);
  border-left: 4px solid var(--bs-info);
  background: var(--bs-info-bg);
  font-size: 13px; color: var(--bs-ink); line-height: 1.6;
  margin-bottom: var(--s4);
}
.bs-flash.success { border-color: var(--bs-success); background: var(--bs-success-bg); }
.bs-flash.warning { border-color: var(--bs-warning); background: var(--bs-warning-bg); }
.bs-flash.danger  { border-color: var(--bs-danger);  background: var(--bs-danger-bg); }

/* Progress bar */
.bs-bar-track {
  background: #e5e7eb; border-radius: 4px; height: 8px; overflow: hidden;
}
.bs-bar-fill {
  height: 100%; border-radius: 4px;
  background: var(--bs-accent);
  transition: width .3s ease;
}

/* Table */
.bs-table-wrap {
  border: 1px solid var(--bs-border);
  border-radius: var(--bs-r-lg);
  overflow: hidden;
  margin-top: var(--s3);
}
.bs-table { width: 100%; border-collapse: collapse; font-size: 13px; }
.bs-table th {
  background: var(--bs-accent); color: #fff;
  padding: 10px 12px; text-align: left;
  font-size: 11px; font-weight: 700;
  text-transform: uppercase; letter-spacing: .04em;
}
.bs-table td {
  padding: 10px 12px;
  border-bottom: 1px solid var(--bs-border);
  vertical-align: middle;
}
.bs-table tr:last-child td { border-bottom: none; }
.bs-table tr:hover td { background: var(--bs-primary-bg); }

/* ── Responsive ──────────────────────────────────────────────────────── */

@media (max-width: 1024px) {
  #bs-frame { grid-template-columns: 1fr; }
  #bs-drawer { height: auto; position: relative; flex-direction: row; flex-wrap: wrap; }
  #bs-main { margin-left: 0; }
  .bs-nav { flex-direction: row; flex-wrap: wrap; }
  .bs-drawer-footer { margin-top: 0; }
}

/* ── Animations & Enhancements ────────────────────────────────────────── */
@keyframes fadeInUp {
  from {
    opacity: 0;
    transform: translateY(10px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.wrap, .container {
  animation: fadeInUp 0.45s ease-out forwards;
}

.bs-stat, .bs-card, .section {
  animation: fadeInUp 0.45s ease-out forwards;
}

/* Total row highlights */
.bs-table tr.total-row td,
table tr.total-row td {
  background: var(--bs-primary-bg) !important;
  font-weight: 700 !important;
  border-top: 2px double var(--bs-accent) !important;
  border-bottom: 2px solid var(--bs-accent) !important;
}

/* Sortable Table Styles */
.bs-table th.sortable-header,
table th.sortable-header {
  position: relative;
  cursor: pointer;
  user-select: none;
  transition: background-color 0.2s;
}
.bs-table th.sortable-header:hover,
table th.sortable-header:hover {
  background-color: rgba(0, 0, 0, 0.15) !important;
}
.sort-indicator {
  margin-left: 6px;
  display: inline-block;
  vertical-align: middle;
}
"""

# ── Python helper functions ───────────────────────────────────────────────────

def ds_stat(label, value, delta=None, delta_type="neutral"):
    """Single stat card. delta_type: 'up' | 'down' | 'neutral'"""
    delta_html = ""
    if delta is not None:
        delta_html = f'<div class="bs-stat-delta {delta_type}">{delta}</div>'
    return (
        f'<div class="bs-stat">'
        f'<div class="bs-stat-label">{label}</div>'
        f'<div class="bs-stat-value">{value}</div>'
        f'{delta_html}'
        f'</div>'
    )


def ds_kpi_row(stats):
    """Grid of stat cards. stats: list of (label, value) or (label, value, delta, delta_type)"""
    cells = ""
    for s in stats:
        label, value = s[0], s[1]
        delta = s[2] if len(s) > 2 else None
        dtype = s[3] if len(s) > 3 else "neutral"
        cells += ds_stat(label, value, delta, dtype)
    return f'<div class="bs-stat-row">{cells}</div>'


def ds_badge(text, variant=""):
    cls = f"bs-badge {variant}".strip()
    return f'<span class="{cls}">{text}</span>'


def ds_pill(text, variant="info"):
    return f'<span class="bs-pill {variant}">{text}</span>'


def ds_flash(text, variant="info"):
    return f'<div class="bs-flash {variant}">{text}</div>'


def ds_bar(val, total, color=None):
    pct = min(val / total * 100, 100) if total else 0
    style = f'style="width:{pct:.1f}%;background:{color}"' if color else f'style="width:{pct:.1f}%"'
    return (
        f'<div class="bs-bar-track">'
        f'<div class="bs-bar-fill" {style}></div>'
        f'</div>'
    )


def ds_card(title, body):
    return (
        f'<div class="bs-card">'
        f'<div class="bs-card-title">{title}</div>'
        f'{body}'
        f'</div>'
    )


def ds_table_wrap(thead, tbody):
    return (
        f'<div class="bs-table-wrap">'
        f'<table class="bs-table">{thead}<tbody>{tbody}</tbody></table>'
        f'</div>'
    )
