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
    """Varre docs/performance/ atras de qualquer MUDANCAS_<CODIGO>.md.

    O codigo vem do NOME do arquivo, nao da pasta — assim lancamento
    (lancamentos/PES-SET-26/), distribuicao (distribuicao/) e perpetuo
    convivem sem o importador precisar saber da estrutura de pastas.
    """
    todos = []
    base = os.path.join(RAIZ, "docs", "performance")
    if not os.path.isdir(base):
        return todos
    for raiz, _dirs, arquivos in os.walk(base):
        for nome in sorted(arquivos):
            if not (nome.startswith("MUDANCAS_") and nome.endswith(".md")):
                continue
            codigo = nome[len("MUDANCAS_"):-len(".md")]
            todos += ler_itens(os.path.join(raiz, nome), codigo)
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



FONTES = {
    "meta":   ("meta_ads_daily", "spend", "leads"),
    "google": ("google_ads_daily", "cost", "conversions"),
}


def _janela(conn, tab, cc, cv, codigo, ini, fim):
    r = conn.execute(text(
        "select coalesce(sum(%s),0), coalesce(sum(%s),0) from %s "
        "where lancamento_codigo=:c and date>=:i and date<=:f" % (cc, cv, tab)),
        {"c": codigo, "i": ini, "f": fim}).one()
    return float(r[0]), float(r[1])


def _delta(a, b):
    if not a:
        return None
    return (b - a) / a * 100


def medir(eng, dias, aplicar):
    """Preenche contexto_metrica: como as metricas se moveram em volta da acao.

    NAO e prova de causa — varias acoes dividem o mesmo dia, e a janela captura
    tudo que mudou no periodo. Por isso vai numa coluna separada do `resultado`,
    que continua sendo texto escrito por gente.
    """
    import datetime
    with eng.connect() as c:
        evs = c.execute(text(
            "select id, codigo, data, plataforma from eventos_trafego order by codigo, data")
        ).mappings().all()
    print("%d eventos a medir (janela de %d dias)" % (len(evs), dias))

    atualizacoes = []
    with eng.connect() as c:
        for e in evs:
            d = e["data"]
            ia, fa = d - datetime.timedelta(days=dias), d - datetime.timedelta(days=1)
            id_, fd = d, d + datetime.timedelta(days=dias - 1)
            plats = (["meta", "google"] if e["plataforma"] in ("ambas", "outro", None)
                     else [e["plataforma"]])
            ga = ca = gd = cd = 0.0
            for pl in plats:
                if pl not in FONTES:
                    continue
                tab, cc, cv = FONTES[pl]
                x = _janela(c, tab, cc, cv, e["codigo"], ia, fa)
                y = _janela(c, tab, cc, cv, e["codigo"], id_, fd)
                ga += x[0]; ca += x[1]; gd += y[0]; cd += y[1]
            if not ga and not gd:
                continue
            # Guarda contra percentual sem sentido: no inicio do lancamento a
            # janela "antes" e quase zero e qualquer variacao vira +40000%.
            # Melhor dizer que nao ha base do que publicar um numero enganoso.
            if ga < 500 or ca < 10:
                atualizacoes.append({"id": e["id"],
                                     "t": "sem base de comparacao (periodo anterior quase sem volume)"})
                continue
            cpa_a = ga / ca if ca else None
            cpa_d = gd / cd if cd else None
            partes = []
            for rot, va, vb in (("gasto", ga, gd), ("conv", ca, cd), ("CPA", cpa_a, cpa_d)):
                if va is None or vb is None:
                    continue
                p = _delta(va, vb)
                if p is None:
                    continue
                partes.append("%s %+.0f%%" % (rot, p))
            if not partes:
                continue
            # Variacao acima de 300% nao e "efeito da acao", e mudanca de
            # patamar (campanha ligando, etapa virando). Reportar "+42570%"
            # daria a um numero sem sentido a aparencia de medicao.
            extremos = [abs(_delta(va, vb) or 0) for va, vb in
                        ((ga, gd), (ca, cd)) if va]
            if extremos and max(extremos) > 300:
                txt = "mudanca de patamar no periodo (nao comparavel)"
            else:
                txt = " · ".join(partes) + " (janela %dd, %s)" % (dias, "+".join(plats))
            atualizacoes.append({"id": e["id"], "t": txt})

    print("  com dado suficiente: %d" % len(atualizacoes))
    if atualizacoes[:3]:
        print("  exemplo:", atualizacoes[0]["t"])
    if not aplicar:
        print("  Simulacao — nada gravado. Use --aplicar.")
        return 0
    with eng.begin() as c:
        for u in atualizacoes:
            c.execute(text("update eventos_trafego set contexto_metrica=:t, "
                           "atualizado_em=now() where id=:id"), u)
    print("  gravados.")
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
    ap.add_argument("--medir", action="store_true",
                    help="preenche contexto_metrica (antes x depois da data)")
    ap.add_argument("--dias", type=int, default=3, help="janela da medicao (padrao 3)")
    a = ap.parse_args()

    load_dotenv()
    eng = create_engine(os.environ["SUPABASE_DB_URL"])
    if a.criar_tabela:
        criar_tabela(eng)
    if a.medir:
        return medir(eng, a.dias, a.aplicar)
    if a.importar:
        return importar(eng, a.aplicar)
    if a.listar:
        return listar(eng, a.listar)
    if not a.criar_tabela:
        ap.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
