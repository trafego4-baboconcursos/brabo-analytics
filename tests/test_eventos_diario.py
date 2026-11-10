"""Leitura dos diarios por etapa (brabo-brain, fase 2) em scripts/eventos.py."""
import io
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts"))
import eventos  # noqa: E402


def _diario(tmp_path, nome, corpo):
    p = tmp_path / nome
    io.open(p, "w", encoding="utf-8").write(corpo)
    return str(p)


def test_data_com_hora(tmp_path):
    p = _diario(tmp_path, "DIARIO_PI-NOV-26_2-CAPTACAO.md",
                "### (10/11/26 09h05) Verba da captação ajustada — autor: Murilo\n- corpo\n")
    evs = eventos.ler_itens(p, "PI-NOV-26")
    assert len(evs) == 1
    assert evs[0]["data"] == "2026-11-10"


def test_data_com_hora_formato_antigo(tmp_path):
    p = _diario(tmp_path, "MUDANCAS_PI-NOV-26.md",
                "### 131. (10/11/26 09h05) Murilo pausou o carrossel\n- corpo\n"
                "### 80. (03/11/26 08h22) Mexer no tCPA?\n- corpo\n"
                "### 81. (03/11/26 ~08h40) Mexidas de CPA\n- corpo\n")
    datas = [e["data"] for e in eventos.ler_itens(p, "PI-NOV-26")]
    assert datas == ["2026-11-10", "2026-11-03", "2026-11-03"]


def test_codigo_etapa_diario():
    assert eventos.codigo_etapa_de("DIARIO_PI-NOV-26_2-CAPTACAO.md") == ("PI-NOV-26", "2-CAPTACAO")
    assert eventos.codigo_etapa_de("DIARIO_BV-26_1-AQUECIMENTO.md") == ("BV-26", "1-AQUECIMENTO")
    assert eventos.codigo_etapa_de("DIARIO_PES-NOV-26_9-GERAL.md") == ("PES-NOV-26", "9-GERAL")


def test_codigo_mudancas():
    assert eventos.codigo_etapa_de("MUDANCAS_PI-NOV-26.md") == ("PI-NOV-26", None)
    assert eventos.codigo_etapa_de("ORCAMENTO_PI-NOV-26.md") is None


def test_autor_fora_da_chave(tmp_path):
    sem = _diario(tmp_path, "MUDANCAS_X-26.md", "### 5. (01/11/26) Título igual\n- a\n")
    com = _diario(tmp_path, "DIARIO_X-26_2-CAPTACAO.md", "### 5. (01/11/26) Título igual — autor: Michel\n- a\n")
    e1 = eventos.ler_itens(sem, "X-26")[0]
    e2 = eventos.ler_itens(com, "X-26")[0]
    assert e1["chave"] == e2["chave"]
    assert e2["autor"] == "Michel"
    assert e1["autor"] is None
    assert e2["titulo"] == "5. (01/11/26) Título igual"


def test_etapa_no_evento(tmp_path):
    p = _diario(tmp_path, "DIARIO_X-26_3-REMARKETING.md", "### (12/11/26 10h00) Lembrete no ar — autor: Gustavo\n- a\n")
    ev = eventos.ler_itens(p, "X-26")[0]
    assert ev["etapa"] == "3-REMARKETING"


def test_coletar_le_diarios(tmp_path, monkeypatch):
    base = tmp_path / "docs" / "performance" / "lancamentos" / "X-26"
    (base / "diario").mkdir(parents=True)
    io.open(base / "MUDANCAS_X-26.md", "w", encoding="utf-8").write("# Índice\n\nSem entradas.\n")
    io.open(base / "diario" / "DIARIO_X-26_2-CAPTACAO.md", "w", encoding="utf-8").write(
        "### (02/11/26 10h00) A — autor: Michel\n- a\n### (03/11/26 11h00) B — autor: Gustavo\n- b\n")
    monkeypatch.setattr(eventos, "RAIZ", str(tmp_path))
    evs = eventos.coletar()
    assert [(e["codigo"], e["etapa"], e["autor"]) for e in evs] == [
        ("X-26", "2-CAPTACAO", "Michel"), ("X-26", "2-CAPTACAO", "Gustavo")]
