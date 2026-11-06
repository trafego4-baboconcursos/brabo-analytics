"""Carga inicial dos cadastros do comercial a partir das planilhas de 2026.

    python scripts/comercial_carga_inicial.py --pasta analises/comercial/extraido --dry-run
    python scripts/comercial_carga_inicial.py --pasta analises/comercial/extraido --gravar

As planilhas têm dados pessoais e não vão para o git; o caminho vem por argumento.
`--dry-run` conta e não grava; `--gravar` cria as tabelas comercial_* e carrega os cadastros
numa transação só (idempotente; só toca comercial_*). `cadastros_da_planilha(pasta)` monta
tudo em memória, sem banco.
"""
from __future__ import annotations

import argparse
import re
import sys
import unicodedata
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from frontend.services.comercial.modelos import Cadastros  # noqa: E402
from frontend.services.comercial.regras import extrair_codigo_at  # noqa: E402
from frontend.services.comercial.tabelas import (  # noqa: E402
    Participacao, RegraPercentual, ValorBase, categorias_ordenadas,
)

VIGENTE_DE = date(2026, 1, 1)

# codigo, nome, ativo
VENDEDORES = [
    ("AT4", "Ediléia", True), ("AT9", "Jheniffer", True), ("AT11", "Priscila", True),
    ("AT12", "Rafael Batista", False), ("AT13", "Izabela", True),
]
CODIGO_POR_NOME = {"Ediléia": "AT4", "Jheniffer": "AT9", "Priscila": "AT11",
                   "Rafael Batista": "AT12", "Rafael": "AT12", "Izabela": "AT13"}

_PLATAFORMA = {"Hotmart Aprovasim": "hotmart", "Hotmart Brabo Editora": "hotmart", "TMB": "tmb"}


def _norm(txt) -> str:
    s = unicodedata.normalize("NFKD", str(txt or "")).encode("ascii", "ignore").decode()
    return " ".join(s.lower().split())


def _col(df: pd.DataFrame, nome: str) -> str:
    """Coluna do DataFrame cujo nome casa com `nome` sem acento/caixa."""
    alvo = _norm(nome)
    for c in df.columns:
        if _norm(c) == alvo:
            return c
    raise KeyError(f"coluna '{nome}' não encontrada em {list(df.columns)}")


def _dec(v) -> Decimal:
    """'89.90', '89,90', '2.998,80', '1.477' (milhar) e '(ATENÇÃO) 1477' -> Decimal finito.

    Vazio/NaN/None levantam ValueError (quem chama decide se pula a linha).
    """
    if v is None or (not isinstance(v, str) and pd.isna(v)):
        raise ValueError("valor vazio")
    t = re.sub(r"^\(.*?\)\s*", "", str(v).strip()).replace(" ", "")
    if not t or t.lower() == "nan":
        raise ValueError("valor vazio")
    if "," in t:  # formato brasileiro: ponto = milhar, vírgula = decimal
        t = t.replace(".", "").replace(",", ".")
    elif re.fullmatch(r"[1-9]\d{0,2}(\.\d{3})+", t):  # '1.477' = milhar
        t = t.replace(".", "")
    try:
        d = Decimal(t)
    except InvalidOperation as e:
        raise ValueError(f"valor numérico inválido: {v!r}") from e
    if not d.is_finite():
        raise ValueError(f"valor não finito: {v!r}")
    return d


def ler_valores_a_preencher(df: pd.DataFrame) -> list[dict]:
    """Linhas da aba 'VALORES A PREENCHER' -> dicts (plataforma, valor_cobrado, valor_base, categoria)."""
    cp, cv, cb, cc = (_col(df, n) for n in ("Plataforma", "Valor_Plataforma",
                                            "Valor_Base_Comissao", "Categoria"))
    out = []
    for idx, r in df.iterrows():
        nome = str(r[cp]).strip()
        if nome not in _PLATAFORMA:
            raise ValueError(f"plataforma desconhecida na planilha: {nome!r}")
        if _norm(r[cb]) == "nao tem":  # sem base definida na planilha: fica de fora (busca devolve None)
            continue
        try:
            cobrado, base = _dec(r[cv]), _dec(r[cb])
        except ValueError as e:
            if "vazio" not in str(e):
                raise
            print(f"AVISO: linha {idx + 2} (Excel) de VALORES A PREENCHER com valor em branco; ignorada",
                  file=sys.stderr)
            continue
        cat = r[cc]
        out.append({
            "plataforma": _PLATAFORMA[nome],
            "valor_cobrado": cobrado,
            "valor_base": base,
            "categoria": "" if pd.isna(cat) else str(cat).strip(),
        })
    return out


def codigo_tmb(utm_content, utm_last_content) -> str | None:
    """Código AT do pedido TMB como o motor vê: utm_content, senão utm_last_content; os dois
    com vendedores diferentes = conflito (None), para a planilha virar atribuição manual."""
    a = extrair_codigo_at(utm_content if isinstance(utm_content, str) else None)
    b = extrair_codigo_at(utm_last_content if isinstance(utm_last_content, str) else None)
    if a and b and a != b:
        return None
    return a or b


def montar_atribuicoes(vendas: pd.DataFrame, codigo_por_transacao: dict[str, str | None],
                       codigo_por_nome: dict[str, str]) -> dict[str, str]:
    """transação -> código do vendedor, só onde a planilha difere do código da venda ou a venda não tem código.

    `vendas` tem as colunas `transacao` e `nome`. Nome fora do mapa é ignorado.
    """
    mapa = {_norm(k): v for k, v in codigo_por_nome.items()}
    out: dict[str, str] = {}
    for tr, nome in zip(vendas["transacao"], vendas["nome"]):
        codigo = mapa.get(_norm(nome))
        if not codigo or not tr:
            continue
        if codigo_por_transacao.get(tr) != codigo:
            out[tr] = codigo
    return out


def montar_ofertas(df: pd.DataFrame) -> dict[str, str]:
    """codigo_do_preco -> nome_deste_preco, só nomes com código AT.

    Código com nomes de AT diferentes é descartado (aviso); com o mesmo AT, fica o nome
    mais frequente (empate: o primeiro visto).
    """
    cc, cn = _col(df, "Código do preço"), _col(df, "Nome deste preço")
    nomes: dict[str, dict[str, int]] = {}
    for cod, nome in zip(df[cc], df[cn]):
        if not isinstance(cod, str) or not cod.strip() or not isinstance(nome, str):
            continue
        if extrair_codigo_at(nome) is None:
            continue
        conta = nomes.setdefault(cod.strip(), {})
        conta[nome.strip()] = conta.get(nome.strip(), 0) + 1
    out: dict[str, str] = {}
    for cod, conta in nomes.items():
        ats = {extrair_codigo_at(n) for n in conta}
        if len(ats) > 1:
            print(f"AVISO: código do preço {cod} com ATs diferentes {sorted(ats)}; ignorado",
                  file=sys.stderr)
            continue
        out[cod] = max(conta, key=lambda n: conta[n])  # max devolve o primeiro em empate
    return out


# ---------------------------------------------------------------- leitura das planilhas

def _um(pasta: Path, padrao: str) -> Path:
    achados = sorted(pasta.glob(padrao))
    if not achados:
        raise FileNotFoundError(f"nada em {pasta} para {padrao}")
    return achados[0]


def _valores_base_da_pasta(pasta: Path) -> list[dict]:
    arquivos = sorted(pasta.glob("**/Vendedores 2026/*.xlsx"))
    if len(arquivos) != 5:
        raise RuntimeError(f"esperava 5 planilhas de vendedor, achei {len(arquivos)}")
    tabelas = []
    for f in arquivos:
        df = pd.read_excel(f, sheet_name="VALORES A PREENCHER", dtype=str)
        tabelas.append(ler_valores_a_preencher(df))
    for f, t in zip(arquivos[1:], tabelas[1:]):
        if t != tabelas[0]:
            raise RuntimeError(f"VALORES A PREENCHER de {f.name} diverge das demais; abortando")
    return tabelas[0]


def _codigos_das_vendas(pasta: Path) -> tuple[dict[str, str | None], set[str]]:
    """(transação -> código AT, pedidos da BASE TMB)."""
    f = _um(pasta, "**/An*lise Comercial 2026/Base de Vendas Geral 2026.xlsx")
    out: dict[str, str | None] = {}
    h = pd.read_excel(f, sheet_name="BASE DE DADOS", dtype=str)
    ct, cn = _col(h, "TRANSAÇÃO"), _col(h, "Nome deste preço")
    for tr, nome in zip(h[ct], h[cn]):
        if isinstance(tr, str) and tr.strip():
            out.setdefault(tr.strip(), extrair_codigo_at(nome if isinstance(nome, str) else None))
    pedidos_tmb: set[str] = set()
    t = pd.read_excel(f, sheet_name="BASE TMB", dtype=str)
    cp, c1, c2 = _col(t, "Pedido"), _col(t, "utm_content"), _col(t, "utm_last_content")
    for pedido, a, b in zip(t[cp], t[c1], t[c2]):
        if isinstance(pedido, str) and pedido.strip():
            out.setdefault(pedido.strip(), codigo_tmb(a, b))
            pedidos_tmb.add(pedido.strip())
    return out, pedidos_tmb


def _ofertas_da_pasta(pasta: Path) -> dict[str, str]:
    f = _um(pasta, "**/An*lise Comercial 2026/Base de Vendas Geral 2026.xlsx")
    head = pd.read_excel(f, sheet_name="BASE DE DADOS", dtype=str, nrows=0)
    cols = [_col(head, "Código do preço"), _col(head, "Nome deste preço")]
    return montar_ofertas(pd.read_excel(f, sheet_name="BASE DE DADOS", dtype=str, usecols=cols))


def _vendas_consolidadas(pasta: Path) -> pd.DataFrame:
    f = _um(pasta, "**/An*lise Comercial 2026/Vendas - Por Vendedor 2026.xlsx")
    head = pd.read_excel(f, sheet_name="VENDAS", dtype=str, nrows=0)
    cols = [_col(head, n) for n in ("TRANSAÇÃO", "NOME", "Mês Ano")]
    df = pd.read_excel(f, sheet_name="VENDAS", dtype=str, usecols=cols)
    df = df[cols]
    df.columns = ["transacao", "nome", "mes_ano"]
    df = df.dropna(subset=["transacao"])
    df["transacao"] = df["transacao"].str.strip()
    return df.drop_duplicates("transacao", keep="first").reset_index(drop=True)


FIM_PARCELADO_4 = date(2026, 9, 30)    # parcelado Hotmart pagava como cartão até set/26
INICIO_PARCELADO_2 = date(2026, 10, 1)
FIM_CS_IZABELA = date(2026, 10, 31)    # condição de CS da Izabela (encerrada)
CS = frozenset({"CROSS SELL", "UP SELL"})


def categorias_apostila(valores: list[ValorBase]) -> frozenset[str]:
    """Categorias de apostila da Hotmart na tabela de valores-base ("APOSTILA ...")."""
    return frozenset(v.categoria for v in valores
                     if v.plataforma == "hotmart" and _norm(v.categoria).startswith("apostila"))


def _regras(apostilas: frozenset[str] = frozenset()) -> list[RegraPercentual]:
    """Regras do time + históricas (decisões de 06/11/26, §9 do plano).

    Tupla: plataforma, modalidade, tipo, pct, vendedor, vigente_de, vigente_ate, categorias, forca_tipo.
    """
    D = Decimal
    ini = VIGENTE_DE
    base = [
        ("hotmart", "cartao_pix", "Ativa", D("0.04"), None, ini, None, None, None),
        ("hotmart", "cartao_pix", "Reativa", D("0.015"), None, ini, None, None, None),
        # Recorrência Garantida / boleto parcelado Hotmart: 4% / 1,5% até 30/09/26, 2% / 0,75% depois
        ("hotmart", "parcelado", "Ativa", D("0.04"), None, ini, FIM_PARCELADO_4, None, None),
        ("hotmart", "parcelado", "Reativa", D("0.015"), None, ini, FIM_PARCELADO_4, None, None),
        ("hotmart", "parcelado", "Ativa", D("0.02"), None, INICIO_PARCELADO_2, None, None, None),
        ("hotmart", "parcelado", "Reativa", D("0.0075"), None, INICIO_PARCELADO_2, None, None, None),
        ("tmb", "parcelado", "Ativa", D("0.02"), None, ini, None, None, None),
        ("tmb", "parcelado", "Reativa", D("0.0075"), None, ini, None, None, None),
        ("hotmart", "cartao_pix", "Ativa", D("0.02"), "AT12", ini, None, None, None),
        ("hotmart", "cartao_pix", "Reativa", D("0.008"), "AT12", ini, None, None, None),
        ("hotmart", "parcelado", "Ativa", D("0.01"), "AT12", ini, None, None, None),
        ("hotmart", "parcelado", "Reativa", D("0.004"), "AT12", ini, None, None, None),
        ("tmb", "parcelado", "Ativa", D("0.01"), "AT12", ini, None, None, None),
        ("tmb", "parcelado", "Reativa", D("0.004"), "AT12", ini, None, None, None),
        # condição de CS da Izabela (AT13), encerrada em 31/10/26: sempre Ativa
        ("tmb", "parcelado", "Ativa", D("0.04"), "AT13", ini, FIM_CS_IZABELA, CS, "Ativa"),
        ("hotmart", "cartao_pix", "Ativa", D("0.04"), "AT13", ini, FIM_CS_IZABELA, CS, "Ativa"),
        ("hotmart", "parcelado", "Ativa", D("0.04"), "AT13", ini, FIM_PARCELADO_4, CS, "Ativa"),
        ("hotmart", "parcelado", "Ativa", D("0.02"), "AT13", INICIO_PARCELADO_2, FIM_CS_IZABELA, CS, "Ativa"),
    ]
    if apostilas:
        base += [
            ("hotmart", "cartao_pix", "Ativa", D("0.05"), "AT13", ini, FIM_CS_IZABELA, apostilas, "Ativa"),
            ("hotmart", "parcelado", "Ativa", D("0.05"), "AT13", ini, FIM_CS_IZABELA, apostilas, "Ativa"),
        ]
    return [RegraPercentual(i, p, m, t, pct, v, de, ate, cats, forca)
            for i, (p, m, t, pct, v, de, ate, cats, forca) in enumerate(base, 1)]


def _montar(pasta: Path) -> tuple[Cadastros, pd.DataFrame, set[str]]:
    valores = [ValorBase(i, v["plataforma"], v["valor_cobrado"], v["valor_base"],
                         v["categoria"], VIGENTE_DE, None)
               for i, v in enumerate(_valores_base_da_pasta(pasta), 1)]
    vendas = _vendas_consolidadas(pasta)
    codigos, pedidos_tmb = _codigos_das_vendas(pasta)
    atrib = montar_atribuicoes(vendas, codigos, CODIGO_POR_NOME)
    cad = Cadastros(
        vendedores={c: n for c, n, _ in VENDEDORES},
        regras=_regras(categorias_apostila(valores)),
        valores_base=valores,
        participacoes=[Participacao(1, "Rafael Batista", Decimal("0.003"), Decimal("0.001"),
                                    VIGENTE_DE, None, "AT12")],
        atribuicoes=atrib,
        ofertas=_ofertas_da_pasta(pasta),
    )
    return cad, vendas, pedidos_tmb


def cadastros_da_planilha(pasta: str | Path) -> Cadastros:
    """Mesma montagem da carga, em memória (sem banco)."""
    return _montar(Path(pasta))[0]


# ---------------------------------------------------------------- gravação

# acessos decididos em 06/11/26 (e-mail sempre em minúsculas)
ACESSOS = [("comercial_brabo@aprovasim.com", "master"), ("comercial2@aprovasim.com", "coordenador")]
TABELAS = ["comercial_vendedores", "comercial_regras_percentual", "comercial_valores_base",
           "comercial_participacoes", "comercial_ofertas", "comercial_atribuicoes", "comercial_acessos"]


def _insert_multiplo(tabela: str, colunas: list[str], linhas: list[dict]) -> tuple[str, dict]:
    """Um INSERT ... VALUES (..),(..) ON CONFLICT DO NOTHING com parâmetros nomeados
    `<coluna>_<i>` (uma ida ao banco por tabela)."""
    valores = ",".join("(" + ",".join(f":{c}_{i}" for c in colunas) + ")" for i in range(len(linhas)))
    sql = f"INSERT INTO {tabela} ({', '.join(colunas)}) VALUES {valores} ON CONFLICT DO NOTHING"
    return sql, {f"{c}_{i}": l[c] for i, l in enumerate(linhas) for c in colunas}


def linhas_para_gravar(cad: Cadastros, pedidos_tmb) -> dict[str, tuple[list[str], list[dict]]]:
    """{tabela: (colunas, linhas)} na ordem de gravação."""
    ativo = {c: a for c, _, a in VENDEDORES}
    sem_id = lambda o: {k: v for k, v in o.__dict__.items() if k != "id"}  # noqa: E731
    return {
        "comercial_vendedores": (["codigo", "nome", "ativo"],
                                 [{"codigo": c, "nome": n, "ativo": ativo.get(c, True)}
                                  for c, n in cad.vendedores.items()]),
        "comercial_regras_percentual": (
            ["plataforma", "modalidade", "tipo", "pct", "vendedor_codigo", "vigente_de", "vigente_ate",
             "categorias", "forca_tipo"],
            # categorias ordenado: a chave natural compara o array elemento a elemento
            [{**sem_id(r), "categorias": categorias_ordenadas(r.categorias)}
             for r in cad.regras]),
        "comercial_valores_base": (
            ["plataforma", "valor_cobrado", "valor_base", "categoria", "vigente_de", "vigente_ate"],
            [sem_id(v) for v in cad.valores_base]),
        "comercial_participacoes": (
            ["beneficiario", "pct_ativa", "pct_reativa", "vigente_de", "vigente_ate", "beneficiario_codigo"],
            [sem_id(p) for p in cad.participacoes]),
        "comercial_ofertas": (["codigo_do_preco", "nome_deste_preco", "codigo_at", "origem"],
                              [{"codigo_do_preco": cp, "nome_deste_preco": n,
                                "codigo_at": extrair_codigo_at(n), "origem": "planilha"}
                               for cp, n in cad.ofertas.items()]),
        "comercial_atribuicoes": (["plataforma", "transacao", "vendedor_codigo", "origem", "status"],
                                  [{"plataforma": "tmb" if tr in pedidos_tmb else "hotmart",
                                    "transacao": tr, "vendedor_codigo": cod,
                                    "origem": "planilha", "status": "aprovada"}
                                   for tr, cod in cad.atribuicoes.items()]),
        "comercial_acessos": (["email", "nivel", "criado_por"],
                              [{"email": e.strip().lower(), "nivel": n, "criado_por": "carga_inicial"}
                               for e, n in ACESSOS]),
    }


def gravar(cad: Cadastros, pedidos_tmb: frozenset[str] | set[str] = frozenset(),
           engine=None) -> dict[str, tuple[int, int]]:
    """Cria as comercial_* e grava os cadastros, tudo numa transação só, idempotente
    (ON CONFLICT DO NOTHING sobre a chave natural; ids vêm do banco). Antes do DDL confere as
    colunas das comercial_* existentes (aborta se divergirem). Toda instrução passa pela guarda
    `exigir_so_comercial`. Um INSERT multi-linha por tabela; a contagem vem do total da
    tabela antes/depois. `pedidos_tmb` decide a plataforma das atribuições.

    `acesso.limpar_cache()` no fim só limpa o cache deste processo (o CLI); o painel, que é
    outro processo, enxerga os acessos novos quando o cache dele expira (TTL de 60 s).

    Devolve {tabela: (inseridas, já existiam)}."""
    from sqlalchemy import text
    from frontend.db_readers.comercial import criar_tabelas, exigir_so_comercial
    from frontend.services.comercial import acesso

    if engine is None:
        from frontend.db import _get_users_engine
        engine = _get_users_engine()

    def run(conn, sql: str, params: dict | None = None):
        exigir_so_comercial(sql)
        return conn.execute(text(sql), params or {})

    contagem: dict[str, tuple[int, int]] = {}
    with engine.begin() as conn:
        criar_tabelas(conn)
        for tabela, (colunas, linhas) in linhas_para_gravar(cad, pedidos_tmb).items():
            if tabela not in TABELAS:
                raise RuntimeError(f"tabela inesperada: {tabela}")
            if not linhas:
                contagem[tabela] = (0, 0)
                continue
            antes = run(conn, f"SELECT count(*) FROM {tabela}").scalar_one()
            run(conn, *_insert_multiplo(tabela, colunas, linhas))
            depois = run(conn, f"SELECT count(*) FROM {tabela}").scalar_one()
            contagem[tabela] = (depois - antes, len(linhas) - (depois - antes))
    acesso.limpar_cache()
    return contagem


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--pasta", required=True)
    modo = ap.add_mutually_exclusive_group()
    modo.add_argument("--dry-run", action="store_true", help="conta, não grava")
    modo.add_argument("--gravar", action="store_true",
                      help="cria as comercial_* e grava os cadastros (idempotente)")
    a = ap.parse_args()
    if not (a.dry_run or a.gravar):
        ap.print_usage(sys.stderr)
        print("escolha --dry-run ou --gravar", file=sys.stderr)
        return 2
    cad, vendas, pedidos_tmb = _montar(Path(a.pasta))
    if a.gravar:
        r = gravar(cad, pedidos_tmb)
        from frontend.services.comercial.snapshot import marcar_desatualizado
        try:
            marcar_desatualizado()
        except Exception as exc:  # cadastro já gravado; o snapshot some pelo dia/ETL
            print(f"aviso: não marcou os snapshots como desatualizados: {exc}", file=sys.stderr)
        print(f"{'tabela':<30}{'inseridas':>10}{'já existiam':>13}")
        for t, (novas, ja) in r.items():
            print(f"{t:<30}{novas:>10}{ja:>13}")
        return 0
    outubro = vendas[vendas["mes_ano"].fillna("").map(_norm) == _norm("10 - Outubro")]
    n_out = sum(1 for t in outubro["transacao"] if t in cad.atribuicoes)
    mapa = {_norm(k) for k in CODIGO_POR_NOME}
    sem_mapa = sorted({n for n in vendas["nome"].dropna().unique() if _norm(n) not in mapa})
    print(f"vendedores={len(cad.vendedores)} regras={len(cad.regras)} "
          f"participacoes={len(cad.participacoes)} valores_base={len(cad.valores_base)} "
          f"atribuicoes={len(cad.atribuicoes)} (outubro={n_out}) ofertas={len(cad.ofertas)} "
          f"acessos={len(ACESSOS)}")
    n_tmb = int(vendas["transacao"].isin(pedidos_tmb).sum())
    print(f"vendas da aba VENDAS encontradas em BASE TMB por Pedido: {n_tmb} de {len(vendas)} "
          f"(BASE TMB tem {len(pedidos_tmb)} pedidos)")
    print(f"vendas na aba VENDAS (únicas): {len(vendas)}; nomes fora do mapa: {sem_mapa or 'nenhum'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
