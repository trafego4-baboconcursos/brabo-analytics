import re
from pathlib import Path

file_path = Path(r"C:\Users\trafe\OneDrive\Desktop\workspace-mmm\analises\[PBB-ABR-26]\ANALISE_CRIATIVOS_[PBB-ABR-26].html")
html = file_path.read_text(encoding='utf-8')

# 1. CSS
css_to_add = """
.filter-bar { display: flex; flex-wrap: wrap; align-items: center; gap: 8px; margin-bottom: 16px; margin-top: 10px; }
.filter-label { font-size: 11px; color: #6b7280; font-weight: 700; text-transform: uppercase; letter-spacing: .05em; white-space: nowrap; }
.filter-btn { padding: 6px 14px; border-radius: 999px; border: 1.5px solid #2f5ee3; background: #fff; color: #2f5ee3; font-size: 13px; font-weight: 600; cursor: pointer; transition: all .15s; font-family: inherit; }
.filter-btn:hover { background: #eef3ff; }
.filter-btn.active { background: #2f5ee3; color: #fff; border-color: #2f5ee3; }
"""
if ".filter-bar {" not in html:
    html = html.replace('</style>\n</head>', css_to_add + '</style>\n</head>')

# 2. Add id="section-criativos" to the info-box containing "1.2 Top 29 Criativos de Captação por Vendas"
if 'id="section-criativos"' not in html:
    html = html.replace('<div class="info-box">\n      <h2>1.2 Top 29 Criativos de Captação por Vendas</h2>', '<div class="info-box" id="section-criativos">\n      <h2>1.2 Top 29 Criativos de Captação por Vendas</h2>')

# 3. Add filter bar HTML
filter_bar_html = """
      <div class="filter-bar">
        <span class="filter-label">Ordenar por:</span>
        <button class="filter-btn active" onclick="sortCreativos(2)">Leads</button>
        <button class="filter-btn" onclick="sortCreativos(3)">Vendas</button>
        <button class="filter-btn" onclick="sortCreativos(4)">Taxa Conv.</button>
        <button class="filter-btn" onclick="sortCreativos(5)">Valor Total</button>
        <button class="filter-btn" onclick="sortCreativos(6)">Valor/Lead</button>
      </div>
"""
if "filter-bar" not in html[html.find("1.2 Top 29 Criativos de Captação"):html.find("1.2 Top 29 Criativos de Captação") + 500]:
    html = re.sub(
        r'(<p>Recorte dos criativos ligados a campanhas de captação via UTM_source.*?</p>)',
        r'\1' + '\n' + filter_bar_html,
        html
    )

# 4. Add id to the table
table_pattern = r'(?s)(<div class="info-box" id="section-criativos">.*?)(<table>)'
html = re.sub(table_pattern, r'\1<table id="criativos-table">', html, count=1)

# 5. Inject data-val into table rows. We'll find the tbody inside the section.
start_tbody = html.find('<tbody>', html.find('id="section-criativos"'))
end_tbody = html.find('</tbody>', start_tbody)
tbody = html[start_tbody:end_tbody]

def inject_data_val(match):
    tds = match.group(0)
    # Parse each td
    td_list = re.findall(r'<td[^>]*>.*?</td>', tds, re.DOTALL)
    if len(td_list) == 7:
        # Col 0: Posição (ignore)
        # Col 1: Criativo (ignore)
        # Col 2: Leads
        # Col 3: Vendas
        # Col 4: Taxa Conv.
        # Col 5: Valor Total
        # Col 6: Valor/Lead
        
        def extract_num(td):
            # Extract text
            text = re.sub(r'<[^>]+>', '', td).strip()
            # Clean text: remove R$, %, spaces
            text = text.replace('R$', '').replace('%', '').strip()
            # Handle dots and commas for standard float conversion
            text = text.replace('.', '').replace(',', '.')
            try:
                return float(text)
            except ValueError:
                return 0.0
                
        for i in range(2, 7):
            val = extract_num(td_list[i])
            td_list[i] = re.sub(r'(<td[^>]*)>', rf'\1 data-val="{val}">', td_list[i])
            
        return "".join(td_list)
    return tds

new_tbody = re.sub(r'(?s)<tr>.*?</tr>', inject_data_val, tbody)
html = html[:start_tbody] + new_tbody + html[end_tbody:]

# 6. Append JS script
js_script = """
<script>
(function() {
  var _sortIdx = 2, _sortDir = -1;
  window.sortCreativos = function(colIdx) {
    var btns = document.querySelectorAll('#section-criativos .filter-btn');
    var targetBtn = Array.from(btns).find(b => b.getAttribute('onclick') === 'sortCreativos(' + colIdx + ')');
    btns.forEach(function(b) { b.classList.remove('active'); });
    if (targetBtn) targetBtn.classList.add('active');
    
    if (_sortIdx === colIdx) { _sortDir = -_sortDir; } else { _sortDir = -1; _sortIdx = colIdx; }
    var tbody = document.querySelector('#criativos-table tbody');
    var rows = Array.from(tbody.querySelectorAll('tr'));
    
    rows.sort(function(a, b) {
      var av = parseFloat((a.cells[colIdx] && a.cells[colIdx].dataset.val) || 0);
      var bv = parseFloat((b.cells[colIdx] && b.cells[colIdx].dataset.val) || 0);
      return (bv - av) * (_sortDir < 0 ? 1 : -1);
    });
    rows.forEach(function(r) { tbody.appendChild(r); });
    
    // Update Posição (Col 0) to keep numbering correct (1º, 2º, etc)
    rows.forEach(function(r, i) {
      if (r.cells[0]) r.cells[0].innerText = (i + 1) + 'º';
    });
  };
})();
</script>
"""
if "window.sortCreativos" not in html:
    html = html.replace('</body>', js_script + '\n</body>')

file_path.write_text(html, encoding='utf-8')
print("Patch successfully applied!")
