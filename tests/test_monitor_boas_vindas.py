"""Monitor de boas-vindas no dia de abertura do carrinho (/boas-vindas) — o que dá
pra testar sem banco nem Active Campaign: datas da Hotmart, série de 5 em 5 min,
quem conta como falha e qual lançamento abre em que dia.

As regras vêm do carrinho do PES-NOV-26 (12/11/26), ver o docstring de
frontend/services/monitor_boas_vindas.py.
"""
import os

os.environ["PRE_WARM_CACHE"] = "false"
os.environ.setdefault("SECRET_KEY", "smoke-secret-key-para-testes")
os.environ.setdefault("SUPABASE_DB_URL", "postgresql://smoke:smoke@127.0.0.1:1/smoke")
os.environ.setdefault("SUPABASE_USERS_URL", "postgresql://smoke:smoke@127.0.0.1:1/smoke")

from datetime import date, datetime, timedelta  # noqa: E402

from frontend.services.monitor_boas_vindas import (  # noqa: E402
    BR, aberta_em, chave_bucket, classificar, config, hora_da_compra, linha_para_abertura, montar_serie,
    parse_hm, tem_monitor,
)


def test_so_os_lancamentos_da_mentoria_vitalicia_tem_a_pagina():
    assert tem_monitor("PES-NOV-26") and tem_monitor("pi-nov-26") and tem_monitor("PBB-AGO-26")
    assert not tem_monitor("BV-26") and not tem_monitor(None) and not tem_monitor("")


def test_menu_do_lancamento_tem_boas_vindas_ao_lado_de_campanhas():
    from frontend.core import _build_funis_nav_groups  # noqa: PLC0415

    def links(codigo, role="admin"):
        grupos = _build_funis_nav_groups(None, codigo, "boas_vindas", {"role": role}, None)
        return {lk["page"]: lk for g in grupos for lk in g["links"]}

    pes = links("PES-NOV-26")
    assert pes["boas_vindas"]["href"] == "/boas-vindas?launch_code=PES-NOV-26"
    assert pes["boas_vindas"]["enabled"] is True
    assert links("BV-26")["boas_vindas"]["enabled"] is False
    assert "boas_vindas" not in links("PES-NOV-26", role="trafego")   # tráfego não vê e-mail de comprador


def test_parse_hm_aceita_os_tres_formatos_da_hotmart():
    # epoch em ms e em s (12/11/26 08:00:00 em Brasília = 11:00 UTC)
    assert parse_hm("1794481200000") == datetime(2026, 11, 12, 8, 0, tzinfo=BR)
    assert parse_hm("1794481200") == datetime(2026, 11, 12, 8, 0, tzinfo=BR)
    assert parse_hm("12/11/2026 08:03:10") == datetime(2026, 11, 12, 8, 3, 10, tzinfo=BR)
    assert parse_hm("12/11/2026") == datetime(2026, 11, 12, tzinfo=BR)
    assert parse_hm("2026-11-12T11:00:00Z") == datetime(2026, 11, 12, 8, 0, tzinfo=BR)
    assert parse_hm("") is None and parse_hm(None) is None and parse_hm("lixo") is None


def _h(hh, mm):
    return datetime(2026, 11, 12, hh, mm, tzinfo=BR)


def test_serie_acumula_ate_o_fim_de_cada_bloco_e_comeca_na_primeira_compra():
    inicio = datetime(2026, 11, 12, tzinfo=BR)
    compras = [_h(8, 0), _h(8, 1), _h(8, 7)]
    entradas = [_h(8, 2), _h(8, 9)]
    serie = montar_serie(inicio, _h(8, 11), compras, entradas, {"2026-11-12T08:15-03:00": 1})
    assert [p["rotulo"] for p in serie] == ["08:00", "08:05", "08:10", "08:15"]
    assert [p["compradores"] for p in serie] == [0, 2, 3, 3]
    assert [p["entradas"] for p in serie] == [0, 1, 2, 2]
    assert serie[-1]["fila"] == 1 and serie[0]["fila"] is None


def test_bloco_em_andamento_mostra_a_hora_da_leitura_e_nao_o_fim_do_bloco():
    # Às 08:06 a linha atual dizia "08:10" (Mateus, 19/11/26). Ao vivo, mostra 08:06.
    inicio = datetime(2026, 11, 12, tzinfo=BR)
    serie = montar_serie(inicio, _h(8, 6), [_h(8, 0), _h(8, 5)], [], {}, marcar_agora=True)
    assert [p["rotulo"] for p in serie] == ["08:00", "08:05", "08:06"]
    assert [p["agora"] for p in serie] == [False, False, True]
    assert serie[-1]["t"] == "2026-11-12T08:10-03:00" and serie[-1]["compradores"] == 2
    # Sem marcar (dia encerrado), continua o fim do bloco.
    assert montar_serie(inicio, _h(8, 6), [_h(8, 0)], [], {})[-1]["rotulo"] == "08:10"


def test_chave_da_fila_e_o_fim_do_bloco_atual():
    assert chave_bucket(_h(8, 11)) == "2026-11-12T08:15-03:00"
    assert chave_bucket(_h(8, 15)) == "2026-11-12T08:20-03:00"


def test_classificar_separa_ja_aluno_a_caminho_e_faltando():
    agora = _h(8, 30)
    compras = {
        "entrou@x.com": (_h(8, 0), "TJSP"),
        "veterano@x.com": (_h(8, 0), "TJSP"),     # comprou antes: ficar fora está certo
        "novo@x.com": (_h(8, 5), "TJSP"),         # aluno novo há 25 min fora: é o problema
        "recente@x.com": (_h(8, 20), "TJSP · BLP"),  # há 10 min: ainda pode chegar
    }
    r = classificar(compras, {"entrou@x.com"}, {"veterano@x.com"}, agora, tolerancia_min=15)
    assert [f["email"] for f in r["faltando"]] == ["novo@x.com"]
    assert r["faltando"][0]["hora"] == "08:05"
    assert r["a_caminho"] == 1 and r["ja_alunos"] == 1
    assert r["situacao"] == {"entrou@x.com": "entrou", "veterano@x.com": "ja_aluno",
                             "novo@x.com": "fora", "recente@x.com": "a_caminho"}


def test_classificar_lista_faltando_do_mais_antigo_pro_mais_novo():
    agora = _h(9, 0)
    compras = {"b@x.com": (_h(8, 10), "p"), "a@x.com": (_h(8, 1), "p")}
    r = classificar(compras, set(), set(), agora, 15)
    assert [f["email"] for f in r["faltando"]] == ["a@x.com", "b@x.com"]


def test_abertura_usa_a_oficial_e_so_produto_numerico():
    por_projeto = config()["por_projeto"]
    a = linha_para_abertura({
        "lancamento_codigo": "PES-NOV-26", "carrinho_start_date": date(2026, 11, 9),
        "carrinho_end_date": date(2026, 11, 23),
        "abertura_oficial_carrinho": date(2026, 11, 12), "abertura_oficial_hora": "07:58",
        "hotmart_produto_ids": ["6857003", "8829061", "oferta:izfne8k1"],
    }, por_projeto)
    assert a["dia"] == date(2026, 11, 12) and a["hora"] == "07:58"
    assert a["fim"] == date(2026, 11, 23)   # o monitor vai até o fim do carrinho cadastrado
    assert a["produtos"] == ["6857003", "8829061"]
    assert a["tag_gatilho"] == "[MENT] [VIT] [TJSP]"


def test_janela_vai_da_abertura_ao_fim_do_carrinho():
    por_projeto = config()["por_projeto"]
    a = linha_para_abertura({"lancamento_codigo": "PES-NOV-26", "abertura_oficial_carrinho": "2026-11-12",
                             "carrinho_end_date": "2026-11-23", "hotmart_produto_ids": ["6857003"]}, por_projeto)
    assert not aberta_em(a, date(2026, 11, 11))
    assert aberta_em(a, date(2026, 11, 12)) and aberta_em(a, date(2026, 11, 18)) and aberta_em(a, date(2026, 11, 23))
    assert not aberta_em(a, date(2026, 11, 24))
    # sem fim cadastrado (ou fim antes da abertura): vale só o dia de abertura
    sem_fim = linha_para_abertura({"lancamento_codigo": "PI-NOV-26", "abertura_oficial_carrinho": "2026-11-19",
                                   "hotmart_produto_ids": ["6856971"]}, por_projeto)
    assert sem_fim["fim"] == date(2026, 11, 19)


def test_pedido_no_carrinho_aprovado_depois_conta_pela_aprovacao():
    # Caso da Talita (18/11/26): pediu em 12/11 08:07 no parcelamento Hotmart, aprovado em 13/11 03:19.
    pedido, aprovacao = _h(8, 7), datetime(2026, 11, 13, 3, 19, tzinfo=BR)
    so_o_dia = (datetime(2026, 11, 12, tzinfo=BR), datetime(2026, 11, 13, tzinfo=BR))
    assert hora_da_compra(pedido, aprovacao, *so_o_dia) == aprovacao   # antes ela sumia da página
    carrinho = (datetime(2026, 11, 12, tzinfo=BR), datetime(2026, 11, 24, tzinfo=BR))
    assert hora_da_compra(pedido, aprovacao, *carrinho) == aprovacao
    # aprovada dentro, pedida antes da abertura: entra (a tag chega na aprovação)
    assert hora_da_compra(datetime(2026, 11, 10, 9, 0, tzinfo=BR), _h(9, 0), *so_o_dia) == _h(9, 0)
    # nem pedido nem aprovação na janela: fora
    assert hora_da_compra(datetime(2026, 11, 10, tzinfo=BR), datetime(2026, 11, 11, tzinfo=BR), *so_o_dia) is None
    # sem a aprovação no banco: vale o pedido
    assert hora_da_compra(pedido, None, *so_o_dia) == pedido


def test_abertura_cai_pro_inicio_do_carrinho_e_ignora_quem_nao_usa_a_automacao():
    por_projeto = config()["por_projeto"]
    sem_oficial = linha_para_abertura({
        "lancamento_codigo": "PI-NOV-26", "carrinho_start_date": "2026-11-16",
        "abertura_oficial_carrinho": None, "hotmart_produto_ids": ["6856971"],
    }, por_projeto)
    assert sem_oficial["dia"] == date(2026, 11, 16) and sem_oficial["curso"] == "INSS"
    # BV-26 (Black Vitalícia) não usa esta automação; lançamento sem produto não tem o que comparar
    assert linha_para_abertura({"lancamento_codigo": "BV-26", "abertura_oficial_carrinho": date(2026, 10, 15),
                                "hotmart_produto_ids": ["8643509"]}, por_projeto) is None
    assert linha_para_abertura({"lancamento_codigo": "PBB-DEZ-26", "abertura_oficial_carrinho": date(2026, 12, 1),
                                "hotmart_produto_ids": []}, por_projeto) is None


def test_serie_de_dia_inteiro_nao_passa_da_meia_noite():
    inicio = datetime(2026, 11, 12, tzinfo=BR)
    fim_do_dia = inicio + timedelta(days=1) - timedelta(seconds=1)
    serie = montar_serie(inicio, fim_do_dia, [_h(23, 58)], [], {})
    assert serie[-1]["t"] == "2026-11-13T00:00-03:00" and serie[-1]["compradores"] == 1


def test_aberturas_guarda_a_mais_recente_e_para_quando_passa_do_dia():
    from frontend.services.monitor_boas_vindas import juntar_pagina_aberturas  # noqa: PLC0415

    desde = datetime(2026, 11, 12, tzinfo=BR)
    acum: dict = {}
    # A API devolve da abertura mais recente pra mais antiga, com fuso do Active (-06:00).
    pagina1 = [
        {"email": "A@x.com ", "tstamp_iso": "2026-11-12T09:00:00-06:00"},   # 12:00 em Brasília
        {"email": "b@x.com", "tstamp_iso": "2026-11-12T06:00:00-06:00"},
    ]
    assert juntar_pagina_aberturas(pagina1, desde, acum) is False      # ainda dentro do dia: continua
    pagina2 = [
        {"email": "a@x.com", "tstamp_iso": "2026-11-12T05:30:00-06:00"},   # abertura mais antiga do mesmo e-mail
        {"email": "velho@x.com", "tstamp_iso": "2026-11-11T20:00:00-06:00"},  # antes do dia: fica de fora
    ]
    assert juntar_pagina_aberturas(pagina2, desde, acum) is True       # passou do dia: para
    assert acum == {"a@x.com": datetime(2026, 11, 12, 12, 0, tzinfo=BR),
                    "b@x.com": datetime(2026, 11, 12, 9, 0, tzinfo=BR)}
    assert juntar_pagina_aberturas([], desde, acum) is True            # página vazia = fim da lista
