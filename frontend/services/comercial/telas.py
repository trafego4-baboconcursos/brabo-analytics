"""View-models das telas da área Comercial (Visão geral, Comissões, Ranking) — Task 5.

O isolamento do vendedor mora AQUI, não no template: `linhas_visiveis` corta as linhas antes
de qualquer agregação, e o Ranking de vendedor nunca recebe comissão. O template só desenha.
"""
from __future__ import annotations

import calendar
import io
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal

from frontend.services.comercial import snapshot as _snap
from frontend.services.comercial.acesso import AcessoComercial, pode
from frontend.services.comercial.calculo import LinhaComissao, calcular
from frontend.services.comercial.snapshot import ResultadoMes

_ZERO = Decimal("0")
COM_VALOR = ("elegivel", "prevista", "reembolso_a_verificar")
_PREVISTA = ("prevista", "reembolso_a_verificar")  # a verificar conta como prevista (decisão Task 3)
_PENDENTE = ("inconsistente", "reembolso_a_verificar")
ORDENS = ("vendido", "qtd", "comissao", "meta")
LIMITE_PERIODO_DIAS = 366
_MESES = ("Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho", "Julho", "Agosto",
          "Setembro", "Outubro", "Novembro", "Dezembro")
SITUACAO_ROTULO = {
    "elegivel": "elegível", "prevista": "prevista", "reembolso_a_verificar": "reembolso a verificar",
    "cancelada": "cancelada", "inconsistente": "inconsistente",
}
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
    return Periodo(mes, date(mes.year, mes.month, calendar.monthrange(mes.year, mes.month)[1]), mes)


def resolver_periodo(mes: str | None, inicio: str | None, fim: str | None, hoje: date) -> Periodo:
    """inicio+fim válidos (fim >= inicio, até 1 ano) -> período livre; senão o mês pedido;
    senão o mês corrente. Parâmetro inválido cai no padrão em vez de virar erro."""
    ini, fi = _dia_de(inicio), _dia_de(fim)
    if ini and fi and ini <= fi and (fi - ini).days < LIMITE_PERIODO_DIAS:
        return Periodo(ini, fi, None)
    return _periodo_mes(_mes_de(mes) or hoje.replace(day=1))


def meses_recentes(hoje: date, n: int = 12) -> list[tuple[str, str]]:
    """[(AAAA-MM, 'Novembro/26'), ...] do mês corrente para trás."""
    saida, m = [], hoje.replace(day=1)
    for _ in range(n):
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


def linhas_visiveis(linhas: list[LinhaComissao], acesso: AcessoComercial | None,
                    vendedor: str | None = None) -> list[LinhaComissao]:
    """Gestor: tudo (ou só um vendedor, com as participações nas vendas dele).
    Vendedor: só as PRÓPRIAS linhas de venda; participação nunca. Sem acesso: nada."""
    if not acesso:
        return []
    if e_gestor(acesso):
        if vendedor:
            return [l for l in linhas if l.vendedor_codigo == vendedor]
        return list(linhas)
    if pode(acesso.nivel, "ver_proprio") and acesso.vendedor_codigo:
        return [l for l in linhas if l.papel == "venda" and l.vendedor_codigo == acesso.vendedor_codigo]
    return []


# ---------------------------------------------------------------- agregações
def _vendas(linhas):
    return [l for l in linhas if l.papel == "venda"]


def _com_valor(linhas):
    return [l for l in linhas if l.situacao in COM_VALOR]


def kpis(linhas: list[LinhaComissao]) -> dict:
    """KPIs do período sobre as linhas JÁ filtradas. Total a pagar = elegível (+ bônus, Task 7)."""
    vendas = _vendas(linhas)
    valor = _com_valor(vendas)
    elegivel = sum((l.valor for l in valor if l.situacao == "elegivel"), _ZERO)
    prevista = sum((l.valor for l in valor if l.situacao in _PREVISTA), _ZERO)
    part = _com_valor([l for l in linhas if l.papel == "participacao"])
    return {
        "vendido": sum((l.valor_base or _ZERO for l in valor), _ZERO),
        "qtd": len(valor),
        "elegivel": elegivel,
        "prevista": prevista,
        "bonus": None,
        "total": elegivel,
        "inconsistencias": sum(1 for l in vendas if l.situacao in _PENDENTE),
        "participacao": sum((l.valor for l in part if l.situacao == "elegivel"), _ZERO),
        "participacao_prevista": sum((l.valor for l in part if l.situacao in _PREVISTA), _ZERO),
    }


def _ordenar_detalhe(ls):
    return sorted(ls, key=lambda l: (l.data, l.transacao))


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
        if l.situacao not in COM_VALOR:
            continue
        chave = {"Ativa": "ativa", "Reativa": "reativa"}.get(l.tipo or "", "outro")
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
        v["a_pagar"] = v["elegivel"]  # + bônus na Task 7
    return sorted(por.values(), key=lambda v: (-v["total"], v["nome"]))


def tabela_participacoes(linhas: list[LinhaComissao]) -> list[dict]:
    """Participação no time (ex.: Rafael Batista), separada da folha dos vendedores."""
    por: dict[str, dict] = {}
    for l in _com_valor(l for l in linhas if l.papel == "participacao"):
        p = por.setdefault(l.beneficiario, {"nome": l.beneficiario, "ativa": _ZERO, "reativa": _ZERO,
                                            "elegivel": _ZERO, "prevista": _ZERO, "total": _ZERO,
                                            "qtd": 0, "detalhe": []})
        p["ativa" if l.tipo == "Ativa" else "reativa"] += l.valor
        p["elegivel" if l.situacao == "elegivel" else "prevista"] += l.valor
        p["total"] += l.valor
        p["qtd"] += 1
        p["detalhe"].append(l)
    for p in por.values():
        p["detalhe"] = _ordenar_detalhe(p["detalhe"])
    return sorted(por.values(), key=lambda p: (-p["total"], p["nome"]))


def opcoes_vendedores(linhas: list[LinhaComissao]) -> list[tuple[str, str]]:
    vistos = {l.vendedor_codigo: l.beneficiario for l in _vendas(linhas) if l.vendedor_codigo}
    return sorted(vistos.items(), key=lambda kv: kv[1])


def ranking(linhas: list[LinhaComissao], acesso: AcessoComercial | None, ordem: str = "vendido") -> dict:
    """Ranking de TODOS os vendedores (nome, qtd, vendido; meta '—' até a Task 7).
    Comissão só para gestor — e o vendedor também não pode ORDENAR por comissão,
    senão a ordem entregaria quem ganhou mais."""
    gestor = e_gestor(acesso)
    if ordem not in ORDENS or (ordem == "comissao" and not gestor) or ordem == "meta":
        ordem = "vendido"  # meta ainda não existe (Task 7): cai no vendido
    por: dict[str, dict] = {}
    for l in _com_valor(_vendas(linhas)):
        if not l.vendedor_codigo:
            continue
        r = por.setdefault(l.vendedor_codigo, {"codigo": l.vendedor_codigo, "nome": l.beneficiario,
                                               "qtd": 0, "vendido": _ZERO, "comissao": _ZERO,
                                               "meta": None, "pct_meta": None})
        r["qtd"] += 1
        r["vendido"] += l.valor_base or _ZERO
        r["comissao"] += l.valor
    chave = {"vendido": lambda r: r["vendido"], "qtd": lambda r: r["qtd"],
             "comissao": lambda r: r["comissao"]}[ordem]
    saida = sorted(por.values(), key=lambda r: (-chave(r), r["nome"]))
    for i, r in enumerate(saida, 1):
        r["pos"] = i
        if not gestor:
            del r["comissao"]
    return {"linhas": saida, "mostra_comissao": gestor, "ordem": ordem}


# ---------------------------------------------------------------- telas
def _cabecalho(res: ResultadoMes, periodo: Periodo, acesso: AcessoComercial) -> dict:
    return {"periodo": periodo, "gerado_em": res.gerado_em, "gestor": e_gestor(acesso),
            "acesso": acesso}


def view_visao(res: ResultadoMes, periodo: Periodo, acesso: AcessoComercial) -> dict:
    gestor = e_gestor(acesso)
    proprias = linhas_visiveis(res.linhas, acesso)
    rk = ranking(res.linhas, acesso, "vendido")
    minha_pos = None
    if not gestor:
        minha_pos = next((r["pos"] for r in rk["linhas"] if r["codigo"] == acesso.vendedor_codigo), None)
    return {
        **_cabecalho(res, periodo, acesso),
        "kpis": kpis(proprias),
        "top3": rk["linhas"][:3],
        "mostra_comissao": rk["mostra_comissao"],
        "minha_pos": minha_pos,
        "total_vendedores": len(rk["linhas"]),
        "sem_data": sorted(res.sem_data, key=lambda a: a[0]) if gestor else [],
    }


def view_comissoes(res: ResultadoMes, periodo: Periodo, acesso: AcessoComercial,
                   vendedor: str | None = None) -> dict:
    gestor = e_gestor(acesso)
    filtro = vendedor if gestor else None
    vis = linhas_visiveis(res.linhas, acesso, filtro)
    return {
        **_cabecalho(res, periodo, acesso),
        "kpis": kpis(vis),
        "vendedores": tabela_vendedores(vis),
        "participacoes": tabela_participacoes(vis) if gestor else [],
        "opcoes_vendedores": opcoes_vendedores(res.linhas) if gestor else [],
        "vendedor": filtro,
        "linhas": vis,
    }


def view_ranking(res: ResultadoMes, periodo: Periodo, acesso: AcessoComercial, ordem: str) -> dict:
    rk = ranking(res.linhas, acesso, ordem)
    maior = max((r["vendido"] for r in rk["linhas"]), default=_ZERO)
    for r in rk["linhas"]:
        r["barra"] = int(r["vendido"] / maior * 100) if maior else 0
    return {**_cabecalho(res, periodo, acesso), **rk,
            "meu_codigo": None if e_gestor(acesso) else acesso.vendedor_codigo}


# ---------------------------------------------------------------- Excel
CABECALHO_RESUMO = ["Vendedor", "Código", "Qtd vendas", "Vendido Ativa", "Comissão Ativa",
                    "Vendido Reativa", "Comissão Reativa", "Comissão elegível", "Comissão prevista",
                    "Bônus", "Total a pagar"]
CABECALHO_VENDAS = ["Transação", "Plataforma", "Papel", "Beneficiário", "Código AT", "Data",
                    "Categoria", "Modalidade", "Tipo", "Valor-base", "%", "Comissão", "Situação",
                    "Motivo", "Atribuição manual"]
_FMT_BRL = '"R$" #,##0.00'


def planilha_xlsx(view: dict) -> bytes:
    """Resumo por beneficiário + todas as linhas visíveis. Números como número (Decimal)."""
    from openpyxl import Workbook  # noqa: PLC0415
    from openpyxl.styles import Font  # noqa: PLC0415

    wb = Workbook()
    ws = wb.active
    ws.title = "Resumo"
    ws.append(CABECALHO_RESUMO)
    for v in view["vendedores"]:
        ws.append([v["nome"], v["codigo"], v["qtd"], v["vendido_ativa"], v["com_ativa"],
                   v["vendido_reativa"], v["com_reativa"], v["elegivel"], v["prevista"],
                   None, v["a_pagar"]])
    for p in view["participacoes"]:
        ws.append([f"{p['nome']} (participação)", None, p["qtd"], None, p["ativa"], None,
                   p["reativa"], p["elegivel"], p["prevista"], None, p["elegivel"]])
    for row in ws.iter_rows(min_row=2, min_col=4, max_col=11):
        for c in row:
            c.number_format = _FMT_BRL

    wv = wb.create_sheet("Vendas")
    wv.append(CABECALHO_VENDAS)
    for l in sorted(view["linhas"], key=lambda l: (l.papel != "venda", l.beneficiario, l.data, l.transacao)):
        wv.append([l.transacao, l.plataforma, l.papel, l.beneficiario, l.vendedor_codigo, l.data,
                   l.categoria, l.modalidade, l.tipo, l.valor_base, l.pct, l.valor,
                   SITUACAO_ROTULO.get(l.situacao, l.situacao), MOTIVO_ROTULO.get(l.motivo, l.motivo),
                   "sim" if l.atribuicao_manual else "não"])
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
