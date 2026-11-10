"""Tela Desempenho da área Comercial — serviço puro (sem banco): comparação, agregação, view-model.

O isolamento da vendedora mora AQUI, como em `telas.py`: tudo que é por vendedora/produto/evolução
é agregado só sobre as linhas dela. O time inteiro entra apenas como números gerais (vendido, vendas,
ticket, meta do time) e como denominador da contribuição — só o quociente vai para ela.
A atendente IA (Camila, papel "ia") nunca entra em time, meta, contribuição nem ranking: bloco `ia`,
só para gestor.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal

from frontend.services.comercial import snapshot as _snap
from frontend.services.comercial import telas
from frontend.services.comercial.acesso import AcessoComercial
from frontend.services.comercial.calculo import PAPEL_IA, LinhaComissao
from frontend.services.comercial.fechamento import e_a_verificar_de_fechado
from frontend.services.comercial.meses import PRIMEIRO_MES, soma_meses, ultimo_dia
from frontend.services.comercial.telas import (
    COM_VALOR, LIMITE_PERIODO_DIAS, Periodo, PeriodoInvalido, _dia_de, _mes_de, _pct_meta,
    _periodo_mes, _so_meu, e_gestor, ranking)

_ZERO = Decimal("0")
SEM_PRODUTO = "—"
_Q = Decimal("0.001")


# ---------------------------------------------------------------- carga
def carregar_linhas(periodo: Periodo) -> list[LinhaComissao]:
    return telas.carregar(periodo).linhas


def carregar_acumulado(periodo: Periodo, *, store=None) -> tuple[list[LinhaComissao], datetime | None]:
    """Linhas de 01/01 do ano de `periodo.fim` até `periodo.fim` + o `gerado_em` mais antigo usado.
    Meses anteriores ao do fim: o que estiver guardado (mesmo velho); só calcula o que não existe
    (~20 s/mês). O mês do fim sempre por `obter_mes`: é o que a tela mostra."""
    fim = periodo.fim
    mes_fim = fim.replace(day=1)
    mes = max(date(fim.year, 1, 1), PRIMEIRO_MES)
    linhas: list[LinhaComissao] = []
    desde: datetime | None = None
    while mes <= mes_fim:
        r = None if mes == mes_fim else _snap.ler_guardado(mes, store=store)
        if r is None:
            r = _snap.obter_mes(mes, store=store)
        linhas.extend(l for l in r.linhas if l.data.date() <= fim)
        g = r.gerado_em
        if g is not None and g.tzinfo is not None:  # congelado vem timestamptz; o resto é SP naive
            g = g.astimezone(_snap._SP).replace(tzinfo=None)
        if g is not None and (desde is None or g < desde):
            desde = g
        mes = soma_meses(mes, 1)
    return linhas, desde


# ---------------------------------------------------------------- comparação
@dataclass(frozen=True)
class Comparacao:
    periodo: Periodo
    corte: date | None   # só no mês corrente: compara "até o mesmo dia" do mês de referência
    rotulo: str


def _comparacao(periodo: Periodo, comp: Periodo, hoje: date) -> Comparacao:
    corte = None
    if not periodo.livre and not comp.livre and periodo.mes == hoje.replace(day=1):
        corte = min(comp.mes + timedelta(days=hoje.day - 1), ultimo_dia(comp.mes))
    rotulo = f"{comp.rotulo} (1–{corte.day})" if corte else comp.rotulo
    return Comparacao(comp, corte, rotulo)


def resolver_comparacao(periodo: Periodo, comparar: str | None, cinicio: str | None, cfim: str | None,
                        hoje: date, *, gestor: bool) -> Comparacao | None:
    """Padrão: mês -> mês anterior; livre -> mesmos N dias imediatamente antes. `comparar=AAAA-MM`
    escolhe o mês; `cinicio/cfim` (só gestor, até LIMITE_PERIODO_DIAS) um intervalo. Sem base -> None."""
    if (cinicio or "").strip() or (cfim or "").strip():
        if not gestor:
            raise PeriodoInvalido("Comparação livre é só para gestores. Escolha um mês.")
        ini, fi = _dia_de(cinicio), _dia_de(cfim)
        if not ini or not fi:
            raise PeriodoInvalido("Comparação livre precisa de data de início e de fim válidas.")
        if fi < ini:
            raise PeriodoInvalido("Na comparação livre, a data final vem antes da inicial.")
        if (fi - ini).days + 1 > LIMITE_PERIODO_DIAS:
            raise PeriodoInvalido(f"Comparação livre de no máximo {LIMITE_PERIODO_DIAS} dias.")
        return _comparacao(periodo, Periodo(ini, fi, None), hoje)
    if (comparar or "").strip():
        m = _mes_de(comparar)
        if m is None:
            raise PeriodoInvalido("Mês de comparação inválido: use o formato AAAA-MM.")
        if not (PRIMEIRO_MES <= m <= hoje.replace(day=1)):
            raise PeriodoInvalido(
                f"Mês de comparação fora do intervalo disponível ({PRIMEIRO_MES:%m/%Y} até o mês atual).")
        return _comparacao(periodo, _periodo_mes(m), hoje)
    if periodo.livre:
        n = (periodo.fim - periodo.inicio).days + 1
        fim_c = periodo.inicio - timedelta(days=1)
        ini_c = fim_c - timedelta(days=n - 1)
        if ini_c < PRIMEIRO_MES:
            return None
        return _comparacao(periodo, Periodo(ini_c, fim_c, None), hoje)
    ant = soma_meses(periodo.mes, -1)
    if ant < PRIMEIRO_MES:
        return None
    return _comparacao(periodo, _periodo_mes(ant), hoje)


# ---------------------------------------------------------------- agregação
def variacao(atual: Decimal | int | None, anterior: Decimal | int | None) -> Decimal | None:
    """(atual ÷ anterior) − 1, três casas; sem base (None ou 0) -> None."""
    if atual is None or not anterior:
        return None
    return ((Decimal(atual) / Decimal(anterior)) - 1).quantize(_Q, rounding=ROUND_HALF_UP)


def _conta(l: LinhaComissao, corte: date | None) -> bool:
    if l.situacao not in COM_VALOR or e_a_verificar_de_fechado(l):
        return False
    return corte is None or l.data.date() <= corte


def _soma_prod(d: dict, produto: str, v: Decimal) -> None:
    d[produto] = d.get(produto, _ZERO) + v


def agregar(linhas: list[LinhaComissao], corte: date | None = None) -> dict:
    """Só venda com valor (COM_VALOR, sem a-verificar de mês fechado) e código de vendedora; a IA
    vira bloco `ia` à parte. `corte`: ignora vendas depois desse dia."""
    time = {"qtd": 0, "vendido": _ZERO}
    vendedores: dict[str, dict] = {}
    produtos: dict[str, dict] = {}
    ia = {"qtd": 0, "vendido": _ZERO, "por_produto": {}}
    dias: dict[date, Decimal] = {}
    for l in linhas:
        if not _conta(l, corte):
            continue
        v = l.valor_base or _ZERO
        prod = l.produto or SEM_PRODUTO
        if l.papel == PAPEL_IA:
            ia["qtd"] += 1
            ia["vendido"] += v
            _soma_prod(ia["por_produto"], prod, v)
            continue
        if l.papel != "venda" or not l.vendedor_codigo:
            continue
        time["qtd"] += 1
        time["vendido"] += v
        ven = vendedores.setdefault(l.vendedor_codigo, {"nome": l.beneficiario, "qtd": 0, "vendido": _ZERO,
                                                         "por_produto": {}})
        ven["qtd"] += 1
        ven["vendido"] += v
        _soma_prod(ven["por_produto"], prod, v)
        p = produtos.setdefault(prod, {"qtd": 0, "vendido": _ZERO, "por_vendedor": {}})
        p["qtd"] += 1
        p["vendido"] += v
        _soma_prod(p["por_vendedor"], l.vendedor_codigo, v)
        d = l.data.date()
        dias[d] = dias.get(d, _ZERO) + v
    return {"time": time, "vendedores": vendedores, "produtos": produtos, "ia": ia, "dias": dias}


# ---------------------------------------------------------------- view-model
def _ticket(vendido: Decimal, qtd: int) -> Decimal | None:
    return (vendido / qtd).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP) if qtd else None


def _razao(a: Decimal, b: Decimal | None) -> Decimal | None:
    return (a / b).quantize(_Q, rounding=ROUND_HALF_UP) if b else None


def _evolucao(dias: dict[date, Decimal], inicio: date, ate: date | None) -> list[Decimal]:
    """Vendido acumulado por índice do dia (1º, 2º…), até `ate` (ou o último dia com venda)."""
    if ate is None:
        if not dias:
            return []
        ate = max(dias)
    acum, saida, d = _ZERO, [], inicio
    while d <= ate:
        acum += dias.get(d, _ZERO)
        saida.append(acum)
        d += timedelta(days=1)
    return saida


def _isoladas(linhas: list[LinhaComissao], acesso: AcessoComercial) -> list[LinhaComissao]:
    """Gestor: tudo. Vendedora: só as vendas dela (IA e participação nunca)."""
    if e_gestor(acesso):
        return list(linhas)
    cod = acesso.vendedor_codigo
    return [l for l in linhas if cod and l.papel == "venda" and l.vendedor_codigo == cod]


def view_desempenho(atual: list[LinhaComissao], comp: list[LinhaComissao] | None,
                    comparacao: Comparacao | None, acumulado: list[LinhaComissao], periodo: Periodo,
                    acesso: AcessoComercial, metas: dict | None, *,
                    meta_time: Decimal | None = None) -> dict:
    """`metas`: por vendedora, já recortada para quem vê (`_so_meu`). `meta_time`: soma das metas de
    TODAS (lida sem recorte; vai inteira à vendedora porque é número geral do time). Período livre:
    ambas None."""
    gestor = e_gestor(acesso)
    corte = comparacao.corte if comparacao else None
    tem_comp = comparacao is not None and comp is not None

    time_a = agregar(atual)["time"]                       # time inteiro: números gerais + denominador
    time_c = agregar(comp or [], corte)["time"] if tem_comp else None
    time_ano = agregar(acumulado)["time"]

    ag_a = agregar(_isoladas(atual, acesso))
    ag_c = agregar(_isoladas(comp or [], acesso), corte) if tem_comp else None
    ag_ano = agregar(_isoladas(acumulado, acesso))
    metas_vis = _so_meu(metas, acesso) or {}

    vendido_a, qtd_a = time_a["vendido"], time_a["qtd"]
    posicao = None
    if not gestor:
        rk = ranking(atual, acesso)["linhas"]
        posicao = next((r["pos"] for r in rk if r["codigo"] == acesso.vendedor_codigo), None)
    resumo = {
        "vendido": vendido_a, "qtd": qtd_a, "ticket": _ticket(vendido_a, qtd_a),
        "meta_time": meta_time, "pct_meta_time": _pct_meta(vendido_a, meta_time),
        "posicao": posicao,
        "var_vendido": variacao(vendido_a, time_c["vendido"]) if time_c else None,
        "var_qtd": variacao(qtd_a, time_c["qtd"]) if time_c else None,
        "var_ticket": (variacao(_ticket(vendido_a, qtd_a), _ticket(time_c["vendido"], time_c["qtd"]))
                       if time_c else None),
    }

    vendedores = []
    for cod, v in ag_a["vendedores"].items():
        c = ag_c["vendedores"].get(cod) if ag_c else None
        ano = ag_ano["vendedores"].get(cod)
        meta = (metas_vis.get(cod) or {}).get("valor")
        top = max(v["por_produto"].items(), key=lambda kv: kv[1])[0] if v["por_produto"] else None
        vendedores.append({
            "codigo": cod, "nome": v["nome"], "qtd": v["qtd"], "vendido": v["vendido"],
            "ticket": _ticket(v["vendido"], v["qtd"]), "por_produto": v["por_produto"], "produto_top": top,
            "meta": meta, "pct_meta": _pct_meta(v["vendido"], meta),
            "contribuicao": _razao(v["vendido"], vendido_a),
            "contribuicao_ano": _razao(ano["vendido"] if ano else _ZERO, time_ano["vendido"]),
            "contribuicao_meta": _razao(v["vendido"], meta_time),
            "var_vendido": variacao(v["vendido"], c["vendido"]) if c else None,
            "var_qtd": variacao(v["qtd"], c["qtd"]) if c else None,
        })
    vendedores.sort(key=lambda r: (-r["vendido"], r["nome"]))

    produtos = []
    for nome, p in ag_a["produtos"].items():
        pc = ag_c["produtos"].get(nome) if ag_c else None
        produtos.append({"produto": nome, "qtd": p["qtd"], "vendido": p["vendido"],
                         "ticket": _ticket(p["vendido"], p["qtd"]), "por_vendedor": p["por_vendedor"],
                         "var_vendido": variacao(p["vendido"], pc["vendido"]) if pc else None})
    produtos.sort(key=lambda r: (-r["vendido"], r["produto"]))

    ia = None
    if gestor:
        ia_c = agregar(comp or [], corte)["ia"] if tem_comp else None
        ia = {**ag_a["ia"], "ticket": _ticket(ag_a["ia"]["vendido"], ag_a["ia"]["qtd"]),
              "var_vendido": variacao(ag_a["ia"]["vendido"], ia_c["vendido"]) if ia_c else None}

    evolucao = {"atual": _evolucao(ag_a["dias"], periodo.inicio, None), "comparacao": None}
    if tem_comp:
        evolucao["comparacao"] = _evolucao(ag_c["dias"], comparacao.periodo.inicio,
                                           corte or comparacao.periodo.fim)
    return {"periodo": periodo, "comparacao": comparacao, "gestor": gestor, "resumo": resumo,
            "vendedores": vendedores, "produtos": produtos, "ia": ia, "evolucao": evolucao,
            "meta_so_mensal": periodo.livre}
