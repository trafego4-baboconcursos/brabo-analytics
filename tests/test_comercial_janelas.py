from datetime import date, datetime

from frontend.db_readers.comercial import janelas_do_periodo

# (lançamento, evento_start_date, aulas_start_date, produtos hotmart, produtos tmb)
LINHAS = [
    ("PES-SET-26", date(2026, 9, 14), date(2026, 9, 14), ["6857003"], ["29395"]),  # 14/09 -> 22/09
    ("BV-26", date(2026, 10, 14), date(2026, 10, 5), ["8643509", " "], []),       # live 14/10 -> 12/10 a 19/10
    ("PBB-AGO-26", None, None, ["6857021"], ["29396"]),                           # sem data: alerta
    ("PI-NOV-26", None, "2026-11-16", "6856971", None),                           # sem evento: usa aulas (texto)
    ("X-SET-26", date(2026, 9, 29), None, [], []),                                # 28/09 -> 06/10 (cruza o mês)
]


def test_evento_vence_aulas_e_filtra_por_sobreposicao():
    janelas, sem_data = janelas_do_periodo(LINHAS, date(2026, 10, 1), date(2026, 10, 31))
    assert [j.lancamento for j in janelas] == ["BV-26", "X-SET-26"]
    bv = janelas[0]
    assert bv.inicio == datetime(2026, 10, 12) and bv.fim == datetime(2026, 10, 19, 23, 59, 59)
    assert bv.produtos_hotmart == frozenset({"8643509"}) and bv.produtos_tmb == frozenset()
    assert sem_data == [("PBB-AGO-26", frozenset({"6857021"}), frozenset({"29396"}))]


def test_evento_nulo_usa_aulas_e_produto_texto():
    janelas, _ = janelas_do_periodo(LINHAS, date(2026, 11, 1), date(2026, 11, 30))
    assert [j.lancamento for j in janelas] == ["PI-NOV-26"]
    assert janelas[0].inicio == datetime(2026, 11, 16)
    assert janelas[0].produtos_hotmart == frozenset({"6856971"}) and janelas[0].produtos_tmb == frozenset()


def test_borda_ultimo_dia():
    janelas, _ = janelas_do_periodo(LINHAS, date(2026, 9, 1), date(2026, 9, 28))
    assert [j.lancamento for j in janelas] == ["PES-SET-26", "X-SET-26"]


def test_live_sobrescreve_e_preenche_data_faltante():
    janelas, sem_data = janelas_do_periodo(LINHAS, date(2026, 8, 1), date(2026, 8, 31),
                                           live={"PBB-AGO-26": date(2026, 8, 17)})
    assert [j.lancamento for j in janelas] == ["PBB-AGO-26"] and sem_data == []
    assert janelas[0].inicio == datetime(2026, 8, 17) and janelas[0].fim == datetime(2026, 8, 24, 23, 59, 59)
    bv = janelas_do_periodo(LINHAS, date(2026, 10, 1), date(2026, 10, 31),
                            live={"BV-26": date(2026, 10, 5)})[0][0]
    assert bv.inicio == datetime(2026, 10, 5)
