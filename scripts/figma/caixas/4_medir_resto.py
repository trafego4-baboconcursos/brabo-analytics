# Completa as medidas: base do cartão, forma da caixa 8, área dos olhos, e prepara o que ainda vai pro VTracer ("+" e "INSS").
import sys, json, numpy as np
from PIL import Image
from scipy import ndimage as ndi
S = sys.argv[1]; E = S + '/caixas/editavel'
F = json.load(open(f'{E}/formas.json')); cortes = json.load(open(f'{E}/cortes.json'))
txt = json.load(open(f'{E}/textos.json', encoding='utf-8')); lg = json.load(open(f'{E}/logos.json'))
for i in range(1, 9):
    k = f'c{i}'; im = np.asarray(Image.open(f'{S}/caixas/orig/{k}.png').convert('RGBA')).astype(int)
    al = im[..., 3] > 128; rgb = im[..., :3]
    if k in cortes: x0c, x1c, ct = cortes[k]; al[:ct, x0c:x1c] = False
    c = F[k]['cartao']; x, y, w, h = c['bbox']; r = float(np.mean(c['raios'][:2]))
    if i == 8:
        rows = [(yy, np.nonzero(al[yy])[0]) for yy in range(al.shape[0]) if al[yy].any()]
        top_y = rows[0][0]; bot_y = rows[-1][0] + 1
        widths = np.array([xs.max() - xs.min() for _, xs in rows])
        wfull = np.median(widths[: len(widths) // 4])
        tab_rows = [(yy, xs) for (yy, xs), ww in zip(rows, widths) if ww < wfull * 0.85]
        tab_y = next(yy for yy, xs in tab_rows if yy > top_y + 50)
        mid = [xs for yy, xs in tab_rows if yy > tab_y + 60 and yy < bot_y - 60]
        tx0 = int(np.median([xs.min() for xs in mid])); tx1 = int(np.median([xs.max() for xs in mid])) + 1
        X0 = int(np.median([xs.min() for yy, xs in rows if top_y + 60 < yy < tab_y - 60])); X1 = int(np.median([xs.max() for yy, xs in rows if top_y + 60 < yy < tab_y - 60])) + 1
        # raio côncavo: na coluna tx0 - d, a borda inferior do cartão de cima desce até tab_y + algo
        def bottom(col): return int(np.nonzero(al[:, col])[0].max()) + 1
        conc = [bottom(tx0 - d) - tab_y for d in range(1, 120)]
        rc = next((d for d, v in enumerate(conc, 1) if v <= 1), 40)
        F[k]['forma8'] = dict(topo=[X0, int(top_y), X1 - X0, int(tab_y - top_y)], aba=[tx0, int(tab_y), tx1 - tx0, int(bot_y - tab_y)], raio=round(r, 1), raio_concavo=rc)
        # olhos: tudo que não é branco/magenta à direita do "?"
        l2 = txt[k]['lines'][1]['bbox']; lum = rgb.mean(2); sat = rgb.max(2) - rgb.min(2)
        eye = al & ~((lum > 235) & (sat < 20)); eye[:, : l2[0] + l2[2] + 4] = False; eye[: l2[1] - 30] = False
        lab, n = ndi.label(ndi.binary_closing(eye, iterations=3)); sz = ndi.sum(eye, lab, range(1, n + 1))
        eye = np.isin(lab, np.where(sz > 300)[0] + 1); ys, xs = np.nonzero(eye)
        F[k]['olhos'] = [int(xs.min()), int(ys.min()), int(xs.max() - xs.min() + 1), int(ys.max() - ys.min() + 1)]
        print(k, F[k]['forma8'], 'olhos', F[k]['olhos']); continue
    p = F[k]['faixa']; px0, py0, pw, ph = p['bbox']
    col = int(x + r + 6)
    if col < px0 - 6:
        cb = int(np.nonzero(al[:, col])[0].max()) + 1; hidden = False
    else:   # base atrás da faixa: mede a curva do canto na coluna x+8 (fora da faixa) e completa o círculo
        d = 8; yc = int(np.nonzero(al[:, x + d])[0].max()) + 1
        cb = int(round(yc + (r - np.sqrt(max(0, r * r - (r - d) ** 2))))); hidden = True
    c['bbox'] = [x, y, w, cb - y]; c['raio'] = round(r, 1); c['base_escondida'] = hidden
    F[k]['faixa']['raio'] = round(float(np.mean(p['raios'])), 1)
    # o que ainda vai pro VTracer: "+" pincelado (2, 3) e a palavra INSS (3)
    keep = np.zeros(al.shape, bool)
    if i in (2, 3):
        keep |= ndi.binary_dilation((rgb[..., 0] > 170) & (rgb[..., 1] > 150) & (rgb[..., 2] < 120) & al, iterations=3)
    if i == 3:
        lb = lg[k]['bbox']; tb = txt[k]['lines'][0]['bbox']
        blue = (rgb[..., 2] > rgb[..., 0] + 60) & al; blue[:, : lb[0] + lb[2] + 5] = False; blue[tb[1] - 5:] = False
        keep |= ndi.binary_dilation(blue, iterations=3)
    if keep.any():
        a = np.asarray(Image.open(f'{S}/caixas/orig/{k}_key.png').convert('RGB')).copy()
        a[~keep] = (255, 0, 255); Image.fromarray(a).save(f'{E}/{k}_detalhes.png')
    print(k, 'cartao', c['bbox'], 'r', c['raio'], 'base escondida' if hidden else '', '| faixa', p['bbox'], 'r', F[k]['faixa']['raio'], p['cor'], 'borda', p['borda_branca'])
json.dump(F, open(f'{E}/formas.json', 'w'), indent=1)
