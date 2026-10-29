"""Regras puras do ETL das aulas ao vivo: janela, numeração das aulas, chat por minuto."""
from __future__ import annotations

import pathlib
import sys
from datetime import date, datetime, timezone

_ETL = pathlib.Path(__file__).resolve().parent.parent / "etl"
if str(_ETL) not in sys.path:
    sys.path.insert(0, str(_ETL))

from etl_youtube_analytics import _aulas_na_janela, _curva_de_rows, _janela_aulas, _janelas  # noqa: E402
from youtube_live_chat import contar_mensagens  # noqa: E402


def _live(vid, inicio, status="complete", titulo="Aula"):
    snip = {"title": titulo, "liveChatId": f"chat-{vid}"}
    if inicio:
        snip["actualStartTime"] = inicio
    return {"id": vid, "snippet": snip, "status": {"lifeCycleStatus": status}}


def test_janela_vai_do_evento_ao_fim_do_carrinho_e_aulas_ate_4_dias_depois_do_evento():
    cfg = {"evento_start_date": date(2026, 11, 9), "evento_end_date": date(2026, 11, 14),
           "carrinho_end_date": "2026-11-20"}
    assert _janelas(cfg, date(2026, 11, 8)) is None
    assert _janelas(cfg, date(2026, 11, 9)) == ((date(2026, 11, 9), date(2026, 11, 18)),
                                                (date(2026, 11, 9), date(2026, 11, 20)))
    assert _janelas(cfg, date(2026, 11, 20)) is not None
    assert _janelas(cfg, date(2026, 11, 21)) is None


def test_aula_5_do_pi_abr_26_cai_na_janela():
    # Evento 06–09/04 no wizard; a Aula 5 foi na segunda, 13/04.
    jan = _janela_aulas({"evento_start_date": "2026-04-06", "evento_end_date": "2026-04-09"})
    assert jan == (date(2026, 4, 6), date(2026, 4, 13))


def test_sem_evento_a_semana_vem_da_abertura_do_carrinho():
    # PI-JAN-26: abertura 15/01 (Aula 4), Aula 1 em 12/01, Aula 5 em 19/01.
    jan = _janela_aulas({"carrinho_start_date": "2026-01-12", "abertura_oficial_carrinho": date(2026, 1, 15)})
    assert jan == (date(2026, 1, 9), date(2026, 1, 19))
    # 2025: só carrinho_start (= dia da Aula 4).
    assert _janela_aulas({"carrinho_start_date": "2025-01-16"}) == (date(2025, 1, 10), date(2025, 1, 20))
    assert _janela_aulas({"carrinho_end_date": "2026-11-20"}) is None
    assert _janelas({"carrinho_end_date": "2026-11-20"}, date(2026, 11, 10)) is None


def test_aulas_sao_as_lives_da_janela_em_ordem_pela_data_de_brasilia():
    broadcasts = [
        _live("mentoria", "2026-09-22T22:15:37Z"),            # depois do evento
        _live("aula2", "2026-09-15T22:56:38Z"),
        _live("agendada", None, status="ready"),              # não começou
        _live("aula1", "2026-09-14T22:56:53Z"),
        _live("aula3", "2026-09-17T02:30:00Z", status="live"),  # 16/09 23h30 em Brasília
        _live("vespera", "2026-09-14T02:00:00Z"),             # 13/09 23h em Brasília
        _live("plataforma", "2026-09-14T20:00:00Z", titulo="Dominando a Plataforma TJSP - Setembro 2026"),
        _live("mentoria2", "2026-09-16T22:00:00Z", titulo="Mentoria Inaugural TJ-SP"),
    ]
    aulas = _aulas_na_janela(broadcasts, date(2026, 9, 14), date(2026, 9, 19))
    assert [a["id"] for a in aulas] == ["aula1", "aula2", "aula3"]
    assert [a["no_ar"] for a in aulas] == [False, False, True]
    assert aulas[2]["chat_id"] == "chat-aula3"


def test_curva_da_api_vira_pico_e_media_por_minuto():
    assert _curva_de_rows([[0, 5, 10], [60, 1399, 1744]]) == [
        {"posicao_seg": 0, "media_simult": 5, "simultaneos": 10},
        {"posicao_seg": 60, "media_simult": 1399, "simultaneos": 1744},
    ]


def _msg(quando, tipo="textMessageEvent"):
    return {"snippet": {"type": tipo, "publishedAt": quando}}


def test_chat_conta_por_minuto_da_transmissao_e_ignora_o_que_nao_e_mensagem():
    inicio = datetime(2026, 11, 9, 22, 0, 0, tzinfo=timezone.utc)
    contagem: dict[int, int] = {}
    tocados = contar_mensagens([
        _msg("2026-11-09T21:59:50Z"),                        # antes do início: minuto 0
        _msg("2026-11-09T22:00:59Z"),
        _msg("2026-11-09T22:01:00Z"),
        _msg("2026-11-09T22:01:30Z", tipo="superChatEvent"),
        _msg("2026-11-09T22:01:40Z", tipo="newSponsorEvent"),  # não é mensagem
    ], inicio, contagem, corte=-1)
    assert contagem == {0: 2, 60: 2}
    assert tocados == {0, 60}


def test_chat_retomado_nao_conta_de_novo_o_que_ja_esta_no_banco():
    inicio = datetime(2026, 11, 9, 22, 0, 0, tzinfo=timezone.utc)
    contagem = {0: 40, 60: 35}  # lido do banco ao reiniciar
    contar_mensagens([_msg("2026-11-09T22:00:10Z"), _msg("2026-11-09T22:01:10Z"),
                      _msg("2026-11-09T22:02:10Z")], inicio, contagem, corte=60)
    assert contagem == {0: 40, 60: 35, 120: 1}
