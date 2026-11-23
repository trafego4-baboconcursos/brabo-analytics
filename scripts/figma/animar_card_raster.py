# Anima um card de carrossel que é imagem "chapada": texto digitado letra a letra (pixels originais)
# com cursor vermelho, e desenhos revelados seguindo o traço. Uso:
#   python animar.py ENTRADA.png SAIDA.mp4 [--debug PREVIA.png]
import sys
from collections import deque
import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage as ndi
import av

W, H, FPS = 1080, 1350, 30
RED = np.array([200, 48, 43], np.float32)
CPS_TITLE, CPS_BODY = 14, 32
DRAW_DUR, GAP, TAIL, BLINK = 1.5, 0.25, 3.0, 0.45


def load(path):
    im = Image.open(path).convert("RGB")
    a = np.asarray(im).astype(np.float32)
    border = np.concatenate([a[:4].reshape(-1, 3), a[-4:].reshape(-1, 3), a[:, :4].reshape(-1, 3), a[:, -4:].reshape(-1, 3)])
    bg = np.median(border, axis=0)
    s = min(W / im.width, H / im.height)
    nw, nh = round(im.width * s), round(im.height * s)
    canvas = Image.new("RGB", (W, H), tuple(int(v) for v in bg))
    canvas.paste(im.resize((nw, nh), Image.LANCZOS), ((W - nw) // 2, (H - nh) // 2))
    return np.asarray(canvas).astype(np.float32), bg


def analyze(a, bg):
    dist = np.sqrt(((a - bg) ** 2).sum(axis=2))
    core = dist > 55
    soft = dist > 7
    lab, n = ndi.label(core, structure=np.ones((3, 3)))
    objs = ndi.find_objects(lab)
    areas = ndi.sum(core, lab, range(1, n + 1))
    # cor média por componente (p/ separar foto colorida)
    sat = np.abs(a - a.mean(axis=2, keepdims=True)).sum(axis=2)
    satm = ndi.mean(sat, lab, range(1, n + 1))
    comps = []
    for i, sl in enumerate(objs):
        y0, y1, x0, x1 = sl[0].start, sl[0].stop, sl[1].start, sl[1].stop
        comps.append(dict(id=i + 1, y0=y0, y1=y1, x0=x0, x1=x1, h=y1 - y0, w=x1 - x0, area=areas[i], sat=satm[i]))
    # fundo estimado (sem tinta) p/ "apagar" o que ainda não apareceu
    near = ndi.binary_dilation(soft, iterations=6)
    far = ~ndi.binary_dilation(soft, iterations=12)     # longe do halo do JPEG
    border = np.concatenate([a[:6].reshape(-1, 3), a[-6:].reshape(-1, 3), a[:, :6].reshape(-1, 3), a[:, -6:].reshape(-1, 3)])
    if np.abs(border - bg).sum(axis=1).mean() < 6:      # fundo liso: apaga com a cor exata
        bgimg = np.where(near[..., None], bg, a)
    else:                                               # papel/gradiente: estima o fundo local
        wgt = ndi.uniform_filter(far.astype(np.float32), 81)
        bgimg = np.stack([ndi.uniform_filter(a[..., c] * far, 81) for c in range(3)], -1) / np.maximum(wgt[..., None], 1e-3)
        bgimg = np.where(wgt[..., None] > 0.02, bgimg, bg)
        bgimg = np.where(near[..., None], bgimg, a)
    # classificação: desenho = componentes grandes/irregulares + o que estiver dentro da área deles
    for c in comps: c["fill"] = c["area"] / max(1, c["h"] * c["w"])
    # título pesado com letras coladas: bloco largo mas "cheio" (desenho de traço é quase vazio)
    big = [c for c in comps if (c["h"] > 135 or c["w"] > 320) and not (c["h"] <= 175 and c["fill"] >= 0.22)]
    photo = [c for c in big if c["fill"] > 0.3 and (c["area"] > 0.12 * W * H or (c["sat"] > 60 and c["area"] > 20000))]
    # avatar redondo no topo (cabeçalho de perfil) também é "foto"
    for c in comps:
        if c not in photo and 60 < c["w"] < 260 and abs(c["w"] - c["h"]) < 0.15 * c["w"] and c["x0"] < 160 and c["y0"] < 220 and c["fill"] > 0.6:
            photo.append(c)
            if c not in big: big.append(c)
    # letra grande (ex.: "$" do título) alinhada com uma linha de texto volta a ser texto
    inside_big = np.zeros(core.shape, bool)
    for c in big: inside_big[c["y0"]:c["y1"], c["x0"]:c["x1"]] = True
    small_mask = np.zeros(core.shape, bool)
    for c in comps:
        if c in big or c["h"] < 12: continue
        cy, cx = (c["y0"] + c["y1"]) // 2, (c["x0"] + c["x1"]) // 2
        if not inside_big[cy, cx]: small_mask[c["y0"]:c["y1"], c["x0"]:c["x1"]] |= core[c["y0"]:c["y1"], c["x0"]:c["x1"]]
    tb = bands(small_mask)
    keep = []
    for c in big:
        if c in photo: keep.append(c); continue
        aligned = any(min(c["y1"], b1) - max(c["y0"], b0) >= 0.6 * c["h"] and c["h"] <= 1.6 * (b1 - b0) and c["w"] < 400
                      for b0, b1 in tb)
        if not aligned: keep.append(c)
    big = keep
    draw_mask = np.zeros(core.shape, bool)
    for c in big:
        if c in photo: continue
        sl = (slice(c["y0"], c["y1"]), slice(c["x0"], c["x1"]))
        comp = lab[sl] == c["id"]
        region = ndi.binary_dilation(comp, iterations=18)
        if c["w"] <= 450:   # caixa/moldura grande não "engole" o texto de dentro
            region |= ndi.binary_fill_holes(comp)
        sub = draw_mask[sl]; sub |= region
    # cabeçalho de perfil: tudo acima do fim do avatar fica fixo desde o início
    header_y = 0
    for c in photo:
        if c["y0"] < 220 and c["x0"] < 160 and c["w"] < 260: header_y = max(header_y, c["y1"] + 8)
    photo_mask = np.zeros(core.shape, bool)
    for c in photo: photo_mask[c["y0"]:c["y1"], c["x0"]:c["x1"]] = True
    if header_y: photo_mask[:header_y, :] = True        # avatar + nome + @ aparecem já no 1º quadro
    # "@perfil" pequeno no topo (sem avatar) também fica fixo
    for b0, b1 in bands((dist > 25)[:110]):
        if b1 < 100 and b1 - b0 < 34: photo_mask[max(0, b0 - 4):b1 + 4, :] = True
    is_draw = np.zeros(n + 1, bool); is_photo = np.zeros(n + 1, bool)
    for c in comps:
        cy, cx = (c["y0"] + c["y1"]) // 2, (c["x0"] + c["x1"]) // 2
        if photo_mask[cy, cx]: is_photo[c["id"]] = True
        elif draw_mask[cy, cx] or c in big: is_draw[c["id"]] = True
    text_core = core & ~is_draw[lab] & ~is_photo[lab]
    draw_core = core & is_draw[lab]
    return dict(dist=dist, core=core, soft=soft, lab=lab, comps=comps, bgimg=bgimg, text=text_core,
                draw=draw_core, photo=photo_mask, n=n)


def bands(mask, min_gap=3):
    prof = mask.sum(axis=1) > 0
    out, y = [], 0
    while y < len(prof):
        if prof[y]:
            s = y
            while y < len(prof) and prof[y]: y += 1
            out.append([s, y])
        else:
            y += 1
    # junta faixas finas (acentos, pingos) com a de baixo; e faixas muito próximas
    merged = []
    for b in out:
        if merged and (b[0] - merged[-1][1] < min_gap): merged[-1][1] = b[1]; continue
        merged.append(b)
    final = []
    i = 0
    while i < len(merged):
        b = merged[i]
        if i + 1 < len(merged):
            nxt = merged[i + 1]
            if (b[1] - b[0]) < 0.45 * (nxt[1] - nxt[0]) and nxt[0] - b[1] < 0.5 * (nxt[1] - nxt[0]):
                final.append([b[0], nxt[1]]); i += 2; continue
        final.append(b); i += 1
    return final


def glyph_steps(mask, y0, y1):
    """segmentos de coluna (≈ letras) da linha, com espaços maiores marcando palavra"""
    col = mask[y0:y1].sum(axis=0) > 0
    segs, x = [], 0
    while x < len(col):
        if col[x]:
            s = x
            while x < len(col) and col[x]: x += 1
            segs.append([s, x])
        else:
            x += 1
    h = y1 - y0
    # quebra a linha em pedaços se houver um vão enorme (texto em colunas/ícone ao lado)
    pieces, cur = [], []
    for sg in segs:
        if cur and sg[0] - cur[-1][1] > 2.5 * h: pieces.append(cur); cur = []
        cur.append(sg)
    if cur: pieces.append(cur)
    return pieces


def build_timeline(info):
    tmap = np.full(info["core"].shape, np.inf, np.float32)
    events = []   # elementos em ordem vertical: ("text", y0, ...) / ("draw", y0, mask)
    text = info["text"]
    for y0, y1 in bands(text):
        for piece in glyph_steps(text, y0, y1):
            events.append(("text", y0, y1, piece))
    # desenho: agrupa em blocos por proximidade vertical
    dl, dn = ndi.label(ndi.binary_dilation(info["draw"], iterations=18))
    for sl in ndi.find_objects(dl):
        if sl is None: continue
        m = np.zeros_like(info["draw"]); m[sl] = info["draw"][sl] & (dl[sl] > 0)
        if m.sum() < 400: continue
        events.append(("draw", sl[0].start, sl[0].stop, m))
    events.sort(key=lambda e: (e[1], e[3][0][0] if e[0] == "text" else 0))
    t = 0.3
    cursor = []          # (t_ini, t_fim, x, y0, y1) posições do cursor por passo
    last_text = None
    for e in events:
        if e[0] == "text":
            _, y0, y1, piece = e
            h = y1 - y0
            cps = CPS_TITLE if h > 70 else CPS_BODY
            dt = 1 / cps
            for k, (sx, ex) in enumerate(piece):
                if k and sx - piece[k - 1][1] > 0.22 * h: t += dt   # espaço entre palavras
                seg = text[y0:y1, sx:ex]
                sub = tmap[y0:y1, sx:ex]
                sub[seg] = np.minimum(sub[seg], t)
                cursor.append((t, ex, y0, y1))
                t += dt
            last_text = (t, piece[-1][1], y0, y1)
            t += 0.12
        else:
            _, y0, y1, m = e
            t += GAP
            order_draw(m, tmap, t, DRAW_DUR)
            t += DRAW_DUR + GAP
    # pixels de antisserrilhado/contorno herdam o tempo do pixel de tinta mais próximo
    known = np.isfinite(tmap)
    if known.any():
        idx = ndi.distance_transform_edt(~known, return_distances=False, return_indices=True)
        near_t = tmap[idx[0], idx[1]]
        tmap = np.where(info["soft"] & ~info["photo"], near_t, tmap)
    tmap[info["photo"]] = 0.0
    return tmap, cursor, t


def order_draw(m, tmap, t0, dur):
    """revela o desenho seguindo o traço: BFS a partir do ponto mais à esquerda de cada pedaço"""
    lab, n = ndi.label(m, structure=np.ones((3, 3)))
    objs = ndi.find_objects(lab)
    order = sorted(range(n), key=lambda i: (objs[i][1].start, objs[i][0].start))
    sizes = ndi.sum(m, lab, range(1, n + 1))
    total = sizes.sum()
    acc = 0
    for i in order:
        sl = objs[i]; comp = lab[sl] == i + 1
        ys, xs = np.nonzero(comp)
        start = np.argmin(xs * 10000 + ys)
        seen = np.full(comp.shape, -1, np.int32)
        q = deque([(ys[start], xs[start])]); seen[ys[start], xs[start]] = 0
        hh, ww = comp.shape; step = 0; ordered = []
        while q:
            y, x = q.popleft(); ordered.append((y, x))
            for dy in (-1, 0, 1):
                for dx in (-1, 0, 1):
                    ny, nx = y + dy, x + dx
                    if 0 <= ny < hh and 0 <= nx < ww and comp[ny, nx] and seen[ny, nx] < 0:
                        seen[ny, nx] = 0; q.append((ny, nx))
            # componente desconexo dentro da caixa: recomeça do próximo não visto
            if not q and len(ordered) < len(ys):
                rest = np.argwhere(comp & (seen < 0))
                if len(rest): y2, x2 = rest[0]; seen[y2, x2] = 0; q.append((y2, x2))
        k = len(ordered)
        a0, a1 = t0 + dur * acc / total, t0 + dur * (acc + k) / total
        for j, (y, x) in enumerate(ordered):
            tmap[sl[0].start + y, sl[1].start + x] = a0 + (a1 - a0) * j / max(1, k - 1)
        acc += k


def render(a, info, tmap, cursor, t_end, out):
    total = t_end + TAIL
    c = av.open(out, "w")
    vs = c.add_stream("libx264", rate=FPS); vs.width, vs.height, vs.pix_fmt = W, H, "yuv420p"; vs.options = {"crf": "18"}
    bgimg = info["bgimg"]
    ci = 0
    for i in range(int(round(total * FPS))):
        t = i / FPS
        vis = (tmap <= t)[..., None]
        frame = np.where(vis, a, bgimg)
        # cursor: depois do último passo já digitado
        while ci + 1 < len(cursor) and cursor[ci + 1][0] <= t: ci += 1
        if cursor and cursor[0][0] <= t:
            tc, x, y0, y1 = cursor[ci]
            typing = ci + 1 < len(cursor) and cursor[ci + 1][0] - tc < 0.5
            done = ci == len(cursor) - 1
            show = (not done and t - tc < 0.6) or (done and int((t - tc) / BLINK) % 2 == 0)
            if show:
                h = y1 - y0; w = max(3, h // 14)
                frame[y0 + h // 10:y1 - h // 20, x + 4:x + 4 + w] = RED
        for p in vs.encode(av.VideoFrame.from_ndarray(frame.astype(np.uint8), format="rgb24")): c.mux(p)
    for p in vs.encode(): c.mux(p)
    c.close()
    return total


if __name__ == "__main__":
    src, out = sys.argv[1], sys.argv[2]
    a, bg = load(src)
    info = analyze(a, bg)
    tmap, cursor, t_end = build_timeline(info)
    if "--debug" in sys.argv:
        dbg = a.copy().astype(np.uint8)
        im = Image.fromarray(dbg); d = ImageDraw.Draw(im)
        tm = info["text"]; dm = info["draw"]
        ov = np.asarray(im).copy(); ov[tm] = [0, 160, 255]; ov[dm] = [255, 120, 0]
        Image.fromarray(ov).resize((540, 675)).save(sys.argv[sys.argv.index("--debug") + 1])
    total = render(a, info, tmap, cursor, t_end, out)
    print(f"ok {total:.1f}s  passos de texto={len(cursor)}  fim da animação={t_end:.1f}s")
