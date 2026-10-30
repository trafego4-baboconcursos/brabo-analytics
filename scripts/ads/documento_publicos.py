"""Documento de públicos de um lançamento: campanha → conjunto/grupo → inclui / exclui, Facebook (Meta) + Google (YouTube).

    python -m scripts.ads.documento_publicos PES-NOV-26            # só o que está ativo
    python -m scripts.ads.documento_publicos PES-NOV-26 --todas    # inclui pausados
    python -m scripts.ads.documento_publicos PES-NOV-26 --saida -  # imprime em vez de gravar

Grava `docs/performance/lancamentos/<LANC>/PUBLICOS_<LANC>.md`, lido direto das plataformas (só leitura). Roda na
criação das campanhas (passo do fluxo de subida no MANUAL_OPERACAO_ADS) e de novo a cada mudança de público: o arquivo
é sobrescrito, não se edita à mão. Cada campanha sai com a conferência da regra SEG-4 (`scripts/ads/publicos.py`).
"""
from __future__ import annotations

import argparse
import datetime as dt
import sys
from pathlib import Path

from scripts.ads import padroes as P
from scripts.ads.publicos import conferir_adset_meta, problemas_publico, produto_do_nome, lancamento_do_nome, \
    publicos_grupos_google, publicos_meta, sujeito_a_regra

RAIZ = Path(__file__).resolve().parents[2]


# ---------------------------------------------------------------------------- funções puras (testadas)
def _celula(itens: list[str]) -> str:
    return "<br>".join(i.replace("|", "\\|") for i in itens) if itens else "—"


def nomes_unicos(publicos: dict[str, str]) -> list[str]:
    """{id: nome} → nomes em ordem; nome repetido (públicos diferentes, mesmo nome) leva o ID para não parecer duplicado."""
    contagem: dict[str, int] = {}
    for n in publicos.values():
        contagem[n] = contagem.get(n, 0) + 1
    return sorted(f"{n} ({i})" if contagem[n] > 1 else n for i, n in publicos.items())


def interesses_meta(targeting: dict) -> tuple[list[str], list[str]]:
    """Interesses/comportamentos do `flexible_spec` (inclusão) e de `exclusions` (exclusão)."""
    def nomes(blocos: list[dict]) -> list[str]:
        return sorted({f"Interesse: {x.get('name', x.get('id'))}" for b in blocos for v in b.values()
                       if isinstance(v, list) for x in v if isinstance(x, dict)})
    exc = targeting.get("exclusions") or {}
    return nomes(targeting.get("flexible_spec") or []), nomes([exc] if exc else [])


def linha_adset_meta(adset: dict, publicos: dict[str, tuple[str, int | None]]) -> dict:
    t = adset.get("targeting") or {}
    nome = lambda a: a.get("name") or publicos.get(a["id"], (a["id"],))[0]
    inc_int, exc_int = interesses_meta(t)
    return {"nome": adset.get("name", adset.get("id")), "status": adset.get("effective_status", ""),
            "inclui": nomes_unicos({a["id"]: nome(a) for a in t.get("custom_audiences", [])}) + inc_int,
            "exclui": nomes_unicos({a["id"]: nome(a) for a in t.get("excluded_custom_audiences", [])}) + exc_int}


def documento_md(lancamento: str, secoes: list[tuple[str, list[dict]]], gerado_em: dt.datetime, todas: bool) -> str:
    """`secoes`: [(título, [campanha])]; campanha = {nome, id, status, linhas [{nome, status, inclui, exclui}],
    problemas [str], sujeita (bool)}."""
    n_prob = sum(len(c["problemas"]) for _, cs in secoes for c in cs)
    out = [
        "---",
        f'titulo: "Públicos por campanha — {lancamento}"',
        "area: lancamento",
        "status: vigente",
        f"atualizado: {gerado_em:%Y-%m-%d}",
        "responde:",
        f'  - "publicos de cada campanha do {lancamento}"',
        f'  - "o que cada conjunto e grupo do {lancamento} inclui e exclui"',
        f'  - "listas de publico e exclusoes do {lancamento} no facebook e no youtube"',
        "relacionados:",
        f'  - "[[MUDANCAS_{lancamento}]]"',
        '  - "[[REGRAS_DECISAO]]"',
        '  - "[[MANUAL_OPERACAO_ADS]]"',
        '  - "[[INDICE_PERFORMANCE]]"',
        "---",
        "",
        f"# Públicos por campanha — {lancamento}",
        "",
        f"> Gerado em {gerado_em:%d/%m/%y %Hh%M} por `python -m scripts.ads.documento_publicos {lancamento}"
        f"{' --todas' if todas else ''}`, direto das plataformas"
        f" ({'campanhas e conjuntos ativos e pausados' if todas else 'só campanhas e conjuntos ativos'}).",
        "> **Não editar à mão:** depois de mexer em público, rodar o comando de novo.",
        f"> Conferência da regra SEG-4 ([[REGRAS_DECISAO]]): **{n_prob} problema(s)**"
        f"{'' if not n_prob else ', listados embaixo de cada campanha'}. Lembrete, depoimento e distribuição ficam fora da regra.",
        "",
    ]
    for titulo, campanhas in secoes:
        out += [f"## {titulo}", ""]
        if not campanhas:
            out += ["Nenhuma campanha.", ""]
            continue
        for c in campanhas:
            out += [f"### {c['nome']}", "",
                    f"ID `{c['id']}` · {c['status']} · {len(c['linhas'])} conjunto(s)/grupo(s)", ""]
            if c["linhas"]:
                col_status = todas
                out.append("| Conjunto / grupo |" + (" Status |" if col_status else "") + " Inclui | Exclui |")
                out.append("|---|" + ("---|" if col_status else "") + "---|---|")
                for ln in c["linhas"]:
                    out.append(f"| {ln['nome'].replace('|', chr(92) + '|')} |" + (f" {ln['status']} |" if col_status else "")
                               + f" {_celula(ln['inclui'])} | {_celula(ln['exclui'])} |")
                out.append("")
            if not c["sujeita"]:
                out += ["SEG-4: fora da regra (não é captação nem pré-quali).", ""]
            elif c["problemas"]:
                out += ["**SEG-4 — problemas:**", *[f"- {p}" for p in c["problemas"]], ""]
            else:
                out += ["SEG-4: ok.", ""]
    return "\n".join(out).rstrip() + "\n"


# ---------------------------------------------------------------------------- leitura das plataformas
def secao_meta(m, lancamento: str, todas: bool) -> list[dict]:
    from scripts.ads.conferir import CONTAS_META
    out = []
    for conta in CONTAS_META:
        pubs = None
        for c in sorted(m.campanhas(conta, lancamento), key=lambda c: c["name"]):
            if lancamento_do_nome(c["name"]) != lancamento.upper():
                continue
            if not todas and c["effective_status"] != "ACTIVE":
                continue
            pubs = pubs if pubs is not None else publicos_meta(m, conta)
            adsets = [s for s in m.adsets(c["id"]) if todas or s.get("effective_status") == "ACTIVE"]
            adsets.sort(key=lambda s: s.get("name", ""))
            out.append({"nome": c["name"], "id": c["id"], "status": c["effective_status"],
                        "linhas": [linha_adset_meta(s, pubs) for s in adsets],
                        "problemas": [p for s in adsets for p in conferir_adset_meta(s, c["name"], pubs)],
                        "sujeita": sujeito_a_regra(c["name"])})
    return out


def secao_google(g, lancamento: str, todas: bool) -> list[dict]:
    out = []
    for conta in P.GOOGLE_CONTAS.values():
        for c in sorted(g.campanhas(conta, lancamento), key=lambda c: c["name"]):
            if lancamento_do_nome(c["name"]) != lancamento.upper():
                continue
            if not todas and c["status"] != "ENABLED":
                continue
            nome_c = c["name"]
            produto = produto_do_nome(nome_c)
            aluno = ((P.ALUNOS_POR_PRODUTO.get(produto) or {}).get("google") or {}).get(conta)
            grupos = sorted(publicos_grupos_google(g, conta, c["id"], todos=todas), key=lambda x: x["nome"])
            probs = []
            if sujeito_a_regra(nome_c):
                for gr in grupos:
                    if gr["status"] != "ENABLED":
                        continue
                    if not gr["tem_publico"] and "[frio]" not in nome_c.lower():
                        probs.append(f"{gr['nome']}: sem público (nem agrupado nem lista) — confirmar que não roda aberto")
                    probs += problemas_publico(gr["nome"], frio="[frio]" in nome_c.lower(), incluidos=gr["incluidos"],
                                               excluidos=gr["excluidos"], aluno_id=aluno,
                                               lancamento=lancamento_do_nome(nome_c), produto=produto,
                                               tamanhos=gr["tamanhos"])
            tipo = c.get("advertisingChannelType", "")
            out.append({"nome": nome_c, "id": c["id"],
                        "status": f"{c['status']} · {tipo}" + (" (só pela interface)" if tipo == "VIDEO" else ""),
                        "linhas": [{"nome": gr["nome"], "status": gr["status"],
                                    "inclui": nomes_unicos(gr["incluidos"]) + sorted(gr["segmentos"]),
                                    "exclui": nomes_unicos(gr["excluidos"])} for gr in grupos],
                        "problemas": probs, "sujeita": sujeito_a_regra(nome_c)})
    return out


# ---------------------------------------------------------------------------- linha de comando
def main() -> int:
    from scripts.ads.google import Google
    from scripts.ads.meta import Meta

    ap = argparse.ArgumentParser()
    ap.add_argument("lancamento")
    ap.add_argument("--todas", action="store_true", help="inclui campanhas/conjuntos/grupos pausados")
    ap.add_argument("--saida", help="caminho do .md ('-' imprime); padrão docs/performance/lancamentos/<LANC>/")
    a = ap.parse_args()
    lanc = a.lancamento.upper()
    secoes = [("Facebook (Meta)", secao_meta(Meta(), lanc, a.todas)),
              ("Google (YouTube)", secao_google(Google(), lanc, a.todas))]
    md = documento_md(lanc, secoes, dt.datetime.now(), a.todas)
    if a.saida == "-":
        print(md)
        return 0
    destino = Path(a.saida) if a.saida else RAIZ / "docs" / "performance" / "lancamentos" / lanc / f"PUBLICOS_{lanc}.md"
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(md, encoding="utf-8")
    n_c = sum(len(cs) for _, cs in secoes)
    n_p = sum(len(c["problemas"]) for _, cs in secoes for c in cs)
    print(f"{destino} — {n_c} campanha(s), {n_p} problema(s) SEG-4")
    indice = RAIZ / "docs" / "performance" / "INDICE_PERFORMANCE.md"
    if indice.exists() and f"[[PUBLICOS_{lanc}]]" not in indice.read_text(encoding="utf-8"):
        print(f"Falta linkar [[PUBLICOS_{lanc}]] na linha do lançamento em INDICE_PERFORMANCE.md (senão o check_docs reprova).")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
