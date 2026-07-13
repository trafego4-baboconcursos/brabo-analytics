# -*- coding: utf-8 -*-
"""Helper: rewrites nav_component.py with correct UTF-8 encoding + Tabler Icons."""
from pathlib import Path

CONTENT = """\
# -*- coding: utf-8 -*-
\"\"\"
nav_component.py — Sidebar App Drawer para Brabo Analytics HTML reports.

    from nav_component import nav_html, FRAME_CLOSE, CAMPAIGNS
\"\"\"

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from design_system import DS_CSS  # noqa: E402

# ── Tabler Icons CDN (webfont, pure CSS, no JS) ───────────────────────────────

_ICONS_CDN = (
    '<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/'
    '@tabler/icons-webfont@3.31.0/dist/tabler-icons.min.css">'
)


# ── Page icon lookup — returns full Tabler class string ───────────────────────

def _page_icon(filename):
    f = filename.upper()
    if "INDEX" in f:            return "ti ti-home"
    if "FUNIL" in f:            return "ti ti-git-merge"
    if "META_ADS" in f:         return "ti ti-brand-meta"
    if "GOOGLE_ADS" in f:       return "ti ti-brand-google"
    if "CRIATIVOS" in f:        return "ti ti-palette"
    if "FACEBOOK" in f:         return "ti ti-brand-facebook"
    if "YOUTUBE" in f:          return "ti ti-brand-youtube"
    if "CONSOLIDADA" in f:      return "ti ti-chart-bar"
    if "ANUNCIOS" in f:         return "ti ti-speakerphone"
    if "LEADS_CONFRONTO" in f:  return "ti ti-users"
    if "META_AUDIENCES" in f:   return "ti ti-user-check"
    if "GOOGLE_AUDIENCES" in f: return "ti ti-trending-up"
    if "GOOGLE_ANUNCIOS" in f:  return "ti ti-ad-2"
    if "TYPEFORM" in f:         return "ti ti-clipboard-list"
    if "VENDAS" in f:           return "ti ti-coin"
    if "INSIGHTS" in f:         return "ti ti-bulb"
    return "ti ti-file"


# ── Frame-close fragment ──────────────────────────────────────────────────────

FRAME_CLOSE = "<!-- BRABO-FRAME-END -->\\n  </main></div>\\n<!-- /BRABO-FRAME-END -->"


# ── Campaign definitions ──────────────────────────────────────────────────────

CAMPAIGNS = {
    "PBB-FEV-26": {
        "label": "PBB-FEV-26",
        "folder": "[PBB-FEV-26]",
        "color": "#667eea",
        "groups": [
            ("Vis\\u00e3o Geral", [
                ("Dashboard", "INDEX_[PBB-FEV-26].html"),
            ]),
            ("M\\u00eddia Paga", [
                ("Meta Ads",          "ANALISE_META_ADS_[PBB-FEV-26].html"),
                ("Google Ads",        "ANALISE_GOOGLE_ADS_[PBB-FEV-26].html"),
                ("Google An\\u00fancios",  "ANALISE_GOOGLE_ANUNCIOS_[PBB-FEV-26].html"),
                ("Criativos",         "ANALISE_CRIATIVOS_[PBB-FEV-26].html"),
                ("Facebook",          "ANALISE_FACEBOOK_[PBB-FEV-26].html"),
                ("YouTube",           "ANALISE_YOUTUBE_[PBB-FEV-26].html"),
                ("Consolidada",       "ANALISE_CONSOLIDADA_[PBB-FEV-26].html"),
                ("An\\u00fancios",     "ANALISE_ANUNCIOS_[PBB-FEV-26].html"),
            ]),
            ("Leads & Audi\\u00eancias", [
                ("Leads Confronto",   "ANALISE_LEADS_CONFRONTO_[PBB-FEV-26].html"),
                ("Meta Audiences",    "ANALISE_META_AUDIENCES_[PBB-FEV-26].html"),
                ("Google Audiences",  "ANALISE_GOOGLE_AUDIENCES_[PBB-FEV-26].html"),
            ]),
            ("Vendas", [
                ("Vendas", "ANALISE_VENDAS_[PBB-FEV-26].html"),
            ]),
            ("Pesquisa", [
                ("Typeform", "ANALISE_TYPEFORM_[PBB-FEV-26].html"),
            ]),
            ("Insights", [
                ("Insights & Recomenda\\u00e7\\u00f5es", "INSIGHTS_RECOMENDACOES_[PBB-FEV-26].html"),
            ]),
        ],
    },
    "PBB-ABR-26": {
        "label": "PBB-ABR-26",
        "folder": "[PBB-ABR-26]",
        "color": "#f5576c",
        "groups": [
            ("Vis\\u00e3o Geral", [
                ("Dashboard",      "INDEX_[PBB-ABR-26].html"),
                ("Funil Completo", "ANALISE_FUNIL_[PBB-ABR-26].html"),
            ]),
            ("M\\u00eddia Paga", [
                ("Meta Ads",       "ANALISE_META_ADS_[PBB-ABR-26].html"),
                ("Google Ads",     "ANALISE_GOOGLE_ADS_[PBB-ABR-26].html"),
                ("Criativos",      "ANALISE_CRIATIVOS_[PBB-ABR-26].html"),
                ("Facebook",       "ANALISE_FACEBOOK_[PBB-ABR-26].html"),
                ("YouTube",        "ANALISE_YOUTUBE_[PBB-ABR-26].html"),
                ("Consolidada",    "ANALISE_CONSOLIDADA_[PBB-ABR-26].html"),
                ("An\\u00fancios", "ANALISE_ANUNCIOS_[PBB-ABR-26].html"),
            ]),
            ("Leads & Audi\\u00eancias", [
                ("Leads Confronto",   "ANALISE_LEADS_CONFRONTO_[PBB-ABR-26].html"),
                ("Meta Audiences",    "ANALISE_META_AUDIENCES_[PBB-ABR-26].html"),
                ("Google Audiences",  "ANALISE_GOOGLE_AUDIENCES_[PBB-ABR-26].html"),
            ]),
            ("Pesquisa", [
                ("Typeform", "ANALISE_TYPEFORM_[PBB-ABR-26].html"),
            ]),
            ("Insights", [
                ("Insights & Recomenda\\u00e7\\u00f5es", "INSIGHTS_RECOMENDACOES_[PBB-ABR-26].html"),
            ]),
        ],
    },
}


# ── Main nav_html function ────────────────────────────────────────────────────

def nav_html(active_campaign=None, active_page_file=None, depth=1):
    \"\"\"Returns sidebar opening fragment wrapped in <!-- BRABO-NAV --> markers.\"\"\"
    if depth == 1:
        logo_src  = "../../img/logo-brabo-concursos.png"
        home_href = "../index.html"
        comp_href = "../COMPARATIVO_ABR_FEV_2026.html"
    else:
        logo_src  = "../img/logo-brabo-concursos.png"
        home_href = "index.html"
        comp_href = "COMPARATIVO_ABR_FEV_2026.html"

    accent = "#2f5ee3"
    if active_campaign and active_campaign in CAMPAIGNS:
        accent = CAMPAIGNS[active_campaign]["color"]

    # ── Campaign switcher ─────────────────────────────────────────────────────
    switch_html = ""
    for camp_key, camp in CAMPAIGNS.items():
        is_active = (camp_key == active_campaign)
        if depth == 0:
            index_href = f"{camp['folder']}/INDEX_[{camp_key}].html"
        elif camp_key == active_campaign:
            index_href = f"INDEX_[{camp_key}].html"
        else:
            index_href = f"../[{camp_key}]/INDEX_[{camp_key}].html"
        cls   = "bs-camp-btn active" if is_active else "bs-camp-btn"
        short = camp_key.replace("PBB-", "").replace("-26", "")
        switch_html += (
            f'<a class="{cls}" href="{index_href}"'
            f' style="--bs-accent:{camp[\'color\']}">{short}</a>'
        )

    # ── Nav links ─────────────────────────────────────────────────────────────
    nav_items_html = ""
    if active_campaign and active_campaign in CAMPAIGNS:
        camp = CAMPAIGNS[active_campaign]
        for i, (group_name, pages) in enumerate(camp["groups"]):
            if i > 0:
                nav_items_html += '<div class="bs-nav-sep"></div>\\n'
            nav_items_html += f'<div class="bs-nav-group">{group_name}</div>\\n'
            for page_label, filename in pages:
                href = filename if depth > 0 else f"{camp['folder']}/{filename}"
                cls  = "bs-nav-link active" if filename == active_page_file else "bs-nav-link"
                icon = _page_icon(filename)
                nav_items_html += (
                    f'<a class="{cls}" href="{href}">'
                    f'<span class="bs-nav-icon"><i class="{icon}"></i></span>'
                    f'{page_label}</a>\\n'
                )
    else:
        nav_items_html += '<div class="bs-nav-group">Campanhas</div>\\n'
        for camp_key, camp in CAMPAIGNS.items():
            href = (f"{camp['folder']}/INDEX_[{camp_key}].html" if depth == 0
                    else f"../{camp['folder']}/INDEX_[{camp_key}].html")
            nav_items_html += (
                f'<a class="bs-nav-link" href="{href}">'
                f'<span class="bs-nav-icon"><i class="ti ti-calendar-event"></i></span>'
                f'{camp[\'label\']}</a>\\n'
            )

    comp_cls = " active" if (active_page_file and "COMPARATIVO" in active_page_file) else ""
    accent_css = f"<style id='brabo-accent'>:root{{--bs-accent:{accent}}}</style>"

    fragment = (
        "<!-- BRABO-NAV -->\\n"
        f"{_ICONS_CDN}\\n"
        f"<style id='brabo-ds-style'>{DS_CSS}</style>\\n"
        f"{accent_css}\\n"
        '<div id="bs-frame">\\n'
        '  <aside id="bs-drawer">\\n'
        '    <div class="bs-brand">\\n'
        f'      <a href="{home_href}">'
        f'<img src="{logo_src}" alt="Brabo Analytics">'
        f'<span class="bs-brand-name">Brabo Analytics</span></a>\\n'
        '    </div>\\n'
        f'    <div class="bs-camp-switch">{switch_html}</div>\\n'
        '    <nav class="bs-nav">\\n'
        f'{nav_items_html}'
        '    </nav>\\n'
        '    <div class="bs-drawer-footer">\\n'
        f'      <a class="bs-comp-link{comp_cls}" href="{comp_href}">'
        '<i class="ti ti-chart-bar"></i>&nbsp;ABR&nbsp;&times;&nbsp;FEV</a>\\n'
        '    </div>\\n'
        '  </aside>\\n'
        '  <main id="bs-main">\\n'
        "<!-- /BRABO-NAV -->"
    )
    return fragment
"""

out = Path(__file__).parent / "nav_component.py"
out.write_text(CONTENT, encoding="utf-8")
print(f"Wrote {len(CONTENT)} chars to {out}")
