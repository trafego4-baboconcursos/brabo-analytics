# Mede cartão e faixa de cada caixa (retângulo, raio do canto, cor, borda branca) a partir do PNG original.
import sys, json, numpy as np
from PIL import Image
from scipy import ndimage as ndi
S = sys.argv[1]; E = S + '/caixas/editavel'
cortes = json.load(open(f'{E}/cortes.json'))
def raio(m, x0, y0, x1, y1):
    # distância na diagonal de cada canto até a forma: d = r(√2 - 1)
    rs = []
    for cx, cy, dx, dy in [(x0, y0, 1, 1), (x1 - 1, y0, -1, 1), (x0, y1 - 1, 1, -1), (x1 - 1, y1 - 1, -1, -1)]:
        d = 0
        while d < 400 and not m[cy + dy * d, cx + dx * d]: d += 1
        rs.append(d * np.sqrt(2) / (np.sqrt(2) - 1))
    return rs
def ret(m):
    ys, xs = np.nonzero(m)
    # bbox robusto: linhas/colunas com pelo menos 30% de preenchimento do máximo
    rows = m.sum(1); cols = m.sum(0)
    ry = np.nonzero(rows > rows.max() * 0.3)[0]; cx = np.nonzero(cols > cols.max() * 0.3)[0]
    x0, x1, y0, y1 = cx.min(), cx.max() + 1, ry.min(), ry.max() + 1
    return [int(x0), int(y0), int(x1 - x0), int(y1 - y0)], raio(m, x0, y0, x1, y1)
out = {}
for i in range(1, 9):
    im = np.asarray(Image.open(f'{S}/caixas/orig/c{i}.png').convert('RGBA')).astype(int)
    al = im[..., 3] > 128; rgb = im[..., :3]; sat = rgb.max(2) - rgb.min(2); lum = rgb.mean(2)
    if f'c{i}' in cortes:
        x0, x1, ct = cortes[f'c{i}']; al[:ct, x0:x1] = False
    lab, n = ndi.label(ndi.binary_closing(sat > 70, iterations=3) & al)
    sizes = ndi.sum(sat > 70, lab, range(1, n + 1)); cy = ndi.center_of_mass(sat > 70, lab, range(1, n + 1))
    H, W = al.shape
    cand = [k + 1 for k in range(n) if cy[k][0] > H * 0.45]
    r = {}
    if cand and i != 8:
        pill = ndi.binary_fill_holes(ndi.binary_closing(lab == max(cand, key=lambda k: sizes[k - 1]), structure=np.ones((31, 31))))
        brush = ndi.binary_dilation((rgb[..., 0] > 170) & (rgb[..., 1] > 150) & (rgb[..., 2] < 120), iterations=6) if i != 6 else np.zeros_like(pill)
        pm = pill & ~brush if i in (2, 3) else pill
        # no 2 e 3 o "+" invade a faixa pela esquerda: mede a faixa sem ele, recompondo a borda esquerda pelo resto
        bb, rr = ret(pm)
        core = ndi.binary_erosion(pill, iterations=8) & ~ndi.binary_dilation((lum > 200) & (sat < 45), iterations=6) & ~brush
        col = np.median(rgb[core], axis=0)
        # borda branca: pixels claros logo abaixo da faixa ainda dentro do recorte
        x, y, w, h = bb; col_mid = slice(x + w // 3, x + 2 * w // 3)
        below = al[y + h:y + h + 30, col_mid] & (lum[y + h:y + h + 30, col_mid] > 200)
        borda = int(np.median(below.sum(0)))
        r['faixa'] = dict(bbox=bb, raios=[round(v, 1) for v in rr], cor='#%02X%02X%02X' % tuple(int(v) for v in col), borda_branca=borda)
        notpill = al & ~ndi.binary_dilation(pill, iterations=borda + 3)
    else:
        notpill = al.copy()
    # cartão = recorte sem a faixa (e sem o que sobra da borda dela)
    card = ndi.binary_opening(notpill, iterations=4)
    lab2, n2 = ndi.label(card); card = lab2 == (np.argmax(ndi.sum(card, lab2, range(1, n2 + 1))) + 1)
    if i == 8:
        r['cartao_forma'] = 'c8'
    bb, rr = ret(card)
    # o cartão continua por trás da faixa: estende até onde a faixa começa se o cartão for cortado por ela
    ccol = np.median(rgb[ndi.binary_erosion(card, iterations=10) & (sat < 30) & (lum > 200)], axis=0)
    r['cartao'] = dict(bbox=bb, raios=[round(v, 1) for v in rr], cor='#%02X%02X%02X' % tuple(int(v) for v in ccol))
    out[f'c{i}'] = r
    print(f'c{i}', json.dumps(r, ensure_ascii=False))
json.dump(out, open(f'{E}/formas.json', 'w'), indent=1)
