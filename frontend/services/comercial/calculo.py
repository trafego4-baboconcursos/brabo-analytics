"""Motor de cálculo da comissão do time comercial (puro: sem banco, sem rede).

Dinheiro em Decimal, sem arredondar por linha (a planilha soma base x % crua).
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from frontend.services.comercial.modelos import Cadastros, Venda
from frontend.services.comercial.regras import Janela, situacao, tipo_venda
from frontend.services.comercial.tabelas import (
    BASE_TMB_POR_CATEGORIA,
    buscar_valor_base,
    escolher_percentual,
    participacoes_vigentes,
)

_ZERO = Decimal("0")
_SEM_VENDEDOR = "(sem vendedor)"


@dataclass(frozen=True)
class LinhaComissao:
    transacao: str
    plataforma: str
    papel: str  # "venda" | "participacao"
    beneficiario: str
    vendedor_codigo: str | None
    data: datetime
    tipo: str | None
    modalidade: str
    categoria: str | None
    valor_base: Decimal | None
    pct: Decimal | None
    valor: Decimal
    situacao: str  # elegivel | prevista | cancelada | inconsistente
    motivo: str | None
    regra_id: int | None
    atribuicao_manual: bool


def _nome_vendedor(codigo: str | None, cad: Cadastros) -> str:
    if not codigo:
        return _SEM_VENDEDOR
    nome = cad.vendedores.get(codigo)
    if nome:
        return nome
    m = re.search(r"\d+", codigo)
    return f"Vendedor {int(m.group())}" if m else codigo


def _vendedor(venda: Venda, cad: Cadastros) -> tuple[str | None, bool, str | None]:
    """(codigo, atribuicao_manual, motivo_de_inconsistencia)."""
    aprovado = cad.atribuicoes.get(venda.transacao)
    if aprovado:
        return aprovado, True, None
    if venda.conflito_codigo:
        return venda.codigo_at, False, "conflito_codigo"
    if not venda.codigo_at:
        return None, False, "sem_codigo"
    return venda.codigo_at, False, None


def _base(venda: Venda, cad: Cadastros, dia) -> tuple[Decimal | None, str | None]:
    """Valor-base e categoria: tabela primeiro; TMB cai na base fixa por categoria."""
    achado = buscar_valor_base(cad.valores_base, venda.plataforma, venda.valor_cobrado, dia)
    if achado:
        return achado.valor_base, achado.categoria
    if venda.plataforma == "tmb" and venda.categoria in BASE_TMB_POR_CATEGORIA:
        return BASE_TMB_POR_CATEGORIA[venda.categoria], venda.categoria
    return None, venda.categoria


def _linha_venda(venda: Venda, cad: Cadastros, tipo: str, sit: str, dia) -> LinhaComissao:
    codigo, manual, motivo = _vendedor(venda, cad)
    base, categoria = _base(venda, cad, dia)
    regra = None
    if motivo is None:
        if base is None:
            motivo = "sem_valor_base"
        else:
            regra = escolher_percentual(cad.regras, venda.plataforma, venda.modalidade,
                                        tipo, codigo, dia)
            if regra is None:
                motivo = "sem_regra"
    pct = regra.pct if regra else None
    if motivo is not None:
        situacao_final, valor = "inconsistente", _ZERO
    elif sit == "cancelada":
        situacao_final, valor = "cancelada", _ZERO
    else:
        situacao_final, valor = sit, base * pct
    return LinhaComissao(
        transacao=venda.transacao, plataforma=venda.plataforma, papel="venda",
        beneficiario=_nome_vendedor(codigo, cad), vendedor_codigo=codigo, data=venda.data,
        tipo=tipo, modalidade=venda.modalidade, categoria=categoria, valor_base=base,
        pct=pct, valor=valor, situacao=situacao_final, motivo=motivo,
        regra_id=regra.id if regra else None, atribuicao_manual=manual,
    )


def _linhas_participacao(venda: Venda, cad: Cadastros, linha: LinhaComissao,
                         dia) -> list[LinhaComissao]:
    saida = []
    for p in participacoes_vigentes(cad.participacoes, dia):
        if p.beneficiario_codigo is not None:
            if p.beneficiario_codigo == linha.vendedor_codigo:
                continue
        elif p.beneficiario == linha.beneficiario:
            continue
        pct = p.pct_ativa if linha.tipo == "Ativa" else p.pct_reativa
        saida.append(LinhaComissao(
            transacao=venda.transacao, plataforma=venda.plataforma, papel="participacao",
            beneficiario=p.beneficiario, vendedor_codigo=linha.vendedor_codigo,
            data=venda.data, tipo=linha.tipo, modalidade=venda.modalidade,
            categoria=linha.categoria, valor_base=linha.valor_base, pct=pct,
            valor=linha.valor_base * pct, situacao=linha.situacao, motivo=None,
            regra_id=p.id, atribuicao_manual=linha.atribuicao_manual,
        ))
    return saida


def calcular(vendas: list[Venda], cad: Cadastros, janelas: list[Janela],
             hoje: datetime) -> list[LinhaComissao]:
    linhas: list[LinhaComissao] = []
    for venda in vendas:
        sit = situacao(venda.pago, venda.data, venda.cancelada_em, hoje)
        if sit == "nao_paga":
            continue
        tipo = tipo_venda(venda.plataforma, venda.produto_id, venda.produto, venda.data, janelas)
        dia = venda.data.date()
        linha = _linha_venda(venda, cad, tipo, sit, dia)
        linhas.append(linha)
        if linha.situacao in ("elegivel", "prevista"):
            linhas.extend(_linhas_participacao(venda, cad, linha, dia))
    return linhas


def resumo_por_beneficiario(linhas: list[LinhaComissao]) -> dict[str, dict[str, Decimal]]:
    resumo: dict[str, dict[str, Decimal]] = {}
    for l in linhas:
        if l.situacao not in ("elegivel", "prevista"):
            continue
        r = resumo.setdefault(l.beneficiario, {"Ativa": _ZERO, "Reativa": _ZERO, "total": _ZERO,
                                               "elegivel": _ZERO, "prevista": _ZERO})
        r[l.tipo] += l.valor
        r["total"] += l.valor
        r[l.situacao] += l.valor
    return resumo
