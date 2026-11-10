"""Tela Desempenho — serviço puro (comparação, agregação, isolamento da vendedora)."""
from datetime import date, datetime
from decimal import Decimal

import pytest

from frontend.services.comercial.acesso import AcessoComercial
from frontend.services.comercial.calculo import LinhaComissao
from frontend.services.comercial.desempenho import (
    Comparacao, agregar, resolver_comparacao, variacao, view_desempenho)
from frontend.services.comercial.telas import Periodo, PeriodoInvalido

D = Decimal
P_NOV = Periodo(date(2026, 11, 1), date(2026, 11, 30), date(2026, 11, 1))
P_OUT = Periodo(date(2026, 10, 1), date(2026, 10, 31), date(2026, 10, 1))
P_MAR = Periodo(date(2027, 3, 1), date(2027, 3, 31), date(2027, 3, 1))
P_JAN26 = Periodo(date(2026, 1, 1), date(2026, 1, 31), date(2026, 1, 1))


def linha(cod, produto, valor, dia, *, situacao="elegivel", papel="venda", nome=None):
    nome = nome or {"AT4": "Edileia", "AT9": "Zelia", "AT5": "Beto", "AT6": "Cida"}.get(cod, "Camila")
    return LinhaComissao(
        transacao=f"T{id(object())}", plataforma="hotmart", papel=papel, beneficiario=nome,
        vendedor_codigo=cod, data=datetime(dia.year, dia.month, dia.day, 10), tipo="Ativa",
        modalidade="", categoria=None, valor_base=D(valor), pct=None, valor=D("0"),
        situacao=situacao, motivo=None, regra_id=None, atribuicao_manual=False, produto=produto)


ATUAL = [linha("AT4", "Black", "1000", date(2026, 10, 3)),
         linha("AT9", "PES", "2000", date(2026, 10, 4)),
         linha("AT5", "PES", "500", date(2026, 10, 5)),
         linha("AT6", "PBB", "500", date(2026, 10, 6)),
         linha(None, "PES", "700", date(2026, 10, 4), papel="ia")]
COMP = [linha("AT4", "Black", "800", date(2026, 9, 3)), linha("AT9", "PES", "1000", date(2026, 9, 4)),
        linha(None, "PES", "100", date(2026, 9, 4), papel="ia")]
ACUM = ATUAL + COMP + [linha("AT9", "PES", "4000", date(2026, 8, 4))]
COMPARACAO = Comparacao(Periodo(date(2026, 9, 1), date(2026, 9, 30), date(2026, 9, 1)), None, "Setembro/26")
METAS = {"AT4": {"nome": "Edileia", "valor": D("2000")}, "AT9": {"nome": "Zelia", "valor": D("3000")}}
METAS_SO_DELA = {"AT4": METAS["AT4"]}
METAS_TOTAL = D("5000")
ACESSO_EDILEIA = AcessoComercial("vendedor", "AT4")
ACESSO_MASTER = AcessoComercial("master", None)


def test_comparacao_padrao_mes_anterior_com_corte_no_mes_corrente():
    c = resolver_comparacao(P_NOV, None, None, None, date(2026, 11, 9), gestor=False)
    assert (c.periodo.mes, c.corte) == (date(2026, 10, 1), date(2026, 10, 9))
    c2 = resolver_comparacao(P_OUT, None, None, None, date(2026, 11, 9), gestor=False)
    assert (c2.periodo.mes, c2.corte) == (date(2026, 9, 1), None)
    assert c.rotulo == "Outubro/26 (1–9)" and c2.rotulo == "Setembro/26"


def test_corte_mes_curto():
    c = resolver_comparacao(P_MAR, None, None, None, date(2027, 3, 31), gestor=True)
    assert c.corte == date(2027, 2, 28)


def test_comparacao_livre_padrao_mesmo_tamanho_antes():
    p = Periodo(date(2026, 10, 10), date(2026, 10, 19), None)
    c = resolver_comparacao(p, None, None, None, date(2026, 11, 9), gestor=True)
    assert (c.periodo.inicio, c.periodo.fim) == (date(2026, 9, 30), date(2026, 10, 9))


def test_vendedora_so_compara_com_mes():
    with pytest.raises(PeriodoInvalido):
        resolver_comparacao(P_NOV, None, "2026-09-01", "2026-09-30", date(2026, 11, 9), gestor=False)
    c = resolver_comparacao(P_NOV, "2026-08", None, None, date(2026, 11, 9), gestor=False)
    assert (c.periodo.mes, c.corte) == (date(2026, 8, 1), date(2026, 8, 9))


def test_comparacao_limites():
    h = date(2026, 11, 9)
    for ruim in ("2025-12", "2026-12", "xx"):
        with pytest.raises(PeriodoInvalido):
            resolver_comparacao(P_NOV, ruim, None, None, h, gestor=True)
    with pytest.raises(PeriodoInvalido):
        resolver_comparacao(P_NOV, None, "2026-01-01", "2026-06-30", h, gestor=True)
    c = resolver_comparacao(P_NOV, None, "2026-09-01", "2026-09-10", h, gestor=True)
    assert c.periodo.livre and c.corte is None


def test_comparacao_antes_do_primeiro_mes():
    assert resolver_comparacao(P_JAN26, None, None, None, date(2026, 11, 9), gestor=True) is None


def test_variacao_base_zero():
    assert variacao(D("10"), D("0")) is None and variacao(D("10"), None) is None
    assert variacao(D("110"), D("100")) == D("0.100")


def test_agregar_conta_so_venda_com_valor_e_respeita_corte():
    ls = [linha("AT4", "Black", "1000", date(2026, 10, 3)), linha("AT4", "Black", "500", date(2026, 10, 20)),
          linha("AT9", "PES", "800", date(2026, 10, 3), situacao="cancelada"),
          linha(None, "PES", "0", date(2026, 10, 3), situacao="inconsistente"),
          linha(None, "PES", "700", date(2026, 10, 4), papel="ia")]
    a = agregar(ls, corte=date(2026, 10, 9))
    assert a["time"] == {"qtd": 1, "vendido": D("1000")}
    assert a["ia"]["vendido"] == D("700") and "AT9" not in a["vendedores"]


def test_produto_vazio_vira_traco():
    a = agregar([linha("AT4", "", "1000", date(2026, 10, 3))])
    assert list(a["produtos"]) == ["—"]


def test_vendedora_ve_so_o_dela_e_a_contribuicao_mas_nao_a_meta_do_time_individual():
    v = view_desempenho(ATUAL, COMP, COMPARACAO, ACUM, P_OUT, ACESSO_EDILEIA, METAS_SO_DELA,
                        meta_time=METAS_TOTAL)
    assert [r["codigo"] for r in v["vendedores"]] == ["AT4"]
    assert v["vendedores"][0]["contribuicao"] == D("0.250")          # 1000 de 4000 do time
    assert v["vendedores"][0]["contribuicao_ano"] is not None
    assert v["resumo"]["meta_time"] == METAS_TOTAL and v["resumo"]["vendido"] == D("4000")
    assert v["ia"] is None and v["resumo"]["posicao"] == 2
    s = str(v)
    assert "AT9" not in s and "Zelia" not in s and "AT5" not in s and "Beto" not in s
    assert all(set(p["por_vendedor"]) <= {"AT4"} for p in v["produtos"])


def test_gestor_ve_time_meta_e_ia():
    v = view_desempenho(ATUAL, COMP, COMPARACAO, ACUM, P_OUT, ACESSO_MASTER, METAS,
                        meta_time=sum(m["valor"] for m in METAS.values()))
    assert v["resumo"]["meta_time"] == D("5000")
    assert v["ia"]["vendido"] == D("700") and v["resumo"]["vendido"] == D("4000")
    assert v["resumo"]["qtd"] == 4 and v["resumo"]["ticket"] == D("1000")
    assert len(v["vendedores"]) == 4
    assert v["resumo"]["var_vendido"] == D("1.222")  # 4000 vs 1800


# ---------------------------------------------------------------- carga (Task 3)
class StoreMemoria:
    def __init__(self, guardados):
        self.guardados, self.calculos, self.puts = dict(guardados), 0, []

    def fechamento(self, mes):
        return None

    def get(self, mes):
        return self.guardados.get(mes)

    def inicio_calculo(self):
        return datetime(2026, 11, 10, 9)

    def put(self, r, calculo_inicio):
        self.puts.append(r.mes)
        self.guardados[r.mes] = r

    def marcar_desatualizado(self, mes):
        pass


@pytest.fixture
def store_memoria(monkeypatch):
    import frontend.services.comercial.snapshot as snap
    from frontend.services.comercial.snapshot import ResultadoMes
    guardados = {}
    for m in range(1, 10):  # jan–set guardados, velhos (de outro dia)
        mes = date(2026, m, 1)
        guardados[mes] = ResultadoMes(mes, [linha("AT4", "Black", "100", mes)], [], datetime(2026, 10, 1))
    st = StoreMemoria(guardados)

    def fake(mes, hoje):
        st.calculos += 1
        return ResultadoMes(mes, [linha("AT4", "Black", "50", date(2026, 10, 3))], [], hoje)
    monkeypatch.setattr(snap, "calcular_mes", fake)
    return st


def test_acumulado_nunca_calcula_mes_passado_e_sinaliza_faltantes(store_memoria):
    from frontend.services.comercial.desempenho import carregar_acumulado
    del store_memoria.guardados[date(2026, 3, 1)]  # mês passado sem nada guardado
    linhas, desde, faltantes = carregar_acumulado(P_OUT, store=store_memoria)
    assert store_memoria.calculos == 1 and store_memoria.puts == [date(2026, 10, 1)]  # só o mês do fim
    assert faltantes == [date(2026, 3, 1)] and len(linhas) == 9
    assert desde == datetime(2026, 10, 1)  # o mais antigo usado


def test_acumulado_completo_sem_faltantes(store_memoria):
    from frontend.services.comercial.desempenho import carregar_acumulado
    linhas, _, faltantes = carregar_acumulado(P_OUT, store=store_memoria)
    assert faltantes == [] and len(linhas) == 10 and store_memoria.calculos == 1


def test_acumulado_mes_do_fim_sempre_por_obter_mes_e_corta_depois_do_fim(store_memoria):
    from frontend.services.comercial.desempenho import carregar_acumulado
    from frontend.services.comercial.snapshot import ResultadoMes
    # outubro guardado mas desatualizado -> recalcula (é o que a tela mostra); linha de 03/10 passa do fim 02/10
    store_memoria.guardados[date(2026, 10, 1)] = ResultadoMes(
        date(2026, 10, 1), [], [], datetime(2026, 10, 1), desatualizado=True)
    livre = Periodo(date(2026, 9, 20), date(2026, 10, 2), None)
    linhas, _, _f = carregar_acumulado(livre, store=store_memoria)
    assert store_memoria.calculos == 1
    assert all(l.data.date() <= date(2026, 10, 2) for l in linhas) and len(linhas) == 9


def test_carregar_linhas_e_telas_carregar(monkeypatch):
    from frontend.services.comercial import desempenho
    from frontend.services.comercial.snapshot import ResultadoMes
    monkeypatch.setattr(desempenho.telas, "carregar", lambda p: ResultadoMes(p.mes, ATUAL, [], datetime(2026, 11, 1)))
    assert desempenho.carregar_linhas(P_OUT) == ATUAL


def test_acumulado_mistura_congelado_tz_aware_com_guardado_naive(store_memoria):
    from datetime import timezone
    from frontend.services.comercial.desempenho import carregar_acumulado
    from frontend.services.comercial.snapshot import ResultadoMes
    # jan fechado: fechado_em timestamptz (UTC) = 2026-01-31 23:00 SP -> mais antigo que os naive de 01/10
    congelado = ResultadoMes(date(2026, 1, 1), [linha("AT4", "Black", "10", date(2026, 1, 5))], [],
                             datetime(2026, 2, 1, 2, tzinfo=timezone.utc), fechado=True,
                             fechado_em=datetime(2026, 2, 1, 2, tzinfo=timezone.utc))
    store_memoria.fechamento = lambda mes: congelado if mes == date(2026, 1, 1) else None
    linhas, desde, _f = carregar_acumulado(P_OUT, store=store_memoria)
    assert desde == datetime(2026, 1, 31, 23) and desde.tzinfo is None
    assert len(linhas) == 10


# ---------------------------------------------------------------- Task 4: ressalvas da revisão da Task 2
def test_vendedora_sem_venda_no_periodo_ganha_linha_zerada():
    sem_venda = [l for l in ATUAL if l.vendedor_codigo != "AT4"]
    v = view_desempenho(sem_venda, COMP, COMPARACAO, ACUM, P_OUT, ACESSO_EDILEIA, METAS_SO_DELA,
                        meta_time=METAS_TOTAL)
    assert [r["codigo"] for r in v["vendedores"]] == ["AT4"]
    r = v["vendedores"][0]
    assert r["qtd"] == 0 and r["vendido"] == D("0") and r["contribuicao"] == D("0.000")
    assert r["contribuicao_ano"] is not None and r["pct_meta"] == D("0.000")
    assert v["resumo"]["posicao"] is None
    assert "AT9" not in str(v) and "Zelia" not in str(v)


def test_gestor_nao_ganha_linha_zerada():
    v = view_desempenho([l for l in ATUAL if l.vendedor_codigo != "AT4"], COMP, COMPARACAO, ACUM, P_OUT,
                        ACESSO_MASTER, METAS, meta_time=METAS_TOTAL)
    assert "AT4" not in [r["codigo"] for r in v["vendedores"]]


def test_evolucao_atual_alinha_com_a_comparacao():
    # mês corrente: série atual vai até hoje, mesmo sem venda nos últimos dias
    v = view_desempenho(ATUAL, COMP, COMPARACAO, ACUM, P_OUT, ACESSO_MASTER, METAS, meta_time=METAS_TOTAL,
                        hoje=date(2026, 10, 20))
    assert len(v["evolucao"]["atual"]) == 20
    assert v["evolucao"]["atual"][-1] == D("4000")
    # mês encerrado: até o último dia do período
    v2 = view_desempenho(ATUAL, COMP, COMPARACAO, ACUM, P_OUT, ACESSO_MASTER, METAS, meta_time=METAS_TOTAL,
                         hoje=date(2026, 11, 6))
    assert len(v2["evolucao"]["atual"]) == 31
    assert len(v2["evolucao"]["comparacao"]) == 30
    g = v2["grafico"]
    assert len(g["atual"]) == 31 and g["atual"][-1] == 4000.0 and len(g["rotulos"]) == 31


def test_acumulado_incompleto_zera_contribuicao_ano():
    v = view_desempenho(ATUAL, COMP, COMPARACAO, ACUM, P_OUT, ACESSO_EDILEIA, METAS_SO_DELA,
                        meta_time=METAS_TOTAL, acumulado_incompleto=True)
    assert v["acumulado_incompleto"] is True and v["vendedores"][0]["contribuicao_ano"] is None


def test_ia_nao_muda_posicao_nem_contribuicao():
    sem_ia = [l for l in ATUAL if l.papel != "ia"]
    a = view_desempenho(ATUAL, COMP, COMPARACAO, ACUM, P_OUT, ACESSO_EDILEIA, METAS_SO_DELA, meta_time=METAS_TOTAL)
    b = view_desempenho(sem_ia, COMP, COMPARACAO, ACUM, P_OUT, ACESSO_EDILEIA, METAS_SO_DELA, meta_time=METAS_TOTAL)
    assert a["resumo"]["posicao"] == b["resumo"]["posicao"] == 2
    assert a["vendedores"][0]["contribuicao"] == b["vendedores"][0]["contribuicao"] == D("0.250")
    assert a["vendedores"][0]["contribuicao_meta"] == D("0.200")  # 1000 de meta do time 5000
