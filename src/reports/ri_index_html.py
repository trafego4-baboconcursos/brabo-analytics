from __future__ import annotations

from pathlib import Path


def _format_number(value: object) -> str:
    if isinstance(value, float):
        return f"{value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return str(value)


def write_ri_campaign_index_html(output_path: Path, rows: list[dict]) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    total_launches = len(rows)
    total_sales = sum(int(row.get("total_sales", 0) or 0) for row in rows)
    total_ri_sales = sum(int(row.get("ri_sales", 0) or 0) for row in rows)
    total_revenue = sum(float(row.get("total_revenue", 0) or 0.0) for row in rows)
    total_ri_revenue = sum(float(row.get("ri_revenue", 0) or 0.0) for row in rows)
    latest_report = rows[0].get('report_html', '') if rows else ''

    table_rows = []
    for row in rows:
        report_html = row.get('report_html', '') or ''
        launch_code = row.get('launch_code', '')
        launch_label = f'<a href="{report_html}">{launch_code}</a>' if report_html else str(launch_code)
        table_rows.append(
            "<tr>"
            f"<td>{launch_label}</td>"
            f"<td>{row.get('created_at', '')}</td>"
            f"<td>{_format_number(row.get('total_sales', 0))}</td>"
            f"<td>{_format_number(row.get('hotmart_sales', 0))}</td>"
            f"<td>{_format_number(row.get('tmb_sales', 0))}</td>"
            f"<td>{_format_number(row.get('total_revenue', 0.0))}</td>"
            f"<td>{_format_number(row.get('fb_spend', 0.0))}</td>"
            f"<td>{_format_number(row.get('yt_spend', 0.0))}</td>"
            f"<td>{_format_number(row.get('ri_sales', 0))}</td>"
            f"<td>{_format_number(row.get('ri_revenue', 0.0))}</td>"
            f"<td>{_format_number(row.get('ri_buyers_with_utm', 0))}</td>"
            f"<td>{_format_number(row.get('ri_buyers_without_utm', 0))}</td>"
            f"<td>{_format_number(row.get('roas', 0.0))}</td>"
            "</tr>"
        )

    html = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>RI Index</title>
    <style>
        * {{ box-sizing: border-box; }}
        body {{ margin: 0; font-family: Segoe UI, Arial, sans-serif; background: #f4f1ec; color: #222; }}
        .wrap {{ max-width: 1400px; margin: 0 auto; padding: 28px; }}
        .hero {{ background: linear-gradient(135deg, #1e1e1e, #eb5757); color: #fff; border-radius: 20px; padding: 28px; box-shadow: 0 18px 50px rgba(0,0,0,.18); }}
        .hero h1 {{ margin: 0 0 8px; font-size: 34px; }}
        .hero p {{ margin: 0; opacity: .88; }}
        .cards {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 14px; margin: 18px 0 24px; }}
        .card {{ background: #fff; border-radius: 16px; padding: 18px; box-shadow: 0 10px 30px rgba(0,0,0,.06); border: 1px solid rgba(0,0,0,.05); }}
        .card .label {{ font-size: 12px; text-transform: uppercase; letter-spacing: .08em; color: #777; }}
        .card .value {{ font-size: 26px; font-weight: 800; margin-top: 6px; color: #111; }}
        .section {{ margin-top: 18px; background: #fff; border-radius: 20px; padding: 18px; box-shadow: 0 10px 30px rgba(0,0,0,.06); }}
        table {{ width: 100%; border-collapse: collapse; }}
        th, td {{ padding: 12px 10px; border-bottom: 1px solid #ece7e1; text-align: left; font-size: 14px; }}
        th {{ background: #faf7f3; position: sticky; top: 0; z-index: 1; }}
        tbody tr:hover {{ background: #fff8f4; }}
        .meta {{ margin-top: 10px; color: #666; font-size: 13px; }}
        .table-wrap {{ overflow-x: auto; }}
        .filter-bar {{ display: flex; gap: 10px; align-items: center; margin-bottom: 14px; }}
        .filter-bar input {{ flex: 1; padding: 9px 14px; border: 1px solid #ddd; border-radius: 10px; font-size: 14px; outline: none; }}
        .filter-bar input:focus {{ border-color: #eb5757; box-shadow: 0 0 0 3px rgba(235,87,87,.15); }}
        .filter-bar .clear-btn {{ padding: 9px 16px; border: none; background: #eb5757; color: #fff; border-radius: 10px; cursor: pointer; font-size: 14px; }}
        .filter-bar .clear-btn:hover {{ background: #c94444; }}
        .no-match {{ display: none; padding: 20px; text-align: center; color: #999; }}
    </style>
</head>
<body>
<div class="wrap">
    <div class="hero">
        <h1>RI Index</h1>
        <p>Comparativo histórico de campanhas com resumo geral e recorte de Recuperador Inteligente.</p>
        {f'<p style="margin-top: 10px;"><a href="{latest_report}" style="color:#fff;text-decoration:underline;">Abrir relatório mais recente</a> | <a href="RI_INDEX.csv" style="color:#fff;text-decoration:underline;">Abrir índice CSV</a></p>' if latest_report else ''}
    </div>

    <div class="cards">
        <div class="card"><div class="label">Campanhas</div><div class="value">{total_launches}</div></div>
        <div class="card"><div class="label">Vendas Totais</div><div class="value">{total_sales}</div></div>
        <div class="card"><div class="label">Receita Total</div><div class="value">{_format_number(total_revenue)}</div></div>
        <div class="card"><div class="label">Vendas RI</div><div class="value">{total_ri_sales}</div></div>
        <div class="card"><div class="label">Receita RI</div><div class="value">{_format_number(total_ri_revenue)}</div></div>
    </div>

    <div class="section">
        <h2>Histórico por campanha</h2>
        <div class="filter-bar">
            <input type="text" id="ri-filter" placeholder="Filtrar por campanha, período... (ex: PBB, ABR, 26)" oninput="filterTable()" />
            <button class="clear-btn" onclick="clearFilter()">Limpar</button>
        </div>
        <div class="table-wrap">
            <table>
                <thead>
                    <tr>
                        <th>Campanha</th>
                        <th>Atualizado em</th>
                        <th>Vendas Total</th>
                        <th>Hotmart</th>
                        <th>TMB</th>
                        <th>Receita</th>
                        <th>Gasto FB</th>
                        <th>Gasto YT</th>
                        <th>Vendas RI</th>
                        <th>Receita RI</th>
                        <th>RI com UTM</th>
                        <th>RI sem UTM</th>
                        <th>ROAS</th>
                    </tr>
                </thead>
                <tbody id="ri-tbody">
                    {''.join(table_rows) if table_rows else '<tr><td colspan="13">Sem dados</td></tr>'}
                </tbody>
            </table>
            <div class="no-match" id="no-match">Nenhuma campanha encontrada para o filtro aplicado.</div>
        </div>
        <div class="meta">Fonte: tabela ri_campaign_summary no SQLite. Atualizado em cada execução da análise.</div>
    </div>
</div>
<script>
    function filterTable() {{
        var q = document.getElementById('ri-filter').value.trim().toLowerCase();
        var rows = document.querySelectorAll('#ri-tbody tr');
        var visible = 0;
        rows.forEach(function(row) {{
            var text = row.textContent.toLowerCase();
            if (!q || text.includes(q)) {{
                row.style.display = '';
                visible++;
            }} else {{
                row.style.display = 'none';
            }}
        }});
        document.getElementById('no-match').style.display = (visible === 0 && q) ? 'block' : 'none';
    }}
    function clearFilter() {{
        document.getElementById('ri-filter').value = '';
        filterTable();
    }}
</script>
</body>
</html>
"""
    output_path.write_text(html, encoding="utf-8")
