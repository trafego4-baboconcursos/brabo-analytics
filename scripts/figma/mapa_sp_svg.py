import json, math, sys
d = json.load(open(sys.argv[1], encoding="utf-8"))
polys = d["features"][0]["geometry"]["coordinates"]
main = max((p[0] for p in polys), key=len)
lat0 = -22.3; k = math.cos(math.radians(lat0))
proj = lambda lon, lat: (lon * k, -lat)
pts = [proj(*p) for p in main]
def dp(points, eps):
    if len(points) < 3: return points
    (x1, y1), (x2, y2) = points[0], points[-1]
    dx, dy = x2 - x1, y2 - y1; L = math.hypot(dx, dy) or 1e-9
    dmax, idx = 0, 0
    for i in range(1, len(points) - 1):
        x0, y0 = points[i]; dd = abs(dy * x0 - dx * y0 + x2 * y1 - y2 * x1) / L
        if dd > dmax: dmax, idx = dd, i
    if dmax > eps: return dp(points[:idx + 1], eps)[:-1] + dp(points[idx:], eps)
    return [points[0], points[-1]]
ring = pts[:-1] if pts[0] == pts[-1] else pts
far = max(range(len(ring)), key=lambda i: (ring[i][0]-ring[0][0])**2 + (ring[i][1]-ring[0][1])**2)
simp = dp(ring[:far + 1], 0.035)[:-1] + dp(ring[far:] + [ring[0]], 0.035)[:-1]
W, H, PAD_T, PAD = 620, 480, 70, 30
xs = [p[0] for p in simp]; ys = [p[1] for p in simp]
minx, maxx, miny, maxy = min(xs), max(xs), min(ys), max(ys)
s = min((W - 2 * PAD) / (maxx - minx), (H - PAD_T - PAD - 40) / (maxy - miny))
ox = (W - (maxx - minx) * s) / 2 - minx * s; oy = PAD_T - miny * s
T = lambda x, y: (round(x * s + ox, 1), round(y * s + oy, 1))
P = [T(*p) for p in simp]
city = {"Araçatuba": (-50.43, -21.21), "Bauru": (-49.06, -22.32), "Campinas": (-47.06, -22.91), "Presidente Prudente": (-51.39, -22.12),
        "Ribeirão Preto": (-47.81, -21.18), "Santos": (-46.33, -23.96), "São José do Rio Preto": (-49.38, -20.82),
        "São José dos Campos": (-45.89, -23.18), "Sorocaba": (-47.46, -23.50)}
cap = T(*proj(-46.63, -23.55))
INK, RED = "#1A1A1A", "#C8302B"
outline = "M" + " L".join(f"{x} {y}" for x, y in P + [P[0]])   # aberto (sem Z) p/ animar o traço
pins = ""
for name, (lon, lat) in city.items():
    x, y = T(*proj(lon, lat))
    if name == "Santos": x += 16; y += 4        # afasta do X da Capital (vizinhas no mapa)
    x, y = round(x, 1), round(y, 1)
    pins += (f'<path d="M{x} {y} C{x-3} {y-8} {x-12} {y-15} {x-12} {y-24} A12 12 0 1 1 {x+12} {y-24} C{x+12} {y-15} {x+3} {y-8} {x} {y} Z" '
             f'stroke="{RED}" stroke-width="5.5" stroke-linejoin="round" fill="none"/><circle cx="{x}" cy="{y-24}" r="4" fill="{RED}"/>')
cx, cy = cap
X = f'<path d="M{cx-10} {cy-10} L{cx+10} {cy+10}" stroke="{INK}" stroke-width="7" stroke-linecap="round"/><path d="M{cx+10} {cy-10} L{cx-10} {cy+10}" stroke="{INK}" stroke-width="7" stroke-linecap="round"/>'
# mar: ondinhas a sudeste da costa
sx, sy = T(*proj(-45.2, -24.35))
waves = "".join(f'<path d="M{sx-60+dx} {sy+dy} q12 -10 24 0 t24 0 t24 0" stroke="{INK}" stroke-width="5" stroke-linecap="round" fill="none"/>' for dx, dy in [(0, 0), (40, 26), (-10, 52)])
svg = (f'<svg width="{W}" height="{H}" viewBox="0 0 {W} {H}" fill="none" xmlns="http://www.w3.org/2000/svg">'
       f'<path d="{outline}" stroke="{INK}" stroke-width="8" stroke-linecap="round" stroke-linejoin="round" fill="none"/>'
       f'{waves}{X}{pins}</svg>')
open(sys.argv[2], "w", encoding="utf-8").write(svg)
print("pontos contorno:", len(P), "| tamanho svg:", len(svg), "| capital:", cap, "| mar:", (sx, sy))
