"""Receitas das peças NATIVAS do storyboard no Figma (regra do usuário, 11/11/26):
texto, caixa, selo, carimbo, botão, folha, cartão, itens, medalhas e gráficos viram camadas
editáveis; só ilustração, vídeo e fundo ficam como imagem (IMAGEM).

`receita(cena, peca)` devolve a árvore que scripts/figma/storyboard_video.js desenha:
  frame  {t, nome, auto: "H"|"V"|None, pad [t,r,b,l], gap, alinhar, raio, fill, opac, borda
          {cor, peso, lados}, sombra {y, blur, a}, w, h, rot, filhos, ancora, filhas, pv, cores}
  texto  {t, caminho (prop editável) ou None, texto, familia, estilo, tamanho, cor, ls, lh,
          largura (fixa → quebra linha), alinhar, maiusc, destaque {inicio, fim, cor}, realce}
  vetor  {t, nome, path (SVG d), traco {cor, peso, tracejado}, fill, bx, by}
Medidas já no palco (vídeo × k). Os números são os mesmos de modelo/src/cenas/*.tsx — mudou
lá, muda aqui (o teste de catálogo pega texto apontando para prop errada).

`ancora`: de que lado a peça cresce quando o texto muda (esq = left fixo no vídeo; centro =
centralizada; dir = right fixo). `pv`: onde a peça foi posta, em px do vídeo (a volta compara
contra isso). `filhas`: frame que recebe peças filhas (folha, cartão).
"""
from __future__ import annotations

import json
import re
from pathlib import Path

IMAGEM = object()   # peça que fica como imagem (ilustração, faixa)
_TOKENS = Path(__file__).resolve().parent / "modelo" / "src" / "tokens.json"
_COR = json.loads(_TOKENS.read_text(encoding="utf-8"))["cor"]
HIGHLIGHT = "#D4FF50CC"
TILT = {"Manchete": -3, "Carimbo": 3, "PapelMesa": -2}   # Sheet: tilt → fica em tilt/3


def _num(v, k):
    return round(v * k, 2)


def _t(texto, familia, estilo, tamanho, cor, k, caminho=None, ls=0.0, lh=None, largura=None,
       alinhar="LEFT", maiusc=False, **extra):
    no = {"t": "texto", "caminho": caminho, "texto": texto, "familia": familia, "estilo": estilo,
          "tamanho": _num(tamanho, k), "cor": cor, "ls": _num(ls, k), "lh": lh,
          "largura": largura, "alinhar": alinhar, "maiusc": maiusc}
    no.update(extra)
    return no


def _f(nome, filhos, *, auto="V", pad=(0, 0, 0, 0), gap=0, alinhar="MIN", raio=0, fill=None, opac=1.0,
       borda=None, sombra=None, w=None, h=None, rot=0.0, ancora="esq", filhas=False, cores=None, k=0.5):
    return {"t": "frame", "nome": nome, "auto": auto, "pad": [_num(p, k) for p in pad], "gap": _num(gap, k),
            "alinhar": alinhar, "raio": _num(raio, k) if raio < 999 else 999, "fill": fill, "opac": opac,
            "borda": borda and {**borda, "peso": _num(borda["peso"], k)},
            "sombra": sombra and {"y": _num(sombra[0], k), "blur": _num(sombra[1], k), "a": sombra[2]},
            "w": w, "h": h, "rot": rot, "ancora": ancora, "filhas": filhas, "cores": cores, "filhos": filhos}


def _path_figma(d: str, k: float) -> str:
    """SVG d absoluto (M/L/C/S/Z) → só M/L/C/Z sem vírgula (o que o vectorPaths do Figma aceita),
    escalado por k. S (curva suave) vira C com o 1º controle refletido do anterior."""
    toks = re.findall(r"[A-Za-z]|-?\d+(?:\.\d+)?", d)
    f = lambda v: f"{v * k:g}"  # noqa: E731
    out, i, cmd, pos, ctrl = [], 0, None, (0.0, 0.0), None
    while i < len(toks):
        if toks[i].isalpha():
            cmd = toks[i]
            i += 1
            if cmd in "Zz":
                out.append("Z")
                continue
        n = {"M": 2, "L": 2, "C": 6, "S": 4}[cmd]
        v = [float(x) for x in toks[i:i + n]]
        i += n
        if cmd == "S":
            c1 = (2 * pos[0] - ctrl[0], 2 * pos[1] - ctrl[1]) if ctrl else pos
            v = [*c1, *v]
            cmd_out = "C"
        else:
            cmd_out = cmd
        out.append(cmd_out + " " + " ".join(f(x) for x in v))
        pos = (v[-2], v[-1])
        ctrl = (v[-4], v[-3]) if cmd_out == "C" else None
        if cmd == "M":
            cmd = "L"          # pares depois do M são L
    return " ".join(out)


def _vet(nome, pts_ou_path, k, traco=None, fill=None):
    d = pts_ou_path if isinstance(pts_ou_path, str) else " ".join(
        f"{'M' if i == 0 else 'L'} {x} {y}" for i, (x, y) in enumerate(pts_ou_path))
    d = _path_figma(d, k)
    nums = [float(n) for n in re.findall(r"-?\d+(?:\.\d+)?", d)]
    return {"t": "vetor", "nome": nome, "path": d, "bx": min(nums[0::2]), "by": min(nums[1::2]),
            "traco": traco and {**traco, "peso": _num(traco["peso"], k)}, "fill": fill}


def _partir(texto, alvo):
    i = texto.find(alvo)
    return (i, i + len(alvo)) if i >= 0 else None


def _destaque(texto, alvo, cor):
    r = _partir(texto, alvo)
    return {"inicio": r[0], "fim": r[1], "cor": cor} if r else None


def receita(cena: dict, peca: dict, formato: str = "story", k: float = 0.5):
    """Árvore da peça nativa (dict), IMAGEM, ou None (sem receita para esse formato → imagem)."""
    if formato != "story":
        return None
    comp, pid, p = cena["componente"], peca["id"], cena["props"]
    caixa = peca.get("caixa") or [peca["x"], peca["y"], peca["w"], peca["h"]]
    W = _num(caixa[2], k)
    aj = cena.get("ajustes", {}).get(formato, {}).get(pid, {})
    e = aj.get("escala", 1)
    rot_aj = -aj.get("rot", 0)           # CSS horário → Figma anti-horário
    s = k * e                             # medida do código × s = palco
    centro_caixa = peca.get("origem") or [caixa[0] + caixa[2] / 2, caixa[1] + caixa[3] / 2]
    centro_visivel = [peca["x"] + peca["w"] / 2, peca["y"] + peca["h"] / 2]
    r = _montar(comp, pid, p, s, W, rot_aj, _num(caixa[3], k))
    if r is None or r is IMAGEM:
        return r
    # peça de largura fixa é posta pela caixa; a que abraça o conteúdo, pelo que se vê
    r["pv"] = centro_caixa if r["w"] is not None else centro_visivel
    return r


def _montar(comp, pid, p, s, W, rot_aj, Hc):
    C = _COR
    if pid in ("imagem", "faixa"):
        return IMAGEM
    m = re.fullmatch(r"(etiquetas|itens)\[(\d+)\]", pid)

    if comp == "Desenho" and m:
        i = int(m.group(2))
        et = p["etiquetas"][i]
        return _f(pid, [_t(et["texto"], "Inter", "Extra Bold", 54, et.get("corTexto", C["paper"]), s,
                           caminho=f"etiquetas[{i}].texto")],
                  auto="H", pad=(14, 30, 14, 30), raio=14, fill=et.get("cor", C["ink"]), sombra=(14, 30, 0.3),
                  rot=-et.get("rot", 0) + rot_aj, k=s,
                  cores={"fill": f"etiquetas[{i}].cor", "texto": f"etiquetas[{i}].corTexto"})

    if pid == "folha":
        filhos = []
        if comp == "PapelMesa":
            filhos.append(_f("· fita", [], auto=None, fill="#EBE1C8BF", w=170 * s, h=52 * s, rot=4, k=s))
        return _f("Folha de papel", filhos, auto=None, fill=C["paper"], sombra=(40, 80, 0.55), w=W,
                  h=Hc, rot=-TILT[comp] / 3 + rot_aj, filhas=True, k=s)
    if pid == "cartao":
        return _f("Cartão", [], auto=None, fill=C["card"], borda={"cor": C["line"], "peso": 2, "lados": "todos"},
                  raio=40, w=W, h=Hc, rot=rot_aj, filhas=True, k=s)

    if pid == "kicker":
        txt = p["kicker"]
        if comp in ("Manchete", "Carimbo", "PapelMesa"):       # Kicker do papel: linha embaixo
            return _f("kicker", [_t(txt, "JetBrains Mono", "Regular", 26, "#6B655C", s, caminho="kicker",
                                    ls=3, largura=W, maiusc=True)],
                      pad=(0, 0, 18, 0), borda={"cor": "#1A1A1A", "peso": 2, "lados": "baixo"}, w=W, rot=rot_aj, k=s)
        cor = {"Cartao": C["coral"], "Rota": "#C9C4BC"}.get(comp, C["muted"])
        return _f("kicker", [_t(txt, "JetBrains Mono", "Regular", 26, cor, s, caminho="kicker", ls=3, largura=W)],
                  w=W, rot=rot_aj, k=s)

    if pid in ("titulo", "pergunta"):
        txt = p[pid]
        if comp == "Rota":
            d = p["tituloDestaque"]["texto"]
            r = _partir(txt, d)
            return _f("titulo", [_t(txt, "Inter", "Extra Bold", 84, C["text"], s, caminho="titulo", lh=1.05, largura=W,
                                    realce=[{"inicio": r[0], "fim": r[1], "cor": C["coral"]}] if r else [])],
                      w=W, rot=rot_aj, k=s)
        estilo = {
            "Manchete": ("Source Serif Pro", "Bold", 104, 1.02, C["ink"], 0),
            "Carimbo": ("Source Serif Pro", "Bold", 96, 1.05, C["ink"], 0),
            "PapelMesa": ("Source Serif Pro", "Bold", 64, 1.1, C["ink"], 0),
            "Checklist": ("Inter", "Extra Bold", 84, 1.05, C["text"], 0),
            "Cartao": ("Inter", "Extra Bold", 150, 1.0, C["text"], -5),
            "Splash": ("Inter", "Extra Bold", 120, 1.0, C["text"], -3),
        }[comp]
        fam, est, tam, lh, cor, ls = estilo
        return _f(pid, [_t(txt, fam, est, tam, cor, s, caminho=pid, lh=lh, ls=ls, largura=W,
                           alinhar="CENTER" if comp == "Splash" else "LEFT")], w=W, rot=rot_aj, k=s)

    if pid == "corpo":
        txt = p["corpo"]
        return _f("corpo", [_t(txt, "Source Serif Pro", "Regular", 48, C["ink"], s, caminho="corpo", lh=1.35, largura=W,
                               destaque=_destaque(txt, p["destaque"]["texto"], HIGHLIGHT))], w=W, rot=rot_aj, k=s)

    if pid == "subtitulo":
        if comp == "Cartao":
            return _f("subtitulo", [_t(p["subtitulo"]["texto"], "Inter", "Regular", 46, C["muted"], s,
                                       caminho="subtitulo.texto", largura=W)], w=W, rot=rot_aj, k=s)
        return _f("subtitulo", [_t(p["subtitulo"], "Inter", "Semi Bold", 48, C["text"], s, caminho="subtitulo",
                                   largura=W, alinhar="CENTER")], w=W, rot=rot_aj, ancora="centro", k=s)

    if pid == "mao":
        tam = 64
        return _f("mao", [_t(p["mao"]["texto"], "Caveat", "Bold", tam, C["marker"], s, caminho="mao.texto")],
                  rot=rot_aj, ancora="dir" if comp == "PapelMesa" else "esq", k=s)

    if pid == "carimbo":
        cartao = comp == "Cartao"
        cor = C["lime"] if cartao else C["marker"]
        return _f("carimbo", [_t(p["carimbo"]["texto"], "Anton", "Regular", 96 if cartao else 92, cor, s,
                                 caminho="carimbo.texto", ls=4)],
                  auto="H", pad=(4, 30, 4, 30), raio=14, borda={"cor": cor, "peso": 8, "lados": "todos"},
                  opac=1.0 if cartao else 0.92, rot=(12 if cartao else 8) + rot_aj, k=s)

    if pid == "selo":
        if comp == "Grafico":
            tam = round(44 * min(1, 32 / len(p["selo"])))
            return _f("selo", [_t(p["selo"], "Inter", "Semi Bold", tam, C["coral"], s, caminho="selo")],
                      auto="H", pad=(18, 34, 18, 34), raio=999, borda={"cor": C["coral"], "peso": 3, "lados": "todos"},
                      rot=rot_aj, ancora="centro", k=s)
        return _f("selo", [_t(p["selo"]["texto"], "Inter", "Extra Bold", 52, C["text"], s, caminho="selo.texto")],
                  auto="H", pad=(20, 34, 20, 34), raio=999, fill=C["card"], borda={"cor": C["line"], "peso": 2, "lados": "todos"},
                  sombra=(16, 40, 0.5), rot=rot_aj, k=s)

    if pid == "rotuloCume":
        return _f("rotuloCume", [_t(p["rotuloCume"], "Inter", "Extra Bold", 54, "#FFFFFF", s, caminho="rotuloCume")],
                  auto="H", pad=(16, 30, 16, 30), raio=999, fill=C["coral"], sombra=(14, 34, 0.35), rot=rot_aj, k=s)

    if pid == "rotuloFim":
        return _f("rotuloFim", [
            _t(p["rotuloFim"]["valor"], "Inter", "Extra Bold", 76, C["green"], s, caminho="rotuloFim.valor", alinhar="RIGHT"),
            _t(p["rotuloFim"]["sub"], "JetBrains Mono", "Regular", 24, C["muted"], s, caminho="rotuloFim.sub", alinhar="RIGHT"),
        ], alinhar="MAX", rot=rot_aj, ancora="dir", k=s)

    if pid == "numero" and comp == "Grafico":
        valor = f"{p['valorFinal']:,}".replace(",", ".")
        return _f("numero", [
            _t(p["prefixo"], "Inter", "Extra Bold", 96, C["text"], s, caminho="prefixo"),
            _t(valor, "Inter", "Extra Bold", 190, C["text"], s, caminho="valorFinal", ls=-6, lh=1.1),
        ], auto="H", gap=10, rot=rot_aj, k=s)
    if pid == "numero" and comp == "Contador":
        return _f("numero", [
            _t(str(p["numero"]), "Inter", "Extra Bold", 380, C["text"], s, caminho="numero", ls=-14, lh=1.0),
            _t(p["rotulo"], "Inter", "Extra Bold", 72, C["text"], s, caminho="rotulo", lh=1.05),
        ], auto="H", gap=30, alinhar="MAX", rot=rot_aj, k=s)

    if pid == "medalhas":
        md = p["medalhas"]
        bolas = [_f("· medalha", [_t(md["marca"], "Inter", "Extra Bold", 150 * 0.43, C["ink"], s,
                                     caminho="medalhas.marca" if i == 0 else None)],
                    auto="H", alinhar="CENTER", raio=999, fill="#E9B949", w=150 * s, h=150 * s, k=s)
                 for i in range(md["quantidade"])]
        return _f("medalhas", bolas + [_t(md["texto"], "Inter", "Extra Bold", 64, C["text"], s, caminho="medalhas.texto")],
                  auto="H", gap=26, alinhar="CENTER", rot=rot_aj, k=s)

    if comp == "Checklist" and m:
        i = int(m.group(2))
        ultimo = p.get("destacarUltimo") and i == len(p["itens"]) - 1
        fundo = C["coral"] if ultimo else C["card"]
        check = _f("· check", [_t("✓", "Inter", "Extra Bold", 36, C["coral"] if ultimo else C["ink"], s)],
                   auto="H", alinhar="CENTER", raio=999, fill="#FFFFFF" if ultimo else C["lime"], w=60 * s, h=60 * s, k=s)
        return _f(pid, [check, _t(p["itens"][i]["texto"], "Inter", "Extra Bold" if ultimo else "Semi Bold", 48,
                                  C["text"], s, caminho=f"itens[{i}].texto")],
                  auto="H", pad=(30, 34, 30, 34), gap=30, alinhar="CENTER", raio=26, fill=fundo,
                  borda={"cor": C["coral"] if ultimo else C["line"], "peso": 2, "lados": "todos"}, w=W, rot=rot_aj, k=s)

    if pid == "grafico" and comp == "Grafico":
        Wg, H = 880, 440
        pts = p["pontos"]
        mn, mx = p.get("escala") or [min(pts) * 0.9, max(pts) * 1.25]
        linha = [((i / (len(pts) - 1)) * Wg, H - ((v - mn) / (mx - mn)) * H) for i, v in enumerate(pts)]
        filhos = [_vet(f"Grade {i + 1}", [(0, i / 3 * H), (Wg, i / 3 * H)], s,
                       traco={"cor": "#F2EFE952", "peso": 2, "tracejado": [8, 10]}) for i in range(4)]
        filhos += [_vet("Eixo vertical", [(0, 0), (0, H)], s, traco={"cor": "#F2EFE980", "peso": 3}),
                   _vet("Eixo horizontal", [(0, H), (Wg, H)], s, traco={"cor": "#F2EFE980", "peso": 3}),
                   _vet("Área", linha + [(Wg, H), (0, H)], s, fill="#3DDC8429"),
                   _vet("Linha", linha, s, traco={"cor": C["green"], "peso": 8})]
        filhos += [_t(p["eixo"][0], "JetBrains Mono", "Regular", 28, "#C9C4BC", s, caminho="eixo[0]", x=0, y=(H + 22) * s),
                   _t(p["eixo"][1], "JetBrains Mono", "Regular", 28, "#C9C4BC", s, caminho="eixo[1]", xd=Wg * s,
                      y=(H + 22) * s, alinhar="RIGHT")]
        return _f("grafico", filhos, auto=None, w=Wg * s, h=(H + 60) * s, rot=rot_aj, k=s)

    if pid == "grafico" and comp == "PapelMesa":
        Wg, H = 780, 420
        filhos = [_vet("Eixo horizontal", [(0, H), (Wg, H)], s, traco={"cor": C["ink"], "peso": 3}),
                  _vet("Eixo vertical", [(0, 0), (0, H)], s, traco={"cor": C["ink"], "peso": 3}),
                  _vet("Curva ruim", "M 0 330 C 80 300, 140 340, 220 310 S 380 330, 460 300 S 640 320, 780 300", s,
                       traco={"cor": "#9A948A", "peso": 7}),
                  _vet("Curva boa", "M 0 340 C 160 320, 280 260, 420 190 S 660 60, 780 30", s,
                       traco={"cor": C["ink"], "peso": 8}),
                  _vet("Círculo à mão", "M 700 -10 C 790 -40, 860 30, 800 80 C 740 120, 640 80, 660 20 C 670 -10, 720 -30, 760 -25",
                       s, traco={"cor": C["marker"], "peso": 7}),
                  _t(p["curvaRuim"]["rotulo"], "JetBrains Mono", "Regular", 26, "#7A746A", s, caminho="curvaRuim.rotulo",
                     xd=Wg * s, y=338 * s, alinhar="RIGHT"),
                  _t(p["curvaBoa"]["rotulo"], "JetBrains Mono", "Regular", 26, C["ink"], s, caminho="curvaBoa.rotulo",
                     x=430 * s, y=128 * s)]
        return _f("grafico", filhos, auto=None, w=Wg * s, h=H * s, rot=rot_aj, k=s)

    if pid == "adesivo":
        return _f("adesivo", [_t(p["adesivo"]["texto"], "Anton", "Regular", 88, C["ink"], s, caminho="adesivo.texto")],
                  auto="H", pad=(10, 26, 10, 26), fill="#F7F3EA", sombra=(12, 30, 0.35), rot=6 + rot_aj, k=s)

    if pid == "botao":
        return _f("botao", [_t(p["titulo"], "Inter", "Extra Bold", 56, "#FFFFFF", s, caminho="titulo", alinhar="CENTER"),
                            _t(p["subtitulo"], "Inter", "Semi Bold", 38, "#FFFFFFE6", s, caminho="subtitulo", alinhar="CENTER")],
                  pad=(26, 44, 26, 44), alinhar="CENTER", raio=30, fill=C["coral"], sombra=(20, 50, 0.4),
                  rot=rot_aj, ancora="centro", k=s)
    if pid == "chamada":
        return _f("chamada", [_t(p["chamada"]["texto"], "Inter", "Extra Bold", 48, "#FFFFFF", s, caminho="chamada.texto")],
                  rot=rot_aj, ancora="centro", k=s)
    return None
