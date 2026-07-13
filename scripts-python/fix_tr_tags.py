import re
from pathlib import Path

file_path = Path(r"C:\Users\trafe\OneDrive\Desktop\workspace-mmm\analises\[PBB-ABR-26]\ANALISE_CRIATIVOS_[PBB-ABR-26].html")
html = file_path.read_text(encoding='utf-8')

# Fix rows that end with </tr><td...>...</td>
fixed_html = re.sub(r'</tr>(<td[^>]*>.*?</td>)', r'\1</tr>', html)

# Some rows might be missing <tr> entirely at the start of the row
def fix_start(match):
    text = match.group(0)
    if not text.startswith('<tr>'):
        return '<tr>' + text
    return text

fixed_html = re.sub(r'(?:<tr>)?<td>\d+º</td>', fix_start, fixed_html)

file_path.write_text(fixed_html, encoding='utf-8')
print("Successfully fixed table rows HTML tags.")
