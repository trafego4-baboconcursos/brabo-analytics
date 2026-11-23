# Desenha título e corpo do card como o Figma (mesmas fontes, tamanhos, entrelinha, posições e cores)
from PIL import Image, ImageDraw, ImageFont
import os
FD = os.path.join(os.path.dirname(__file__), "fonts")
INK, BODY, RED = (26, 26, 26), (34, 34, 34), (200, 48, 43)
def roboto(size, weight):
    f = ImageFont.truetype(os.path.join(FD, "RobotoCondensed.ttf"), size); f.set_variation_by_name(weight); return f
TITLE = dict(x=62, y=210, lh=137.2, font=ImageFont.truetype(os.path.join(FD, "BarlowCondensed-Bold.ttf"), 140),
             runs=[("QUANTO PAGA", INK)])
R, B = roboto(50, "Regular"), roboto(50, "Bold")
BODYT = dict(x=62, y=1016, lh=72, runs=[("Salário inicial de ", BODY, R), ("R$ 6.782,54\n", RED, B),
             ("+ vale-alimentação de R$ 80 por dia\n+ auxílio-saúde e auxílio-transporte\nSomando, ", BODY, R),
             ("passa de R$ 9 mil por mês.", RED, B)])
DY = {"title": 0, "body": 0}   # ajuste fino vertical (calibrado contra a referência do Figma)

def glyphs(block, default_font=None):
    """lista de (char, cor, fonte, x, baseline) na ordem de digitação"""
    out = []; line = 0; x = block["x"]
    for run in block["runs"]:
        text, color = run[0], run[1]; font = run[2] if len(run) > 2 else block["font"]
        asc, desc = font.getmetrics()
        for ch in text:
            if ch == "\n":
                out.append(("\n", color, font, x, None)); line += 1; x = block["x"]; continue
            top = block["y"] + line * block["lh"]
            base = top + (block["lh"] - (asc + desc)) / 2 + asc
            out.append((ch, color, font, x, base))
            x += font.getlength(ch)
    return out

def draw(img, gl, n, dy=0, cursor=False):
    d = ImageDraw.Draw(img); last = None
    for ch, color, font, x, base in gl[:n]:
        if ch == "\n": last = None; continue
        d.text((x, base + dy), ch, font=font, fill=color, anchor="ls"); last = (x + font.getlength(ch), base + dy, font)
    if cursor:
        if n < len(gl) and gl[n][4] is not None and (n == 0 or gl[n-1][0] == "\n"):
            ch, color, font, x, base = gl[n]; last = (x, base + dy, font)
        if last:
            x, base, font = last; asc, desc = font.getmetrics()
            d.rectangle([x + 3, base - asc * 0.78, x + 3 + max(3, font.size // 18), base + desc * 0.25], fill=RED)
