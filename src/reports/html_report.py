from pathlib import Path


def render_report(output_path: Path, data: dict) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    title = f"Analise de Atribuicao UTM - {data['launch_code']}"
    html = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
    <link rel="icon" type="image/png" href="../../img/favicon-brabo-concursos.png">
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
            background: linear-gradient(135deg, #eb5757 0%, #ff9500 100%);
            color: #333;
            line-height: 1.6;
        }}
        .container {{
            max-width: 1200px;
            margin: 20px auto;
            background: white;
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
            overflow: hidden;
            border-radius: 8px;
        }}
        .content {{ padding: 40px; max-width: 100%; margin: 0 auto; }}
        .header {{
            background: white;
            color: #333;
            padding: 40px 20px;
            display: flex;
            justify-content: center;
            align-items: center;
            text-align: center;
            flex-wrap: wrap;
            border-bottom: 1px solid #eee;
        }}
        .header-logo {{ width: 100%; margin-bottom: 20px; }}
        .header-logo a {{ display: inline-block; text-decoration: none; }}
        .header-logo img {{ height: 60px; width: auto; }}
        .header-title h1 {{ font-size: 28px; font-weight: 700; margin-bottom: 5px; }}
        .header-title p {{ font-size: 16px; opacity: 0.9; }}
        .nav-links {{ margin-top: 14px; display: flex; gap: 10px; justify-content: center; flex-wrap: wrap; }}
        .nav-links a {{ display: inline-block; padding: 10px 14px; border-radius: 999px; text-decoration: none; font-weight: 700; font-size: 13px; }}
        .nav-links a.primary {{ background: #eb5757; color: #fff; }}
        .nav-links a.secondary {{ background: #f2f2f2; color: #333; border: 1px solid #ddd; }}
        .section {{ margin-bottom: 40px; }}
        .section-title {{
            font-size: 24px; color: #eb5757; font-weight: 700; margin-bottom: 20px;
            padding-bottom: 10px; border-bottom: 3px solid #eb5757; text-align: center;
        }}
        .subsection-title {{ font-size: 18px; color: #ff9500; font-weight: 600; margin-top: 20px; margin-bottom: 15px; }}
        .kpi-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 16px; margin-bottom: 20px; }}
        .kpi {{ background: #f9f9f9; border-radius: 8px; padding: 16px; border-left: 4px solid #eb5757; }}
        .kpi h3 {{ font-size: 14px; color: #666; text-transform: uppercase; letter-spacing: 0.6px; }}
        .kpi p {{ font-size: 22px; font-weight: 700; margin-top: 6px; color: #333; }}
        table {{ width: 100%; border-collapse: collapse; margin-bottom: 20px; background: #f9f9f9; border-radius: 4px; overflow: hidden; }}
        th {{ background: #eb5757; color: white; padding: 12px; text-align: left; font-weight: 600; }}
        td {{ padding: 12px; border-bottom: 1px solid #ddd; }}
        tr:last-child td {{ border-bottom: none; }}
        .list {{ margin-left: 18px; }}
        .list li {{ margin-bottom: 6px; }}
    </style>
</head>
<body>
<div class="container">
    <div class="header">
        <div style="text-align: center; width: 100%;">
            <div class="header-logo">
                <a href="INDEX_[{data['launch_code']}].html" title="Voltar ao Indice">
                    <img src="../../img/logo-brabo-concursos.png" alt="Brabo Concursos">
                </a>
            </div>
            <div class="header-title">
                <h1>Analise de Atribuicao UTM</h1>
                <p>{data['launch_code']} - Compradores atribuidos a origem do lead</p>
                <div class="nav-links">
                    <a class="primary" href="RI_INDEX.html">Voltar ao RI Index</a>
                    <a class="secondary" href="RI_[{data['launch_code']}].csv">Abrir CSV da campanha</a>
                </div>
            </div>
        </div>
    </div>
    <div class="content">
        <div class="section">
            <h2 class="section-title">Resumo Executivo</h2>
            <div class="kpi-grid">
                <div class="kpi"><h3>Total de vendas</h3><p>{data['total_sales']}</p></div>
                <div class="kpi"><h3>Valor das vendas (R$)</h3><p>{data['total_revenue']}</p></div>
                <div class="kpi"><h3>Gasto Facebook (R$)</h3><p>{data['fb_spend']}</p></div>
                <div class="kpi"><h3>Gasto YouTube (R$)</h3><p>{data['yt_spend']}</p></div>
                <div class="kpi"><h3>ROAS Geral</h3><p>{data['roas']}</p></div>
                <div class="kpi"><h3>Com UTM (lead encontrado)</h3><p>{data['buyers_with_utm']} ({data['buyers_with_utm_pct']})</p></div>
                <div class="kpi"><h3>Sem UTM (lead nao localizado)</h3><p>{data['buyers_without_utm']} ({data['buyers_without_utm_pct']})</p></div>
            </div>
        </div>

        <div class="section">
            <h2 class="section-title">Recuperador Inteligente (RI) - Bloco Dedicado</h2>
            <div class="kpi-grid">
                <div class="kpi"><h3>Vendas RI</h3><p>{data['ri_summary']['sales']}</p></div>
                <div class="kpi"><h3>Receita RI (R$)</h3><p>{data['ri_summary']['revenue']}</p></div>
                <div class="kpi"><h3>RI com UTM</h3><p>{data['ri_summary']['buyers_with_utm']} ({data['ri_summary']['buyers_with_utm_pct']})</p></div>
                <div class="kpi"><h3>RI sem UTM</h3><p>{data['ri_summary']['buyers_without_utm']} ({data['ri_summary']['buyers_without_utm_pct']})</p></div>
            </div>
        </div>

        <div class="section">
            <h2 class="section-title">Distribuicao por Fonte (Compradores com UTM)</h2>
            <table>
                <thead>
                    <tr>
                        <th>Fonte</th>
                        <th>Compradores</th>
                        <th>% do total com UTM</th>
                        <th>Gasto (R$)</th>
                        <th>Vendas (R$)</th>
                        <th>ROAS</th>
                    </tr>
                </thead>
                <tbody>
                    {''.join([f"<tr><td>{r['source']}</td><td>{r['buyers']}</td><td>{r['pct']}</td><td>{r['spend']}</td><td>{r['revenue']}</td><td>{r['roas']}</td></tr>" for r in data['distribution']])}
                </tbody>
            </table>
        </div>

        <div class="section">
            <h2 class="section-title">Top UTMs por Fonte</h2>
            {''.join(_render_top_utm_section(data['top_utms']))}
        </div>
    </div>
</div>
</body>
</html>
"""
    output_path.write_text(html, encoding="utf-8")


def _render_top_utm_section(top_utms: dict) -> list[str]:
    sections = []
    for source, items in top_utms.items():
        rows = []
        for item in items:
            rows.append(
                "<tr>"
                f"<td>{item['buyers']}</td>"
                f"<td>{item['revenue']}</td>"
                f"<td>{item['cartao']}</td>"
                f"<td>{item['boleto']}</td>"
                f"<td>{item['pix']}</td>"
                f"<td>{item['outros']}</td>"
                f"<td>{item['utm_source']}</td>"
                f"<td>{item['utm_medium']}</td>"
                f"<td>{item['utm_campaign']}</td>"
                "</tr>"
            )
        table = f"""
        <h3 class="subsection-title">{source}</h3>
        <table>
            <thead>
                <tr>
                    <th>Compradores</th>
                    <th>Receita (R$)</th>
                    <th>Cartao</th>
                    <th>Boleto</th>
                    <th>Pix</th>
                    <th>Outros</th>
                    <th>utm_source</th>
                    <th>utm_medium</th>
                    <th>utm_campaign</th>
                </tr>
            </thead>
            <tbody>
                {''.join(rows) if rows else '<tr><td colspan=\"9\">Sem dados</td></tr>'}
            </tbody>
        </table>
        """
        sections.append(table)
    return sections
