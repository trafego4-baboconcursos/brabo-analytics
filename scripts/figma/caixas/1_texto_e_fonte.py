# Separa o texto de cada caixa, escolhe a fonte mais próxima (disponível no Figma), apaga o texto do PNG e vetoriza o fundo.
import sys, os, re, json, numpy as np, cv2
from PIL import Image, ImageFont, ImageDraw
from scipy import ndimage as ndi
S = sys.argv[1]; D = S + '/caixas/orig'; F = S + '/fonts'; OUT = S + '/caixas/editavel'; os.makedirs(OUT, exist_ok=True)
SO = [int(x) for x in sys.argv[2].split(',')] if len(sys.argv) > 2 else None
BOXES = {
 1: [('CONCURSO PÚBLICO', 'dark'), ('R$ 7.234,00', 'pill')],
 2: [('CONCURSO INSS', 'dark'), ('7.000 VAGAS', 'pill')],
 3: [('CONCURSO PÚBLICO', 'dark'), ('R$ 7.234,00', 'pill')],
 4: [('CONCURSO PÚBLICO', 'dark'), ('+ 40 ANOS', 'pill')],
 5: [('CONCURSO INSS', 'dark'), ('R$ 7.234,00', 'pill')],
 6: [('CONCURSO INSS', 'dark'), ('+40 ANOS', 'dark')],
 7: [('CONCURSO INSS', 'dark'), ('NÍVEL MÉDIO', 'pill')],
 8: [('Você viu isso sobre', 'dark'), ('o INSS?', 'dark')],
}
CANDS = [('ArchivoBlack-Regular', None, 'Archivo Black', 'Regular')]
for f, fam in [('Barlow-Black', 'Barlow'), ('BarlowCondensed-Black', 'Barlow Condensed'), ('BarlowSemiCondensed-Black', 'Barlow Semi Condensed'),
               ('FiraSansCondensed-Black', 'Fira Sans Condensed'), ('SairaCondensed-Black', 'Saira Condensed'), ('EncodeSansCondensed-Black', 'Encode Sans Condensed'),
               ('Poppins-Black', 'Poppins'), ('Kanit-Black', 'Kanit'), ('TitilliumWeb-Black', 'Titillium Web'), ('Lato-Black', 'Lato'), ('BeVietnamPro-Black', 'Be Vietnam Pro')]:
    CANDS.append((f, None, fam, 'Black'))
CANDS += [('Poppins-ExtraBold', None, 'Poppins', 'ExtraBold'), ('LilitaOne-Regular', None, 'Lilita One', 'Regular'), ('Anton-Regular', None, 'Anton', 'Regular')]
for f, fam in [('Archivo', 'Archivo'), ('SofiaSansCondensed', 'Sofia Sans Condensed'), ('SofiaSans', 'Sofia Sans'), ('SofiaSansSemiCondensed', 'Sofia Sans Semi Condensed'), ('SofiaSansExtraCondensed', 'Sofia Sans Extra Condensed'), ('RobotoCondensed', 'Roboto Condensed'), ('WorkSans', 'Work Sans'), ('Rubik', 'Rubik'),
               ('NunitoSans', 'Nunito Sans'), ('Nunito', 'Nunito'), ('Montserrat', 'Montserrat'), ('Exo2', 'Exo 2'), ('SchibstedGrotesk', 'Schibsted Grotesk'),
               ('PublicSans', 'Public Sans'), ('Chivo', 'Chivo'), ('Figtree', 'Figtree'), ('Gabarito', 'Gabarito'), ('Onest', 'Onest'), ('AlbertSans', 'Albert Sans'),
               ('HankenGrotesk', 'Hanken Grotesk'), ('Heebo', 'Heebo'), ('RedHatDisplay', 'Red Hat Display'), ('Epilogue', 'Epilogue'), ('Lexend', 'Lexend'),
               ('Mulish', 'Mulish'), ('Outfit', 'Outfit'), ('Urbanist', 'Urbanist'), ('Raleway', 'Raleway'), ('SourceSans3', 'Source Sans 3'), ('Inter', 'Inter'), ('KumbhSans', 'Kumbh Sans')]:
    CANDS.append((f, {'wght': 900, 'wdth': 100}, fam, 'Black')); CANDS.append((f, {'wght': 800, 'wdth': 100}, fam, 'ExtraBold'))
for w, st in [(62.5, 'ExtraCondensed '), (75, 'Condensed '), (87.5, 'SemiCondensed '), (100, '')]:
    CANDS.append(('NotoSans', {'wght': 900, 'wdth': w}, 'Noto Sans', st + 'Black')); CANDS.append(('NotoSans', {'wght': 800, 'wdth': w}, 'Noto Sans', st + 'ExtraBold'))
for f, fam in [('Manrope', 'Manrope'), ('PlusJakartaSans', 'Plus Jakarta Sans'), ('WixMadeforDisplay', 'Wix Madefor Display'), ('RethinkSans', 'Rethink Sans')]:
    CANDS.append((f, {'wght': 800}, fam, 'ExtraBold'))
_fc = {}
def font(f, ax, size=200):
    k = (f, json.dumps(ax), size)
    if k in _fc: return _fc[k]
    ft = ImageFont.truetype(f'{F}/{f}.ttf', size)
    if ax:
        vals = []
        for a in ft.get_variation_axes():
            n = a['name'] if isinstance(a['name'], str) else a['name'].decode()
            v = ax['wght'] if 'eight' in n else ax.get('wdth', a['default']) if 'idth' in n else a['default']
            vals.append(max(a['minimum'], min(a['maximum'], v)))
        ft.set_variation_by_axes(vals)
    _fc[k] = ft; return ft
def render(f, ax, text, track=0.0):
    ft = font(f, ax); im = Image.new('L', (int(200 * len(text) * 1.3 + 400 + abs(track) * len(text)), 500), 0); d = ImageDraw.Draw(im)
    for i, ch in enumerate(text): d.text((50 + ft.getlength(text[:i]) + i * track, 120), ch, font=ft, fill=255)
    m = np.asarray(im) > 127; ys, xs = np.nonzero(m)
    return m[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
def iou(t, r):
    h, w = t.shape; rr = np.asarray(Image.fromarray(r.astype(np.uint8) * 255).resize((w, h), Image.BILINEAR)) > 127
    return (t & rr).sum() / (t | rr).sum()
def best_font(t, text):
    th, tw = t.shape; res = []
    for f, ax, fam, st in CANDS:
        if not os.path.exists(f'{F}/{f}.ttf'): continue
        try: r = render(f, ax, text)
        except Exception: continue
        s = th / r.shape[0]; gaps = max(1, len(text) - 1)
        track = (tw / s - r.shape[1]) / gaps            # tracking em px numa fonte de 200
        if abs(track) > 50: continue
        r2 = render(f, ax, text, track); te = track / 200
        res.append((iou(t, r2) - 3 * max(0, abs(te) - 0.03), fam, st, te, f, ax))  # espaçamento fora do natural = fonte de largura errada
    res.sort(key=lambda x: -x[0]); return res
rep = json.load(open(f'{OUT}/textos.json', encoding='utf-8')) if SO and os.path.exists(f'{OUT}/textos.json') else {}
for i, lines in BOXES.items():
    if SO and i not in SO: continue
    a = np.asarray(Image.open(f'{D}/c{i}_key.png').convert('RGB')).astype(int); H, W = a.shape[:2]
    lum = a.mean(2); sat = a.max(2) - a.min(2)
    key = (a[..., 0] > 200) & (a[..., 2] > 200) & (a[..., 1] < 80)
    dark = (lum < 95) & (sat < 50) & ~key
    satm = (sat > 70) & ~key
    lab, n = ndi.label(ndi.binary_closing(satm, iterations=3))
    sizes = ndi.sum(satm, lab, range(1, n + 1)); cy = ndi.center_of_mass(satm, lab, range(1, n + 1))
    cand = [k + 1 for k in range(n) if cy[k][0] > H * 0.45]
    pill = ndi.binary_fill_holes(lab == max(cand, key=lambda k: sizes[k - 1])) if cand and i != 8 else np.zeros_like(satm)  # c8 não tem faixa
    pfull = ndi.binary_fill_holes(ndi.binary_closing(pill, structure=np.ones((31, 31)))) & ~key  # fecha os entalhes das letras na borda
    pcore = ndi.binary_erosion(pill, iterations=3)
    white = (lum > 200) & (sat < 45) & pill
    dl, dn = ndi.label(dark, structure=np.ones((3, 3))); comps = []
    for k, sl in enumerate(ndi.find_objects(dl)):
        area = int((dl[sl] == k + 1).sum())
        if area >= 40: comps.append(dict(k=k + 1, y0=sl[0].start, y1=sl[0].stop, x0=sl[1].start, x1=sl[1].stop, area=area))
    med = np.median([c['area'] for c in comps])
    big = sorted([c for c in comps if c['area'] > 0.25 * med], key=lambda c: (c['y0'] + c['y1']) / 2); bands = []
    for c in big:
        m = (c['y0'] + c['y1']) / 2
        if bands and bands[-1]['y0'] < m < bands[-1]['y1']:
            b = bands[-1]; b['c'].append(c); b['y0'] = min(b['y0'], c['y0']); b['y1'] = max(b['y1'], c['y1'])
        else: bands.append(dict(y0=c['y0'], y1=c['y1'], c=[c]))
    bands = [b for b in bands if len(b['c']) >= 2]
    for c in comps:
        if any(c is x for b in bands for x in b['c']): continue
        m = (c['y0'] + c['y1']) / 2
        b = min(bands, key=lambda b: 0 if b['y0'] <= m <= b['y1'] else min(abs(m - b['y0']), abs(m - b['y1'])))
        hb = b['y1'] - b['y0']
        if b['y0'] - hb * 0.7 < m < b['y1'] + hb * 0.3 and min(x['x0'] for x in b['c']) - hb < c['x0'] < max(x['x1'] for x in b['c']) + hb: b['c'].append(c)
    out = []; fills = []; erase = np.zeros((H, W), bool); dbands = iter(bands)
    for text, kind in lines:
        green = None
        if kind == 'dark':
            b = next(dbands); ks = [c['k'] for c in b['c']]
            if i == 8 and text.startswith('o '):
                lh0 = b['y1'] - b['y0']; g = satm & (a[..., 1] > a[..., 0] + 40); g[:max(0, int(b['y0'] - 0.3 * lh0))] = 0; g[int(b['y1'] + 0.3 * lh0):] = 0
                gl, gn = ndi.label(g); gs = ndi.sum(g, gl, range(1, gn + 1)); g = np.isin(gl, np.where(gs > 200)[0] + 1)
                gx1 = np.nonzero(g.any(0))[0].max(); lh = b['y1'] - b['y0']
                ks = [c['k'] for c in b['c'] if c['x0'] < gx1 + 0.55 * lh]; green = g
            m = np.isin(dl, ks) | (green if green is not None else False)
        else:
            wl, wn = ndi.label(white); ws = ndi.sum(white, wl, range(1, wn + 1))
            fora = set(np.unique(wl[white & ~pcore]).tolist())  # toca a borda da faixa = contorno, não letra
            m = np.isin(wl, [k + 1 for k in range(wn) if ws[k] > 60 and (k + 1) not in fora])
        ys, xs = np.nonzero(m); y0, y1, x0, x1 = ys.min(), ys.max() + 1, xs.min(), xs.max() + 1
        core = ndi.binary_erosion(m, iterations=3)
        if green is not None: core &= ~green
        col = np.median(a[core], axis=0) if core.any() else a[m].mean(0)
        res = best_font(m[y0:y1, x0:x1], text); top = res[0]
        info = dict(text=text, bbox=[int(x0), int(y0), int(x1 - x0), int(y1 - y0)], color='#%02X%02X%02X' % tuple(int(v) for v in col),
                    family=top[1], style=top[2], tracking_em=round(top[3], 4), iou=round(top[0], 3),
                    alternativas=[f'{r[1]} {r[2]} ({r[0]:.3f})' for r in res[1:4]])
        if green is not None:
            info['green'] = '#%02X%02X%02X' % tuple(int(v) for v in np.median(a[ndi.binary_erosion(green, iterations=3)], axis=0))
        out.append(info); erase |= m
        if kind == 'pill' or (i == 6 and text.startswith('+')):
            # faixa inteira repintada (o contorno escuro das letras deixava fantasma); protege o "+" pincelado amarelo
            brush = ndi.binary_dilation((a[..., 0] > 170) & (a[..., 1] > 150) & (a[..., 2] < 120), iterations=4) if i != 6 else np.zeros_like(m)
            md = pfull & ~brush
            ring = pcore & ~brush & ~ndi.binary_dilation(m, iterations=14)
        else:
            # cartão: área folgada em volta do texto, longe da borda do recorte, do logo e da faixa
            prot = ndi.binary_dilation(satm & ~(green if green is not None else False), iterations=4) | ndi.binary_dilation(pill, iterations=4)
            interior = ndi.binary_erosion(~key, iterations=14)
            md = ndi.binary_dilation(m, iterations=16) & interior & ~prot
            if i == 8 and text.startswith('o '): md[:, x1 + 3:] = False   # olhinhos 👀
            ring = ndi.binary_dilation(m, iterations=26) & ~ndi.binary_dilation(m, iterations=16) & interior & ~prot
        fills.append((md, np.median(a[ring], axis=0)))
    rep[f'c{i}'] = dict(size=[W, H], lines=out)
    clean = a.astype(np.uint8).copy()
    for md, c in fills: clean[md] = c.astype(np.uint8)
    em = (np.any([md for md, _ in fills], axis=0)).astype(np.uint8) * 255
    clean = np.where(key[..., None], np.array([255, 0, 255], np.uint8), clean)
    Image.fromarray(clean.astype(np.uint8)).save(f'{OUT}/c{i}_limpo.png')
    Image.fromarray(em).save(f'{OUT}/c{i}_mascara.png')
    print(f'c{i}', [(l['text'], l['family'], l['style'], l['iou'], l['alternativas'][0]) for l in out], flush=True)
json.dump(rep, open(f'{OUT}/textos.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
