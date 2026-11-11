"""View-models das telas da área Comercial (Visão geral, Comissões, Ranking) — Task 5.

O isolamento do vendedor mora AQUI, não no template: `linhas_visiveis` corta as linhas antes
de qualquer agregação, e o Ranking de vendedor nunca recebe comissão. O template só desenha.
"""
from __future__ import annotations

import io
import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal

from frontend.services.comercial import snapshot as _snap
from frontend.services.comercial.acesso import AcessoComercial, pode
from frontend.services.comercial.calculo import PAPEL_IA, LinhaComissao, calcular
from frontend.services.comercial.fechamento import e_a_verificar_de_fechado
from frontend.services.comercial.meses import PRIMEIRO_MES, soma_meses, ultimo_dia
from frontend.services.comercial.snapshot import ResultadoMes

_ZERO = Decimal("0")
COM_VALOR = ("elegivel", "prevista", "reembolso_a_verificar")
_PREVISTA = ("prevista", "reembolso_a_verificar")  # a verificar conta como prevista (decisão Task 3)
# Ruling 10: sem_codigo (venda orgânica, ~800/mês) NÃO é pendência — vira lista reivindicável (Task 6)
_MOTIVOS_PENDENTES = ("conflito_codigo", "sem_valor_base", "sem_regra")
ORDENS = ("vendido", "qtd", "comissao", "meta")
LIMITE_PERIODO_DIAS = 92           # período livre: só gestor, até 92 dias (custo ~20 s/mês de dado)
_MES_ABREV = {"JAN": 1, "FEV": 2, "MAR": 3, "ABR": 4, "MAI": 5, "JUN": 6, "JUL": 7, "AGO": 8,
              "SET": 9, "OUT": 10, "NOV": 11, "DEZ": 12}
_MESES = ("Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho", "Julho", "Agosto",
          "Setembro", "Outubro", "Novembro", "Dezembro")
SITUACAO_ROTULO = {
    "elegivel": "elegível", "prevista": "prevista", "reembolso_a_verificar": "reembolso a verificar",
    "cancelada": "cancelada", "inconsistente": "inconsistente", "estorno": "estorno",
}
ESTORNO = "estorno"  # Task 7b: linha negativa de venda paga em mês fechado e cancelada depois
MOTIVO_ROTULO = {
    "sem_codigo": "sem código AT", "conflito_codigo": "conflito de código (content × last_content)",
    "sem_valor_base": "sem valor-base cadastrado", "sem_regra": "sem regra de percentual",
}


# ---------------------------------------------------------------- período
@dataclass(frozen=True)
class Periodo:
    inicio: date
    fim: date
    mes: date | None  # None = período livre (calculado ao vivo, sem snapshot)

    @property
    def livre(self) -> bool:
        return self.mes is None

    @property
    def query(self) -> str:
        if self.livre:
            return f"inicio={self.inicio.isoformat()}&fim={self.fim.isoformat()}"
        return f"mes={self.mes:%Y-%m}"

    @property
    def rotulo(self) -> str:
        if self.livre:
            return f"{self.inicio:%d/%m/%Y} a {self.fim:%d/%m/%Y}"
        return f"{_MESES[self.mes.month - 1]}/{self.mes:%y}"


def _mes_de(txt: str | None) -> date | None:
    try:
        return datetime.strptime((txt or "").strip(), "%Y-%m").date().replace(day=1)
    except ValueError:
        return None


def _dia_de(txt: str | None) -> date | None:
    try:
        return date.fromisoformat((txt or "").strip())
    except ValueError:
        return None


def _periodo_mes(mes: date) -> Periodo:
    return Periodo(mes, ultimo_dia(mes), mes)


class PeriodoInvalido(ValueError):
    """Parâmetro de período fora do permitido; a mensagem vai para a tela (400)."""


def resolver_periodo(mes: str | None, inicio: str | None, fim: str | None, hoje: date,
                     *, gestor: bool = False) -> Periodo:
    """Sem parâmetro -> mês corrente. `mes` só de 2026-01 ao mês corrente. `inicio`/`fim`
    (período livre, calculado ao vivo) só para gestor e até LIMITE_PERIODO_DIAS dias.
    Fora disso -> PeriodoInvalido: todo pedido custa cálculo, nada de trabalho sem limite."""
    if (inicio or "").strip() or (fim or "").strip():
        if not gestor:
            raise PeriodoInvalido("Período livre é só para gestores. Escolha um mês.")
        ini, fi = _dia_de(inicio), _dia_de(fim)
        if not ini or not fi:
            raise PeriodoInvalido("Período livre precisa de data de início e de fim válidas.")
        if fi < ini:
            raise PeriodoInvalido("No período livre, a data final vem antes da inicial.")
        if (fi - ini).days + 1 > LIMITE_PERIODO_DIAS:
            raise PeriodoInvalido(f"Período livre de no máximo {LIMITE_PERIODO_DIAS} dias.")
        return Periodo(ini, fi, None)
    if not (mes or "").strip():
        return _periodo_mes(hoje.replace(day=1))
    m = _mes_de(mes)
    if m is None:
        raise PeriodoInvalido("Mês inválido: use o formato AAAA-MM.")
    if not (PRIMEIRO_MES <= m <= hoje.replace(day=1)):
        raise PeriodoInvalido(f"Mês fora do intervalo disponível ({PRIMEIRO_MES:%m/%Y} até o mês atual).")
    return _periodo_mes(m)


def mes_do_codigo(codigo: str) -> date | None:
    """'PES-NOV-26' -> 2026-11-01; código sem mês (ex.: 'BV-26') -> None."""
    m = re.search(r"-([A-Z]{3})-(\d{2})$", (codigo or "").strip().upper())
    if not m or m.group(1) not in _MES_ABREV:
        return None
    return date(2000 + int(m.group(2)), _MES_ABREV[m.group(1)], 1)


def separar_sem_data(sem_data: list, periodo: Periodo) -> tuple[list, list]:
    """(perto, antigos): perto = mês do código a ±1 mês do período, ou código sem mês
    (sempre mostrado). Ruling 11: os antigos não ocupam o topo da Visão geral."""
    de, ate = soma_meses(periodo.inicio.replace(day=1), -1), soma_meses(periodo.fim.replace(day=1), 1)
    perto, antigos = [], []
    for a in sorted(sem_data, key=lambda a: a[0]):
        m = mes_do_codigo(a[0])
        (perto if m is None or de <= m <= ate else antigos).append(a)
    return perto, antigos


def meses_recentes(hoje: date, n: int = 12) -> list[tuple[str, str]]:
    """[(AAAA-MM, 'Novembro/26'), ...] do mês corrente para trás."""
    saida, m = [], hoje.replace(day=1)
    for _ in range(n):
        if m < PRIMEIRO_MES:
            break  # fora da janela aceita por resolver_periodo
        saida.append((f"{m:%Y-%m}", _periodo_mes(m).rotulo))
        m = (m - timedelta(days=1)).replace(day=1)
    return saida


def calcular_periodo(inicio: date, fim: date, hoje: datetime | None = None) -> ResultadoMes:
    """Mesma composição de `snapshot.calcular_mes`, para um intervalo qualquer. Não grava."""
    from frontend.db_readers.comercial import ler_cadastros, ler_janelas, ler_vendas  # noqa: PLC0415

    cad = ler_cadastros()
    vendas = ler_vendas(inicio, fim, transacoes_extra=frozenset(cad.atribuicoes), ofertas=cad.ofertas)
    janelas, sem_data = ler_janelas(inicio, fim)
    linhas = calcular(vendas, cad, janelas, hoje or _snap.agora_sp())
    return ResultadoMes(inicio, linhas, sem_data, _snap.agora_sp())


def carregar(periodo: Periodo) -> ResultadoMes:
    """Mês -> snapshot (ou cálculo + gravação); período livre -> cálculo ao vivo."""
    if periodo.livre:
        return calcular_periodo(periodo.inicio, periodo.fim)
    return _snap.obter_mes(periodo.mes)


# ---------------------------------------------------------------- isolamento
def e_gestor(acesso: AcessoComercial | None) -> bool:
    return bool(acesso) and pode(acesso.nivel, "ver_time")


def _do_marketing(l: LinhaComissao) -> bool:
    return l.papel == "venda" and l.situacao == "inconsistente" and l.motivo == "sem_codigo"


def linhas_visiveis(linhas: list[LinhaComissao], acesso: AcessoComercial | None,
                    vendedor: str | None = None) -> list[LinhaComissao]:
    """Gestor: tudo (ou só um vendedor, com as participações nas vendas dele).
    Vendedor: só as PRÓPRIAS linhas de venda; participação nunca. Sem acesso: nada."""
    if not acesso:
        return []
    if e_gestor(acesso):
        if vendedor:
            return [l for l in linhas if l.vendedor_codigo == vendedor]
        # venda sem código AT é do marketing (Rafael, 10/11/26): fora da tela e da planilha
        return [l for l in linhas if not _do_marketing(l)]
    if pode(acesso.nivel, "ver_proprio") and acesso.vendedor_codigo:
        return [l for l in linhas if l.papel == "venda" and l.vendedor_codigo == acesso.vendedor_codigo]
    return []


# ---------------------------------------------------------------- agregações
def _vendas(linhas):
    return [l for l in linhas if l.papel == "venda"]


def _com_valor(linhas):
    """Linhas que valem como venda do período. A pendência de reembolso de venda de mês fechado
    (Ruling 22, valor 0) fica de fora: não é venda nem dinheiro deste mês — só conta como
    inconsistência."""
    return [l for l in linhas if l.situacao in COM_VALOR and not e_a_verificar_de_fechado(l)]


def _estornos(linhas):
    return [l for l in linhas if l.situacao == ESTORNO]


def kpis(linhas: list[LinhaComissao]) -> dict:
    """KPIs do período sobre as linhas JÁ filtradas. Total a pagar = elegível; o bônus (Task 7a)
    entra depois, em `com_bonus`, lido na hora da tela (não faz parte do cálculo guardado).
    Estorno (Task 7b) entra no elegível (reduz o pagamento), não no vendido nem na quantidade."""
    vendas = _vendas(linhas)
    valor = _com_valor(vendas)
    estorno = sum((l.valor for l in _estornos(vendas)), _ZERO)
    elegivel = sum((l.valor for l in valor if l.situacao == "elegivel"), _ZERO) + estorno
    prevista = sum((l.valor for l in valor if l.situacao in _PREVISTA), _ZERO)
    part_todas = [l for l in linhas if l.papel == "participacao"]
    part = _com_valor(part_todas) + _estornos(part_todas)
    return {
        "vendido": sum((l.valor_base or _ZERO for l in valor), _ZERO),
        "qtd": len(valor),
        "elegivel": elegivel,
        "prevista": prevista,
        "estorno": estorno,
        "bonus": None,
        "total": elegivel,
        "inconsistencias": sum(1 for l in vendas if l.situacao == "reembolso_a_verificar"
                               or (l.situacao == "inconsistente" and l.motivo in _MOTIVOS_PENDENTES)),
        "sem_codigo": sum(1 for l in vendas if l.situacao == "inconsistente" and l.motivo == "sem_codigo")
                      + sum(1 for l in linhas if l.papel == "ia" and l.situacao != "cancelada"),
        "participacao": sum((l.valor for l in part if l.situacao in ("elegivel", ESTORNO)), _ZERO),
        "participacao_prevista": sum((l.valor for l in part if l.situacao in _PREVISTA), _ZERO),
    }


def _ordenar_detalhe(ls):
    return sorted(ls, key=lambda l: (l.data, l.transacao))


def todas_as_vendas(linhas: list[LinhaComissao]) -> list[LinhaComissao]:
    """Lista unificada da Visão geral (Rafael, 11/11/26): uma linha por venda, mais recente
    primeiro. Participação fica de fora (repetiria a venda); IA entra, marcada na tela.
    Recebe as linhas JÁ filtradas por `linhas_visiveis` (vendedor só vê as dele)."""
    vendas = [l for l in linhas if l.papel in ("venda", PAPEL_IA)]
    return sorted(vendas, key=lambda l: (l.data, l.transacao), reverse=True)


def tabela_vendedores(linhas: list[LinhaComissao]) -> list[dict]:
    """Uma linha por vendedor (linhas de venda com código), ordenada pelo total da comissão."""
    por: dict[str, dict] = {}
    for l in _vendas(linhas):
        if not l.vendedor_codigo:
            continue  # sem vendedor vai para Inconsistências, não para a folha
        v = por.setdefault(l.vendedor_codigo, {
            "codigo": l.vendedor_codigo, "nome": l.beneficiario, "vendido_ativa": _ZERO,
            "com_ativa": _ZERO, "vendido_reativa": _ZERO, "com_reativa": _ZERO, "vendido_outro": _ZERO,
            "com_outro": _ZERO, "elegivel": _ZERO, "prevista": _ZERO, "total": _ZERO, "qtd": 0,
            "bonus": None, "detalhe": []})
        v["detalhe"].append(l)
        chave = {"Ativa": "ativa", "Reativa": "reativa"}.get(l.tipo or "", "outro")
        if l.situacao == ESTORNO:  # reduz a comissão (elegível); não é venda do período
            v["com_" + chave] += l.valor
            v["elegivel"] += l.valor
            v["total"] += l.valor
            continue
        if l.situacao not in COM_VALOR or e_a_verificar_de_fechado(l):
            continue
        v["vendido_" + chave] += l.valor_base or _ZERO
        v["com_" + chave] += l.valor
        v["qtd"] += 1
        if l.situacao == "elegivel":
            v["elegivel"] += l.valor
        else:
            v["prevista"] += l.valor
        v["total"] += l.valor
    for v in por.values():
        v["detalhe"] = _ordenar_detalhe(v["detalhe"])
        v["a_pagar"] = v["elegivel"]  # + bônus: aplicar_bonus
    return sorted(por.values(), key=lambda v: (-v["total"], v["nome"]))


# ---------------------------------------------------------------- bônus e meta (Task 7a)
# Lidos na hora da tela (comercial_bonus / comercial_metas), fora do snapshot: mudar bônus ou
# meta não recalcula nada. O recorte do vendedor é feito NA CONSULTA (só a própria linha) e de
# novo aqui (`_so_meu`), antes de qualquer soma.
def ler_extras(periodo: "Periodo", acesso: AcessoComercial | None) -> tuple[dict | None, dict | None]:
    """(bônus, metas) do mês — {código: {...}}. Período livre: (None, None) (bônus e meta são
    mensais). Vendedor: só a própria linha."""
    from frontend.db_readers import comercial as com  # noqa: PLC0415
    if periodo.livre or not acesso:
        return None, None
    codigo = None if e_gestor(acesso) else acesso.vendedor_codigo
    if not e_gestor(acesso) and not codigo:
        return {}, {}
    return com.ler_bonus_mes(periodo.mes, codigo), com.ler_metas_mes(periodo.mes, codigo)


def ler_vendedores_ativos() -> list[tuple[str, str]]:
    """[(código, nome)] dos vendedores ativos — o formulário de bônus do gestor."""
    from sqlalchemy import text  # noqa: PLC0415
    from frontend.db_readers import comercial as com  # noqa: PLC0415

    def ler():
        with com._get_users_engine().connect() as conn:
            return [tuple(r) for r in conn.execute(text(com.SQL_VENDEDORES_LISTA)).fetchall()]
    return com._tolerante(ler, [])


def _so_meu(d: dict | None, acesso: AcessoComercial | None, vendedor: str | None = None) -> dict | None:
    if d is None:
        return None
    if not e_gestor(acesso):
        cod = acesso.vendedor_codigo if acesso else None
        return {k: v for k, v in d.items() if cod and k == cod}
    if vendedor:
        return {k: v for k, v in d.items() if k == vendedor}
    return dict(d)


def com_bonus(k: dict, bonus: dict | None, fechado: bool = False) -> dict:
    """KPIs + bônus: total a pagar = elegível + bônus. Sem bônus (período livre) -> '—'.
    Mês fechado (Ruling 17): as previstas são pagas no fechamento -> elegível + prevista + bônus."""
    if bonus is None:
        return k
    soma = sum((b["valor"] for b in bonus.values()), _ZERO)
    return {**k, "bonus": soma, "total": k["elegivel"] + (k["prevista"] if fechado else _ZERO) + soma}


def aplicar_bonus(vendedores: list[dict], bonus: dict | None, fechado: bool = False) -> list[dict]:
    """Bônus em cada linha (a_pagar = elegível + bônus; mês fechado: + prevista). Vendedor com
    bônus e sem venda no mês entra numa linha zerada — senão o total do KPI não fecharia."""
    if bonus is None:
        return vendedores
    por = {v["codigo"]: v for v in vendedores}
    for cod, b in bonus.items():
        if cod not in por:
            por[cod] = {"codigo": cod, "nome": b["nome"], "vendido_ativa": _ZERO, "com_ativa": _ZERO,
                        "vendido_reativa": _ZERO, "com_reativa": _ZERO, "vendido_outro": _ZERO,
                        "com_outro": _ZERO, "elegivel": _ZERO, "prevista": _ZERO, "total": _ZERO, "qtd": 0,
                        "detalhe": []}
    for v in por.values():
        b = bonus.get(v["codigo"])
        v["bonus"] = b["valor"] if b else _ZERO
        v["bonus_justificativa"] = (b or {}).get("justificativa")
        v["a_pagar"] = v["elegivel"] + (v["prevista"] if fechado else _ZERO) + v["bonus"]
    return sorted(por.values(), key=lambda v: (-v["total"], -v["bonus"], v["nome"]))


def _pct_meta(vendido: Decimal, meta: Decimal | None) -> Decimal | None:
    from decimal import ROUND_HALF_UP  # noqa: PLC0415
    if not meta:
        return None
    return (vendido / meta).quantize(Decimal("0.001"), rounding=ROUND_HALF_UP)  # 85,3%


def tabela_participacoes(linhas: list[LinhaComissao]) -> list[dict]:
    """Participação no time (ex.: Rafael Batista), separada da folha dos vendedores."""
    por: dict[str, dict] = {}
    part = [l for l in linhas if l.papel == "participacao"]
    for l in _com_valor(part) + _estornos(part):
        p = por.setdefault(l.beneficiario, {"nome": l.beneficiario, "ativa": _ZERO, "reativa": _ZERO,
                                            "elegivel": _ZERO, "prevista": _ZERO, "total": _ZERO,
                                            "qtd": 0, "detalhe": []})
        p["ativa" if l.tipo == "Ativa" else "reativa"] += l.valor
        p["elegivel" if l.situacao in ("elegivel", ESTORNO) else "prevista"] += l.valor
        p["total"] += l.valor
        p["qtd"] += 0 if l.situacao == ESTORNO else 1
        p["detalhe"].append(l)
    for p in por.values():
        p["detalhe"] = _ordenar_detalhe(p["detalhe"])
    return sorted(por.values(), key=lambda p: (-p["total"], p["nome"]))


def opcoes_vendedores(linhas: list[LinhaComissao]) -> list[tuple[str, str]]:
    vistos = {l.vendedor_codigo: l.beneficiario for l in _vendas(linhas) if l.vendedor_codigo}
    return sorted(vistos.items(), key=lambda kv: kv[1])


def ranking(linhas: list[LinhaComissao], acesso: AcessoComercial | None, ordem: str = "vendido",
            metas: dict | None = None) -> dict:
    """Ranking de TODOS os vendedores (nome, qtd, vendido, meta e % da meta).
    Vendedor (10/11/26): vê posição e nome de todos, mas valores só da própria linha; as
    linhas dos outros ficam só com codigo/nome/pos. Vendedor só ordena por "vendido" (qualquer
    outra ordem entregaria o que ele não vê). A posição é calculada antes do corte."""
    gestor = e_gestor(acesso)
    metas = _so_meu(metas, acesso) or {}
    if ordem not in ORDENS or (ordem != "vendido" and not gestor):
        ordem = "vendido"
    por: dict[str, dict] = {}
    def linha(l):
        return por.setdefault(l.vendedor_codigo, {"codigo": l.vendedor_codigo, "nome": l.beneficiario,
                                                  "qtd": 0, "vendido": _ZERO, "comissao": _ZERO,
                                                  "meta": None, "pct_meta": None})
    for l in _com_valor(_vendas(linhas)):
        if not l.vendedor_codigo:
            continue
        r = linha(l)
        r["qtd"] += 1
        r["vendido"] += l.valor_base or _ZERO
        r["comissao"] += l.valor
    # estorno reduz a comissão, não o vendido; vendedor só com estorno no mês também entra
    # (mesma comissão da tela de Comissões)
    for l in _estornos(_vendas(linhas)):
        if l.vendedor_codigo:
            linha(l)["comissao"] += l.valor
    for cod, m in metas.items():  # com meta e sem venda: aparece com 0%
        por.setdefault(cod, {"codigo": cod, "nome": m["nome"], "qtd": 0, "vendido": _ZERO,
                             "comissao": _ZERO, "meta": None, "pct_meta": None})
    for r in por.values():
        m = metas.get(r["codigo"])
        r["meta"] = m["valor"] if m else None
        r["pct_meta"] = _pct_meta(r["vendido"], r["meta"])
    chave = {"vendido": lambda r: r["vendido"], "qtd": lambda r: r["qtd"],
             "comissao": lambda r: r["comissao"],
             "meta": lambda r: r["pct_meta"] if r["pct_meta"] is not None else Decimal("-1")}[ordem]
    saida = sorted(por.values(), key=lambda r: (-chave(r), r["nome"]))
    for i, r in enumerate(saida, 1):
        r["pos"] = i
        if not gestor:
            del r["comissao"]
    if not gestor:
        meu = acesso.vendedor_codigo if acesso else None
        saida = [r if r["codigo"] == meu else {"codigo": r["codigo"], "nome": r["nome"], "pos": r["pos"]}
                 for r in saida]
    return {"linhas": saida, "mostra_comissao": gestor, "ordem": ordem}


# ---------------------------------------------------------------- telas
def _cabecalho(res: ResultadoMes, periodo: Periodo, acesso: AcessoComercial) -> dict:
    return {"periodo": periodo, "gerado_em": res.gerado_em, "gestor": e_gestor(acesso),
            "acesso": acesso, "fechado": res.fechado, "fechado_em": res.fechado_em,
            "fechado_por": res.fechado_por}


def _bonus_do_mes(res: ResultadoMes, bonus: dict | None) -> dict | None:
    """Mês fechado: o bônus congelado no fechamento (nunca o de comercial_bonus)."""
    return (res.bonus or {}) if res.fechado else bonus


def view_visao(res: ResultadoMes, periodo: Periodo, acesso: AcessoComercial,
               bonus: dict | None = None, metas: dict | None = None) -> dict:
    gestor = e_gestor(acesso)
    proprias = linhas_visiveis(res.linhas, acesso)
    perto, antigos = separar_sem_data(res.sem_data, periodo)
    rk = ranking(res.linhas, acesso, "vendido", metas)
    k = com_bonus(kpis(proprias), _so_meu(_bonus_do_mes(res, bonus), acesso), res.fechado)
    metas_vis = _so_meu(metas, acesso)
    meta_total = sum((m["valor"] for m in metas_vis.values()), _ZERO) if metas_vis else None
    minha_pos = None
    if not gestor:
        minha_pos = next((r["pos"] for r in rk["linhas"] if r["codigo"] == acesso.vendedor_codigo), None)
    return {
        **_cabecalho(res, periodo, acesso),
        "kpis": k,
        "meta": meta_total,
        "pct_meta": _pct_meta(k["vendido"], meta_total),
        "top3": rk["linhas"][:3],
        "mostra_comissao": rk["mostra_comissao"],
        "minha_pos": minha_pos,
        "total_vendedores": len(rk["linhas"]),
        "sem_data": perto if gestor else [],
        "sem_data_antigos": antigos if gestor else [],
        "vendas": todas_as_vendas(proprias),
    }


def view_comissoes(res: ResultadoMes, periodo: Periodo, acesso: AcessoComercial,
                   vendedor: str | None = None, bonus: dict | None = None,
                   vendedores_ativos: list | None = None, hoje: date | None = None,
                   ultimo_fechado: bool = True) -> dict:
    from frontend.services.comercial import fechamento as fech  # noqa: PLC0415
    gestor = e_gestor(acesso)
    filtro = vendedor if gestor else None
    vis = linhas_visiveis(res.linhas, acesso, filtro)
    b = _so_meu(_bonus_do_mes(res, bonus), acesso, filtro)
    participacoes = tabela_participacoes(vis) if gestor else []
    for p in participacoes:
        p["a_pagar"] = p["elegivel"] + (p["prevista"] if res.fechado else _ZERO)
    # "Fechar mês": só gestor, mês que já terminou e ainda aberto — contagens do mês inteiro
    fechar = None
    if (gestor and pode(acesso.nivel, "fechar_mes") and not periodo.livre and not res.fechado and hoje
            and fech.pode_fechar_mes(periodo.mes, hoje)):
        k_mes = kpis(res.linhas)
        fechar = fech.info_fechar(res.linhas, k_mes["inconsistencias"] - fech.a_verificar(res.linhas),
                                  periodo.rotulo)
    return {
        **_cabecalho(res, periodo, acesso),
        "kpis": com_bonus(kpis(vis), b, res.fechado),
        "vendedores": aplicar_bonus(tabela_vendedores(vis), b, res.fechado),
        "edita_bonus": (gestor and pode(acesso.nivel, "lancar_bonus") and not periodo.livre
                        and bonus is not None and not res.fechado),
        "vendedores_ativos": list(vendedores_ativos or []) if gestor and not res.fechado else [],
        "participacoes": participacoes,
        "opcoes_vendedores": opcoes_vendedores(res.linhas) if gestor else [],
        "vendedor": filtro,
        "linhas": vis,
        "fechar": fechar,
        "reabre": gestor and pode(acesso.nivel, "fechar_mes") and res.fechado and ultimo_fechado,
        "reabre_bloqueado": gestor and pode(acesso.nivel, "fechar_mes") and res.fechado and not ultimo_fechado,  # Ruling 19b
    }


def view_ranking(res: ResultadoMes, periodo: Periodo, acesso: AcessoComercial, ordem: str,
                 metas: dict | None = None) -> dict:
    rk = ranking(res.linhas, acesso, ordem, metas)
    maior = max((r["vendido"] for r in rk["linhas"] if "vendido" in r), default=_ZERO)
    for r in rk["linhas"]:
        if "vendido" in r:
            r["barra"] = int(r["vendido"] / maior * 100) if maior else 0
    return {**_cabecalho(res, periodo, acesso), **rk, "tem_meta": metas is not None,
            "meu_codigo": None if e_gestor(acesso) else acesso.vendedor_codigo}


# ---------------------------------------------------------------- Excel
CABECALHO_RESUMO = ["Vendedor", "Código", "Qtd vendas", "Vendido Ativa", "Comissão Ativa",
                    "Vendido Reativa", "Comissão Reativa", "Comissão elegível", "Comissão prevista",
                    "Bônus", "Total a pagar"]
CABECALHO_VENDAS = ["Transação", "Plataforma", "Papel", "Beneficiário", "Código AT", "Data",
                    "Categoria", "Modalidade", "Tipo", "Valor-base", "%", "Comissão", "Situação",
                    "Motivo", "Atribuição manual"]
_FMT_BRL = '"R$" #,##0.00'


def celula_segura(v):
    """Texto que o Excel leria como fórmula (= + - @) ganha um apóstrofo na frente."""
    if isinstance(v, str) and v[:1] in ("=", "+", "-", "@"):
        return "'" + v
    return v


def planilha_xlsx(view: dict) -> bytes:
    """Resumo por beneficiário + todas as linhas visíveis. Números como número (Decimal)."""
    from openpyxl import Workbook  # noqa: PLC0415
    from openpyxl.styles import Font  # noqa: PLC0415

    wb = Workbook()
    ws = wb.active
    ws.title = "Resumo"
    ws.append(CABECALHO_RESUMO)
    for v in view["vendedores"]:
        ws.append([celula_segura(x) for x in [v["nome"], v["codigo"], v["qtd"], v["vendido_ativa"], v["com_ativa"],
                   v["vendido_reativa"], v["com_reativa"], v["elegivel"], v["prevista"],
                   v.get("bonus"), v["a_pagar"]]])
    for p in view["participacoes"]:
        ws.append([celula_segura(x) for x in [f"{p['nome']} (participação)", None, p["qtd"], None, p["ativa"], None,
                   p["reativa"], p["elegivel"], p["prevista"], None, p.get("a_pagar", p["elegivel"])]])
    for row in ws.iter_rows(min_row=2, min_col=4, max_col=11):
        for c in row:
            c.number_format = _FMT_BRL

    wv = wb.create_sheet("Vendas")
    wv.append(CABECALHO_VENDAS)
    for l in sorted(view["linhas"], key=lambda l: (l.papel != "venda", l.beneficiario, l.data, l.transacao)):
        wv.append([celula_segura(x) for x in [l.transacao, l.plataforma,
                   "IA (sem comissão)" if l.papel == PAPEL_IA else l.papel, l.beneficiario, l.vendedor_codigo, l.data,
                   l.categoria, l.modalidade, l.tipo, l.valor_base, l.pct, l.valor,
                   SITUACAO_ROTULO.get(l.situacao, l.situacao), MOTIVO_ROTULO.get(l.motivo, l.motivo),
                   "sim" if l.atribuicao_manual else "não"]])
    for row in wv.iter_rows(min_row=2):
        row[5].number_format = "dd/mm/yyyy hh:mm"
        row[9].number_format = _FMT_BRL
        row[10].number_format = "0.00%"
        row[11].number_format = _FMT_BRL
    for sheet in (ws, wv):
        for c in sheet[1]:
            c.font = Font(bold=True)
        sheet.freeze_panes = "A2"
        for col in sheet.columns:
            letra = col[0].column_letter
            sheet.column_dimensions[letra].width = max(10, min(40, len(str(col[0].value)) + 4))
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()
