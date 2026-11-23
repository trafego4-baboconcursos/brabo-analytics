import sys
import numpy as np
import av
from fractions import Fraction
from PIL import Image

vid, base_txt, base_bg, out = sys.argv[1:5]
SLOT = (62, 386, 956, 580)          # x, y, w, h da área da ilustração no card
T_START = 0.08                      # pula o 1º quadro (imagem parada antes do corte)
TEXT_IN = (1.0, 1.5)                # fade do texto
HOLD = 2.0                          # segura o último quadro
FPS = 30

bg = np.asarray(Image.open(base_bg).convert("RGB")).astype(np.float32)
tx = np.asarray(Image.open(base_txt).convert("RGB")).astype(np.float32)
card_bg = bg[5, 5].copy()

src = av.open(vid)
vframes = [(float(f.time), f.to_ndarray(format="rgb24")) for f in src.decode(video=0) if float(f.time) >= T_START - 1e-6]
t0 = vframes[0][0]; vdur = vframes[-1][0] - t0
x, y, w, h = SLOT
SCALE = float(sys.argv[5]) if len(sys.argv) > 5 else 1.0   # largura do vídeo em fração da área (sem borda esfumada)
w2 = int(round(w * SCALE / 2) * 2); x = x + (w - w2) // 2; w = w2
vh = int(round(w * 720 / 1280)); vy = y + (h - vh) // 2
# máscara com borda esfumada (some no creme do card)
F = 0   # sem borda esfumada (pedido do usuário)
yy, xx = np.mgrid[0:vh, 0:w]
edge = np.minimum.reduce([xx, w - 1 - xx, yy, vh - 1 - yy]).astype(np.float32)
mask = np.clip(edge / F, 0, 1)[..., None] ** 1.5 if F > 0 else np.ones((vh, w, 1), np.float32)
# corrige o tom do creme do vídeo para o creme do card
vid_bg = np.median(np.concatenate([vframes[-1][1][0], vframes[-1][1][-1]]), axis=0).astype(np.float32)
gain = card_bg / np.maximum(vid_bg, 1)

total = vdur + HOLD
out_c = av.open(out, "w")
vs = out_c.add_stream("libx264", rate=FPS); vs.width, vs.height, vs.pix_fmt = 1080, 1350, "yuv420p"
vs.options = {"crf": "18", "preset": "medium"}
asrc = src.streams.audio[0] if src.streams.audio else None
as_ = None
if asrc is not None:
    as_ = out_c.add_stream("aac", rate=asrc.rate); as_.layout = asrc.layout.name; as_.time_base = Fraction(1, asrc.rate)
n = int(round(total * FPS))
vi = 0
for i in range(n):
    t = i / FPS
    while vi + 1 < len(vframes) and vframes[vi + 1][0] - t0 <= t: vi += 1
    fr = Image.fromarray(vframes[vi][1]).resize((w, vh), Image.LANCZOS)
    fr = np.clip(np.asarray(fr).astype(np.float32) * gain, 0, 255)
    # troca o "papel" do vídeo (textura + vinheta) pelo creme liso do card; o desenho fica intacto
    dist = np.sqrt(((fr - card_bg) ** 2).sum(axis=2, keepdims=True))
    ink = np.clip((dist - 10) / 26, 0, 1)
    fr = card_bg * (1 - ink) + fr * ink
    k = np.clip((t - TEXT_IN[0]) / (TEXT_IN[1] - TEXT_IN[0]), 0, 1)
    k = k * k * (3 - 2 * k)
    canvas = bg * (1 - k) + tx * k
    reg = canvas[vy:vy + vh, x:x + w]
    canvas[vy:vy + vh, x:x + w] = reg * (1 - mask) + fr * mask
    frame = av.VideoFrame.from_ndarray(canvas.astype(np.uint8), format="rgb24")
    for p in vs.encode(frame): out_c.mux(p)
for p in vs.encode(): out_c.mux(p)
# áudio do Gemini (recodificado em AAC), alinhado ao corte do início
if asrc is not None:
    src2 = av.open(vid); a_in = src2.streams.audio[0]
    res = av.AudioResampler(format="fltp", layout=a_in.layout.name, rate=a_in.rate)
    for af in src2.decode(audio=0):
        if af.time is not None and af.time < T_START: continue
        for r in res.resample(af):
            r.pts = None; r.time_base = Fraction(1, a_in.rate)
            for p in as_.encode(r): out_c.mux(p)
    for p in as_.encode(): out_c.mux(p)
out_c.close()
print("ok", round(total, 2), "s", n, "quadros")
