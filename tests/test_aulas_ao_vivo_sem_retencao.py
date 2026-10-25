from frontend.db_readers import youtube_aulas


def test_retencao_vazia_tem_as_mesmas_chaves_do_retorno_cheio(monkeypatch):
    # sem launch_code o reader nem consulta o banco; o contrato do dicionário vazio é o que o template usa
    vazio = youtube_aulas.read_retencao_video("")
    for chave in ("aulas", "totais", "segmentos", "curvas_js", "tem_pago"):
        assert chave in vazio, f"'{chave}' faltando: o template serializa curvas_js e quebra com 500"
    assert vazio["curvas_js"] == [] and vazio["aulas"] == []
