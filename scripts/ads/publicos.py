"""Conferência de público (regra SEG-4) em todos os conjuntos/grupos de um lançamento, Meta + Google, só leitura.

    python -m scripts.ads.publicos PES-NOV-26
    python -m scripts.ads.publicos PI-NOV-26 --todas      # inclui pausadas

Por conjunto (Meta) e por grupo (Google), reprova quando:
- não exclui a lista de alunos do produto, ou a inclui;
- não exclui os cadastrados do lançamento atual, ou os inclui;
- campanha de frio tem público próprio (lista, site, engajamento) na inclusão — só semelhante é frio;
- inclui público de outro produto (PES = só TJ-SP);
- inclui lista com menos de PUBLICO_MINIMO pessoas (grupo que não entrega);
- exclui um público semelhante (tira milhões de pessoas parecidas com o aluno do alcance — caso do PBB-AGO-26).
A conferência é contra a regra, nunca contra o lançamento anterior (o erro do PES-NOV-26 veio copiado do SET).
Também roda dentro de `python -m scripts.ads.conferir`.
"""
from __future__ import annotations

import argparse
import re
import sys

from scripts.ads import padroes as P
from scripts.ads.meta import expert_do_nome

PRODUTO_POR_EXPERT = {v: k for k, v in P.EXPERT_POR_PREFIXO.items()}
_SEMELHANTE = ("SEMELHANTE", "SIMILAR", "LOOKALIKE")


# ---------------------------------------------------------------------------- funções puras (testadas)
def sujeito_a_regra(nome_campanha: str) -> bool:
    """SEG-4 vale para captação/cadastro e pré-qualificação. Lembrete, depoimento, reabertura e afins miram
    cadastrado/aluno de propósito e ficam de fora."""
    n = nome_campanha.lower()
    return any(k in n for k in ("[cadastro]", "capta", "pré-qualifica", "pre-qualifica"))


def produto_do_nome(nome: str) -> str | None:
    e = expert_do_nome(nome)
    return PRODUTO_POR_EXPERT.get(e) if e else None


def lancamento_do_nome(nome: str) -> str | None:
    m = re.search(r"\[((?:PES|PI|PBB)-[A-Z]{3}-\d{2}|BV-\d{2})\]", nome.upper())
    return m.group(1) if m else None


def eh_cadastrado_do_lancamento(nome_publico: str, lancamento: str) -> bool:
    n = nome_publico.upper()
    return "CADASTR" in n and lancamento.upper() in n


def eh_semelhante(nome_publico: str) -> bool:
    return any(s in nome_publico.upper() for s in _SEMELHANTE)


def de_outro_produto(nome_publico: str, produto: str) -> str | None:
    n = nome_publico.upper()
    for outro, marcas in P.MARCAS_PRODUTO.items():
        if outro == produto:
            continue
        if any(re.search(rf"(?<![A-Z]){re.escape(m)}(?![A-Z])", n) for m in marcas):
            return outro
    return None


def problemas_publico(nome: str, *, frio: bool, incluidos: dict[str, str], excluidos: dict[str, str],
                      aluno_id: str | None, lancamento: str | None, produto: str | None,
                      tamanhos: dict[str, int | None]) -> list[str]:
    """`incluidos`/`excluidos`: {id: nome}. `tamanhos`: {id: pessoas ou None quando desconhecido}."""
    out = []
    if not aluno_id:
        out.append(f"{nome}: lista de alunos do produto {produto or '?'} não definida em padroes.ALUNOS_POR_PRODUTO")
    else:
        if aluno_id in incluidos:
            out.append(f"{nome}: INCLUI a lista de alunos ({incluidos[aluno_id]})")
        if aluno_id not in excluidos:
            out.append(f"{nome}: não exclui alunos do produto")
    if lancamento:
        if not any(eh_cadastrado_do_lancamento(n, lancamento) for n in excluidos.values()):
            out.append(f"{nome}: não exclui cadastrados do {lancamento}")
        inc_cad = [n for n in incluidos.values() if eh_cadastrado_do_lancamento(n, lancamento)]
        if inc_cad:
            out.append(f"{nome}: INCLUI cadastrados do próprio lançamento ({', '.join(inc_cad)})")
    if frio:
        quentes = [n for n in incluidos.values() if not eh_semelhante(n)]
        if quentes:
            out.append(f"{nome}: frio com {len(quentes)} público(s) próprio(s) na inclusão ({', '.join(quentes[:4])}"
                       f"{'…' if len(quentes) > 4 else ''}) — deveriam ser exclusão")
    semelhantes_excluidos = [n for n in excluidos.values() if eh_semelhante(n)]
    if semelhantes_excluidos:
        out.append(f"{nome}: exclui público semelhante ({', '.join(semelhantes_excluidos)}) — semelhante não é exclusão")
    if produto:
        outros = [f"{n} ({o})" for n in incluidos.values() if (o := de_outro_produto(n, produto))]
        if outros:
            out.append(f"{nome}: inclui público de outro produto: {', '.join(outros)}")
    pequenos = [i for i in incluidos if tamanhos.get(i) is not None and tamanhos[i] < P.PUBLICO_MINIMO]
    if pequenos:
        nomes = ", ".join(f"{incluidos[i]} ({tamanhos[i]})" for i in pequenos)
        if len(pequenos) == len(incluidos):
            out.append(f"{nome}: NÃO ENTREGA — todo o público incluído tem menos de {P.PUBLICO_MINIMO} pessoas: {nomes}")
        else:
            out.append(f"{nome}: lista(s) vazia(s)/< {P.PUBLICO_MINIMO} dentro do público (não derruba o grupo; limpar): {nomes}")
    return out


# ---------------------------------------------------------------------------- leitura das plataformas
def publicos_meta(m, conta: str) -> dict[str, tuple[str, int | None]]:
    """{id: (nome, tamanho aproximado)} dos públicos personalizados da conta."""
    out = {}
    for a in m.listar(f"{conta}/customaudiences", fields="id,name,approximate_count_lower_bound", limit=500):
        n = a.get("approximate_count_lower_bound")
        out[a["id"]] = (a.get("name", ""), int(n) if n is not None and int(n) >= 0 else None)
    return out


def conferir_adset_meta(adset: dict, nome_campanha: str, publicos: dict[str, tuple[str, int | None]]) -> list[str]:
    if not sujeito_a_regra(nome_campanha):
        return []
    t = adset.get("targeting") or {}
    nome = f"{adset.get('name', adset.get('id'))}"
    produto = produto_do_nome(nome_campanha)
    inc = {a["id"]: a.get("name") or publicos.get(a["id"], ("?",))[0] for a in t.get("custom_audiences", [])}
    exc = {a["id"]: a.get("name") or publicos.get(a["id"], ("?",))[0] for a in t.get("excluded_custom_audiences", [])}
    return problemas_publico(
        nome, frio="[frio]" in nome_campanha.lower(), incluidos=inc, excluidos=exc,
        aluno_id=(P.ALUNOS_POR_PRODUTO.get(produto) or {}).get("meta"),
        lancamento=lancamento_do_nome(nome_campanha), produto=produto,
        tamanhos={i: publicos[i][1] if i in publicos else None for i in inc})


def _listas_google(g, conta: str) -> dict[str, tuple[str, int]]:
    cache = g.__dict__.setdefault("_listas_cache", {})
    if conta not in cache:
        cache[conta] = {r["userList"]["id"]: (r["userList"]["name"], max(int(r["userList"].get("sizeForDisplay") or 0),
                                                                          int(r["userList"].get("sizeForSearch") or 0)))
                        for r in g.buscar(conta, """SELECT user_list.id, user_list.name, user_list.size_for_display,
                            user_list.size_for_search FROM user_list""")}
    return cache[conta]


def publicos_grupos_google(g, conta: str, campanha_id: str) -> list[dict]:
    """Por grupo ativo: {nome, incluidos {id: nome}, excluidos {id: nome}, tamanhos {id: n}, tem_publico}.
    Público agrupado: inclusão/exclusão dentro do Audience. Sem ele: user_list do grupo + negativos da campanha."""
    listas = _listas_google(g, conta)
    uid = lambda rn: rn.split("/")[-1]
    grupos = {r["adGroup"]["id"]: {"nome": r["adGroup"]["name"], "incluidos": {}, "excluidos": {}, "tem_publico": False}
              for r in g.buscar(conta, f"""SELECT ad_group.id, ad_group.name FROM ad_group
                  WHERE campaign.id = {campanha_id} AND ad_group.status = 'ENABLED'""")}
    neg_camp = {uid(r["campaignCriterion"]["userList"]["userList"]) for r in g.buscar(conta, f"""SELECT
        campaign_criterion.user_list.user_list FROM campaign_criterion WHERE campaign.id = {campanha_id}
        AND campaign_criterion.type = 'USER_LIST' AND campaign_criterion.negative = TRUE""")}
    auds = {}
    for r in g.buscar(conta, f"""SELECT ad_group.id, ad_group_criterion.type, ad_group_criterion.negative,
            ad_group_criterion.audience.audience, ad_group_criterion.user_list.user_list FROM ad_group_criterion
            WHERE campaign.id = {campanha_id} AND ad_group_criterion.type IN ('AUDIENCE', 'USER_LIST')"""):
        gr = grupos.get(r["adGroup"]["id"])
        if not gr:
            continue
        c = r["adGroupCriterion"]
        if c["type"] == "AUDIENCE":
            auds[r["adGroup"]["id"]] = c["audience"]["audience"]
        elif not auds.get(r["adGroup"]["id"]):   # user_list solto só vale sem público agrupado
            alvo = gr["excluidos"] if c.get("negative") else gr["incluidos"]
            alvo[uid(c["userList"]["userList"])] = None
            gr["tem_publico"] |= not c.get("negative")
    for gid, gr in grupos.items():
        if gid in auds:
            gr["incluidos"], gr["excluidos"], gr["tem_publico"] = {}, {}, True
            a = g.buscar(conta, f"""SELECT audience.dimensions, audience.exclusion_dimension FROM audience
                WHERE audience.resource_name = '{auds[gid]}'""")[0]["audience"]
            for d in a.get("dimensions", []):
                for s in (d.get("audienceSegments") or {}).get("segments", []):
                    if "userList" in s:
                        gr["incluidos"][uid(s["userList"]["userList"])] = None
            for e in (a.get("exclusionDimension") or {}).get("exclusions", []):
                if "userList" in e:
                    gr["excluidos"][uid(e["userList"]["userList"])] = None
        else:
            gr["excluidos"].update({i: None for i in neg_camp})
        for k in ("incluidos", "excluidos"):
            gr[k] = {i: listas.get(i, (f"lista {i}", None))[0] for i in gr[k]}
        gr["tamanhos"] = {i: listas[i][1] if i in listas else None for i in gr["incluidos"]}
    return list(grupos.values())


def conferir_campanha_google(g, conta: str, campanha: dict) -> list[str]:
    nome_c = campanha["name"]
    if not sujeito_a_regra(nome_c):
        return []
    produto = produto_do_nome(nome_c)
    aluno = ((P.ALUNOS_POR_PRODUTO.get(produto) or {}).get("google") or {}).get(conta)
    out = []
    for gr in publicos_grupos_google(g, conta, campanha["id"]):
        if not gr["tem_publico"] and "[frio]" not in nome_c.lower():
            out.append(f"{gr['nome']}: sem público (nem agrupado nem lista) — confirmar que não roda aberto")
        out += problemas_publico(gr["nome"], frio="[frio]" in nome_c.lower(), incluidos=gr["incluidos"],
                                 excluidos=gr["excluidos"], aluno_id=aluno, lancamento=lancamento_do_nome(nome_c),
                                 produto=produto, tamanhos=gr["tamanhos"])
    return out


# ---------------------------------------------------------------------------- linha de comando
def main() -> int:
    from scripts.ads.conferir import CONTAS_META
    from scripts.ads.google import Google
    from scripts.ads.meta import Meta

    ap = argparse.ArgumentParser()
    ap.add_argument("lancamento")
    ap.add_argument("--todas", action="store_true", help="inclui campanhas/conjuntos pausados")
    a = ap.parse_args()
    total = 0
    m = Meta()
    for conta in CONTAS_META:
        pubs = None
        for c in m.campanhas(conta, a.lancamento):
            if not a.todas and c["effective_status"] != "ACTIVE":
                continue
            pubs = pubs if pubs is not None else publicos_meta(m, conta)
            probs = []
            for s in m.adsets(c["id"]):
                if a.todas or s.get("effective_status") == "ACTIVE":
                    probs += conferir_adset_meta(s, c["name"], pubs)
            total += len(probs)
            print(f"[{'OK' if not probs else '!!'}] Meta {c['name']}")
            for p in probs:
                print(f"      - {p}")
    g = Google()
    for conta in P.GOOGLE_CONTAS.values():
        for c in g.campanhas(conta, a.lancamento):
            if not a.todas and c["status"] != "ENABLED":
                continue
            probs = conferir_campanha_google(g, conta, c)
            total += len(probs)
            print(f"[{'OK' if not probs else '!!'}] Google {c['name']}")
            for p in probs:
                print(f"      - {p}")
    print(f"\n{total} problema(s) de público.")
    return 1 if total else 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
