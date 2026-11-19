"""Snapshot do debriefing com o carrinho aberto não pode usar o cache de vendas vencido.

Incidente 19/11/26 (PI-NOV-26): na abertura entraram 316 vendas em minutos; o snapshot montado na janela do
stale-while-revalidate gravou receita R$ 1.726 e ROAS 0,00x. A montagem agora recalcula os leitores de venda."""
import asyncio
from types import SimpleNamespace

from frontend import cache
from frontend.services import debriefing_build as db


def _rodar(monkeypatch, aberto: bool):
    visto = {}

    async def _build(launch, launches, lazy):
        visto["vendas"] = cache._force_refresh_since(launch.code, "vendas::None::None")
        visto["dia1"] = cache._force_refresh_since(launch.code, "dia1_sales::x")
        visto["meta"] = cache._force_refresh_since(launch.code, "meta::a::b")
        visto["outro_lancamento"] = cache._force_refresh_since("OUTRO-26", "vendas::None::None")
        return {"falhas": []}

    import frontend.db_readers.debriefing_snapshot as snap
    import frontend.services.fetch as fetch
    monkeypatch.setattr(db, "build_debriefing_context", _build)
    monkeypatch.setattr(fetch, "carrinho_aberto", lambda code: aberto)
    monkeypatch.setattr(snap, "write_snapshot", lambda code, built, ms: 1024)
    monkeypatch.setattr(snap, "read_snapshot", lambda code: None)
    asyncio.run(db.refresh_debriefing_snapshot(SimpleNamespace(code="PI-NOV-26"), []))
    return visto


def test_carrinho_aberto_forca_vendas_na_montagem(monkeypatch):
    v = _rodar(monkeypatch, aberto=True)
    assert v["vendas"] is not None and v["dia1"] is not None   # leitores de venda recalculam na hora
    assert v["meta"] is None                                    # o resto segue no cache
    assert v["outro_lancamento"] is None                        # e só este lançamento
    assert cache._FORCE_REFRESH.get() is None                   # o contexto é desfeito no fim


def test_carrinho_fechado_nao_forca_nada(monkeypatch):
    v = _rodar(monkeypatch, aberto=False)
    assert v["vendas"] is None and v["dia1"] is None
