"""Acusa tomada do bruto visível por menos de MIN_S entre as animações (o "flash").

Lê INSERTS de src/Composition.tsx e detecta os cortes de câmera do bruto com o ffmpeg.
Uso: python checar_cortes.py [public/ad358-feed.mp4 | public/ad358-h.mp4]
"""
import re, subprocess, sys

MIN_S = 0.6
FADE_S = 0.2  # fade de saída/entrada do Cutaway (6 quadros)
VIDEO = sys.argv[1] if len(sys.argv) > 1 else "public/ad358-story.mp4"

src = open("src/Composition.tsx", encoding="utf-8").read()
inserts = [(n, float(a), float(b) if b != "DURACAO_S" else 146.4)
           for n, a, b in re.findall(r'nome: "([^"]+)",\s*C: \w+, de: ([\d.]+), ate: ([\d.]+|DURACAO_S)', src)]
inserts.sort(key=lambda x: x[1])

out = subprocess.run(["ffmpeg", "-i", VIDEO, "-vf", "scale=270:-1,select='gt(scene,0.3)',showinfo",
                      "-an", "-f", "null", "-"], capture_output=True, text=True).stderr
cortes = [0.0] + [float(x) for x in re.findall(r"pts_time:([\d.]+)", out)] + [146.4]

def tomada(t):
    """Tomada [c0, c1) do bruto que está no ar no instante t."""
    for c0, c1 in zip(cortes, cortes[1:]):
        if c0 <= t < c1:
            return c0, c1
    return cortes[-2], cortes[-1]

problemas = 0
for n, de, ate in inserts:
    # SAÍDA: o fade começa em ate-FADE e revela a tomada desse instante.
    # Se ela acaba (corte) antes de MIN_S e antes da próxima animação cobrir, é flash.
    t = round(ate - FADE_S, 3)
    c0, c1 = tomada(t)
    prox = min([d for _, d, _ in inserts if d >= ate - 1e-6] + [9e9])
    if c1 < 146.4 and c1 < prox and c1 - t < MIN_S:
        problemas += 1
        print(f"FLASH {c1 - t:.2f}s na saída de '{n}' ({de}-{ate}); corte em {c1:.2f} -> terminar em {c1 + FADE_S:.2f}")
    # ENTRADA: até de+FADE a animação ainda está transparente. Se um corte cai pouco
    # antes disso, a tomada nova aparece só um instante por baixo do fade.
    t = round(de + FADE_S, 3)
    c0, c1 = tomada(t)
    ant = max([a for _, _, a in inserts if a <= de + 1e-6] + [-1])
    if c0 > 0 and c0 > ant and t - c0 < MIN_S:
        problemas += 1
        print(f"FLASH {t - c0:.2f}s na entrada de '{n}' ({de}-{ate}); corte em {c0:.2f} -> começar em {c0 - FADE_S:.2f}")
print(f"{len(inserts)} animações, {len(cortes)-2} cortes, {problemas} flash(es) < {MIN_S}s")
sys.exit(1 if problemas else 0)
