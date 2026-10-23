from frontend.db_readers.instagram_detail import _por_formato, _taxas_por_alcance


def _post(tipo, reach, likes=0, comments=0, saved=0, shares=0, views=None):
    inter = likes + comments + saved + shares
    return {"media_type": tipo, "reach": reach, "like_count": likes, "comments_count": comments, "saved": saved,
            "shares": shares, "views": views, "engagement_alcance": inter}


def test_taxas_sao_media_ponderada_pelo_alcance_e_ignoram_post_sem_alcance():
    posts = [
        _post("VIDEO", 1000, likes=50, comments=10, saved=30, shares=10),   # 100 interações
        _post("IMAGE", 3000, likes=100, comments=0, saved=0, shares=20),    # 120 interações
        _post("IMAGE", None, likes=999),                                    # sem alcance coletado: fora da conta
    ]
    t = _taxas_por_alcance(posts)
    assert t["er_alcance"] == 5.5       # 220 ÷ 4000
    assert t["taxa_salvamento"] == 0.75  # 30 ÷ 4000
    assert t["taxa_envio"] == 0.75       # 30 ÷ 4000


def test_sem_nenhum_alcance_as_taxas_ficam_none_e_nao_dividem_por_zero():
    t = _taxas_por_alcance([_post("IMAGE", None, likes=5)])
    assert t == {"er_alcance": None, "taxa_salvamento": None, "taxa_envio": None}
    assert _taxas_por_alcance([]) == {"er_alcance": None, "taxa_salvamento": None, "taxa_envio": None}


def test_por_formato_agrupa_rotula_e_ordena_pelo_alcance_medio():
    posts = [_post("IMAGE", 500, likes=5), _post("VIDEO", 2000, likes=40), _post("CAROUSEL_ALBUM", 800, saved=8),
             _post("VIDEO", 1000, likes=10), _post("STRANGE", 100)]
    linhas = _por_formato(posts)
    assert [l["formato"] for l in linhas] == ["Reels / Vídeo", "Carrossel", "Imagem", "Outros"]
    reels = linhas[0]
    assert reels["posts"] == 2 and reels["avg_reach"] == 1500
