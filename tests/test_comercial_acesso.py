import pytest

from frontend.services.comercial import acesso as ac
from frontend.services.comercial.acesso import AcessoComercial, acesso_comercial, nivel_comercial, pode

ACOES_TUDO = ["ver_time", "editar_regras", "editar_participacoes", "aprovar", "lancar_bonus",
              "fechar_mes", "ver_proprio", "reivindicar"]
SO_VENDEDOR = {"ver_proprio", "reivindicar"}


@pytest.fixture(autouse=True)
def _limpa():
    ac.limpar_cache()


@pytest.mark.parametrize("nivel", ["master", "coordenador"])
@pytest.mark.parametrize("acao", ACOES_TUDO)
def test_master_coordenador_tudo(nivel, acao):
    assert pode(nivel, acao) is True


@pytest.mark.parametrize("acao", ACOES_TUDO)
def test_vendedor(acao):
    assert pode("vendedor", acao) is (acao in SO_VENDEDOR)


@pytest.mark.parametrize("acao", ACOES_TUDO)
def test_sem_nivel(acao):
    assert pode(None, acao) is False


def test_acao_desconhecida_nega():
    assert pode("master", "xyz") is False


def test_admin_vira_master_sem_consultar():
    def ler(_):
        raise AssertionError("não deveria consultar")
    r = acesso_comercial({"role": "admin", "email": "a@x.com"}, ler=ler)
    assert r == AcessoComercial("master", None)
    assert nivel_comercial({"role": "admin", "email": "a@x.com"}, ler=ler) == "master"


def test_email_desconhecido_none():
    assert acesso_comercial({"role": "leitura", "email": "z@x.com"}, ler=lambda e: None) is None
    assert nivel_comercial({"role": "leitura", "email": "z@x.com"}, ler=lambda e: None) is None


def test_email_normalizado_e_codigo():
    vistos = []
    def ler(e):
        vistos.append(e)
        return {"nivel": "vendedor", "vendedor_codigo": "V1"}
    r = acesso_comercial({"role": "comercial", "email": "  Ana@X.COM "}, ler=ler)
    assert vistos == ["ana@x.com"]
    assert r == AcessoComercial("vendedor", "V1")


def test_sem_email():
    assert acesso_comercial({"role": "comercial"}, ler=lambda e: {"nivel": "master"}) is None


def test_tabela_ausente_none(monkeypatch):
    from sqlalchemy.exc import ProgrammingError
    def lanca(email):
        raise ProgrammingError("s", {}, Exception('relation "comercial_acessos" does not exist'))
    monkeypatch.setattr(ac, "_ler_banco", lanca)
    assert acesso_comercial({"role": "comercial", "email": "a@x.com"}) is None


def test_outro_erro_propaga(monkeypatch):
    def lanca(email):
        raise RuntimeError("conexão caiu")
    monkeypatch.setattr(ac, "_ler_banco", lanca)
    with pytest.raises(RuntimeError):
        acesso_comercial({"role": "comercial", "email": "a@x.com"})


def test_cache_60s(monkeypatch):
    n = []
    monkeypatch.setattr(ac, "_ler_banco", lambda e: n.append(e) or {"nivel": "master", "vendedor_codigo": None})
    u = {"role": "comercial", "email": "a@x.com"}
    acesso_comercial(u); acesso_comercial(u)
    assert len(n) == 1


@pytest.mark.parametrize("codigo", [None, "", "  "])
def test_vendedor_sem_codigo_fail_closed(codigo):
    r = acesso_comercial({"role": "comercial", "email": "v@x.com"},
                         ler=lambda e: {"nivel": "vendedor", "vendedor_codigo": codigo})
    assert r is None


def test_master_sem_codigo_ok():
    r = acesso_comercial({"role": "comercial", "email": "m@x.com"},
                         ler=lambda e: {"nivel": "master", "vendedor_codigo": None})
    assert r == AcessoComercial("master", None)


def test_ddl_check_e_indice():
    from frontend.db_readers.comercial import DDL
    j = "\n".join(DDL)
    assert "nivel <> 'vendedor' OR vendedor_codigo IS NOT NULL" in j
    assert "ux_comercial_acessos_email_lower" in j


@pytest.mark.parametrize("acao", ACOES_TUDO)
def test_consulta_so_ve_o_time(acao):
    # Financeiro/RH (10/11/26): vê o que o gestor vê, não altera nada
    assert pode("consulta", acao) is (acao == "ver_time")


def test_consulta_sem_codigo_tem_acesso():
    r = acesso_comercial({"role": "comercial", "email": "fin@x.com"},
                         ler=lambda _e: {"nivel": "consulta", "vendedor_codigo": None})
    assert r == AcessoComercial("consulta", None)
