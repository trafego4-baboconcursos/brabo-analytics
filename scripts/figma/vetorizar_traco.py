# Converte o desenho de traço de uma região da imagem em linhas abertas (SVG) para o Figma animar.
# Uso: python vetorizar.py IMAGEM.jpg x0 y0 x1 y1 SAIDA.svg [--previa PREVIA.png]
import sys, math
import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage as ndi
from skimage.morphology import skeletonize

img, x0, y0, x1, y1, out = sys.argv[1], *map(int, sys.argv[2:6]), sys.argv[6]
a = np.asarray(Image.open(img).convert("RGB")).astype(np.float32)
H, W = a.shape[:2]
bg = np.median(np.concatenate([a[:6].reshape(-1, 3), a[-6:].reshape(-1, 3)]), axis=0)
reg = a[y0:y1, x0:x1]
dist = np.sqrt(((reg - bg) ** 2).sum(axis=2))
ink = dist > 70
ink = ndi.binary_opening(ink, iterations=1) | (dist > 140)
# remove sujeira pequena
lab, n = ndi.label(ink, structure=np.ones((3, 3)))
sizes = ndi.sum(ink, lab, range(1, n + 1))
ink = np.isin(lab, np.where(sizes >= 25)[0] + 1)
# letras miúdas dentro do desenho (ex.: "DIPLOMA", "TJSP") viram imagem com fade, não linha
lab, n = ndi.label(ink, structure=np.ones((3, 3)))
small = np.zeros(n + 1, bool)
for i, sl in enumerate(ndi.find_objects(lab)):
    h, w = sl[0].stop - sl[0].start, sl[1].stop - sl[1].start
    if h <= 34 and w <= 42: small[i + 1] = True
detail = small[lab]
# agrupa: só vira detalhe se tiver vizinhos pequenos (palavra), traço solto fica vetor
dlab, dn = ndi.label(ndi.binary_dilation(detail, iterations=7))
cnt = ndi.sum(detail & (lab > 0), dlab, range(1, dn + 1))
ncomp = np.array([len(np.unique(lab[(dlab == k + 1) & detail])) for k in range(dn)]) if dn else np.array([])
keep_words = np.zeros(dn + 1, bool)
for k in range(dn): keep_words[k + 1] = ncomp[k] >= 3
detail = detail & keep_words[dlab]
ink = ink & ~detail
if "--detalhe" in sys.argv:
    dfull = np.zeros((H, W), np.uint8)
    dd = ndi.binary_dilation(detail, iterations=2)
    alpha = np.clip((dist - 20) / 80, 0, 1) * dd
    dfull[y0:y1, x0:x1] = (alpha * 255).astype(np.uint8)
    rgba = np.zeros((H, W, 4), np.uint8); rgba[..., :3] = a.astype(np.uint8); rgba[..., 3] = dfull
    Image.fromarray(rgba, "RGBA").save(sys.argv[sys.argv.index("--detalhe") + 1])
# espessura média do traço
edt = ndi.distance_transform_edt(ink)
sk = skeletonize(ink)
stroke_w = max(3.0, float(np.median(edt[sk])) * 2.0 + 1.0) if sk.any() else 6.0
# cor do traço
inkcol = reg[ink].mean(axis=0) if ink.any() else np.array([20, 20, 40])

# --- grafo do esqueleto -> polilinhas ---
pts = set(zip(*np.nonzero(sk)))
N8 = [(-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1)]
def nb(p): return [(p[0] + dy, p[1] + dx) for dy, dx in N8 if (p[0] + dy, p[1] + dx) in pts]
deg = {p: len(nb(p)) for p in pts}
nodes = {p for p in pts if deg[p] != 2}
used = set(); paths = []
def edge_key(p, q): return (p, q) if p < q else (q, p)
def walk(start, nxt):
    path = [start, nxt]; used.add(edge_key(start, nxt)); prev, cur = start, nxt
    while cur not in nodes:
        cand = [q for q in nb(cur) if q != prev and edge_key(cur, q) not in used]
        if not cand: break
        q = cand[0]; used.add(edge_key(cur, q)); path.append(q); prev, cur = cur, q
    return path
for s in nodes:
    for q in nb(s):
        if edge_key(s, q) not in used: paths.append(walk(s, q))
# laços sem nós (círculos perfeitos)
for p in pts:
    for q in nb(p):
        if edge_key(p, q) not in used: paths.append(walk(p, q))

def rdp(P, eps):
    if len(P) < 3: return P
    (ya, xa), (yb, xb) = P[0], P[-1]; dy, dx = yb - ya, xb - xa; L = math.hypot(dy, dx)
    best, idx = 0, 0
    for i in range(1, len(P) - 1):
        yy, xx = P[i]
        d = abs(dy * (xx - xa) - dx * (yy - ya)) / L if L else math.hypot(yy - ya, xx - xa)
        if d > best: best, idx = d, i
    if best > eps: return rdp(P[:idx + 1], eps)[:-1] + rdp(P[idx:], eps)
    return [P[0], P[-1]]

# junta caminhos que se continuam (mesma ponta) p/ ter traços mais longos
paths = [p for p in paths if len(p) >= 3]
merged = True
while merged:
    merged = False
    for i in range(len(paths)):
        for j in range(len(paths)):
            if i == j: continue
            a1, b1 = paths[i], paths[j]
            if a1[-1] == b1[0] and deg.get(a1[-1], 0) == 3:
                # continua só se a direção for parecida
                v1 = np.subtract(a1[-1], a1[max(0, len(a1) - 6)]); v2 = np.subtract(b1[min(len(b1) - 1, 5)], b1[0])
                c = np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2) + 1e-9)
                if c > 0.7:
                    paths[i] = a1 + b1[1:]; paths.pop(j); merged = True; break
        if merged: break

def smooth_d(P):
    P = rdp(P, 1.2)
    P = [(x + x0, y + y0) for y, x in P]
    if len(P) == 2: return f"M{P[0][0]:.1f} {P[0][1]:.1f} L{P[1][0]:.1f} {P[1][1]:.1f}"
    d = f"M{P[0][0]:.1f} {P[0][1]:.1f}"
    for i in range(1, len(P) - 1):
        mx, my = (P[i][0] + P[i + 1][0]) / 2, (P[i][1] + P[i + 1][1]) / 2
        d += f" Q{P[i][0]:.1f} {P[i][1]:.1f} {mx:.1f} {my:.1f}"
    d += f" L{P[-1][0]:.1f} {P[-1][1]:.1f}"
    return d

# ordem de desenho: de cima p/ baixo, da esquerda p/ direita, traços longos primeiro dentro da mesma faixa
paths.sort(key=lambda p: (round(min(q[0] for q in p) / 60), min(q[1] for q in p)))
col = "#%02X%02X%02X" % tuple(int(v) for v in inkcol)
els = [f'<path d="{smooth_d(p)}" stroke="{col}" stroke-width="{stroke_w:.1f}" stroke-linecap="round" stroke-linejoin="round" fill="none"/>' for p in paths]
svg = f'<svg width="{W}" height="{H}" viewBox="0 0 {W} {H}" fill="none" xmlns="http://www.w3.org/2000/svg">' + "".join(els) + "</svg>"
open(out, "w", encoding="utf-8").write(svg)
print(f"traços={len(paths)} espessura={stroke_w:.1f} cor={col} tamanho_svg={len(svg)}")
if "--previa" in sys.argv:
    pv = Image.new("RGB", (x1 - x0, y1 - y0), tuple(int(v) for v in bg)); d = ImageDraw.Draw(pv)
    for p in paths:
        P = rdp(p, 1.2); d.line([(x, y) for y, x in P], fill=(20, 20, 60), width=max(2, int(stroke_w)), joint="curve")
    side = Image.new("RGB", (2 * (x1 - x0) + 10, y1 - y0), (120, 120, 120))
    side.paste(Image.fromarray(reg.astype(np.uint8)), (0, 0)); side.paste(pv, (x1 - x0 + 10, 0))
    side.save(sys.argv[sys.argv.index("--previa") + 1])
