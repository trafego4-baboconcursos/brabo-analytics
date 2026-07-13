from pathlib import Path
import re
t = Path(r"c:\Users\trafe\OneDrive\Desktop\workspace-mmm\analises\[PBB-ABR-26]\ANALISE_ANUNCIOS_[PBB-ABR-26].html").read_text(encoding="utf-8")
hits = list(re.finditer(r"<h2[^>]*>(.*?)</h2>", t, re.S))
print(f"h2 count: {len(hits)}")
for i, m in enumerate(hits):
    print(f"{i}: {m.group(1)[:80]}")
print()
# Find divs with explicit width or max-width in style attr
hits2 = list(re.finditer(r'style="[^"]*width[^"]*"', t))
print(f"inline width styles: {len(hits2)}")
for m in hits2[:20]:
    print(repr(t[m.start()-60:m.end()+60]))
    print()
# Find .container divs
hits3 = list(re.finditer(r'<div class="container[^"]*"', t))
print(f"container divs: {len(hits3)}")
for m in hits3[:20]:
    print(repr(t[m.start():m.start()+120]))
