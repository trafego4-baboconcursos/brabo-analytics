from frontend.services import criativo_midia as cm


def test_codigo_do_anuncio_no_nome_do_arquivo():
    assert cm._codigo("AD387 - Ivan Carro + leg - PES-NOV-26 (Story).mp4") == "AD387"
    assert cm._codigo("AD123-PQ - INSS [PI-NOV-26] .mp4") == "AD123"
    assert cm._codigo("Card 2 - TJ-SP.jpg") is None
    assert cm._codigo("AD-TR35 - Black") == "AD-TR35"


def test_ordem_dos_quadros_do_carrossel():
    nomes = ["AD417 - Card 10.png", "AD417 - Card 2.png", "AD417 - Card 1.png", "AD417 - Cards - capa.png", "Card 3 - TJ-SP.jpg"]
    assert sorted(nomes, key=cm._ordem) == [
        "AD417 - Cards - capa.png", "AD417 - Card 1.png", "AD417 - Card 2.png", "Card 3 - TJ-SP.jpg", "AD417 - Card 10.png",
    ]


def test_mesma_arte_em_varios_tamanhos_nao_e_carrossel():
    for nome in ("AD210 - 1080X1350.jpg", "AD210 - 1200X628.jpg", "AD210 - 1080x1920.jpg"):
        assert cm._FORMATO_RE.search(nome)
    assert not cm._FORMATO_RE.search("AD417 - Card 3.png")


def test_tipo_do_arquivo():
    assert cm._tipo_arquivo({"mimeType": "image/png", "name": "a.png"}) == "image"
    assert cm._tipo_arquivo({"mimeType": "video/mp4", "name": "a.mp4"}) == "drive_video"
    assert cm._tipo_arquivo({"mimeType": "application/octet-stream", "name": "a.MOV"}) == "drive_video"
    assert cm._tipo_arquivo({"mimeType": "application/vnd.google-apps.document", "name": "prompt"}) is None
