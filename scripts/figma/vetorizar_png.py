# PNG (com ou sem transparência) -> SVG fiel em camadas de cor, pronto para o upload_assets do Figma.
# Fundo transparente: pré-mistura com magenta (cor-chave), traça com VTracer, apaga os caminhos magenta
# e recorta tudo pela silhueta do alfa (clip-path) — senão o VTracer traça o fundo escondido.
# Uso: python scripts/figma/vetorizar_png.py ENTRADA.png SAIDA.svg [--silhueta ORIGINAL.png] [--corte x0,x1,ytopo]
#   --silhueta: PNG cujo alfa define o recorte (quando ENTRADA já é uma versão editada, ex. sem texto)
#   --corte: tira do recorte tudo acima de ytopo entre x0 e x1 (ex. "lombada" do contorno do logo que vira elipse)
# Exige: pip install vtracer opencv-python-headless (fora do requirements; só para produção de arte)
import sys, re, argparse, numpy as np, cv2, vtracer
from PIL import Image

ap = argparse.ArgumentParser()
ap.add_argument('entrada'); ap.add_argument('saida')
ap.add_argument('--silhueta'); ap.add_argument('--corte')
# preset "fiel": filter_speckle, color_precision, layer_difference, corner_threshold, length_threshold,
# max_iterations, splice_threshold, path_precision. No Python 3.14 o vtracer dá segfault com argumentos
# nomeados — por isso a chamada é toda posicional.
ap.add_argument('--preset', default='4,7,10,60,3.5,10,45,2')
a = ap.parse_args()

def magenta(c):
    c = c.lstrip('#'); r, g, b = int(c[:2], 16), int(c[2:4], 16), int(c[4:], 16)
    return r > 180 and b > 180 and g < 110

im = Image.open(a.entrada).convert('RGBA'); px = np.asarray(im)
al = px[..., 3]; solid = al > 100
k = al[..., None] / 255.0
comp = (px[..., :3] * k + np.array([255, 0, 255]) * (1 - k)).astype(np.uint8)
comp[~solid] = (255, 0, 255)
chave = a.saida[:-4] + '_chave.png'; Image.fromarray(comp).save(chave)

p = [float(x) if '.' in x else int(x) for x in a.preset.split(',')]
vtracer.convert_image_to_svg_py(chave, a.saida, 'color', 'stacked', 'spline', *p)
s = open(a.saida, encoding='utf-8').read()
s = re.sub(r'<path [^>]*fill="(#[0-9A-Fa-f]{6})"[^>]*/>', lambda m: '' if magenta(m.group(1)) else m.group(0), s)

sil = (np.asarray(Image.open(a.silhueta).convert('RGBA'))[..., 3] > 100) if a.silhueta else solid.copy()
if a.corte:
    x0, x1, yt = map(int, a.corte.split(',')); sil[:yt, x0:x1] = False
m = cv2.morphologyEx(sil.astype(np.uint8) * 255, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
cs, _ = cv2.findContours(m, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_NONE)
dd = ''.join('M' + ' L'.join(f'{x} {y}' for x, y in cv2.approxPolyDP(c, 0.8, True).reshape(-1, 2)) + ' Z '
             for c in cs if cv2.contourArea(c) > 30)
defs = f'<defs><clipPath id="silhueta"><path d="{dd}" clip-rule="evenodd" fill-rule="evenodd"/></clipPath></defs><g clip-path="url(#silhueta)">'
s = re.sub(r'(<svg [^>]*>)', lambda mm: mm.group(1) + defs, s, count=1).replace('</svg>', '</g></svg>')
open(a.saida, 'w', encoding='utf-8').write(s)
print(f'{a.saida}: {len(s) / 1024:.0f} KB, {s.count("<path")} formas')
