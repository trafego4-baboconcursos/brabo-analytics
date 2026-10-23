from datetime import date

from src.periodo import MAX_DIAS, resolver_periodo

HOJE = date(2026, 10, 23)


def test_atalho_de_dias_termina_hoje():
    assert resolver_periodo(7, hoje=HOJE) == (date(2026, 10, 17), HOJE, 7, False)
    assert resolver_periodo(30, hoje=HOJE)[:2] == (date(2026, 9, 24), HOJE)


def test_intervalo_livre_vale_quando_os_dois_vem():
    r = resolver_periodo(30, "2026-09-01", "2026-09-30", hoje=HOJE)
    assert r == (date(2026, 9, 1), date(2026, 9, 30), 30, True)


def test_intervalo_incompleto_ou_invalido_cai_no_atalho():
    assert resolver_periodo(7, "2026-09-01", None, hoje=HOJE)[3] is False
    assert resolver_periodo(7, "lixo", "2026-09-30", hoje=HOJE)[3] is False
    assert resolver_periodo(0, hoje=HOJE)[2] == 30           # dias inválidos → 30
    assert resolver_periodo(9999, hoje=HOJE)[2] == 30


def test_datas_invertidas_sao_trocadas_e_futuro_e_cortado():
    r = resolver_periodo(30, "2026-09-30", "2026-09-01", hoje=HOJE)
    assert r[:2] == (date(2026, 9, 1), date(2026, 9, 30))
    r = resolver_periodo(30, "2026-10-20", "2026-12-31", hoje=HOJE)      # fim no futuro
    assert r[:2] == (date(2026, 10, 20), HOJE) and r[3] is True
    r = resolver_periodo(30, "2027-01-01", "2027-02-01", hoje=HOJE)      # tudo no futuro: vira o dia de hoje
    assert r[:3] == (HOJE, HOJE, 1)


def test_intervalo_livre_tem_teto():
    r = resolver_periodo(30, "2020-01-01", "2026-10-01", hoje=HOJE)
    assert r[2] == MAX_DIAS and r[1] == date(2026, 10, 1)
