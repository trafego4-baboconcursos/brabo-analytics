"""Gera os loadings 8 bits dos temas de filme -> frontend/templates/_loading_pixel.html.

Cada sprite é um mapa de caracteres (um caractere = um pixel; '.' = vazio) com uma
paleta. O script junta pixels vizinhos da mesma cor em um <path> por cor e escreve
SVGs com shape-rendering crispEdges. Animação é CSS (layout.css, bloco "8 bits"):

- quadros: <g class="fr frN f{i}"> alternados com steps(1) (--i, --n, --t);
- movimento: classes próprias de cada sprite (bob do DeLorean, aranha descendo,
  varredura do visor...), com translate em unidades do grid.

Uso:  python scripts/gerar_pixel_loading.py          (reescreve o partial)
      python scripts/gerar_pixel_loading.py --check  (só confere se está atualizado)
"""
from __future__ import annotations

import math
import pathlib
import sys

SAIDA = pathlib.Path(__file__).resolve().parents[1] / "frontend" / "templates" / "_loading_pixel.html"


def grade(linhas: list[str]) -> list[str]:
    larg = max(len(l) for l in linhas)
    return [l.ljust(larg, ".") for l in linhas]


def com_contorno(linhas: list[str], cor: str = "k") -> list[str]:
    """Põe um pixel de contorno em volta de tudo que não é vazio (grid cresce 1 de cada lado)."""
    g = grade(linhas)
    h, w = len(g), len(g[0])
    out = [["."] * (w + 2) for _ in range(h + 2)]
    for y in range(h):
        for x in range(w):
            if g[y][x] != ".":
                out[y + 1][x + 1] = g[y][x]
    for y in range(h + 2):
        for x in range(w + 2):
            if out[y][x] != ".":
                continue
            for dy, dx in ((0, 1), (0, -1), (1, 0), (-1, 0)):
                yy, xx = y + dy, x + dx
                if 0 <= yy < h + 2 and 0 <= xx < w + 2 and out[yy][xx] not in (".", cor):
                    out[y][x] = cor
                    break
    return ["".join(r) for r in out]


def paths(linhas: list[str], paleta: dict[str, str], ox: int = 0, oy: int = 0) -> str:
    """Um <path> por cor, juntando pixels contíguos da mesma linha."""
    por_cor: dict[str, list[str]] = {}
    for y, linha in enumerate(linhas):
        x = 0
        while x < len(linha):
            c = linha[x]
            if c == "." or c not in paleta:
                x += 1
                continue
            n = 1
            while x + n < len(linha) and linha[x + n] == c:
                n += 1
            por_cor.setdefault(c, []).append(f"M{x + ox} {y + oy}h{n}v1h-{n}z")
            x += n
    return "".join(f'<path fill="{paleta[c]}" d="{"".join(d)}"/>' for c, d in por_cor.items())


def quadros(lista: list[str], t: str) -> str:
    n = len(lista)
    return "".join(
        f'<g class="fr fr{n} f{i}" style="--i:{i};--n:{n};--t:{t}">{conteudo}</g>'
        for i, conteudo in enumerate(lista)
    )


def svg(tema: str, w: int, h: int, px: int, corpo: str) -> str:
    return (
        f'<svg class="bs-px bs-px-{tema}" viewBox="0 0 {w} {h}" width="{w * px}" height="{h * px}" '
        f'shape-rendering="crispEdges" aria-hidden="true">{corpo}</svg>'
    )


# ── Outatime: DeLorean voando (rodas recolhidas, brilho azul embaixo) ─────────
def delorean() -> str:
    pal = {"K": "#14171c", "S": "#c9ced6", "H": "#eef1f5", "D": "#5a616b", "W": "#6fd3ff",
           "R": "#ff3b3b", "L": "#fff3b0", "F": "#f4f4f4", "B": "#33c9ff", "b": "#9be7ff",
           "O": "#ff7a00", "Y": "#ffd400", "V": "#ffffff"}
    carro = grade([
        "..........KKKKKKKKKKKK..........",
        "..FF.....KDKDKDKDKWWWWK.........",
        ".KFFK...KDKDKDKDKKWWHWWWK.......",
        "KKKKKKKKKKSSSSSSSSSSSSSSKKKKKK..",
        "KDSDSDSDSSHHHHHHHHHHHHHHHHHHSSKK",
        "KRSSSSSSSSSSSKSSSSSSSSSSSSSSSSSL",
        "KDDDDDDDDDDDDKDDDDDDDDDDDDDDDDDK",
        ".KKKDDDDDKKKKKKKKKKKKKDDDDDKKKK.",
    ])
    ox, oy = 10, 3
    glow_a = ["...BBBBBBB...........BBBBBBB....", "....bbbbb.............bbbbb....."]
    glow_b = ["...bbbbbbb...........bbbbbbb....", "....BBBBB.............BBBBB....."]
    fogo_a = ["..OOOY", "OYYYYY", "..OOOY"]
    fogo_b = ["....OY", ".OOOYY", "....OY"]
    f1 = paths(glow_a, pal, ox, oy + 8) + paths(fogo_a, pal, ox - 6, oy + 4)
    f2 = paths(glow_b, pal, ox, oy + 8) + paths(fogo_b, pal, ox - 6, oy + 4)
    # linhas de velocidade: período 8, andam 8 para a esquerda e repetem
    vel = "".join(f"M{x} {y}h3v1h-3z" for y in (1, 13) for x in range(0, 64, 8))
    vel += "".join(f"M{x} {y}h2v1h-2z" for y in (7,) for x in range(4, 64, 8))
    corpo = (
        f'<g class="px-vel"><path fill="#ffffff" opacity=".55" d="{vel}"/></g>'
        f'<g class="px-bob">{quadros([f1, f2], ".24s")}{paths(carro, pal, ox, oy)}</g>'
    )
    return svg("outatime", 44, 15, 6, corpo)


# ── Predador: mira com a tríade de lasers vermelhos ───────────────────────────
def predador() -> str:
    n, c, r = 25, 12, 10.5
    anel_a, anel_b = [], []
    for y in range(n):
        for x in range(n):
            d = math.hypot(x - c, y - c)
            if abs(d - r) < 0.55:
                ang = (math.degrees(math.atan2(y - c, x - c)) + 360) % 360
                (anel_a if int(ang // 30) % 2 == 0 else anel_b).append(f"M{x} {y}h1v1h-1z")
    marcas = "".join(f"M{x} {y}h1v1h-1z" for x, y in
                     [(12, 0), (12, 1), (12, 23), (12, 24), (0, 12), (1, 12), (23, 12), (24, 12)])
    pontos = [(12, 7), (8, 15), (16, 15)]

    def dots(cor: str) -> str:
        return f'<path fill="{cor}" d="{"".join(f"M{x} {y}h2v2h-2z" for x, y in pontos)}"/>'

    f1 = f'<path fill="#ff4500" d="{"".join(anel_a)}"/><path fill="#7a2a08" d="{"".join(anel_b)}"/>' + dots("#ff1a1a")
    f2 = f'<path fill="#7a2a08" d="{"".join(anel_a)}"/><path fill="#ff4500" d="{"".join(anel_b)}"/>' + dots("#6b0a0a")
    corpo = f'<path fill="#ffae00" d="{marcas}"/>{quadros([f1, f2], ".5s")}'
    return svg("predador", n, n, 5, corpo)


# ── Aranha pendurada no fio (Amigão da Vizinhança e Aranhaverso) ──────────────
ARANHA_A = [
    "..L.......L..",
    "...L.....L...",
    "L...L.C.L...L",
    ".L...CCC...L.",
    "..LLCCCCCLL..",
    "....CEECC....",
    "..LLCCCCCLL..",
    ".L..CCCCC..L.",
    "L....CCC....L",
    ".....CCC.....",
    "......C......",
]
ARANHA_B = [
    "L.........L..",
    ".L.......L...",
    "..LL..C.LL..L",
    "....LCCCL..L.",
    "..LLCCCCCLL..",
    "....CEECC....",
    "..LLCCCCCLL..",
    "....CCCCCL...",
    "..LL.CCC..LL.",
    ".L...CCC....L",
    "......C......",
]


def aranha(tema: str, cor: str, perna: str, fantasmas: tuple[str, str] | None = None) -> str:
    w, h, ox = 17, 24, 2
    oy = 8  # a aranha começa no y=8 e desce até 4 unidades
    fio = f'<path fill="{perna}" d="M{ox + 6} -20h1v{oy + 20}h-1z"/>'

    def sprite(mapa: list[str], c: str, l: str, dx: int = 0) -> str:
        pal = {"C": c, "L": l, "E": "#ffffff" if c != "#ffffff" else "#111111"}
        return paths(mapa, pal, ox + dx, oy)

    if fantasmas:
        rosa, ciano = fantasmas
        fa = sprite(ARANHA_A, rosa, rosa, -1) + sprite(ARANHA_A, ciano, ciano, 1) + sprite(ARANHA_A, cor, perna)
        fb = sprite(ARANHA_B, rosa, rosa, -1) + sprite(ARANHA_B, ciano, ciano, 1) + sprite(ARANHA_B, cor, perna)
    else:
        fa, fb = sprite(ARANHA_A, cor, perna), sprite(ARANHA_B, cor, perna)
    corpo = f'<g class="px-desce">{fio}{quadros([fa, fb], ".4s")}</g>'
    return svg(tema, w, h, 5, corpo)


# ── Diretiva Primária: capacete com a varredura vermelha no visor ─────────────
def capacete() -> str:
    pal = {"S": "#c9d4df", "H": "#eef3f8", "D": "#7f8c99", "K": "#0b0f14", "F": "#d9a98a",
           "f": "#b9876a", "M": "#6b3f2e", "k": "#2a3440"}
    mapa = com_contorno([
        ".......SSSSSSSSSS.......",
        ".....SSHHSSSDDSSSSS.....",
        "....SSHHSSSSDDSSSSSS....",
        "...SSHSSSSSSDDSSSSSSS...",
        "...SSSSSSSSSDDSSSSSSS...",
        "..SSSSSSSSSSSSSSSSSSSS..",
        "..SKKKKKKKKKKKKKKKKKKS..",
        "..SKKKKKKKKKKKKKKKKKKS..",
        "..SKKKKKKKKKKKKKKKKKKS..",
        "..SSSSSSSSSSSSSSSSSSSS..",
        "...SDDSFFFFFFFFFFSDDS...",
        "...SDDSFFFFFFFFFFSDDS...",
        "....SDSFFFMMMMFFFSDS....",
        ".....SSfFFFFFFFFfSS.....",
        "......SSfFFFFFFfSS......",
        ".......SSSFFFFSSS.......",
        ".........SSSSSS.........",
    ], "k")
    # visor: colunas 4..21 do mapa com contorno (x+1), linhas 7..9 (y+1)
    scan = '<path fill="#7a1010" d="M4 7h3v1h-3zM4 9h3v1h-3z"/><path fill="#ff3b30" d="M4 8h3v1h-3z"/>'
    corpo = f'{paths(mapa, pal)}<g class="px-scan">{scan}</g>'
    return svg("diretiva", 26, 19, 5, corpo)


# ── Esta Casa É Minha: casa com neve no telhado e pisca-pisca ─────────────────
def casa() -> str:
    pal = {"S": "#4a5a6a", "W": "#eef4fb", "R": "#b23a3a", "B": "#7a2222", "Y": "#ffd23f",
           "y": "#c98a00", "G": "#1e6b45", "O": "#ffd23f", "C": "#5a3a2a", "k": "#2a1d17"}
    base = [
        "................CCC...",
        "................CCC...",
        ".........WW.....CCC...",
        "........WWWW....CCC...",
        ".......WSSSSW...CCC...",
        "......WSSSSSSW..CCC...",
        ".....WSSSSSSSSW.CCC...",
        "....WSSSSSSSSSSWCCC...",
        "...WSSSSSSSSSSSSWCC...",
        "..WSSSSSSSSSSSSSSW....",
        ".WSSSSSSSSSSSSSSSSW...",
        "......................",
        "..BRRRRRRRRRRRRRRRB...",
        "..BRYYYRRRRRRRYYYRB...",
        "..BRYyYRRRRRRRYyYRB...",
        "..BRYYYRRGGGRRYYYRB...",
        "..BRRRRRRGGGRRRRRRB...",
        "..BRRRRRRGOGRRRRRRB...",
        "..BRRRRRRGGGRRRRRRB...",
        ".BBBBBBBBBBBBBBBBBBB..",
    ]
    mapa = com_contorno(base, "k")
    cores = ["#ff3b3b", "#2ecc71", "#ffd23f", "#3fa9ff"]

    def luzes(desl: int) -> str:
        fio = '<path fill="#1e6b45" d="M2 12h20v1h-20z"/>'
        bolas = "".join(
            f'<path fill="{cores[(i + desl) % 4]}" d="M{x} 12h1v2h-1z"/>'
            for i, x in enumerate(range(3, 22, 2))
        )
        return fio + bolas

    corpo = paths(mapa, pal) + quadros([luzes(0), luzes(1)], ".6s")
    return svg("kevin", 24, 22, 5, corpo)


# ── Quemlândia: o coração do Grinch crescendo três tamanhos ──────────────────
CORACOES = [
    [".RR.RR.", "RRRRRRR", "RRRRRRR", ".RRRRR.", "..RRR..", "...R..."],
    ["..RRR.RRR..", ".RRRRRRRRR.", "RRWRRRRRRRR", "RWRRRRRRRRR", "RRRRRRRRRRR",
     ".RRRRRRRRR.", "..RRRRRRR..", "...RRRRR...", "....RRR....", ".....R....."],
    ["..RRRR...RRRR..", ".RRRRRR.RRRRRR.", "RRWWRRRRRRRRRRR", "RWWRRRRRRRRRRRR",
     "RWRRRRRRRRRRRRR", "RRRRRRRRRRRRRRR", ".RRRRRRRRRRRRR.", "..RRRRRRRRRRR..",
     "...RRRRRRRRR...", "....RRRRRRR....", ".....RRRRR.....", "......RRR......",
     ".......R......."],
]


def grinch() -> str:
    pal = {"R": "#e23b3b", "W": "#ffb3b3", "g": "#8cc63f"}
    w, h = 19, 17
    fr = []
    for mapa in CORACOES:
        m = com_contorno(mapa, "g")
        ox = (w - len(m[0])) // 2
        oy = (h - len(m)) // 2
        fr.append(paths(m, pal, ox, oy))
    fr.append(fr[-1])  # segura o tamanho grande um quadro a mais
    return svg("grinch", w, h, 6, quadros(fr, "2.4s"))


def gerar() -> str:
    partes = [
        "{# GERADO por scripts/gerar_pixel_loading.py — não editar à mão. Loadings 8 bits dos",
        "   temas de filme; quem mostra/anima cada um é o bloco \"8 bits\" de layout.css. #}",
        delorean(),
        predador(),
        aranha("spidey", "#d81f26", "#c9d2f0"),
        aranha("aranhaverso", "#ffffff", "#f4f2fa", ("#ff2ec4", "#00e5ff")),
        capacete(),
        casa(),
        grinch(),
    ]
    return "\n".join(partes) + "\n"


def main() -> int:
    novo = gerar()
    if "--check" in sys.argv:
        atual = SAIDA.read_text(encoding="utf-8") if SAIDA.exists() else ""
        if atual != novo:
            print(f"{SAIDA} desatualizado: rode sem --check")
            return 1
        print("ok")
        return 0
    SAIDA.write_text(novo, encoding="utf-8", newline="\n")
    print(f"gravado {SAIDA} ({len(novo)} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
