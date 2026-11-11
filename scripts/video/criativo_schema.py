"""criativo.json → validação + resolução para a composição genérica do modelo Remotion.

O criativo.json descreve um vídeo animado: formatos (bruto, legenda queimada,
ganho dos efeitos) e cenas (componente da biblioteca, de/até em segundos do
bruto, props, efeitos). Âncoras: `ancora_palavras` dá nome a palavras faladas;
nas props, qualquer texto "@nome" (ou "@nome+0.3" / "@nome-0.5") vira o segundo
em que a palavra é dita, procurada DENTRO de [de, ate] da cena.

Uso:
    python -m scripts.video.criativo_schema criativo.json \
        --transcricao src/data/captions.json --saida src/data/criativo.resolvido.json
"""
from __future__ import annotations

import argparse
import copy
import difflib
import json
import re
import sys
import unicodedata
from pathlib import Path

NOMES_CENAS = Path(__file__).resolve().parent / "modelo" / "src" / "cenas" / "nomes.json"
TOLERANCIA_EMENDA_S = 1 / 30  # menos de 1 quadro = cenas coladas
_ARROBA = re.compile(r"^@(\w+)([+-]\d+(?:\.\d+)?)?$")


class CriativoInvalido(ValueError):
    """criativo.json com erro de conteúdo; a mensagem diz o que corrigir."""


def _nomes_cenas() -> list[str]:
    return json.loads(NOMES_CENAS.read_text(encoding="utf-8"))


def _normalizar(palavra: str) -> str:
    sem_acento = unicodedata.normalize("NFKD", palavra.lower())
    sem_acento = "".join(c for c in sem_acento if not unicodedata.combining(c))
    return re.sub(r"[^\w$]", "", sem_acento)


def _validar_formatos(formatos: dict) -> None:
    if not formatos:
        raise CriativoInvalido("criativo sem 'formatos' (story, feed e/ou h)")
    for nome, f in formatos.items():
        for chave in ("video", "legenda_queimada", "ganho_sfx"):
            if chave not in f:
                raise CriativoInvalido(f"formato {nome}: falta '{chave}'")
        if f["legenda_queimada"] and "queimada_desde_s" not in f:
            raise CriativoInvalido(
                f"formato {nome}: legenda_queimada=true exige 'queimada_desde_s' "
                "(segundo em que a legenda do bruto começa; antes disso entra a nossa)")


CAMPOS_AJUSTE = ("dx", "dy", "rot", "escala")


def _validar_ajustes(c: dict, formatos: dict) -> None:
    """`ajustes = {formato: {peça: {dx, dy, rot, escala}}}`: o que o usuário moveu no Figma."""
    for formato, pecas in c.get("ajustes", {}).items():
        if formato not in formatos:
            raise CriativoInvalido(f"cena '{c['id']}': ajuste no formato '{formato}', que não está em 'formatos'")
        for peca, aj in pecas.items():
            if not peca:
                raise CriativoInvalido(f"cena '{c['id']}': ajuste com peça sem nome ({formato})")
            ruins = [k for k, v in aj.items()
                     if k not in CAMPOS_AJUSTE or isinstance(v, bool) or not isinstance(v, (int, float))]
            if ruins or aj.get("escala", 1) <= 0:
                raise CriativoInvalido(
                    f"cena '{c['id']}', peça '{peca}' ({formato}): ajuste aceita só números em "
                    f"{', '.join(CAMPOS_AJUSTE)} (escala > 0); veio {aj}")


def _achar_palavra(palavra: str, de: float, ate: float, transcricao: list[dict]) -> float:
    alvo = _normalizar(palavra)
    for c in transcricao:
        s = c["startMs"] / 1000
        if de <= s <= ate and _normalizar(c["text"]) == alvo:
            return round(s, 3)
    ditas = [c["text"].strip() for c in transcricao if de <= c["startMs"] / 1000 <= ate]
    parecidas = difflib.get_close_matches(palavra, ditas, n=3, cutoff=0.6)
    dica = f"; parecidas: {', '.join(repr(p) for p in parecidas)}" if parecidas else ""
    raise CriativoInvalido(f"âncora '{palavra}' não é dita entre {de} s e {ate} s{dica}")


def carregar_criativo(caminho: Path, transcricao: list[dict]) -> dict:
    """Lê e valida o criativo.json; preenche `ancoras_s` de cada cena."""
    dados = json.loads(Path(caminho).read_text(encoding="utf-8"))
    duracao = float(dados["duracao_s"])
    _validar_formatos(dados.get("formatos", {}))
    nomes = _nomes_cenas()
    cenas = sorted(dados.get("cenas", []), key=lambda c: c["de"])
    anterior = None
    for c in cenas:
        if c["componente"] not in nomes:
            raise CriativoInvalido(f"cena '{c['id']}': componente '{c['componente']}' não existe (há: {', '.join(nomes)})")
        if not 0 <= c["de"] < c["ate"]:
            raise CriativoInvalido(f"cena '{c['id']}': precisa de 0 ≤ de < ate (está {c['de']} → {c['ate']})")
        if c["ate"] > duracao + 1e-6:
            raise CriativoInvalido(f"cena '{c['id']}' termina em {c['ate']} s, depois do fim do vídeo ({duracao} s)")
        if anterior and c["de"] < anterior["ate"] - TOLERANCIA_EMENDA_S:
            raise CriativoInvalido(
                f"cenas '{anterior['id']}' ({anterior['de']}–{anterior['ate']}) e '{c['id']}' "
                f"({c['de']}–{c['ate']}) se sobrepõem; para emendar, a 2ª começa onde a 1ª termina")
        _validar_ajustes(c, dados["formatos"])
        c["ancoras_s"] = {
            nome: _achar_palavra(palavra, c["de"], c["ate"], transcricao)
            for nome, palavra in c.get("ancora_palavras", {}).items()
        }
        anterior = c
    dados["cenas"] = cenas
    return dados


def _trocar_arrobas(valor, ancoras: dict, cena_id: str):
    if isinstance(valor, dict):
        return {k: _trocar_arrobas(v, ancoras, cena_id) for k, v in valor.items()}
    if isinstance(valor, list):
        return [_trocar_arrobas(v, ancoras, cena_id) for v in valor]
    if isinstance(valor, str):
        m = _ARROBA.match(valor)
        if m:
            nome, ajuste = m.group(1), m.group(2)
            if nome not in ancoras:
                raise CriativoInvalido(f"cena '{cena_id}': '{valor}' usa a âncora '@{nome}', que não está em ancora_palavras")
            return round(ancoras[nome] + (float(ajuste) if ajuste else 0.0), 3)
    return valor


def _regras_de_cena(c: dict) -> None:
    em = c["props"].get("em", {})
    if c["componente"] == "Rota" and "saiTitulo" in em and "bandeira" in em and em["saiTitulo"] > em["bandeira"]:
        raise CriativoInvalido(
            f"cena '{c['id']}' (Rota): saiTitulo ({em['saiTitulo']}) precisa ser antes da bandeira "
            f"({em['bandeira']}), senão o título cobre o rótulo do cume")


def resolver_criativo(dados: dict) -> dict:
    """Troca as âncoras "@nome" das props por segundos e calcula cobertos/cta para a composição."""
    r = copy.deepcopy(dados)
    for c in r["cenas"]:
        c["props"] = _trocar_arrobas(c.get("props", {}), c.get("ancoras_s", {}), c["id"])
        c["sfx"] = _trocar_arrobas(c.get("sfx", []), c.get("ancoras_s", {}), c["id"])
        _regras_de_cena(c)
    r["cobertos"] = [[c["de"], c["ate"]] for c in r["cenas"] if c["componente"] != "Cta"]
    cta = [c for c in r["cenas"] if c["componente"] == "Cta"]
    r["cta"] = [cta[0]["de"], cta[0]["ate"]] if cta else None
    return r


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Valida o criativo.json e gera o criativo.resolvido.json")
    ap.add_argument("criativo", type=Path)
    ap.add_argument("--transcricao", type=Path, required=True, help="captions.json (formato Caption do Remotion)")
    ap.add_argument("--saida", type=Path, required=True)
    a = ap.parse_args(argv)
    # console do Windows (cp1252) não tem todos os caracteres: troca por "?" em vez de quebrar
    for saida in (sys.stdout, sys.stderr):
        if hasattr(saida, "reconfigure"):
            saida.reconfigure(errors="replace")
    transcricao = json.loads(a.transcricao.read_text(encoding="utf-8"))
    try:
        r = resolver_criativo(carregar_criativo(a.criativo, transcricao))
    except CriativoInvalido as e:
        print(f"criativo inválido: {e}", file=sys.stderr)
        return 1
    a.saida.write_text(json.dumps(r, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"ok: {len(r['cenas'])} cenas, {len(r['formatos'])} formatos -> {a.saida}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
