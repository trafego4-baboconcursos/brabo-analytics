"""Regras puras de classificação da comissão do time comercial (sem banco/rede).

Datetimes são naive, já em America/Sao_Paulo.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from datetime import date, datetime, timedelta

_RE_AT = re.compile(r"\bat\s?(\d+)", re.IGNORECASE)
_PROJETO_POR_PREFIXO = {"PI": "INSS", "PES": "TJ", "PBB": "BB"}
_DIAS_GARANTIA = 7


def _norm(texto: str | None) -> str:
    """Maiúsculo, sem acento."""
    if not texto:
        return ""
    sem_acento = unicodedata.normalize("NFKD", texto)
    return "".join(c for c in sem_acento if not unicodedata.combining(c)).upper()


def extrair_codigo_at(texto: str | None) -> str | None:
    """'COM. LEAD - AT9' -> 'AT9'; sem zero à esquerda; 'at' dentro de palavra não conta."""
    if not texto:
        return None
    m = _RE_AT.search(texto)
    return f"AT{int(m.group(1))}" if m else None


def modalidade_hotmart(tipo_de_cobranca: str | None, metodo_de_pagamento: str | None) -> str:
    """'parcelado' (parcelamento Hotmart) ou 'cartao_pix' (todo o resto)."""
    tipo = _norm(tipo_de_cobranca)
    metodo = _norm(metodo_de_pagamento)
    if "PARCELADO" in tipo or "INSTALLMENTS" in metodo:
        return "parcelado"
    return "cartao_pix"


def categoria_tmb(utm_campaign: str | None, oferta: str | None) -> str | None:
    """LEAD / CROSS SELL / UP SELL, procurando em utm_campaign e depois em oferta."""
    for texto in (utm_campaign, oferta):
        t = _norm(texto)
        for chave, categoria in (("LEAD", "LEAD"), ("CROSS", "CROSS SELL"), ("UP", "UP SELL")):
            if chave in t:
                return categoria
    return None


def projeto_do_produto(nome: str | None) -> str:
    """Espelha o project_case de frontend/db_readers/sales.py (mesma ordem)."""
    n = (nome or "").lower()
    if "black vital" in n:
        return "BLACK"
    if "inss" in n:
        return "INSS"
    if "tj" in n or "tjsp" in n or "escrevente" in n:
        return "TJ"
    if "bb" in n or "banco do brasil" in n or "bbsa" in n:
        return "BB"
    return "OUTRO"


@dataclass(frozen=True)
class Janela:
    lancamento: str
    projeto: str
    inicio: datetime
    fim: datetime
    produtos_hotmart: frozenset[str]
    produtos_tmb: frozenset[str]


def janela_reativa(lancamento: str, aulas_start: date, produtos_hotmart, produtos_tmb) -> Janela:
    """Segunda da semana de aulas_start 00:00:00 -> segunda seguinte 23:59:59."""
    segunda = aulas_start - timedelta(days=aulas_start.weekday())
    inicio = datetime(segunda.year, segunda.month, segunda.day)
    fim = inicio + timedelta(days=7, hours=23, minutes=59, seconds=59)
    prefixo = lancamento.split("-")[0].upper()
    return Janela(
        lancamento=lancamento,
        projeto=_PROJETO_POR_PREFIXO.get(prefixo, "OUTRO"),
        inicio=inicio,
        fim=fim,
        produtos_hotmart=frozenset(str(p) for p in produtos_hotmart),
        produtos_tmb=frozenset(str(p) for p in produtos_tmb),
    )


def tipo_venda(
    plataforma: str,
    produto_id: str | None,
    produto_nome: str | None,
    quando: datetime,
    janelas: list[Janela],
) -> str:
    """'Reativa' se a venda cai numa janela de aulas de produto do lançamento; senão 'Ativa'."""
    pid = str(produto_id).strip() if produto_id not in (None, "") else ""
    for j in janelas:
        if not (j.inicio <= quando <= j.fim):
            continue
        if plataforma == "hotmart":
            if pid and pid in j.produtos_hotmart:
                return "Reativa"
        elif plataforma == "tmb":
            if pid:
                if pid in j.produtos_tmb:
                    return "Reativa"
            elif projeto_do_produto(produto_nome) == j.projeto:
                return "Reativa"
    return "Ativa"


def situacao(pago: bool, data_venda: datetime, cancelada_em: datetime | None, hoje: datetime,
             decisao: str | None = None) -> str:
    """elegivel | prevista | cancelada | nao_paga | reembolso_a_verificar (garantia de 7 dias).

    Cancelada em até 7 dias -> cancelada. Cancelada depois: o banco só tem a data de conclusão
    do reembolso, não a do pedido -> `reembolso_a_verificar` até o gestor decidir
    (`decisao` "tira" -> cancelada; "mantem" -> elegível/prevista pela data).
    """
    if not pago:
        return "nao_paga"
    limite = data_venda + timedelta(days=_DIAS_GARANTIA)
    if cancelada_em is not None:
        if cancelada_em <= limite or decisao == "tira":
            return "cancelada"
        if decisao != "mantem":
            return "reembolso_a_verificar"
    return "elegivel" if hoje > limite else "prevista"
