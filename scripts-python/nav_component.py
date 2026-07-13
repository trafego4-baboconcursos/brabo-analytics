# -*- coding: utf-8 -*-
"""
nav_component.py — Sidebar App Drawer para Brabo Analytics HTML reports.

    from nav_component import nav_html, FRAME_CLOSE, CAMPAIGNS
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from design_system import DS_CSS  # noqa: E402

# ── Tabler Icons CDN (webfont, pure CSS, no JS) ───────────────────────────────

_ICONS_CDN = (
    '<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/'
    '@tabler/icons-webfont@3.31.0/dist/tabler-icons.min.css">'
)

# ── Global JS for interactive components (sorting, filtering, totals) ──────────

GLOBAL_JS = """<script id="brabo-global-js">
document.addEventListener("DOMContentLoaded", function() {
  // 1. Identificar linhas de totalização
  document.querySelectorAll("table, .bs-table").forEach(function(table) {
    table.querySelectorAll("tbody tr").forEach(function(row) {
      if (row.cells.length > 0) {
        var firstCellText = row.cells[0].innerText.toLowerCase();
        if (firstCellText.includes("total") || firstCellText.includes("media") || firstCellText.includes("consolidado")) {
          row.classList.add("total-row");
        }
      }
    });
  });

  // 2. Ordenação automática de tabelas
  document.querySelectorAll(".bs-table, table").forEach(function(table) {
    var headers = table.querySelectorAll("thead th");
    if (!headers.length) return;
    
    var sortIndex = -1;
    var sortDirection = 1;
    
    headers.forEach(function(header, index) {
      if (header.closest("#bs-drawer")) return;
      
      header.classList.add("sortable-header");
      header.setAttribute("title", "Clique para ordenar esta coluna");
      
      header.addEventListener("click", function() {
        var tbody = table.querySelector("tbody");
        if (!tbody) return;
        var rows = Array.from(tbody.querySelectorAll("tr"));
        
        var totalRows = [];
        var dataRows = rows.filter(function(row) {
          if (row.classList.contains("total-row")) {
            totalRows.push(row);
            return false;
          }
          return true;
        });
        
        if (sortIndex === index) {
          sortDirection = -sortDirection;
        } else {
          sortDirection = -1;
          sortIndex = index;
        }
        
        headers.forEach(function(h) {
          var ind = h.querySelector(".sort-indicator");
          if (ind) ind.remove();
        });
        
        var indSpan = document.createElement("span");
        indSpan.className = "sort-indicator";
        indSpan.style.opacity = "0.8";
        indSpan.style.fontSize = "9px";
        indSpan.innerHTML = sortDirection === 1 ? '<i class="ti ti-chevron-up"></i>' : '<i class="ti ti-chevron-down"></i>';
        header.appendChild(indSpan);
        
        dataRows.sort(function(a, b) {
          var cellA = a.cells[index];
          var cellB = b.cells[index];
          if (!cellA || !cellB) return 0;
          
          var valA = cellA.getAttribute("data-val") !== null ? cellA.getAttribute("data-val") : cellA.innerText;
          var valB = cellB.getAttribute("data-val") !== null ? cellB.getAttribute("data-val") : cellB.innerText;
          
          var cleanA = parseFloat(valA.toString().replace(/[R$\\s%]/g, "").replace(/\\./g, "").replace(",", "."));
          var cleanB = parseFloat(valB.toString().replace(/[R$\\s%]/g, "").replace(/\\./g, "").replace(",", "."));
          
          if (!isNaN(cleanA) && !isNaN(cleanB)) {
            return (cleanA - cleanB) * sortDirection;
          }
          return valA.toString().localeCompare(valB.toString()) * sortDirection;
        });
        
        tbody.innerHTML = "";
        dataRows.forEach(function(r) { tbody.appendChild(r); });
        totalRows.forEach(function(r) { tbody.appendChild(r); });
      });
    });
  });

  // 3. Filtro de busca rápida dinâmico
  document.querySelectorAll(".bs-table, table").forEach(function(table) {
    if (table.closest("#bs-drawer")) return;
    
    var tbody = table.querySelector("tbody");
    if (!tbody) return;
    var rows = tbody.querySelectorAll("tr");
    
    var dataRowsCount = Array.from(rows).filter(function(r) { return !r.classList.contains("total-row"); }).length;
    if (dataRowsCount <= 5) return;
    
    var filterContainer = document.createElement("div");
    filterContainer.className = "table-filter-wrap";
    filterContainer.style.display = "flex";
    filterContainer.style.alignItems = "center";
    filterContainer.style.gap = "8px";
    filterContainer.style.margin = "12px 0 8px";
    
    var searchIcon = document.createElement("i");
    searchIcon.className = "ti ti-search";
    searchIcon.style.color = "var(--bs-ink-subtle)";
    searchIcon.style.fontSize = "16px";
    
    var filterInput = document.createElement("input");
    filterInput.type = "text";
    filterInput.placeholder = "Filtrar tabela...";
    filterInput.style.padding = "6px 12px 6px 30px";
    filterInput.style.fontSize = "13px";
    filterInput.style.border = "1px solid var(--bs-border)";
    filterInput.style.borderRadius = "var(--bs-r-md)";
    filterInput.style.outline = "none";
    filterInput.style.width = "220px";
    filterInput.style.fontFamily = "inherit";
    filterInput.style.color = "var(--bs-ink)";
    filterInput.style.background = "var(--bs-card)";
    
    var wrapper = document.createElement("div");
    wrapper.style.position = "relative";
    wrapper.style.display = "inline-flex";
    wrapper.style.alignItems = "center";
    
    searchIcon.style.position = "absolute";
    searchIcon.style.left = "10px";
    searchIcon.style.pointerEvents = "none";
    
    wrapper.appendChild(searchIcon);
    wrapper.appendChild(filterInput);
    filterContainer.appendChild(wrapper);
    
    filterInput.addEventListener("input", function() {
      var query = filterInput.value.toLowerCase().normalize("NFKD").replace(/[\\u0300-\\u036f]/g, "");
      rows.forEach(function(row) {
        if (row.classList.contains("total-row")) return;
        var text = row.innerText.toLowerCase().normalize("NFKD").replace(/[\\u0300-\\u036f]/g, "");
        if (text.indexOf(query) > -1) {
          row.style.display = "";
        } else {
          row.style.display = "none";
        }
      });
    });
    
    var parent = table.parentElement;
    if (parent && parent.classList.contains("bs-table-wrap")) {
      parent.parentElement.insertBefore(filterContainer, parent);
    } else {
      table.parentElement.insertBefore(filterContainer, table);
    }
  });
});
</script>"""


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

FRAME_CLOSE = "<!-- BRABO-FRAME-END -->\n  </main></div>\n<!-- /BRABO-FRAME-END -->"


# ── Campaign definitions ──────────────────────────────────────────────────────

CAMPAIGNS = {
    "PES-JAN-26": {
        "label": "PES-JAN-26",
        "folder": "[PES-JAN-26]",
        "color": "#764ba2",
        "groups": [
            ("Vis\u00e3o Geral", [
                ("Dashboard", "INDEX_[PES-JAN-26].html"),
            ]),
            ("M\u00eddia Paga", [
                ("Meta Ads",          "ANALISE_META_ADS_[PES-JAN-26].html"),
                ("Google Ads",        "ANALISE_GOOGLE_ADS_[PES-JAN-26].html"),
                ("YouTube",           "ANALISE_YOUTUBE_[PES-JAN-26].html"),
                ("Meta Posts",        "ANALISE_META_POSTS_[PES-JAN-26].html"),
                ("Atribui\u00e7\u00e3o UTM", "ANALISE_ATRIBUICAO_UTM_[PES-JAN-26].html"),
            ]),
            ("Leads & Audi\u00eancias", [
                ("Leads Confronto",   "ANALISE_LEADS_CONFRONTO_[PES-JAN-26].html"),
                ("Meta Audiences",    "ANALISE_META_AUDIENCES_[PES-JAN-26].html"),
            ]),
            ("Insights", [
                ("Insights & Recomenda\u00e7\u00f5es", "INSIGHTS_RECOMENDACOES_[PES-JAN-26].html"),
            ]),
        ],
    },
    "PBB-FEV-26": {
        "label": "PBB-FEV-26",
        "folder": "[PBB-FEV-26]",
        "color": "#667eea",
        "groups": [
            ("Vis\u00e3o Geral", [
                ("Dashboard", "INDEX_[PBB-FEV-26].html"),
            ]),
            ("M\u00eddia Paga", [
                ("Meta Ads",          "ANALISE_META_ADS_[PBB-FEV-26].html"),
                ("Google Ads",        "ANALISE_GOOGLE_ADS_[PBB-FEV-26].html"),
                ("Google An\u00fancios",  "ANALISE_GOOGLE_ANUNCIOS_[PBB-FEV-26].html"),
                ("Criativos",         "ANALISE_CRIATIVOS_[PBB-FEV-26].html"),
                ("Facebook",          "ANALISE_FACEBOOK_[PBB-FEV-26].html"),
                ("YouTube",           "ANALISE_YOUTUBE_[PBB-FEV-26].html"),
                ("Consolidada",       "ANALISE_CONSOLIDADA_[PBB-FEV-26].html"),
                ("An\u00fancios",     "ANALISE_ANUNCIOS_[PBB-FEV-26].html"),
            ]),
            ("Leads & Audi\u00eancias", [
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
                ("Insights & Recomenda\u00e7\u00f5es", "INSIGHTS_RECOMENDACOES_[PBB-FEV-26].html"),
            ]),
        ],
    },
    "PBB-ABR-26": {
        "label": "PBB-ABR-26",
        "folder": "[PBB-ABR-26]",
        "color": "#f5576c",
        "groups": [
            ("Visao Geral", [
                ("Dashboard",      "INDEX_[PBB-ABR-26].html"),
                ("Sistema Calendario", "SISTEMA_CALENDARIO_2026.html"),
                ("Funil Completo", "ANALISE_FUNIL_[PBB-ABR-26].html"),
            ]),
            ("Midia Paga", [
                ("Meta", "ANALISE_META_ADS_[PBB-ABR-26].html"),
                ("Google", "ANALISE_GOOGLE_ADS_[PBB-ABR-26].html"),
                ("Criativos",      "ANALISE_CRIATIVOS_[PBB-ABR-26].html"),
            ]),
            ("Leads & Audiencias", [
                ("Leads Confronto",   "ANALISE_LEADS_CONFRONTO_[PBB-ABR-26].html"),
                ("Meta Audiences",    "ANALISE_META_AUDIENCES_[PBB-ABR-26].html"),
                ("Google Audiences",  "ANALISE_GOOGLE_AUDIENCES_[PBB-ABR-26].html"),
            ]),
            ("Pesquisa", [
                ("Typeform", "ANALISE_TYPEFORM_[PBB-ABR-26].html"),
                ("Vendas", "ANALISE_VENDAS_[PBB-ABR-26].html"),
                ("Hotmart", "ANALISE_HOTMART_[PBB-ABR-26].html"),
                ("TMB", "ANALISE_TMB_[PBB-ABR-26].html"),
            ]),
            ("Insights", [
                ("Insights & Recomendacoes", "INSIGHTS_RECOMENDACOES_[PBB-ABR-26].html"),
            ]),
        ],
    },
    "PES-MAI-26": {
        "label": "PES-MAI-26",
        "folder": "[PES-MAI-26]",
        "color": "#0f766e",
        "groups": [
            ("Visão Geral", [
                ("Dashboard", "INDEX_[PES-MAI-26].html"),
                ("Sistema Calendario", "../calendario/SISTEMA_CALENDARIO_2026.html"),
                ("Funil Completo", "ANALISE_FUNIL_[PES-MAI-26].html"),
            ]),
            ("Mídia Paga", [
                ("Meta", "ANALISE_META_ADS_[PES-MAI-26].html"),
                ("Google", "ANALISE_GOOGLE_ADS_[PES-MAI-26].html"),
                ("Criativos", "ANALISE_CRIATIVOS_[PES-MAI-26].html"),
            ]),
            ("Leads & Audiências", [
                ("Leads Confronto", "ANALISE_LEADS_CONFRONTO_[PES-MAI-26].html"),
                ("Meta Audiences", "ANALISE_META_AUDIENCES_[PES-MAI-26].html"),
                ("Google Audiences", "ANALISE_GOOGLE_AUDIENCES_[PES-MAI-26].html"),
            ]),
            ("Pesquisa", [
                ("Typeform", "ANALISE_TYPEFORM_[PES-MAI-26].html"),
                ("Vendas", "ANALISE_VENDAS_[PES-MAI-26].html"),
                ("Hotmart", "ANALISE_HOTMART_[PES-MAI-26].html"),
                ("TMB", "ANALISE_TMB_[PES-MAI-26].html"),
            ]),
            ("Insights", [
                ("Insights & Recomendações", "INSIGHTS_RECOMENDACOES_[PES-MAI-26].html"),
            ]),
        ],
    },
}


# ── Main nav_html function ────────────────────────────────────────────────────

def nav_html(active_campaign=None, active_page_file=None, depth=1):
    """Returns sidebar opening fragment wrapped in <!-- BRABO-NAV --> markers."""
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
        short = camp_key.replace("PBB-", "").replace("PES-", "").replace("-26", "")
        switch_html += (
            f'<a class="{cls}" href="{index_href}"'
            f' style="--bs-accent:{camp["color"]}">{short}</a>'
        )

    # ── Nav links ─────────────────────────────────────────────────────────────
    nav_items_html = ""
    if active_campaign and active_campaign in CAMPAIGNS:
        camp = CAMPAIGNS[active_campaign]
        for i, (group_name, pages) in enumerate(camp["groups"]):
            if i > 0:
                nav_items_html += '<div class="bs-nav-sep"></div>\n'
            nav_items_html += f'<div class="bs-nav-group">{group_name}</div>\n'
            for page_label, filename in pages:
                href = filename if depth > 0 else f"{camp['folder']}/{filename}"
                cls  = "bs-nav-link active" if filename == active_page_file else "bs-nav-link"
                icon = _page_icon(filename)
                nav_items_html += (
                    f'<a class="{cls}" href="{href}">'
                    f'<span class="bs-nav-icon"><i class="{icon}"></i></span>'
                    f'{page_label}</a>\n'
                )
    else:
        nav_items_html += '<div class="bs-nav-group">Campanhas</div>\n'
        for camp_key, camp in CAMPAIGNS.items():
            href = (f"{camp['folder']}/INDEX_[{camp_key}].html" if depth == 0
                    else f"../{camp['folder']}/INDEX_[{camp_key}].html")
            nav_items_html += (
                f'<a class="bs-nav-link" href="{href}">'
                f'<span class="bs-nav-icon"><i class="ti ti-calendar-event"></i></span>'
                f'{camp["label"]}</a>\n'
            )

    comp_cls = " active" if (active_page_file and "COMPARATIVO" in active_page_file) else ""
    accent_css = f"<style id='brabo-accent'>:root{{--bs-accent:{accent}}}</style>"

    fragment = (
        "<!-- BRABO-NAV -->\n"
        f"{_ICONS_CDN}\n"
        f"<style id='brabo-ds-style'>{DS_CSS}</style>\n"
        f"{accent_css}\n"
        f"{GLOBAL_JS}\n"
        '<div id="bs-frame">\n'
        '  <aside id="bs-drawer">\n'
        '    <div class="bs-brand">\n'
        f'      <a href="{home_href}">'
        f'<img src="{logo_src}" alt="Brabo Analytics">'
        f'<span class="bs-brand-name">Brabo Analytics</span></a>\n'
        '    </div>\n'
        f'    <div class="bs-camp-switch">{switch_html}</div>\n'
        '    <nav class="bs-nav">\n'
        f'{nav_items_html}'
        '    </nav>\n'
        '    <div class="bs-drawer-footer">\n'
        f'      <a class="bs-comp-link{comp_cls}" href="{comp_href}">'
        '<i class="ti ti-chart-bar"></i>&nbsp;ABR&nbsp;&times;&nbsp;FEV</a>\n'
        '    </div>\n'
        '  </aside>\n'
        '  <main id="bs-main">\n'
        "<!-- /BRABO-NAV -->"
    )
    return fragment
