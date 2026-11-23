import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import av
from fractions import Fraction
import texto_card as tc

src_path, out_path = sys.argv[1], sys.argv[2]
FPS, HOLD = 30, 1.5
T_TITLE, CPS_TITLE = 0.3, 14
T_BODY, CPS_BODY, PAUSE_NL = 1.4, 28, 0.18

def schedule(gl, t0, cps):
    ts, t = [], t0
    for ch, *_ in gl:
        ts.append(t); t += PAUSE_NL if ch == "\n" else 1 / cps
    return ts, t
gt, gb = tc.glyphs(tc.TITLE), tc.glyphs(tc.BODYT)
st, end_t = schedule(gt, T_TITLE, CPS_TITLE)
sb, end_b = schedule(gb, T_BODY, CPS_BODY)
count = lambda ts, t: sum(1 for x in ts if x <= t)

src = av.open(src_path)
frames = [(float(f.time), f.to_image().convert("RGB")) for f in src.decode(video=0)]
vdur = frames[-1][0]; total = vdur + HOLD
out = av.open(out_path, "w")
vs = out.add_stream("libx264", rate=FPS); vs.width, vs.height, vs.pix_fmt = 1080, 1350, "yuv420p"; vs.options = {"crf": "18"}
src_a = av.open(src_path); a_in = src_a.streams.audio[0] if src_a.streams.audio else None
if a_in is not None:
    as_ = out.add_stream("aac", rate=a_in.rate); as_.layout = a_in.layout.name; as_.time_base = Fraction(1, a_in.rate)
vi = 0
for i in range(int(round(total * FPS))):
    t = i / FPS
    while vi + 1 < len(frames) and frames[vi + 1][0] <= t: vi += 1
    im = frames[vi][1].copy()
    nt, nb = count(st, t), count(sb, t)
    typing_title = T_TITLE <= t < end_t
    typing_body = t >= T_BODY and (t < end_b + 1.2)
    blink_on = int(t * 2.5) % 2 == 0
    tc.draw(im, gt, nt, cursor=typing_title)
    tc.draw(im, gb, nb, cursor=(t < end_b and t >= T_BODY) or (end_b <= t < end_b + 1.2 and blink_on))
    for p in vs.encode(av.VideoFrame.from_image(im)): out.mux(p)
for p in vs.encode(): out.mux(p)
if a_in is not None:
    res = av.AudioResampler(format="fltp", layout=a_in.layout.name, rate=a_in.rate)
    for af in src_a.decode(audio=0):
        for r in res.resample(af):
            r.pts = None; r.time_base = Fraction(1, a_in.rate)
            for p in as_.encode(r): out.mux(p)
    for p in as_.encode(): out.mux(p)
out.close()
print(f"ok {total:.2f}s | título termina {end_t:.2f}s | texto termina {end_b:.2f}s")
