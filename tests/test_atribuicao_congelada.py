"""A trava da atribuição: o comprador que a `leads` perdeu continua rastreado.

Contexto (07/10/26): a `leads` tem UMA linha por contato, com um
`lancamento_codigo` só. Quando a pessoa se cadastra num lançamento novo, a
linha é reescrita e o lançamento antigo perde o comprador junto com a UTM que o
trouxe — 32% a 41% em todo lançamento fechado. A trava
(`atribuicao_congelada`) guarda a melhor UTM já vista e preenche esse buraco.

Estes testes isolam a lógica de mescla: nenhum toca o banco.
"""
from __future__ import annotations

import pandas as pd
import pytest


class _Launch:
    def __init__(self, code: str):
        self.code = code
        self.folder = None


class _Vendas:
    def __init__(self, emails: set[str]):
        self.emails_hotmart = set(emails)
        self.emails_tmb = set()
        self.phone_por_email = {}
        self.receita_por_email = {e: 1000.0 for e in emails}
        self.vendas_por_email = {e: 1 for e in emails}


_COLS = ["email", "utm_source", "utm_medium", "utm_campaign", "utm_content",
         "utm_term", "phone", "nome", "sobrenome", "email_norm", "nome_norm"]


def _leads_df(linhas: list[dict]) -> pd.DataFrame:
    df = pd.DataFrame(linhas, columns=_COLS)
    for c in _COLS:
        df[c] = df[c].fillna("").astype(str)
    return df


@pytest.fixture
def atribuir(monkeypatch):
    """_sales_attribution com todo acesso a banco trocado por dado em memória."""
    import frontend.services.attribution as attr
    import frontend.db_readers.leads as leads_mod
    import frontend.db_readers.atribuicao_congelada as congelada_mod
    import frontend.services.fetch as fetch_mod
    import frontend.cache as cache_mod

    monkeypatch.setattr(cache_mod, "_get_cached", lambda *a, **k: None)
    monkeypatch.setattr(cache_mod, "_set_cached", lambda *a, **k: None)
    monkeypatch.setattr(fetch_mod, "_launch_cfg", lambda code: {})
    monkeypatch.setattr(leads_mod, "read_term_campaign_map", lambda code: {})

    def _montar(leads_linhas, congeladas, compradores):
        monkeypatch.setattr(
            leads_mod, "read_ac_leads_for_attribution",
            lambda *a, **k: _leads_df(leads_linhas),
        )
        monkeypatch.setattr(congelada_mod, "ler_congelada", lambda code: congeladas)
        return attr._sales_attribution(_Launch("PI-AGO-26"), _Vendas(compradores))

    return _montar


_UTM_META = {
    "score": 5, "source": "facebook", "medium": "cpc",
    "campaign": "[MA][captação][quente][PI-AGO-26]", "content": "AD219", "term": "",
}


def test_comprador_que_a_leads_perdeu_volta_pela_trava(atribuir):
    """A linha dele virou de outro lançamento; a trava ainda o rastreia."""
    sem_trava = atribuir([], {}, {"perdido@test.com"})
    assert sem_trava["emails_rastreados"] == set()
    assert sem_trava["total_rastreado"] == 0

    com_trava = atribuir([], {"perdido@test.com": _UTM_META}, {"perdido@test.com"})
    assert com_trava["emails_rastreados"] == {"perdido@test.com"}
    assert com_trava["total_rastreado"] == 1
    assert com_trava["por_canal"]["Meta Ads"]["vendas"] == 1


def test_dado_ao_vivo_vence_a_trava_quando_tem_score_maior(atribuir):
    """A trava preenche buraco, não sobrescreve o que a leads ainda tem bom."""
    vivo = {
        "email": "vivo@test.com", "email_norm": "vivo@test.com",
        "utm_source": "google", "utm_medium": "cpc",
        "utm_campaign": "[GA][captação][frio][PI-AGO-26]", "utm_content": "AD400",
        "utm_term": "", "phone": "", "nome": "", "sobrenome": "", "nome_norm": "",
    }
    congelada_fraca = {"vivo@test.com": {**_UTM_META, "score": 0}}
    r = atribuir([vivo], congelada_fraca, {"vivo@test.com"})
    assert r["emails_rastreados"] == {"vivo@test.com"}
    # Venceu o Google (ao vivo), não o Meta (congelado de score 0).
    assert "Google Ads" in r["por_canal"]
    assert r["por_canal"].get("Meta Ads") is None


def test_trava_nao_credita_quem_deixou_de_ser_comprador(atribuir):
    """Venda estornada depois do congelamento não volta pela trava."""
    r = atribuir([], {"estornado@test.com": _UTM_META}, set())
    assert r["emails_rastreados"] == set()
    assert r["total_rastreado"] == 0


def test_sem_trava_o_resultado_e_o_de_antes(atribuir):
    """Tabela ausente (dict vazio) = comportamento idêntico ao de antes dela."""
    vivo = {
        "email": "a@test.com", "email_norm": "a@test.com",
        "utm_source": "facebook", "utm_medium": "cpc",
        "utm_campaign": "[MA][captação][quente][PI-AGO-26]", "utm_content": "AD219",
        "utm_term": "", "phone": "", "nome": "", "sobrenome": "", "nome_norm": "",
    }
    r = atribuir([vivo], {}, {"a@test.com"})
    assert r["emails_rastreados"] == {"a@test.com"}
    assert r["total_rastreado"] == 1


def test_leads_vazia_sem_colunas_nao_quebra(monkeypatch):
    """Caso real: a consulta não devolve linha e o DataFrame vem sem `phone`.

    `read_ac_leads_for_attribution` retorna cedo quando o SELECT vem vazio, sem
    criar `email_norm`/`phone`. Antes da trava a atribuição já tinha retornado
    nesse ponto; agora ela segue, então a cascata de telefone precisa da guarda.
    """
    import frontend.services.attribution as attr
    import frontend.db_readers.leads as leads_mod
    import frontend.db_readers.atribuicao_congelada as congelada_mod
    import frontend.services.fetch as fetch_mod
    import frontend.cache as cache_mod

    monkeypatch.setattr(cache_mod, "_get_cached", lambda *a, **k: None)
    monkeypatch.setattr(cache_mod, "_set_cached", lambda *a, **k: None)
    monkeypatch.setattr(fetch_mod, "_launch_cfg", lambda code: {})
    monkeypatch.setattr(leads_mod, "read_term_campaign_map", lambda code: {})
    # Exatamente o que a função devolve no retorno antecipado: só as colunas do SQL.
    crua = pd.DataFrame(columns=["email", "utm_source", "utm_medium", "utm_campaign",
                                 "utm_content", "utm_term", "phone", "nome", "sobrenome"])
    monkeypatch.setattr(leads_mod, "read_ac_leads_for_attribution", lambda *a, **k: crua)
    monkeypatch.setattr(congelada_mod, "ler_congelada",
                        lambda code: {"congelado@test.com": _UTM_META})

    v = _Vendas({"congelado@test.com", "sem_nada@test.com"})
    r = attr._sales_attribution(_Launch("PI-AGO-26"), v)
    assert r["emails_rastreados"] == {"congelado@test.com"}
    assert r["total_rastreado"] == 1
