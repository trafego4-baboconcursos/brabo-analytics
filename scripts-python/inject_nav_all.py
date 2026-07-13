"""
inject_nav_all.py — Idempotent nav injector for all Brabo Analytics HTML reports.

Run this after (re)generating any HTML report to refresh the nav everywhere:

    .venv\\Scripts\\python.exe scripts-python\\inject_nav_all.py

What it does:
  1. Removes any existing <!-- BRABO-NAV -->...<!-- /BRABO-NAV --> block
  2. Injects the nav immediately after <body ...>
  3. Generates analises/index.html (homepage master)
"""

import re
import sys
from pathlib import Path

ROOT     = Path(__file__).resolve().parent.parent   # workspace root
ANALISES = ROOT / "analises"

# Ensure nav_component is importable from the same folder as this script
sys.path.insert(0, str(Path(__file__).resolve().parent))
from nav_component import nav_html, CAMPAIGNS, FRAME_CLOSE   # noqa: E402


# ── Helpers ───────────────────────────────────────────────────────────────────

_NAV_PATTERN = re.compile(
    r"<!-- BRABO-NAV -->.*?<!-- /BRABO-NAV -->",
    flags=re.DOTALL,
)
_FRAME_END_PATTERN = re.compile(
    r"<!-- BRABO-FRAME-END -->.*?<!-- /BRABO-FRAME-END -->",
    flags=re.DOTALL,
)
_BODY_PATTERN  = re.compile(r"<body[^>]*>", flags=re.IGNORECASE)
_BODY_END_PATTERN = re.compile(r"</body>", re.IGNORECASE)


def inject_file(path: Path, campaign: str | None, depth: int) -> None:
    content = path.read_text(encoding="utf-8")

    # Remove existing nav and frame-end blocks (idempotency)
    content = _NAV_PATTERN.sub("", content)
    content = _FRAME_END_PATTERN.sub("", content)

    # Build new nav (opening: sidebar + <main id=bs-main>)
    nav = nav_html(
        active_campaign=campaign,
        active_page_file=path.name,
        depth=depth,
    )

    # Inject nav right after <body ...>
    m = _BODY_PATTERN.search(content)
    if m:
        pos = m.end()
        content = content[:pos] + "\n" + nav + "\n" + content[pos:]
    else:
        content = nav + "\n" + content

    # Inject frame-close (</main></div>) before </body>
    m2 = _BODY_END_PATTERN.search(content)
    if m2:
        pos2 = m2.start()
        content = content[:pos2] + "\n" + FRAME_CLOSE + "\n" + content[pos2:]

    path.write_text(content, encoding="utf-8")
    print(f"  [OK] {path.name}")


# ── Index page generator ──────────────────────────────────────────────────────

def _card(label: str, href: str, color: str, roas: str, revenue: str, sales: str,
          description: str) -> str:
    return f"""
        <a class="camp-card" href="{href}" style="--accent:{color}">
          <div class="camp-card-header" style="background:{color}">
            <span class="camp-label">{label}</span>
          </div>
          <div class="camp-card-body">
            <div class="camp-kpi-row">
              <div class="kpi"><span class="kpi-val">{roas}</span><span class="kpi-lbl">ROAS</span></div>
              <div class="kpi"><span class="kpi-val">{revenue}</span><span class="kpi-lbl">Faturamento</span></div>
              <div class="kpi"><span class="kpi-val">{sales}</span><span class="kpi-lbl">Vendas</span></div>
            </div>
            <p class="camp-desc">{description}</p>
            <span class="camp-cta">Ver análises →</span>
          </div>
        </a>"""


def generate_index() -> None:
    nav = nav_html(active_campaign=None, active_page_file="index.html", depth=0)

    fev_card = _card(
        label="PBB — FEV 2026",
        href="[PBB-FEV-26]/INDEX_[PBB-FEV-26].html",
        color="#667eea",
        roas="3.17×",
        revenue="R$ 995k",
        sales="813 vendas",
        description="Preparatório Banco do Brasil — fevereiro/2026. Melhor ROAS da série.",
    )
    abr_card = _card(
        label="PBB — ABR 2026",
        href="[PBB-ABR-26]/INDEX_[PBB-ABR-26].html",
        color="#f5576c",
        roas="1.80×",
        revenue="R$ 657k",
        sales="571 vendas",
        description="Preparatório Banco do Brasil — abril/2026.",
    )
    pes_jan_card = _card(
        label="Escrevente TJSP — JAN 2026",
        href="[PES-JAN-26]/INDEX_[PES-JAN-26].html",
        color="#764ba2",
        roas="2.69×",
        revenue="R$ 2,02M",
        sales="1.731 vendas",
        description="Projeto Escrevente TJSP — janeiro/2026. Lançamento inicial de volume recorde.",
    )
    pes_mai_card = _card(
        label="Escrevente TJSP — MAI 2026",
        href="[PES-MAI-26]/INDEX_[PES-MAI-26].html",
        color="#0f766e",
        roas="3.13×",
        revenue="R$ 2,41M",
        sales="1.668 vendas",
        description="Projeto Escrevente TJSP — maio/2026, com funil, mídias, typeform e insights.",
    )
    inss_placeholder = """
        <div class="camp-card" style="--accent:#94a3b8">
          <div class="camp-card-header" style="background:#64748b">
            <span class="camp-label">INSS</span>
          </div>
          <div class="camp-card-body">
            <p class="camp-desc">Ainda não temos análises publicadas para este produto.</p>
            <span class="camp-cta">Em breve</span>
          </div>
        </div>"""
    comp_card = f"""
        <a class="camp-card comp-card" href="COMPARATIVO_ABR_FEV_2026.html">
          <div class="camp-card-header" style="background:linear-gradient(135deg,#f5576c,#667eea)">
            <span class="camp-label">📊 Comparativo ABR × FEV</span>
          </div>
          <div class="camp-card-body">
            <p class="camp-desc">Análise comparativa completa entre as duas edições: mídia, criativos, leads, vendas e pesquisa Typeform.</p>
            <span class="camp-cta">Ver comparativo →</span>
          </div>
        </a>"""

    html = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Brabo Analytics — MMM</title>
<style>
*, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
body {{ background: #0f0f1a; color: #e0e0e0;
       font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; min-height: 100vh; }}
.hero {{
  text-align: center; padding: 60px 24px 40px;
  background: linear-gradient(160deg, #1a1a2e 0%, #16213e 60%, #0f3460 100%);
}}
.hero img {{ height: 52px; margin-bottom: 20px; }}
.hero h1 {{ font-size: 2rem; font-weight: 800; color: #fff; letter-spacing: -.02em; }}
.hero p  {{ color: #9ca3af; margin-top: 8px; font-size: 1rem; }}
.cards-section {{ max-width: 960px; margin: 0 auto; padding: 40px 24px 80px; }}
.cards-section h2 {{ font-size: .75rem; font-weight: 700; color: #6b7280;
                    text-transform: uppercase; letter-spacing: .08em; margin-bottom: 20px; }}
.cards-grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 20px; }}
.camp-card {{
  background: #1a1a2e; border: 1px solid rgba(255,255,255,.08);
  border-radius: 12px; overflow: hidden; text-decoration: none; color: inherit;
  transition: transform .2s, box-shadow .2s;
}}
.camp-card:hover {{ transform: translateY(-4px); box-shadow: 0 12px 32px rgba(0,0,0,.5); }}
.camp-card-header {{ padding: 20px; }}
.camp-label {{ font-size: .9rem; font-weight: 700; color: #fff; }}
.camp-card-body {{ padding: 20px; }}
.camp-kpi-row {{ display: flex; gap: 12px; margin-bottom: 14px; }}
.kpi {{ display: flex; flex-direction: column; align-items: center;
        flex: 1; background: rgba(255,255,255,.05); border-radius: 8px; padding: 10px 4px; }}
.kpi-val {{ font-size: 1.1rem; font-weight: 800; color: #fff; }}
.kpi-lbl {{ font-size: .65rem; color: #9ca3af; margin-top: 2px; }}
.camp-desc {{ font-size: .82rem; color: #9ca3af; line-height: 1.5; margin-bottom: 14px; }}
.camp-cta  {{ font-size: .8rem; font-weight: 600; color: var(--accent, #667eea); }}
.comp-card .camp-card-body .camp-desc {{ margin-top: 8px; }}
</style>
</head>
<body>
{nav}

<div class="hero">
  <img src="../img/logo-brabo-concursos.png" alt="Brabo Concursos">
  <h1>Brabo Analytics</h1>
  <p>Central de análises de campanhas — Marketing de Performance</p>
</div>

<div class="cards-section">
  <h2>Produto — INSS</h2>
  <div class="cards-grid">
{inss_placeholder}
  </div>
</div>

<div class="cards-section">
  <h2>Produto — Banco do Brasil</h2>
  <div class="cards-grid">
{fev_card}
{abr_card}
{comp_card}
  </div>
</div>

<div class="cards-section">
  <h2>Produto — Escrevente TJSP</h2>
  <div class="cards-grid">
{pes_jan_card}
{pes_mai_card}
  </div>
</div>

{FRAME_CLOSE}
</body>
</html>"""

    out = ANALISES / "index.html"
    out.write_text(html, encoding="utf-8")
    print(f"  [OK] index.html gerado ({out.stat().st_size // 1024}KB)")


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    total = 0

    # ── PES-JAN-26 ──
    pes_jan_dir = ANALISES / "[PES-JAN-26]"
    print(f"\n[PES-JAN-26] {pes_jan_dir}")
    for html_file in sorted(pes_jan_dir.glob("*.html")):
        inject_file(html_file, "PES-JAN-26", depth=1)
        total += 1

    # ── PBB-FEV-26 ──
    fev_dir = ANALISES / "[PBB-FEV-26]"
    print(f"\n[PBB-FEV-26] {fev_dir}")
    for html_file in sorted(fev_dir.glob("*.html")):
        inject_file(html_file, "PBB-FEV-26", depth=1)
        total += 1

    # ── PBB-ABR-26 ──
    abr_dir = ANALISES / "[PBB-ABR-26]"
    print(f"\n[PBB-ABR-26] {abr_dir}")
    for html_file in sorted(abr_dir.glob("*.html")):
        inject_file(html_file, "PBB-ABR-26", depth=1)
        total += 1

    # ── PES-MAI-26 ──
    pes_dir = ANALISES / "[PES-MAI-26]"
    print(f"\n[PES-MAI-26] {pes_dir}")
    for html_file in sorted(pes_dir.glob("*.html")):
      inject_file(html_file, "PES-MAI-26", depth=1)
      total += 1

    # ── analises/ root — comparativo ──
    print(f"\n[root] {ANALISES}")
    comp = ANALISES / "COMPARATIVO_ABR_FEV_2026.html"
    if comp.exists():
        inject_file(comp, None, depth=0)
        total += 1

    # ── homepage ──
    print()
    generate_index()
    total += 1

    print(f"\n[OK] {total} arquivos processados")


if __name__ == "__main__":
    main()
