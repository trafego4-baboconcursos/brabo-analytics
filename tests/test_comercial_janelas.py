from datetime import date, datetime

from frontend.db_readers.comercial import janelas_do_periodo

LINHAS = [
    ("PES-SET-26", date(2026, 9, 14), ["6857003"], ["29395"]),   # 14/09 -> 22/09
    ("BV-26", date(2026, 10, 7), ["8643509"], []),               # quarta -> 05/10 a 13/10
    ("PBB-AGO-26", None, ["6857021"], ["29396"]),                # sem data: pulado
    ("PI-NOV-26", "2026-11-16", ["6856971"], None),              # texto ISO
    ("X-SET-26", date(2026, 9, 29), [], []),                     # 28/09 -> 06/10 (cruza o mês)
]


def test_filtra_por_sobreposicao_e_pula_sem_data():
    out = janelas_do_periodo(LINHAS, date(2026, 10, 1), date(2026, 10, 31))
    assert [j.lancamento for j in out] == ["BV-26", "X-SET-26"]
    bv = out[0]
    assert bv.inicio == datetime(2026, 10, 5) and bv.fim == datetime(2026, 10, 12, 23, 59, 59)
    assert bv.produtos_hotmart == frozenset({"8643509"}) and bv.produtos_tmb == frozenset()


def test_texto_iso_e_produtos_nulos():
    out = janelas_do_periodo(LINHAS, date(2026, 11, 1), date(2026, 11, 30))
    assert [j.lancamento for j in out] == ["PI-NOV-26"]
    assert out[0].produtos_tmb == frozenset()


def test_borda_ultimo_dia():
    out = janelas_do_periodo(LINHAS, date(2026, 9, 1), date(2026, 9, 28))
    assert [j.lancamento for j in out] == ["PES-SET-26", "X-SET-26"]


def test_aulas_sobrescreve_e_preenche_data_faltante():
    out = janelas_do_periodo(LINHAS, date(2026, 8, 1), date(2026, 8, 31),
                             aulas={"PBB-AGO-26": date(2026, 8, 17)})
    assert [j.lancamento for j in out] == ["PBB-AGO-26"]
    assert out[0].inicio == datetime(2026, 8, 17) and out[0].fim == datetime(2026, 8, 24, 23, 59, 59)
    bv = janelas_do_periodo(LINHAS, date(2026, 10, 1), date(2026, 10, 31),
                            aulas={"BV-26": date(2026, 10, 14)})[0]
    assert bv.inicio == datetime(2026, 10, 12)
