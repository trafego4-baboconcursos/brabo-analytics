"""Recorta poses/objetos de uma folha em grade. Fundo = branco ligado à borda da FOLHA (flood-fill);
cada pedaço desenhado vai para a célula do seu centro (não corta o que atravessa a grade).
Uso: recortar.py folha.png cols rows prefixo escala [itens_com_furo_transparente,...]"""
import sys
import numpy as np
from PIL import Image, ImageFilter
from scipy import ndimage

src, cols, rows, pref, esc = sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), sys.argv[4], float(sys.argv[5])
furos = {int(x) for x in sys.argv[6].split(",")} if len(sys.argv) > 6 else set()
im = Image.open(src).convert("RGB"); W, H = im.size
a = np.asarray(im).astype(np.int16)
branco = a.min(axis=2) >= 232
lab, _ = ndimage.label(branco)
borda = set(np.unique(np.concatenate([lab[0], lab[-1], lab[:, 0], lab[:, -1]]))) - {0}
fundo = np.isin(lab, list(borda))
comp, n = ndimage.label(~fundo)
tam = ndimage.sum(~fundo, comp, range(1, n + 1))
cent = ndimage.center_of_mass(~fundo, comp, range(1, n + 1))
cw, ch = W / cols, H / rows
lum = a.mean(axis=2)
for r in range(rows):
    for c in range(cols):
        idx = r * cols + c + 1
        ids = [i + 1 for i, (cy, cx) in enumerate(cent) if int(cx // cw) == c and int(cy // ch) == r]
        if not ids: continue
        maior = max(tam[i - 1] for i in ids)
        ids = [i for i in ids if tam[i - 1] >= 0.04 * maior]   # tira poeira e pedaços soltos pequenos
        opaco = np.isin(comp, ids)
        if idx in furos:   # branco fechado vira transparente (ex.: buraco da alça da caneca)
            fech = branco & ~fundo & ndimage.binary_dilation(opaco, iterations=2)
            fl, fn = ndimage.label(fech)
            for k in range(1, fn + 1):
                m = fl == k
                if m.sum() < 0.08 * opaco.sum(): opaco &= ~m
        anel = ndimage.binary_dilation(opaco) & ~ndimage.binary_erosion(opaco)
        alfa = np.where(opaco, 255.0, 0.0)
        alfa[anel] = np.clip((255 - lum[anel]) / 55 * 255, 0, 255)
        ys, xs = np.where(alfa > 10)
        y0, y1, x0, x1 = ys.min(), ys.max() + 1, xs.min(), xs.max() + 1
        rgba = np.dstack([a[..., :3].astype(np.uint8), alfa.astype(np.uint8)])[y0:y1, x0:x1]
        out = Image.fromarray(rgba, "RGBA")
        if esc != 1:
            out = out.resize((round(out.width * esc), round(out.height * esc)), Image.LANCZOS)
            rgb = out.convert("RGB").filter(ImageFilter.UnsharpMask(radius=1.6, percent=70, threshold=2))
            out = Image.merge("RGBA", (*rgb.split(), out.getchannel("A")))
        nome = f"{pref}_{idx:02d}.png"; out.save(nome); print(nome, out.size)
