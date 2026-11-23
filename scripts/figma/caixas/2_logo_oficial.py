# Acha o símbolo do INSS em cada caixa, mede escala/rotação/posição contra o componente vetorial e apaga o símbolo do fundo.
import sys, json, numpy as np
from PIL import Image
from scipy import ndimage as ndi
S = sys.argv[1]; E = S + '/caixas/editavel'
def classes(rgb, al):
    r, g, b = [rgb[..., k].astype(int) for k in range(3)]
    c = np.zeros(rgb.shape[:2], np.uint8)
    c[(g > r + 40) & (g > b) & al] = 1                          # verde
    c[(r > 180) & (g > 110) & (b < 110) & (r > g) & al] = 2     # amarelo
    c[(b > r + 60) & (b > g + 20) & al] = 3                     # azul
    return c
comp = np.asarray(Image.open(f'{S}/caixas/simbolo_inss.png').convert('RGBA'))
cc = classes(comp[..., :3], comp[..., 3] > 128)
txt = json.load(open(f'{E}/textos.json', encoding='utf-8'))
out = {}
for i in range(1, 8):
    a = np.asarray(Image.open(f'{E}/c{i}_limpo.png').convert('RGB'))
    key = (a[..., 0] > 200) & (a[..., 2] > 200) & (a[..., 1] < 80)
    ty0 = txt[f'c{i}']['lines'][0]['bbox'][1]
    c = classes(a, ~key)
    tb = txt[f'c{i}']['lines'][0]['bbox']; c[tb[1] + tb[3]:] = 0   # só acima do fim do título: a ponta do verde desce até ele; faixa e "+" ficam de fora
    lab, n = ndi.label(ndi.binary_closing(c > 0, iterations=6))
    sz = ndi.sum(c > 0, lab, range(1, n + 1))
    if i == 3:   # símbolo à esquerda, palavra "INSS" à direita: fica só o que vai até o fim do amarelo
        yl = np.nonzero((c == 2).any(0))[0].max()
        keep = [k + 1 for k, sl in enumerate(ndi.find_objects(lab)) if sz[k] > 300 and sl[1].start < yl]
    else:
        keep = [int(np.argmax(sz)) + 1]
    sl0 = ndi.find_objects((np.isin(lab, keep)).astype(int))[0]
    y0b, y1b, x0b, x1b = sl0[0].start - 25, sl0[0].stop + 25, sl0[1].start - 25, sl0[1].stop + 25
    keep += [k + 1 for k, sl in enumerate(ndi.find_objects(lab)) if k + 1 not in keep and sl[0].start > y0b and sl[0].stop < y1b and sl[1].start > x0b and sl[1].stop < x1b and (i != 3 or sl[1].start < yl)]  # quadradinhos soltos
    sym = np.isin(lab, keep); c = np.where(sym, c, 0)
    ys, xs = np.nonzero(c); tgt = c[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
    th, tw = tgt.shape; best = None
    for rot in np.arange(-20, 20.5, 0.5):
        rc = np.asarray(Image.fromarray(cc).rotate(rot, Image.NEAREST, expand=True))
        yy, xx = np.nonzero(rc); rc = rc[yy.min():yy.max() + 1, xx.min():xx.max() + 1]
        rr = np.asarray(Image.fromarray(rc).resize((tw, th), Image.NEAREST))
        sc = np.mean([((rr == k) & (tgt == k)).sum() / max(1, ((rr == k) | (tgt == k)).sum()) for k in (1, 2, 3)])
        asp = (rc.shape[1] / rc.shape[0]) / (tw / th)
        if best is None or sc > best[0]: best = (sc, rot, asp, rc.shape)
    sc, rot, asp, rshape = best
    out[f'c{i}'] = dict(bbox=[int(xs.min()), int(ys.min()), int(tw), int(th)], rot=float(rot), iou=round(float(sc), 3), aspecto=round(float(asp), 3))
    # apaga o símbolo: casca do símbolo (com os quadradinhos brancos) vira o branco do cartão/contorno
    hull = ndi.binary_fill_holes(ndi.binary_closing(sym, iterations=12))
    hull = ndi.binary_dilation(hull, iterations=4) & ~key
    ring = ndi.binary_dilation(hull, iterations=10) & ~hull & ~key & (a.min(2) > 200)
    clean = a.copy(); clean[hull] = np.median(a[ring], axis=0).astype(np.uint8)
    Image.fromarray(clean).save(f'{E}/c{i}_semlogo.png')
    print(f'c{i}', out[f'c{i}'])
json.dump(out, open(f'{E}/logos.json', 'w'), indent=1)
