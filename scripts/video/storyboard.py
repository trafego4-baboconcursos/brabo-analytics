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


def dados_storyboard(criativo: dict, captions: list[dict]) -> dict:
    telas = []
    for c in criativo["cenas"]:
        telas.append({
            "id": c["id"],
            "componente": c["componente"],
            "de": c["de"],
            "ate": c["ate"],
            "fala": _fala(captions, c["de"], c["ate"]),
            "efeitos": [f"{t} s {nome}" for t, nome, _vol in c.get("sfx", [])],
            "textos": _textos(c.get("props", {})),
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
        for caminho, novo in textos.items():
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


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Gera os dados do storyboard (Figma) a partir do criativo resolvido")
    ap.add_argument("criativo", type=Path)
    ap.add_argument("--captions", type=Path, required=True)
    ap.add_argument("--saida", type=Path, required=True)
    a = ap.parse_args(argv)
    for s in (sys.stdout, sys.stderr):
        if hasattr(s, "reconfigure"):
            s.reconfigure(errors="replace")
    crit = json.loads(a.criativo.read_text(encoding="utf-8"))
    caps = json.loads(a.captions.read_text(encoding="utf-8"))
    d = dados_storyboard(crit, caps)
    a.saida.parent.mkdir(parents=True, exist_ok=True)
    a.saida.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")
    print(f"ok: {len(d['telas'])} telas -> {a.saida}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
