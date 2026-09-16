"""Contrato do `dbf` — o dicionário que o /debriefing serializa no snapshot.

Três vezes em dois dias o `dbf` ganhou campo novo sem `SNAPSHOT_VERSION` subir
junto, e o resultado foi sempre o mesmo: o snapshot já gravado passava no guard
de versão, o template pedia o campo novo, `/debriefing` devolvia 500. O
comentário em `debriefing_snapshot.py` avisa que subir o número não é opcional —
e três vezes não bastou, porque nada no processo cobra.

Este arquivo cobra. Roda sem banco (só lê o código-fonte), então cai na faixa
rápida do CI (`-m "not smoke and not caracterizacao"`).

Quando falhar por mudança legítima, regrave o manifesto:

    ATUALIZAR_MANIFESTO=1 python -m pytest tests/test_dbf_contrato.py

Ao contrário de `ATUALIZAR_BASELINE=1`, aqui não há risco de escopar e perder o
resto: o manifesto é um arquivo só, reescrito por inteiro.
"""
from __future__ import annotations

import ast
import json
import os
import re
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
PRODUTOR = RAIZ / "frontend" / "services" / "debriefing.py"
VERSAO_EM = RAIZ / "frontend" / "db_readers" / "debriefing_snapshot.py"
MANIFESTO = RAIZ / "tests" / "baseline" / "dbf_manifesto.json"
FUNCAO = "_compute_debriefing_ctx"

# `debriefing.html` e as seções lazy que ele inclui — todas recebem o mesmo `dbf`.
TEMPLATES = [RAIZ / "frontend" / "templates" / "debriefing.html"] + sorted(
    (RAIZ / "frontend" / "templates" / "debriefing").glob("*.html")
)

ATUALIZAR = os.environ.get("ATUALIZAR_MANIFESTO") == "1"


def _retornos_do_proprio_escopo(fn: ast.FunctionDef) -> list[ast.Return]:
    """`return` que pertencem à função em si, não às aninhadas dentro dela.

    `ast.walk` não serve: `_compute_debriefing_ctx` tem meia dúzia de helpers
    declarados no corpo, e os `return` deles (`{"nome": ..., "invest": ...}`)
    entrariam no contrato como se fossem campos do `dbf`."""
    achados: list[ast.Return] = []

    def visita(no: ast.AST) -> None:
        for filho in ast.iter_child_nodes(no):
            if isinstance(filho, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda, ast.ClassDef)):
                continue  # escopo próprio — o que sai dali não é o dbf
            if isinstance(filho, ast.Return):
                achados.append(filho)
            visita(filho)

    visita(fn)
    return achados


def chaves_do_dbf() -> set[str]:
    """As chaves do dicionário que `_compute_debriefing_ctx` devolve.

    Lido por AST em vez de execução: a função precisa de banco e leva ~1 min por
    lançamento, e o que interessa aqui é a *forma*, que é estática."""
    arvore = ast.parse(PRODUTOR.read_text(encoding="utf-8"))
    fn = next(
        (n for n in ast.walk(arvore) if isinstance(n, ast.FunctionDef) and n.name == FUNCAO),
        None,
    )
    assert fn is not None, f"{FUNCAO} não existe mais em {PRODUTOR.name} — atualize este teste."

    dicts = [r for r in _retornos_do_proprio_escopo(fn) if isinstance(r.value, ast.Dict)]
    assert len(dicts) == 1, (
        f"{FUNCAO} passou a ter {len(dicts)} `return` de dicionário no escopo dela "
        f"(linhas {[r.lineno for r in dicts]}). Este teste assume um só — o do `dbf`. "
        "Se a função foi dividida de propósito, ajuste a extração aqui."
    )

    retorno = dicts[0]
    dicionario = retorno.value
    assert isinstance(dicionario, ast.Dict)  # garantido pelo filtro acima

    literais = {k.value for k in dicionario.keys if isinstance(k, ast.Constant) and isinstance(k.value, str)}
    outras = [k for k in dicionario.keys if not (isinstance(k, ast.Constant) and isinstance(k.value, str))]
    assert not outras, (
        f"O `return` do {FUNCAO} ganhou chave que não é string literal "
        f"(`**algo` ou chave calculada, linha {retorno.lineno}). "
        "Assim não dá pra saber a forma do dbf sem executar — desfaça, ou reescreva a extração."
    )
    return literais


def versao_do_snapshot() -> int:
    """`SNAPSHOT_VERSION` lido do código, sem importar o módulo (que puxaria o
    engine do banco e tiraria este teste da faixa rápida)."""
    arvore = ast.parse(VERSAO_EM.read_text(encoding="utf-8"))
    for no in ast.walk(arvore):
        if isinstance(no, ast.Assign) and isinstance(no.value, ast.Constant) and isinstance(no.value.value, int):
            for alvo in no.targets:
                if isinstance(alvo, ast.Name) and alvo.id == "SNAPSHOT_VERSION":
                    return no.value.value
    pytest.fail(f"SNAPSHOT_VERSION não encontrado em {VERSAO_EM.name}.")


def campos_lidos_nos_templates() -> dict[str, list[str]]:
    """`dbf.campo` e `dbf["campo"]` -> em quais templates aparecem."""
    padrao = re.compile(r"""\bdbf(?:\.([a-zA-Z_]\w*)|\[["']([^"']+)["']\])""")
    achados: dict[str, list[str]] = {}
    for arquivo in TEMPLATES:
        texto = arquivo.read_text(encoding="utf-8")
        for ponto, colchete in padrao.findall(texto):
            campo = ponto or colchete
            achados.setdefault(campo, []).append(arquivo.name)
    return achados


def _grava_manifesto(chaves: set[str], versao: int) -> None:
    MANIFESTO.write_text(
        json.dumps({"snapshot_version": versao, "chaves": sorted(chaves)}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def test_dbf_mudou_entao_snapshot_version_subiu():
    """Campo novo (ou removido) no `dbf` obriga `SNAPSHOT_VERSION` a subir.

    Sem isso o snapshot velho continua sendo servido ao template novo, e a
    página quebra pra todo lançamento que já tiver snapshot gravado."""
    chaves = chaves_do_dbf()
    versao = versao_do_snapshot()
    regravar = "  ATUALIZAR_MANIFESTO=1 python -m pytest tests/test_dbf_contrato.py"

    # Só o modo explícito escreve. Um teste que regrava o próprio gabarito numa
    # rodada normal esconde exatamente o que ele existe pra denunciar.
    if ATUALIZAR:
        _grava_manifesto(chaves, versao)
        return

    if not MANIFESTO.exists():
        pytest.fail(f"{MANIFESTO.name} não existe. Gere com:\n{regravar}")

    manifesto = json.loads(MANIFESTO.read_text(encoding="utf-8"))
    esperadas = set(manifesto["chaves"])
    versao_registrada = int(manifesto["snapshot_version"])

    novas = sorted(chaves - esperadas)
    sumidas = sorted(esperadas - chaves)

    if novas or sumidas:
        assert versao > versao_registrada, (
            f"O `dbf` mudou de forma e SNAPSHOT_VERSION continua em {versao}.\n"
            f"  campos novos:     {novas or '—'}\n"
            f"  campos removidos: {sumidas or '—'}\n\n"
            f"Suba SNAPSHOT_VERSION para {versao_registrada + 1} em "
            "frontend/db_readers/debriefing_snapshot.py, NO MESMO COMMIT. Sem isso os "
            "snapshots já gravados seguem sendo servidos ao template novo e /debriefing "
            "devolve 500 em todo lançamento que já tenha snapshot.\n"
            f"Depois:\n{regravar}"
        )
        pytest.fail(  # bump veio junto — só falta o manifesto acompanhar
            f"O `dbf` mudou e SNAPSHOT_VERSION subiu junto ({versao_registrada} -> {versao}), "
            "que é o certo.\n"
            f"  campos novos:     {novas or '—'}\n"
            f"  campos removidos: {sumidas or '—'}\n\n"
            f"Falta registrar isso no manifesto:\n{regravar}"
        )

    if versao != versao_registrada:
        pytest.fail(
            f"SNAPSHOT_VERSION mudou ({versao_registrada} -> {versao}) sem o `dbf` mudar de forma.\n"
            "Se foi proposital (mudou o *conteúdo* de um campo sem mudar o nome, por exemplo), "
            f"registre no manifesto:\n{regravar}"
        )


def test_template_nao_le_campo_que_ninguem_produz():
    """Todo `dbf.x` do template tem que existir no dicionário do produtor.

    Campo que ninguém produz não estoura 500 quando o template tem guarda
    (`{% if dbf.x %}`): ele só cai calado no ramo do "não configurado" pra
    sempre. Foi o caso de `oferta_preco_parcelado`, que nasceu assim."""
    chaves = chaves_do_dbf()
    lidos = campos_lidos_nos_templates()
    orfaos = {campo: sorted(set(arqs)) for campo, arqs in lidos.items() if campo not in chaves}

    assert not orfaos, (
        "Template lê campo do `dbf` que o produtor não devolve:\n"
        + "\n".join(f"  dbf.{campo}  <- {', '.join(arqs)}" for campo, arqs in sorted(orfaos.items()))
        + f"\n\nOu acrescente o campo ao `return` do {FUNCAO} "
        "(frontend/services/debriefing.py), ou tire a referência do template. "
        "Com guarda no template, isso não quebra a página — só exibe o valor errado calado."
    )
