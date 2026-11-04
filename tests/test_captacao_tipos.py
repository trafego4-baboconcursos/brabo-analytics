"""Captação por plataforma e tipo: a classificação pelo nome e a soma por bloco."""
import pytest

from frontend.db_readers.captacao_tipos import montar_blocos, tipo_da_campanha


@pytest.mark.parametrize("nome,tipo", [
    ("[MA][cadastro][captação][quente][principal][PES-NOV-26][26.10.26]", "Principal"),
    ("[MA][cadastro][captação][quente][potencial][PI-NOV-26][02.11.26]", "Potencial"),
    ("[MA][cadastro][captação][frio][imagem][PES-NOV-26][26.10.26]", "Imagem"),
    ("[MA][cadastro][captação][frio][carrossel][PES-NOV-26][04.11.26]", "Carrossel"),
    ("[MA][cadastro][captação][quente][reels][PES-NOV-26][26.10.26]", "Reels/Shorts"),
    ("[GA][cadastro][captação][quente][shorts][PES-NOV-26][26.10.26]", "Reels/Shorts"),
    ("[GA][cadastro][captação][quente][principal][PES-NOV-26][02.11.26] #2", "Principal"),
    ("[MA][cadastro][captação][quente][pós-edital][PES-NOV-26][26.10.26]", "Pós-edital"),
    ("[GA][cadastro][captação][frio][PES-NOV-26][26.10.26]", "Outros"),
])
def test_tipo_da_campanha(nome, tipo):
    assert tipo_da_campanha(nome) == tipo


def test_blocos_somam_e_mostram_extras_so_com_gasto():
    blocos = montar_blocos({"Facebook": [
        ("[MA][captação][quente][principal][X]", 600.0, 60),
        ("[MA][captação][frio][principal][X]", 400.0, 20),
        ("[MA][captação][quente][reels][X]", 100.0, 0),
    ]})
    b = blocos[0]
    por_tipo = {r["tipo"]: r for r in b["linhas"]}
    assert list(por_tipo) == ["Principal", "Potencial", "Imagem", "Carrossel", "Reels/Shorts"]  # sem extras
    assert por_tipo["Principal"]["campanhas"] == 2 and por_tipo["Principal"]["gasto"] == 1000.0
    assert por_tipo["Principal"]["leads"] == 80 and por_tipo["Principal"]["cpl"] == pytest.approx(12.5)
    assert por_tipo["Reels/Shorts"]["cpl"] == 0.0 and por_tipo["Potencial"]["gasto"] == 0.0
    assert b["total"]["gasto"] == 1100.0 and b["total"]["leads"] == 80
    assert sum(r["pct_gasto"] for r in b["linhas"]) == pytest.approx(100.0)


def test_pos_edital_entra_como_linha_extra_e_fecha_o_total():
    b = montar_blocos({"YouTube": [("[GA][captação][quente][pós-edital][X]", 300.0, 30.4),
                                   ("[GA][captação][quente][principal][X]", 100.0, 10)]})[0]
    assert [r["tipo"] for r in b["linhas"]][-1] == "Pós-edital"
    assert sum(r["gasto"] for r in b["linhas"]) == b["total"]["gasto"] == 400.0
