# -*- coding: utf-8 -*-
"""
Indexa os diarios de mudanca na tabela eventos_trafego.

POR QUE: o diario (.md) e a narrativa legivel por gente; o banco tem a metrica.
Sem um indice legivel por maquina, cruzar acao com resultado depende de parsear
titulo de markdown — fragil, e inutil pro dashboard. Cada item do diario vira
uma linha aqui, com escopo (lancamento/perpetuo/distribuicao), produto e expert.

    python scripts/eventos.py --criar-tabela     # cria a tabela (idempotente)
    python scripts/eventos.py --importar         # simula a importacao dos .md
    python scripts/eventos.py --importar --aplicar
    python scripts/eventos.py --listar PES-SET-26

Reimportar nao duplica: a chave e codigo + hash do titulo.
"""
import argparse
import hashlib
import io
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
from sqlalchemy import create_engine, text

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DIR_LANC = os.path.join(RAIZ, "docs", "performance", "lancamentos")

RE_DATA = re.compile(r"\((\d{2})/(\d{2})/(\d{2})\)")
RE_REGRA = re.compile(r"\b((?:ORC|CPA|SEG|META|VER)-\d+)\b")

PRODUTO = {"PBB": "PBB", "PES": "PES", "PI": "PI"}
EXPERT_POR_PRODUTO = {"PBB": "Felipe Graton", "PES": "Ivan Neto", "PI": "Mateus Andrade"}

# palavra-chave -> tipo. Ordem importa: a primeira que casar vence.
TIPOS = [
    ("orcamento", ("orçament", "orcament", "verba", "budget", "investiment")),
    ("cpa",       ("cpa", "target_cpa", "lance", "bid")),
    ("pausa",     ("pausad", "pausar", "pausa ", "desativ", "encerr")),
    ("ativacao",  ("ativad", "ativar", "ativaç", "reativ", "subir no ar")),
    ("criativo",  ("criativo", "anúncio", "anuncio", "ad0", "ad1", "ad2", "ad3",
                   "ad4", "ad5", "ad6", "ad7", "vídeo", "video", "carrossel", "copy")),
    ("publico",   ("público", "publico", "audience", "lookalike", "segmenta",
                   "cascat", "lista", "customer match")),
    ("estrutura", ("campanha criada", "criada", "criadas", "duplic", "estrutura",
                   "grupo", "ad set", "renomea")),
    ("analise",   ("análise", "analise", "levantamento", "diagnóstico", "confront",
                   "auditoria", "fechamento")),
]


def escopo_de(codigo):
    if codigo.startswith("DISTRIBUICAO-"):
        return "distribuicao"
    if codigo.startswith("PERPETUO-"):
        return "perpetuo"
    return "lancamento"


def produto_de(codigo):
    if codigo.startswith(("DISTRIBUICAO-", "PERPETUO-")):
        for p in PRODUTO:
            if p in codigo:
                return p
        return "PERPETUO" if codigo.startswith("PERPETUO") else None
    return PRODUTO.get(codigo.split("-")[0])


def expert_de(codigo):
    if codigo.startswith("DISTRIBUICAO-"):
        return codigo.replace("DISTRIBUICAO-", "").replace("-", " ").title()
    return EXPERT_POR_PRODUTO.get(produto_de(codigo) or "")


def classificar(titulo):
    t = titulo.lower()
    for tipo, chaves in TIPOS:
        if any(k in t for k in chaves):
            return tipo
    return "outro"


def plataforma_de(titulo):
    t = titulo.lower()
    m = any(k in t for k in ("meta", "facebook", "instagram", "reels", "ad set"))
    g = any(k in t for k in ("google", "youtube", "shorts", "demand gen", "search", "pmax"))
    if m and g:
        return "ambas"
    if m:
        return "meta"
    if g:
        return "google"
    return "outro"


RE_H2_DATA = re.compile(r"^## (\d{4})-(\d{2})-(\d{2})")


def ler_itens(caminho, codigo):
    """Extrai os '### ' do diario, ignorando o bloco de sumario gerado.

    A data vem do titulo quando ele traz "(DD/MM/AA)" (padrao do PES-SET-26)
    ou, quando nao traz, do cabecalho "## YYYY-MM-DD" acima dele (padrao do
    PBB-AGO-26 e do PI-AGO-26). Sem o fallback, dois dos tres diarios ficavam
    de fora inteiros.
    """
    eventos = []
    no_sumario = False
    data_secao = None
    pendente = None   # (dict do evento, linhas do corpo)

    def fechar():
        if pendente:
            ev, corpo = pendente
            texto = ev["titulo"] + " " + " ".join(corpo[:12])
            ev["plataforma"] = plataforma_de(texto)
            if ev["tipo"] == "outro":
                ev["tipo"] = classificar(texto)
            if not ev["regra"]:
                m = RE_REGRA.search(texto)
                ev["regra"] = m.group(1) if m else None
            eventos.append(ev)

    for linha in io.open(caminho, encoding="utf-8"):
        if "SUMARIO:INICIO" in linha:
            no_sumario = True
            continue
        if "SUMARIO:FIM" in linha:
            no_sumario = False
            continue
        if no_sumario:
            continue

        h2 = RE_H2_DATA.match(linha)
        if h2:
            data_secao = "-".join(h2.groups())
            continue

        if linha.startswith("### "):
            fechar()
            pendente = None
            titulo = linha[4:].strip()
            m = RE_DATA.search(titulo)
            if m:
                d, mo, a = m.groups()
                data = "20%s-%s-%s" % (a, mo, d)
            elif data_secao:
                data = data_secao
            else:
                continue
            chave = "%s#%s" % (codigo, hashlib.sha1(titulo.encode("utf-8")).hexdigest()[:12])
            ev = {
                "chave": chave, "data": data, "escopo": escopo_de(codigo), "codigo": codigo,
                "produto": produto_de(codigo), "expert": expert_de(codigo),
                "plataforma": None, "tipo": classificar(titulo), "titulo": titulo,
                "regra": None,
                "fonte": os.path.relpath(caminho, RAIZ).replace(os.sep, "/"),
            }
            pendente = (ev, [])
        elif pendente and linha.strip():
            pendente[1].append(linha.strip())

    fechar()
    return eventos


def coletar():
    todos = []
    if not os.path.isdir(DIR_LANC):
        return todos
    for codigo in sorted(os.listdir(DIR_LANC)):
        d = os.path.join(DIR_LANC, codigo)
        if not os.path.isdir(d):
            continue
        for nome in sorted(os.listdir(d)):
            if nome.startswith("MUDANCAS_") and nome.endswith(".md"):
                todos += ler_itens(os.path.join(d, nome), codigo)
    return todos


def criar_tabela(eng):
    ddl = io.open(os.path.join(RAIZ, "etl", "schema.sql"), encoding="utf-8").read()
    i = ddl.index("CREATE TABLE IF NOT EXISTS eventos_trafego")
    bloco = ddl[i:]
    # Tira os comentarios ANTES de separar por ";" — ha ponto-e-virgula dentro
    # de comentario no DDL, e o split ingenuo cortava a tabela no meio.
    limpo = chr(10).join(l.split("--")[0] for l in bloco.split(chr(10)))
    with eng.begin() as c:
        for stmt in [x.strip() for x in limpo.split(";") if x.strip()]:
            c.execute(text(stmt))
    print("tabela eventos_trafego criada/confirmada")


def importar(eng, aplicar):
    evs = coletar()
    print("\n%d itens datados encontrados nos diarios" % len(evs))
    if not evs:
        return 0
    from collections import Counter
    print("\n  por lancamento:")
    for k, n in Counter(e["codigo"] for e in evs).most_common():
        print("    %-14s %3d" % (k, n))
    print("\n  por tipo:")
    for k, n in Counter(e["tipo"] for e in evs).most_common():
        print("    %-12s %3d" % (k, n))
    print("\n  por plataforma:")
    for k, n in Counter(e["plataforma"] for e in evs).most_common():
        print("    %-12s %3d" % (k, n))
    com_regra = sum(1 for e in evs if e["regra"])
    print("\n  com ID de regra citado: %d de %d" % (com_regra, len(evs)))

    if not aplicar:
        print("\n  Simulacao — nada gravado. Use --aplicar.\n")
        return 0

    sql = text("""
        INSERT INTO eventos_trafego
            (chave, data, escopo, codigo, produto, expert, plataforma, tipo,
             titulo, regra, fonte)
        VALUES (:chave, :data, :escopo, :codigo, :produto, :expert, :plataforma,
                :tipo, :titulo, :regra, :fonte)
        ON CONFLICT (chave) DO UPDATE SET
            data = EXCLUDED.data, tipo = EXCLUDED.tipo,
            plataforma = EXCLUDED.plataforma, regra = EXCLUDED.regra,
            titulo = EXCLUDED.titulo, fonte = EXCLUDED.fonte,
            atualizado_em = NOW()
    """)
    with eng.begin() as c:
        for e in evs:
            c.execute(sql, e)
        n = c.execute(text("select count(*) from eventos_trafego")).scalar()
    print("\n  gravados. Total na tabela: %d\n" % n)
    return 0


def listar(eng, codigo):
    with eng.connect() as c:
        rows = c.execute(text("""
            select data, tipo, plataforma, coalesce(regra,'-') regra, titulo
            from eventos_trafego where codigo = :c order by data, id
        """), {"c": codigo}).mappings().all()
    print("\n%d eventos em %s\n" % (len(rows), codigo))
    for r in rows:
        print("  %s  %-10s %-7s %-6s %s" % (r["data"], r["tipo"], r["plataforma"],
                                            r["regra"], r["titulo"][:70]))
    return 0


def main():
    ap = argparse.ArgumentParser(description="Indexa diarios em eventos_trafego")
    ap.add_argument("--criar-tabela", action="store_true")
    ap.add_argument("--importar", action="store_true")
    ap.add_argument("--aplicar", action="store_true", help="grava (senao, simula)")
    ap.add_argument("--listar", metavar="CODIGO")
    a = ap.parse_args()

    load_dotenv()
    eng = create_engine(os.environ["SUPABASE_DB_URL"])
    if a.criar_tabela:
        criar_tabela(eng)
    if a.importar:
        return importar(eng, a.aplicar)
    if a.listar:
        return listar(eng, a.listar)
    if not a.criar_tabela:
        ap.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
