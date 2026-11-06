"""Fechar o mês, reabrir e estorno da área Comercial (Task 7b, Ruling 17).

- **Fechar** (master/coordenador): só mês que já terminou (SP), sem nenhuma venda em
  *reembolso a verificar*. Congela as linhas de um cálculo NOVO (não o snapshot, que pode estar
  velho), o bônus de cada vendedor e os totais. Total pago do mês fechado = elegível + prevista
  + bônus: as previstas são pagas no fechamento.
- **Reabrir**: exige motivo; o mês volta a ser calculado ao vivo.
- **Estorno**: no cálculo de um mês ABERTO M, cada linha congelada (elegível/prevista, valor > 0)
  de um mês fechado C para o qual M é o primeiro mês aberto depois de C, cuja venda hoje está
  cancelada (≤ 7 dias) ou com decisão "tira", vira uma linha negativa em M — mesmo papel e
  beneficiário da original. Uma por (mês original, transação, papel, beneficiário): o estorno já
  congelado num mês fechado posterior não se repete.
"""
from __future__ import annotations

import json
import re
from dataclasses import replace
from datetime import date, datetime
from decimal import ROUND_HALF_UP, Decimal

from frontend.services.comercial.calculo import LinhaComissao, resumo_por_beneficiario
from frontend.services.comercial.modelos import Venda
from frontend.services.comercial.regras import situacao

ESTORNO = "estorno"
_PAGAS = ("elegivel", "prevista")
_ZERO = Decimal("0")
_CENTAVO = Decimal("0.01")
_RE_MOTIVO = re.compile(r"^estorno de (\d{4})-(\d{2})$")
PRIMEIRO_MES = date(2026, 1, 1)


# ---------------------------------------------------------------- meses
def soma_meses(m: date, n: int) -> date:
    t = m.year * 12 + m.month - 1 + n
    return date(t // 12, t % 12 + 1, 1)


def meses_do_estorno(mes: date, fechados) -> list[date]:
    """Meses fechados C para os quais `mes` é o primeiro mês aberto depois: a sequência de
    fechados logo antes de `mes` (do mais recente para trás, para no primeiro aberto)."""
    saida, c = [], soma_meses(mes.replace(day=1), -1)
    while c in fechados and c >= PRIMEIRO_MES:
        saida.append(c)
        c = soma_meses(c, -1)
    return saida


def meses_seguintes(mes: date, hoje: date) -> list[date] | None:
    """Meses depois de `mes` até o corrente — o estorno deles depende do estado de `mes`.
    Mais de 3 -> None (marca todos de uma vez), como regras_tela.meses_desde."""
    atual, m, saida = hoje.replace(day=1), soma_meses(mes.replace(day=1), 1), []
    while m <= atual:
        saida.append(m)
        m = soma_meses(m, 1)
    return None if len(saida) > 3 else saida


def pode_fechar_mes(mes: date, hoje: date) -> bool:
    """Só mês que já terminou: de 2026-01 até o mês anterior ao corrente (SP)."""
    return PRIMEIRO_MES <= mes.replace(day=1) < hoje.replace(day=1)


# ---------------------------------------------------------------- estorno
def motivo_estorno(mes_original: date) -> str:
    return f"estorno de {mes_original:%Y-%m}"


def mes_do_estorno(motivo: str | None) -> date | None:
    m = _RE_MOTIVO.match(motivo or "")
    return date(int(m.group(1)), int(m.group(2)), 1) if m else None


def _chave(mes_original: date, l: LinhaComissao) -> tuple:
    return (mes_original, l.transacao, l.papel, l.beneficiario)


def candidatas(congeladas: dict[date, list[LinhaComissao]]) -> list[tuple[date, LinhaComissao]]:
    """(mês original, linha) das linhas pagas congeladas que ainda não têm estorno congelado
    em nenhum dos meses fechados lidos."""
    ja = {_chave(mes_do_estorno(l.motivo), l)
          for ls in congeladas.values() for l in ls if l.situacao == ESTORNO}
    saida = []
    for c in sorted(congeladas):
        for l in congeladas[c]:
            if l.situacao in _PAGAS and l.valor > _ZERO and _chave(c, l) not in ja:
                saida.append((c, l))
    return saida


def cancelada_agora(venda: Venda, decisao: str | None, hoje: datetime) -> bool:
    """A linha congelada prova que a venda foi paga: só importa o cancelamento (≤ 7 dias) ou
    a decisão "tira" do gestor."""
    return situacao(True, venda.data, venda.cancelada_em, hoje, decisao) == "cancelada"


def estornos(cands: list[tuple[date, LinhaComissao]], vendas_atuais: dict[str, Venda],
             decisoes: dict[str, str], hoje: datetime) -> list[LinhaComissao]:
    """Linhas negativas para as candidatas cuja venda hoje está cancelada. Venda que sumiu da
    leitura não gera estorno (sem prova de cancelamento)."""
    saida, vistos = [], set()
    for c, l in cands:
        chave = _chave(c, l)
        if chave in vistos:
            continue
        v = vendas_atuais.get(l.transacao)
        if v is None or not cancelada_agora(v, decisoes.get(l.transacao), hoje):
            continue
        vistos.add(chave)
        saida.append(replace(l, valor=-l.valor, situacao=ESTORNO, motivo=motivo_estorno(c)))
    return saida


# ---------------------------------------------------------------- fechar
def a_verificar(linhas: list[LinhaComissao]) -> int:
    return sum(1 for l in linhas if l.papel == "venda" and l.situacao == "reembolso_a_verificar")


def _q(v: Decimal) -> str:
    return str(v.quantize(_CENTAVO, rounding=ROUND_HALF_UP))


def bonus_para_json(bonus: dict[str, dict]) -> str:
    return json.dumps({cod: {"valor": str(b["valor"]), "nome": b.get("nome"),
                             "justificativa": b.get("justificativa")} for cod, b in sorted(bonus.items())},
                      ensure_ascii=False)


def bonus_de_json(dados) -> dict[str, dict]:
    d = json.loads(dados) if isinstance(dados, (str, bytes)) else (dados or {})
    return {cod: {"valor": Decimal(b["valor"]), "nome": b.get("nome") or cod,
                  "justificativa": b.get("justificativa")} for cod, b in d.items()}


def totais(linhas: list[LinhaComissao], bonus: dict[str, dict]) -> dict:
    """Totais congelados (arredondados meio-para-cima só aqui). Pago = elegível (com estornos)
    + prevista + bônus, sobre as linhas de venda; participação à parte."""
    vendas = [l for l in linhas if l.papel == "venda"]
    part = [l for l in linhas if l.papel == "participacao"]
    soma = lambda ls, sits: sum((l.valor for l in ls if l.situacao in sits), _ZERO)  # noqa: E731
    eleg, prev, est = soma(vendas, ("elegivel",)), soma(vendas, ("prevista",)), soma(vendas, (ESTORNO,))
    b = sum((x["valor"] for x in bonus.values()), _ZERO)
    return {
        "elegivel": _q(eleg + est), "prevista": _q(prev), "estorno": _q(est), "bonus": _q(b),
        "total_pago": _q(eleg + est + prev + b),
        "participacao": _q(soma(part, ("elegivel", "prevista", ESTORNO))),
        "linhas": len(linhas), "vendas_pagas": sum(1 for l in vendas if l.situacao in _PAGAS),
        "por_beneficiario": {n: {k: _q(v) for k, v in r.items()}
                             for n, r in sorted(resumo_por_beneficiario(linhas).items())},
    }


def resumo_txt(t: dict) -> str:
    return (f"{t['linhas']} linhas; elegível {t['elegivel']}, prevista {t['prevista']}, "
            f"bônus {t['bonus']}, total pago {t['total_pago']}")


class AVerificar(Exception):
    """Fechar recusado: ainda há vendas em reembolso a verificar (decidir antes)."""

    def __init__(self, qtd: int):
        super().__init__(qtd)
        self.qtd = qtd


def fechar(mes: date, por: str, hoje: datetime) -> dict:
    """Recalcula o mês do zero e congela. Devolve os totais. Recusas: `mes_nao_terminou`,
    `ja_fechado` (EscritaRecusada) e AVerificar(qtd)."""
    from frontend.db_readers import comercial as com  # noqa: PLC0415
    from frontend.services.comercial import snapshot as snap  # noqa: PLC0415
    mes = mes.replace(day=1)
    if not pode_fechar_mes(mes, hoje.date()):
        raise com.EscritaRecusada("mes_nao_terminou")
    if com.mes_fechado(mes):
        raise com.EscritaRecusada("ja_fechado")
    res = snap.recalcular_mes(mes, hoje=hoje)  # cálculo novo, nunca o snapshot guardado
    n = a_verificar(res.linhas)
    if n:
        raise AVerificar(n)
    bonus = com.ler_bonus_mes(mes)
    t = totais(res.linhas, bonus)
    com.fechar_mes(mes, snap.linhas_para_json(res.linhas), bonus_para_json(bonus), json.dumps(t, ensure_ascii=False),
                   resumo_txt(t), por)
    return t


# ---------------------------------------------------------------- tela
def info_fechar(linhas: list[LinhaComissao], pendentes: int, rotulo: str) -> dict:
    """Contagens da confirmação do botão "Fechar mês" (do cálculo exibido)."""
    vendas = [l for l in linhas if l.papel == "venda"]
    previstas = sum(1 for l in vendas if l.situacao == "prevista")
    av = a_verificar(linhas)
    confirma = (f"Fechar {rotulo}? {previstas} venda(s) prevista(s) serão pagas neste fechamento e "
                f"{pendentes} inconsistência(s) pendente(s) ficam sem comissão. Depois de fechado, nada "
                "muda neste mês sem reabrir.")
    return {"previstas": previstas, "a_verificar": av, "pendentes": pendentes, "confirma": confirma}
