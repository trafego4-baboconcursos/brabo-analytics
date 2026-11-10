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
- **Venda tardia** (Ruling 20): venda de um desses meses fechados C, paga hoje mas ausente das
  linhas congeladas de C (paga/ingerida depois do fechamento), entra em M calculada pela própria
  data, com motivo "venda de AAAA-MM após o fechamento". Não se repete depois que M fecha (a
  transação passa a estar num congelado).
- **Horizonte** (Ruling 21): ancorado no mês CALCULADO, não em hoje — o mesmo M dá os mesmos
  candidatos em qualquer data (o congelado de M, feito depois de M acabar, traz os estornos e as
  vendas tardias de M-1). Candidatos = os HORIZONTE_MESES meses fechados mais recentes da
  sequência de fechados logo antes de M; de meses mais antigos, só linhas com decisão "tira".
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field, replace
from datetime import date, datetime
from decimal import ROUND_HALF_UP, Decimal

from frontend.services.comercial.calculo import LinhaComissao, resumo_por_beneficiario
from frontend.services.comercial.meses import PRIMEIRO_MES, soma_meses, ultimo_dia  # noqa: F401
from frontend.services.comercial.modelos import Venda
from frontend.services.comercial.regras import situacao

ESTORNO = "estorno"
_PAGAS = ("elegivel", "prevista")
_ZERO = Decimal("0")
_CENTAVO = Decimal("0.01")
_RE_MOTIVO = re.compile(r"^estorno de (\d{4})-(\d{2})$")
# Ruling 21: estorno/venda tardia de M só dos 2 meses fechados logo antes de M (M-1, M-2, se
# ambos na sequência de fechados) + linhas de qualquer idade com decisão "tira"
HORIZONTE_MESES = 2


# ---------------------------------------------------------------- meses
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


def meses_candidatos(mes: date, fechados) -> tuple[list[date], list[date]]:
    """(no horizonte, mais antigos) da sequência de fechados logo antes de `mes`."""
    run = meses_do_estorno(mes, fechados)
    return run[:HORIZONTE_MESES], run[HORIZONTE_MESES:]


def primeiro_aberto_depois(mes: date, fechados) -> date:
    m = soma_meses(mes.replace(day=1), 1)
    while m in fechados:
        m = soma_meses(m, 1)
    return m


def tem_mes_de_efeito(mes_venda: date, fechados) -> bool:
    """Venda que NÃO está em congelado nenhum: mês aberto -> efeito nele; mês fechado -> venda
    tardia, só se esse mês é candidato do primeiro mês aberto depois dele (Ruling 21)."""
    mes_venda = mes_venda.replace(day=1)
    if mes_venda not in fechados:
        return True
    rec, _ = meses_candidatos(primeiro_aberto_depois(mes_venda, fechados), fechados)
    return mes_venda in rec


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


_RE_MOTIVO_FECHADO = re.compile(r"^venda de \d{4}-\d{2} \(fechado\)$")


def motivo_fechado(mes_original: date) -> str:
    return f"venda de {mes_original:%Y-%m} (fechado)"


def e_a_verificar_de_fechado(l: LinhaComissao) -> bool:
    """Linha-aviso da Ruling 22 (valor 0): não é venda nem dinheiro do mês, só pendência."""
    return l.situacao == "reembolso_a_verificar" and bool(_RE_MOTIVO_FECHADO.match(l.motivo or ""))


def a_verificar_de_fechados(cands: list[tuple[date, LinhaComissao]], vendas_atuais: dict[str, Venda],
                            decisoes: dict[str, str], hoje: datetime) -> list[LinhaComissao]:
    """Ruling 22: linha de venda congelada (paga) de um mês candidato cuja venda hoje está em
    reembolso a verificar (concluído depois dos 7 dias) e SEM decisão -> linha de valor 0 no mês
    aberto, para aparecer na fila de Inconsistências e bloquear o fechamento até decidir. Depois
    da decisão: "tira" vira estorno (`estornos`), "mantem" some. Participação segue o estorno."""
    saida, vistos = [], set()
    for c, l in cands:
        if l.papel != "venda" or l.transacao in vistos or l.transacao in decisoes:
            continue
        v = vendas_atuais.get(l.transacao)
        if v is None or situacao(True, v.data, v.cancelada_em, hoje, None) != "reembolso_a_verificar":
            continue
        vistos.add(l.transacao)
        saida.append(replace(l, valor=_ZERO, situacao="reembolso_a_verificar", motivo=motivo_fechado(c)))
    return saida


def motivo_tardia(mes_original: date) -> str:
    return f"venda de {mes_original:%Y-%m} após o fechamento"


def marcar_tardias(linhas: list[LinhaComissao]) -> list[LinhaComissao]:
    """Linhas de venda tardia: motivo explica de onde vem. Linha inconsistente mantém o motivo
    dela (sem código, sem regra...) — é ele que a tela de Inconsistências usa."""
    return [l if l.motivo is not None else replace(l, motivo=motivo_tardia(l.data.date().replace(day=1)))
            for l in linhas]


@dataclass
class Pendentes:
    """O que os meses fechados logo antes de M ainda devem a M (estorno e venda tardia)."""
    recentes: list[date] = field(default_factory=list)       # fechados dentro do horizonte
    congeladas: dict = field(default_factory=dict)            # {mês: [LinhaComissao]}
    ja_congeladas: set = field(default_factory=set)           # transações nos congelados lidos inteiros
    cands: list = field(default_factory=list)                 # [(mês original, linha)] de estorno


def ler_pendentes(mes: date, hoje: datetime, tira: set[str]) -> Pendentes | None:
    """Lê do banco só o necessário: congelados inteiros dos meses no horizonte; dos mais
    antigos, só as linhas das transações com decisão "tira". None = nenhum mês fechado antes."""
    from frontend.db_readers.comercial import (  # noqa: PLC0415
        ler_linhas_das_transacoes, ler_linhas_fechadas, meses_fechados,
    )
    from frontend.services.comercial.snapshot import linhas_de_json  # noqa: PLC0415
    rec, antigos = meses_candidatos(mes, meses_fechados())  # Ruling 21: não depende de `hoje`
    if not rec:
        return None
    cong = {m: linhas_de_json(j) for m, j in ler_linhas_fechadas(rec).items()}
    ja = {l.transacao for ls in cong.values() for l in ls}
    for m, js in ler_linhas_das_transacoes(antigos, tira).items():
        cong.setdefault(m, []).extend(linhas_de_json(js))
    return Pendentes(sorted(rec), cong, ja, candidatas(cong))


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
        "linhas": sum(1 for l in linhas if l.papel != "ia"), "vendas_pagas": sum(1 for l in vendas if l.situacao in _PAGAS),
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


def _relogio_banco() -> datetime:
    from frontend.services.comercial import snapshot as snap  # noqa: PLC0415
    return snap.StoreBanco().inicio_calculo()


def fechar(mes: date, por: str, hoje: datetime) -> dict:
    """Recalcula o mês do zero e congela. Devolve os totais. Recusas: `mes_nao_terminou`,
    `ja_fechado`, `mudou_durante_o_fechamento` (EscritaRecusada) e AVerificar(qtd)."""
    from frontend.db_readers import comercial as com  # noqa: PLC0415
    from frontend.services.comercial import snapshot as snap  # noqa: PLC0415
    mes = mes.replace(day=1)
    if not pode_fechar_mes(mes, hoje.date()):
        raise com.EscritaRecusada("mes_nao_terminou")
    if com.mes_fechado(mes):
        raise com.EscritaRecusada("ja_fechado")
    desde = _relogio_banco()  # Finding 1: escrita gravada depois disto não está no cálculo
    res = snap.recalcular_mes(mes, hoje=hoje)  # cálculo novo, nunca o snapshot guardado
    n = a_verificar(res.linhas)
    if n:
        raise AVerificar(n)
    bonus = com.ler_bonus_mes(mes)
    t = totais(res.linhas, bonus)
    com.fechar_mes(mes, snap.linhas_para_json(res.linhas), bonus_para_json(bonus), json.dumps(t, ensure_ascii=False),
                   resumo_txt(t), por, desde=desde)
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
