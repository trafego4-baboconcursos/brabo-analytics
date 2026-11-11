"""Storyboard do criativo no Figma: dados de cada tela (ida) e textos editados (volta).

Ida: `dados_storyboard(criativo, captions)` monta, por cena, a fala (palavras dentro de
[de, ate]), os efeitos e os TEXTOS EDITÁVEIS — toda string das props, menos caminhos de
arquivo — indexados pelo caminho da prop ("destaque.texto", "etiquetas[0].texto").
No Figma cada texto vira uma camada TEXT com esse caminho no nome.

Volta: o Claude lê as camadas das telas marcadas "Aprovado", chama
`diferencas_textos` para LISTAR o que mudou (e mostrar ao usuário) e só depois
`aplicar_textos` para gravar no criativo.json.

Uso (ida):
    python -m scripts.video.storyboard src/data/criativo.resolvido.json \
        --captions src/data/captions.json --saida out/storyboard.json
"""
from __future__ import annotations

import argparse
import copy
import json
import math
import re
import sys
from pathlib import Path

_ARQUIVO = re.compile(r"\.(jpe?g|png|webp|gif|svg|mp4|mov|wav|mp3)$", re.I)
_PASSO = re.compile(r"([^.\[\]]+)|\[(\d+)\]")


def _textos(valor, caminho: str = "") -> dict[str, str]:
    if isinstance(valor, dict):
        out: dict[str, str] = {}
        for k, v in valor.items():
            out.update(_textos(v, f"{caminho}.{k}" if caminho else k))
        return out
    if isinstance(valor, list):
        out = {}
        for i, v in enumerate(valor):
            out.update(_textos(v, f"{caminho}[{i}]"))
        return out
    if isinstance(valor, str) and not _ARQUIVO.search(valor) and not valor.startswith("@"):
        return {caminho: valor}
    return {}


def _fala(captions: list[dict], de: float, ate: float) -> str:
    palavras = [c["text"].strip() for c in captions if de <= c["startMs"] / 1000 < ate]
    return " ".join(palavras)


def dados_storyboard(criativo: dict, captions: list[dict], pecas: dict | None = None) -> dict:
    """`pecas` (pecas.json do render de camadas): a tela vira palco editável — fundo + uma camada
    por peça + legenda — em vez do still único."""
    telas = []
    for c in criativo["cenas"]:
        props = c.get("props", {})
        if pecas and c["id"] in pecas:
            cam = copy.deepcopy(pecas[c["id"]])
            for p in cam["pecas"]:
                p["nome"] = nome_camada(p["id"], props)
                if (nat := _spec_nativo(c, p)) is not None:
                    p["nativo"] = nat
            telas.append({"camadas": cam})
        else:
            telas.append({})
        # texto de peça caixa + lettering é editado no próprio balão, não na caixa TEXTOS
        nativos = {f"{p['id']}." for p in telas[-1].get("camadas", {}).get("pecas", []) if "nativo" in p}
        textos = {k: v for k, v in _textos(props).items() if not any(k.startswith(n) for n in nativos)}
        telas[-1]["rotulos"] = {k: nome_camada(k, props) for k in textos}
        telas[-1].update({
            "id": c["id"],
            "componente": c["componente"],
            "de": c["de"],
            "ate": c["ate"],
            "fala": _fala(captions, c["de"], c["ate"]),
            "efeitos": [f"{t} s {nome}" for t, nome, _vol in c.get("sfx", [])],
            "textos": textos,
        })
    return {"codigo": criativo["codigo"], "telas": telas}


def _passos(caminho: str) -> list[str | int]:
    return [int(i) if i else k for k, i in _PASSO.findall(caminho)]


def _ler(props, caminho: str):
    alvo = props
    for p in _passos(caminho):
        alvo = alvo[p]
    return alvo


def diferencas_textos(criativo: dict, lidos: dict[str, dict[str, str]]) -> list[tuple[str, str, str, str]]:
    """[(cena, caminho, antes, depois)] só do que mudou. Caminho inexistente é erro (camada renomeada?)."""
    cenas = {c["id"]: c for c in criativo["cenas"]}
    saida = []
    for cena_id, textos in lidos.items():
        props = cenas[cena_id]["props"]
        por_nome = {nome_camada(k, props): k for k in _textos(props)}
        for caminho, novo in textos.items():
            caminho = por_nome.get(caminho, caminho)   # camada vem com o nome em português
            try:
                antes = _ler(props, caminho)
            except (KeyError, IndexError, TypeError):
                raise KeyError(f"cena '{cena_id}': o texto '{caminho}' não existe nas props (camada renomeada no Figma?)")
            if antes != novo:
                saida.append((cena_id, caminho, antes, novo))
    return saida


def aplicar_textos(criativo: dict, lidos: dict[str, dict[str, str]]) -> dict:
    """Cópia do criativo com os textos trocados (só os caminhos listados)."""
    novo = copy.deepcopy(criativo)
    cenas = {c["id"]: c for c in novo["cenas"]}
    for cena_id, caminho, _antes, depois in diferencas_textos(criativo, lidos):
        passos = _passos(caminho)
        alvo = cenas[cena_id]["props"]
        for p in passos[:-1]:
            alvo = alvo[p]
        alvo[passos[-1]] = depois
    return novo


# Nomes das camadas no Figma em português (o usuário não lê "kicker"/"etiquetas[0]").
# O id da peça / caminho da prop continua sendo a chave no código; a volta traduz de novo.
NOMES = {
    "kicker": "Sobretítulo", "titulo": "Título", "subtitulo": "Subtítulo", "corpo": "Texto",
    "folha": "Folha de papel", "cartao": "Cartão", "carimbo": "Carimbo", "mao": "Anotação à mão",
    "selo": "Selo", "numero": "Número", "grafico": "Gráfico", "rotuloFim": "Valor final",
    "rotuloCume": "Placa no topo", "pergunta": "Pergunta", "adesivo": "Adesivo", "medalhas": "Medalhas",
    "imagem": "Ilustração", "botao": "Botão", "chamada": "Chamada", "faixa": "Faixa", "prefixo": "Moeda",
    "eixo": "Eixo", "rotulo": "Rótulo", "destaque": "Marca-texto", "tituloDestaque": "Destaque do título",
    "curvaRuim": "Curva ruim", "curvaBoa": "Curva boa",
    "etiquetas": "Balão", "itens": "Item",
    # subcampos
    "texto": "texto", "valor": "texto", "sub": "linha de baixo", "marca": "marca",
}


def nome_camada(caminho: str, props: dict) -> str:
    """Nome em português de uma peça ou texto: "etiquetas[0]" → "Balão 1 · trabalha",
    "rotuloFim.valor" → "Valor final · texto". Sem tradução, devolve o próprio caminho."""
    passos = _passos(caminho)
    if not passos or not isinstance(passos[0], str) or passos[0] not in NOMES:
        return caminho
    nome = NOMES[passos[0]]
    resto = passos[1:]
    if resto and isinstance(resto[0], int):
        nome += f" {resto[0] + 1}"
        try:
            item = props[passos[0]][resto[0]]
            if isinstance(item, dict) and isinstance(item.get("texto"), str) and len(resto) == 1:
                nome += f" · {item['texto']}"
        except (KeyError, IndexError, TypeError):
            pass
        resto = resto[1:]
    for p in resto:
        nome += f" · {NOMES.get(p, p) if isinstance(p, str) else p + 1}"
    return nome


def diferencas_ajustes(criativo: dict, manifesto: dict, lidos: dict[str, dict[str, dict]],
                       formato: str = "story", escala_palco: float = 2.0) -> list[tuple[str, str, dict, dict]]:
    """[(cena, peça, ajuste antes, ajuste depois)] do que o usuário moveu, girou ou redimensionou.

    `manifesto[cena]["pecas"]`: caixa {id, x, y, w, h} de cada peça no canvas do vídeo, como foi
    renderizada (já com o ajuste atual). `lidos[cena][peça]`: camada no Figma, no palco reduzido
    por `escala_palco` — centro da caixa (cx, cy, que não muda ao girar), largura sem rotação e
    rotação do Figma (anti-horária; no CSS é horária, por isso o sinal inverte). O que mudou soma ao
    ajuste que já existia. Abaixo de 1 px / 0,5° / 1 % é ruído do arraste e não conta.

    `origem` (opcional, do render "caixa:"): centro da caixa da <Peca>, em volta do qual o vídeo
    gira/escala. No Figma o usuário gira/escala em volta do centro da IMAGEM; quando os dois não
    coincidem (caixa mais larga que o visível), o deslocamento compensa:
        d1 = d0 + (F − B) − ΔR·ΔS·(V − B)
    F = centro no Figma, B = origem, V = centro visível renderizado (tudo no canvas do vídeo).
    """
    cenas = {c["id"]: c for c in criativo["cenas"]}
    saida = []
    for cena_id, camadas in lidos.items():
        caixas = {p["id"]: p for p in manifesto[cena_id]["pecas"]}
        atuais = cenas[cena_id].get("ajustes", {}).get(formato, {})
        por_nome = {nome_camada(i, cenas[cena_id].get("props", {})): i for i in caixas}
        for peca, l in camadas.items():
            peca = por_nome.get(peca, peca)   # camada vem com o nome em português
            if "fonte" in l:                  # caixa + lettering: conta em diferencas_nativas
                continue
            if peca not in caixas:
                raise KeyError(f"cena '{cena_id}': a camada '{peca}' não está no pecas.json (renomeada no Figma?)")
            b = caixas[peca]
            # peça filha (ex.: kicker dentro da folha) vive no frame da mãe: coordenadas locais a ela
            ox, oy = (caixas[b["pai"]]["x"], caixas[b["pai"]]["y"]) if b.get("pai") else (0, 0)
            antes = dict(atuais.get(peca, {}))
            depois = dict(antes)
            vx, vy = b["x"] + b["w"] / 2, b["y"] + b["h"] / 2
            bx, by = b.get("origem", (vx, vy))
            fx, fy = l["cx"] * escala_palco + ox, l["cy"] * escala_palco + oy
            rot_css = -l["rot"] if abs(l["rot"]) >= 0.5 else 0.0
            razao = l["largura"] * escala_palco / b["w"]
            if abs(razao - 1) < 0.01:
                razao = 1.0
            a = math.radians(rot_css)
            ux, uy = vx - bx, vy - by
            rx = razao * (ux * math.cos(a) - uy * math.sin(a))
            ry = razao * (ux * math.sin(a) + uy * math.cos(a))
            dx, dy = (fx - bx) - rx, (fy - by) - ry
            if abs(dx) >= 1:
                depois["dx"] = round(antes.get("dx", 0) + dx)
            if abs(dy) >= 1:
                depois["dy"] = round(antes.get("dy", 0) + dy)
            if rot_css:
                depois["rot"] = round(antes.get("rot", 0) + rot_css, 1)
            if razao != 1.0:
                depois["escala"] = round(antes.get("escala", 1) * razao, 3)
            if depois != antes:
                saida.append((cena_id, peca, antes, depois))
    return saida


# --- caixa + lettering (peças nativas no Figma) ---------------------------------------------
_TOKENS = Path(__file__).resolve().parent / "modelo" / "src" / "tokens.json"


def _cores() -> dict:
    return json.loads(_TOKENS.read_text(encoding="utf-8"))["cor"]


def _spec_nativo(cena: dict, peca: dict, formato: str = "story", k: float = 0.5) -> dict | None:
    """Como desenhar a peça como caixa + texto vivo no Figma (palco × k), ou None se ela é imagem.
    Balão (Desenho, story): fundo ink, letra Inter 800 54 px, padding 14/30, raio 14 — os mesmos
    números de cenas/Desenho.tsx, vezes a escala do ajuste."""
    m = re.fullmatch(r"etiquetas\[(\d+)\]", peca["id"])
    if not (m and cena["componente"] == "Desenho" and formato == "story" and "origem" in peca):
        return None
    e = cena["props"]["etiquetas"][int(m.group(1))]
    aj = cena.get("ajustes", {}).get(formato, {}).get(peca["id"], {})
    s = aj.get("escala", 1) * k
    cores = _cores()
    return {"texto": e["texto"], "fonte": round(54 * s, 2), "cor": e.get("cor", cores["ink"]),
            "corTexto": e.get("corTexto", cores["paper"]), "padV": round(14 * s, 2), "padH": round(30 * s, 2),
            "raio": round(14 * s, 2), "rot": -(e.get("rot", 0) + aj.get("rot", 0)),
            "cx": peca["origem"][0] * k, "cy": peca["origem"][1] * k}


def diferencas_nativas(criativo: dict, manifesto: dict, lidos: dict, nativos0: dict,
                       formato: str = "story", escala_palco: float = 2.0):
    """Volta das peças caixa + lettering. Devolve (ajustes, props):
    - ajustes [(cena, peça, antes, depois)]: o centro da caixa no Figma vira o centro no vídeo. Texto
      maior/menor cresce a caixa para a direita nos dois lados (auto layout no Figma, left fixo no
      vídeo), então esse crescimento é descontado; letra maior vira `escala`, em volta do centro.
    - props [(cena, caminho, antes, depois)]: texto e cores mudados (aplicar com aplicar_props).
    `nativos0[cena][peça]` = {largura, rot, fonte} como o Figma criou a caixa."""
    cenas = {c["id"]: c for c in criativo["cenas"]}
    cores = _cores()
    ajustes, props = [], []
    for cena_id, camadas in lidos.items():
        cena = cenas[cena_id]
        caixas = {p["id"]: p for p in manifesto[cena_id]["pecas"]}
        por_nome = {nome_camada(i, cena.get("props", {})): i for i in caixas}
        atuais = cena.get("ajustes", {}).get(formato, {})
        for peca, l in camadas.items():
            peca = por_nome.get(peca, peca)
            if "fonte" not in l or peca not in nativos0.get(cena_id, {}):
                continue
            n0, b = nativos0[cena_id][peca], caixas[peca]
            antes = dict(atuais.get(peca, {}))
            depois = dict(antes)
            razao = l["fonte"] / n0["fonte"]
            if abs(razao - 1) < 0.01:
                razao = 1.0
            # quanto o texto (sem a escala) cresceu, em px do vídeo; metade disso o vídeo já anda sozinho
            cresceu = escala_palco * (l["largura"] / razao - n0["largura"])
            dx = l["cx"] * escala_palco - b["origem"][0] - (cresceu / 2 if razao == 1.0 else 0)
            dy = l["cy"] * escala_palco - b["origem"][1]
            if abs(dx) >= 1:
                depois["dx"] = round(antes.get("dx", 0) + dx)
            if abs(dy) >= 1:
                depois["dy"] = round(antes.get("dy", 0) + dy)
            drot = l["rot"] - n0["rot"]
            if abs(drot) >= 0.5:
                depois["rot"] = round(antes.get("rot", 0) - drot, 1)
            if razao != 1.0:
                depois["escala"] = round(antes.get("escala", 1) * razao, 3)
            if depois != antes:
                ajustes.append((cena_id, peca, antes, depois))
            e = cena["props"]["etiquetas"][int(peca[peca.index("[") + 1:-1])]
            for campo, padrao in (("texto", None), ("cor", cores["ink"]), ("corTexto", cores["paper"])):
                atual = e.get(campo, padrao)
                if campo in l and l[campo] != atual:
                    props.append((cena_id, f"{peca}.{campo}", atual, l[campo]))
    return ajustes, props


def aplicar_props(criativo: dict, difs: list[tuple[str, str, object, object]]) -> dict:
    """Cópia do criativo com as props trocadas pelo caminho (cria o campo se não existia, ex.: cor)."""
    novo = copy.deepcopy(criativo)
    cenas = {c["id"]: c for c in novo["cenas"]}
    for cena_id, caminho, _antes, depois in difs:
        passos = _passos(caminho)
        alvo = cenas[cena_id]["props"]
        for p in passos[:-1]:
            alvo = alvo[p]
        alvo[passos[-1]] = depois
    return novo


def caixa_alfa(caminho: Path, limiar: int = 8) -> tuple[int, int, int, int] | None:
    """(x, y, w, h) do que é visível (alfa > limiar) no PNG; None se a imagem está vazia."""
    from PIL import Image  # só o ETL local de vídeo usa; fora do requirements do servidor
    with Image.open(caminho) as img:
        if "A" not in img.getbands():       # PNG opaco (peça em tela cheia): a imagem toda
            return 0, 0, img.width, img.height
        bbox = img.getchannel("A").point(lambda a: 255 if a > limiar else 0).getbbox()
    if not bbox:
        return None
    x0, y0, x1, y1 = bbox
    return x0, y0, x1 - x0, y1 - y0


def montar_pecas(pasta: Path) -> dict:
    """pecas.json a partir do render de camadas (render-pecas.mjs).

    Espera `<pasta>/<cena>/fundo.png`, `<cena>/<peça>.png` (canvas inteiro, alfa) e
    `<cena>/lista.json` = [{id, pai?}] na ordem de empilhamento. Corta cada peça pelo alfa em
    `<peça>.recorte.png`; peça sem pixel visível no instante do storyboard fica de fora.
    """
    from PIL import Image
    pasta = Path(pasta)

    def recortar(png: Path) -> dict | None:
        caixa = caixa_alfa(png)
        if caixa is None:
            return None
        x, y, w, h = caixa
        recorte = png.with_suffix(".recorte.png")
        with Image.open(png) as img:
            img.crop((x, y, x + w, y + h)).save(recorte)
        return {"arquivo": recorte.relative_to(pasta).as_posix(), "x": x, "y": y, "w": w, "h": h}

    manifesto = {}
    for lista in sorted(pasta.glob("*/lista.json")):
        cena = lista.parent
        pecas = []
        for item in json.loads(lista.read_text(encoding="utf-8")):
            r = recortar(cena / f"{item['id']}.png")
            if r is None:
                continue
            p = {"id": item["id"], **r, **({"pai": item["pai"]} if item.get("pai") else {})}
            # centro da caixa da <Peca> (render "caixa:"): origem de giro/escala no vídeo
            caixa_png = cena / f"{item['id']}.caixa.png"
            if caixa_png.exists() and (cx := caixa_alfa(caixa_png)):
                p["origem"] = [cx[0] + cx[2] / 2, cx[1] + cx[3] / 2]
            pecas.append(p)
        manifesto[cena.name] = {"fundo": (cena / "fundo.png").relative_to(pasta).as_posix(), "pecas": pecas}
        # a nossa legenda fica por cima de tudo no vídeo: camada de cima, travada no Figma
        if (cena / "legenda.png").exists() and (leg := recortar(cena / "legenda.png")):
            manifesto[cena.name]["legenda"] = leg
    return manifesto


def aplicar_ajustes(criativo: dict, difs: list[tuple[str, str, dict, dict]], formato: str = "story") -> dict:
    """Cópia do criativo com os ajustes de `diferencas_ajustes` gravados em cenas[].ajustes[formato]."""
    novo = copy.deepcopy(criativo)
    cenas = {c["id"]: c for c in novo["cenas"]}
    for cena_id, peca, _antes, depois in difs:
        cenas[cena_id].setdefault("ajustes", {}).setdefault(formato, {})[peca] = dict(depois)
    return novo


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Gera os dados do storyboard (Figma) a partir do criativo resolvido")
    ap.add_argument("criativo", type=Path)
    ap.add_argument("--captions", type=Path, required=True)
    ap.add_argument("--saida", type=Path, required=True)
    ap.add_argument("--camadas", type=Path, help="pasta do render-pecas.mjs (<output>/pecas/<COD>/<formato>): "
                    "corta as peças, grava pecas.json lá e põe as camadas nas telas")
    a = ap.parse_args(argv)
    for s in (sys.stdout, sys.stderr):
        if hasattr(s, "reconfigure"):
            s.reconfigure(errors="replace")
    crit = json.loads(a.criativo.read_text(encoding="utf-8"))
    caps = json.loads(a.captions.read_text(encoding="utf-8"))
    pecas = None
    if a.camadas:
        pecas = montar_pecas(a.camadas)
        (a.camadas / "pecas.json").write_text(json.dumps(pecas, ensure_ascii=False, indent=1), encoding="utf-8")
    d = dados_storyboard(crit, caps, pecas=pecas)
    a.saida.parent.mkdir(parents=True, exist_ok=True)
    a.saida.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")
    print(f"ok: {len(d['telas'])} telas -> {a.saida}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
