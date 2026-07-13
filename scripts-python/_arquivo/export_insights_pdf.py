from pathlib import Path
from bs4 import BeautifulSoup
from fpdf import FPDF
import re

workspace = Path(r"c:/Users/trafe/OneDrive/Desktop/workspace-mmm")
html_path = workspace / r"analises/[PBB-ABR-26]/INSIGHTS_RECOMENDACOES_[PBB-ABR-26].html"
pdf_path = workspace / r"INSIGHTS_RECOMENDACOES_[PBB-ABR-26].pdf"

html = html_path.read_text(encoding="utf-8")
soup = BeautifulSoup(html, "html.parser")

for tag in soup(["script", "style"]):
    tag.decompose()

content = []
for tag in soup.find_all(["h1", "h2", "h3", "p", "li", "tr"]):
    if tag.name == "tr":
        cells = [c.get_text(" ", strip=True) for c in tag.find_all(["th", "td"])]
        text = " | ".join([c for c in cells if c])
    else:
        text = tag.get_text(" ", strip=True)
    if text:
        content.append((tag.name, text))

pdf = FPDF()
pdf.set_auto_page_break(auto=True, margin=12)
pdf.add_page()
usable_w = pdf.w - pdf.l_margin - pdf.r_margin


def safe_text(text: str) -> str:
    text = text.encode("latin-1", "replace").decode("latin-1")
    # Break very long tokens to avoid FPDF line-wrap exceptions.
    def break_token(match):
        token = match.group(0)
        return " ".join(token[i:i+30] for i in range(0, len(token), 30))

    return re.sub(r"\S{45,}", break_token, text)

for kind, text in content:
    text = safe_text(text)
    if kind == "h1":
        pdf.set_font("Helvetica", "B", 16)
        pdf.set_x(pdf.l_margin)
        pdf.multi_cell(usable_w, 9, text)
        pdf.ln(2)
    elif kind == "h2":
        pdf.set_font("Helvetica", "B", 13)
        pdf.set_x(pdf.l_margin)
        pdf.multi_cell(usable_w, 8, text)
        pdf.ln(1)
    elif kind == "h3":
        pdf.set_font("Helvetica", "B", 11)
        pdf.set_x(pdf.l_margin)
        pdf.multi_cell(usable_w, 7, text)
    elif kind == "li":
        pdf.set_font("Helvetica", "", 10)
        pdf.set_x(pdf.l_margin)
        pdf.multi_cell(usable_w, 6, f"- {text}")
    elif kind == "tr":
        pdf.set_font("Helvetica", "", 9)
        pdf.set_x(pdf.l_margin)
        pdf.multi_cell(usable_w, 5, text)
    else:
        pdf.set_font("Helvetica", "", 10)
        pdf.set_x(pdf.l_margin)
        pdf.multi_cell(usable_w, 6, text)

pdf.output(str(pdf_path))
print(f"PDF_OK|{pdf_path}|{pdf_path.stat().st_size}")
