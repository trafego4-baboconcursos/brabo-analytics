"""
Aplica todas as modificações do META_ADS para GOOGLE_ADS + YouTube:
1. Título atualizado
2. Badge Google/YouTube no hero
3. Cards KPI com gradiente azul Google
4. CSS filter-bar, criativo-sub, tr:hover
5. Tabela criativos com filtros, data-val, nomes
6. JS sortCreativos
"""
from pathlib import Path
import re

FILE = Path(r'c:\Users\trafe\OneDrive\Desktop\workspace-mmm\analises\[PBB-ABR-26]\ANALISE_GOOGLE_ADS_[PBB-ABR-26].html')
t = FILE.read_text(encoding='utf-8')

# ── 1. Título ────────────────────────────────────────────────────────────────
t = t.replace(
    '<title>Google Ads + YouTube — Ecossistema ABR-26</title>',
    '<title>Analise de Criativos Google Ads + YouTube</title>'
)

# ── 2. CSS: cards gradiente + novas regras ────────────────────────────────────
OLD_CARD_CSS = (
    '        .card { background: #f8fafc; border: 1px solid #e5e7eb; border-radius: 14px; padding: 18px; }\n'
    '        .card .label { font-size: 12px; color: #6b7280; text-transform: uppercase; letter-spacing: .04em; margin-bottom: 8px; }\n'
    '        .card .value { font-size: 28px; font-weight: 800; color: #111827; }\n'
    '        .card .sub { margin-top: 6px; font-size: 13px; color: #6b7280; }'
)
NEW_CARD_CSS = (
    '        .card { background: linear-gradient(135deg, #4285f4 0%, #1a56d4 100%); border: none; border-radius: 14px; padding: 18px; box-shadow: 0 4px 12px rgba(66,133,244,.25); }\n'
    '        .card .label { font-size: 12px; color: rgba(255,255,255,.8); text-transform: uppercase; letter-spacing: .04em; margin-bottom: 8px; }\n'
    '        .card .value { font-size: 28px; font-weight: 800; color: #fff; }\n'
    '        .card .sub { margin-top: 6px; font-size: 13px; color: rgba(255,255,255,.75); }\n'
    '        .google-brand { display: inline-flex; align-items: center; gap: 10px; padding: 8px 16px; border-radius: 999px; border: 1px solid #bfdbfe; background: #fff; color: #0f172a; font-weight: 700; font-size: 14px; margin-bottom: 14px; }\n'
    '        .google-brand i { color: #4285f4; font-size: 22px; }\n'
    '        .filter-bar { display: flex; flex-wrap: wrap; align-items: center; gap: 8px; margin-bottom: 16px; }\n'
    '        .filter-label { font-size: 11px; color: #6b7280; font-weight: 700; text-transform: uppercase; letter-spacing: .05em; white-space: nowrap; }\n'
    '        .filter-btn { padding: 6px 14px; border-radius: 999px; border: 1.5px solid #4285f4; background: #fff; color: #4285f4; font-size: 13px; font-weight: 600; cursor: pointer; transition: all .15s; font-family: inherit; }\n'
    '        .filter-btn:hover { background: #eef3ff; }\n'
    '        .filter-btn.active { background: #4285f4; color: #fff; border-color: #4285f4; }\n'
    '        .criativo-sub { font-size: 11px; color: #6b7280; font-weight: 400; display: block; margin-top: 2px; }\n'
    '        tr:hover td { background: #f0f5ff; }'
)
t = t.replace(OLD_CARD_CSS, NEW_CARD_CSS)

# ── 3. Hero: adicionar badges ─────────────────────────────────────────────────
OLD_HERO = (
    '        <div class="hero">\n'
    '            <h1>Google Ads + YouTube — Ecossistema ABR-26</h1>'
)
NEW_HERO = (
    '        <div class="hero">\n'
    '            <div style="display:flex; gap:10px; flex-wrap:wrap; margin-bottom:6px;">\n'
    '                <div class="google-brand"><i class="ti ti-brand-google"></i> Google Ads</div>\n'
    '                <div class="google-brand"><i class="ti ti-brand-youtube"></i> YouTube</div>\n'
    '                <div class="google-brand"><i class="ti ti-calendar-event"></i> Abril 2026</div>\n'
    '            </div>\n'
    '            <h1>Analise de Criativos Google Ads + YouTube</h1>'
)
t = t.replace(OLD_HERO, NEW_HERO)

# ── 4. Tabela criativos: rebuild com filtros + data-val + nomes ───────────────
NAMES = {
    'AD092': 'Dois personagens casa do Thales',
    'AD050': 'Banco do Brasil 2 - cx nova',
    'AD110': 'Banco do Brasil 2 - cx nova',
    'AD113': 'Dois personagens ape do Felipe',
    'AD058': 'Casa do Thales',
    'AD112': 'Imagem apostilas',
    'AD059': 'Fachada Banco do Brasil + cx nova',
    'AD109': 'Fachada Banco do Brasil com cx',
    'AD114': 'Flip chart colorido Estúdio',
}

ROWS = [
    ('AD092', '20.611,83', 20611.83, '2.552', 2552, 25,  '40.132,02', 40132.02, '1.95x', 1.95, '0.98%', 0.98),
    ('AD084', '28.696,82', 28696.82, '4.353', 4353, 18,  '28.877,42', 28877.42, '1.01x', 1.01, '0.41%', 0.41),
    ('AD093', '13.451,35', 13451.35, '2.319', 2319, 16,  '25.643,60', 25643.60, '1.91x', 1.91, '0.69%', 0.69),
    ('AD050', '15.101,42', 15101.42, '2.550', 2550, 16,  '25.555,26', 25555.26, '1.69x', 1.69, '0.63%', 0.63),
    ('AD037', '17.751,47', 17751.47, '2.748', 2748, 12,  '19.324,62', 19324.62, '1.09x', 1.09, '0.44%', 0.44),
    ('AD110', '9.264,62',   9264.62, '1.764', 1764, 12,  '18.916,40', 18916.40, '2.04x', 2.04, '0.68%', 0.68),
    ('AD113', '5.021,05',   5021.05, '577',    577, 10,  '16.427,34', 16427.34, '3.27x', 3.27, '1.73%', 1.73),
    ('AD058', '8.036,72',   8036.72, '818',    818,  7,  '11.342,94', 11342.94, '1.41x', 1.41, '0.86%', 0.86),
    ('AD112', '3.421,82',   3421.82, '425',    425,  5,   '7.692,90',  7692.90, '2.25x', 2.25, '1.18%', 1.18),
    ('AD098', '5.808,80',   5808.80, '700',    700,  4,   '6.362,76',  6362.76, '1.10x', 1.10, '0.57%', 0.57),
    ('AD059', '6.021,90',   6021.90, '564',    564,  3,   '4.928,40',  4928.40, '0.82x', 0.82, '0.53%', 0.53),
    ('AD048', '2.083,41',   2083.41, '170',    170,  3,   '4.928,40',  4928.40, '2.37x', 2.37, '1.76%', 1.76),
    ('AD109', '3.581,21',   3581.21, '394',    394,  3,   '4.824,18',  4824.18, '1.35x', 1.35, '0.76%', 0.76),
    ('AD090', '3.531,93',   3531.93, '182',    182,  2,   '3.181,38',  3181.38, '0.90x', 0.90, '1.10%', 1.10),
    ('AD040', '3.072,71',   3072.71, '278',    278,  1,   '1.538,58',  1538.58, '0.50x', 0.50, '0.36%', 0.36),
    ('AD097', '1.769,43',   1769.43, '112',    112,  1,   '1.538,58',  1538.58, '0.87x', 0.87, '0.89%', 0.89),
    ('AD103', '1.742,42',   1742.42, '56',      56,  0,      '0,00',      0.00, '0.00x', 0.00, '0.00%', 0.00),
    ('AD091', '1.131,78',   1131.78, '28',      28,  0,      '0,00',      0.00, '0.00x', 0.00, '0.00%', 0.00),
    ('AD111', '1.053,00',   1053.00, '21',      21,  0,      '0,00',      0.00, '0.00x', 0.00, '0.00%', 0.00),
    ('AD031',   '903,49',    903.49, '54',      54,  0,      '0,00',      0.00, '0.00x', 0.00, '0.00%', 0.00),
    ('AD102',   '895,79',    895.79, '21',      21,  0,      '0,00',      0.00, '0.00x', 0.00, '0.00%', 0.00),
    ('AD114',   '674,51',    674.51, '91',      91,  0,      '0,00',      0.00, '0.00x', 0.00, '0.00%', 0.00),
    ('AD099',   '645,90',    645.90, '60',      60,  0,      '0,00',      0.00, '0.00x', 0.00, '0.00%', 0.00),
    ('AD117',   '561,59',    561.59, '79',      79,  0,      '0,00',      0.00, '0.00x', 0.00, '0.00%', 0.00),
]

def build_rows():
    lines = []
    for ad, inv_fmt, inv_val, lds_fmt, lds_val, vnd_val, fat_fmt, fat_val, roas_fmt, roas_val, conv_fmt, conv_val in ROWS:
        name = NAMES.get(ad, '')
        name_span = f'<span class="criativo-sub">{name}</span>' if name else ''
        fat_display = f'R$ {fat_fmt}' if fat_val > 0 else 'R$ 0,00'
        lines.append(
            f"    <tr><td><strong>{ad}</strong>{name_span}</td>"
            f"<td class='numero' data-val='{inv_val}'>R$ {inv_fmt}</td>"
            f"<td class='numero' data-val='{lds_val}'>{lds_fmt}</td>"
            f"<td class='numero' data-val='{vnd_val}'>{vnd_val}</td>"
            f"<td class='numero' data-val='{fat_val}'>{fat_display}</td>"
            f"<td class='numero' data-val='{roas_val}'>{roas_fmt}</td>"
            f"<td class='numero' data-val='{conv_val}'>{conv_fmt}</td></tr>"
        )
    return '\n'.join(lines)

NEW_CRIATIVOS_SECTION = (
    "<div class='section' id='section-criativos'>"
    "<h2>Criativos de captação — YouTube ABR</h2>"
    "<div class='filter-bar'>"
    "<span class='filter-label'>Ordenar por:</span>"
    "<button class='filter-btn active' onclick='sortCreativos(0)'>Investimento</button>"
    "<button class='filter-btn' onclick='sortCreativos(1)'>Leads</button>"
    "<button class='filter-btn' onclick='sortCreativos(2)'>Vendas</button>"
    "<button class='filter-btn' onclick='sortCreativos(3)'>Faturamento</button>"
    "<button class='filter-btn' onclick='sortCreativos(4)'>ROAS</button>"
    "<button class='filter-btn' onclick='sortCreativos(5)'>Taxa Conv.</button>"
    "</div>"
    "<div class='table-wrap'><table id='criativos-table'>"
    "<thead><tr>"
    "<th>Criativo</th>"
    "<th class='numero'>Investimento</th>"
    "<th class='numero'>Leads</th>"
    "<th class='numero'>Vendas</th>"
    "<th class='numero'>Faturamento</th>"
    "<th class='numero'>ROAS</th>"
    "<th class='numero'>Taxa Conv.</th>"
    "</tr></thead>"
    "<tbody>\n"
    + build_rows() + "\n"
    "  </tbody></table></div></div>"
)

# Find and replace the old criativos section (it starts with <div class='section'><h2>Criativos de captação — YouTube ABR</h2>)
old_start = "<div class='section'><h2>Criativos de captação — YouTube ABR</h2>"
old_end_marker = "</tbody></table></div></div>"
idx_start = t.find(old_start)
idx_end = t.find(old_end_marker, idx_start) + len(old_end_marker)
OLD_CRIATIVOS = t[idx_start:idx_end]
t = t.replace(OLD_CRIATIVOS, NEW_CRIATIVOS_SECTION)

# ── 5. JS sortCreativos ───────────────────────────────────────────────────────
JS = """<script>
(function() {
  var _sortIdx = 0, _sortDir = -1;
  var colMap = [1, 2, 3, 4, 5, 6];
  window.sortCreativos = function(colIdx) {
    var btns = document.querySelectorAll('#section-criativos .filter-btn');
    btns.forEach(function(b, i) { b.classList.toggle('active', i === colIdx); });
    if (_sortIdx === colIdx) { _sortDir = -_sortDir; } else { _sortDir = -1; _sortIdx = colIdx; }
    var tbody = document.querySelector('#criativos-table tbody');
    var rows = Array.from(tbody.querySelectorAll('tr'));
    var tc = colMap[colIdx];
    rows.sort(function(a, b) {
      var av = parseFloat((a.cells[tc] && a.cells[tc].dataset.val) || 0);
      var bv = parseFloat((b.cells[tc] && b.cells[tc].dataset.val) || 0);
      return (bv - av) * (_sortDir < 0 ? 1 : -1);
    });
    rows.forEach(function(r) { tbody.appendChild(r); });
  };
})();
</script>
</body>"""

t = t.replace('</body>', JS)

FILE.write_text(t, encoding='utf-8')
print("✅ ANALISE_GOOGLE_ADS atualizado com sucesso!")
print(f"   Tamanho final: {len(t):,} chars")
