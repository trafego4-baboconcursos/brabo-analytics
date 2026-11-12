"""Ilustração → vídeo pela API de vídeo da ElevenLabs (flows/video, start_frame)."""
import base64

import pytest

from scripts.video.eleven_video import duracao_veo, montar_pedido


def test_duracao_e_a_menor_do_veo_que_cobre_a_cena():
    assert duracao_veo(3.27) == 4      # sem-faculdade
    assert duracao_veo(4.4) == 6       # tem-filho
    assert duracao_veo(5.48) == 6      # dona-de-casa
    assert duracao_veo(8.0) == 8
    with pytest.raises(ValueError, match="8 s"):
        duracao_veo(9.5)


def test_filtro_tira_as_faixas_pretas_e_volta_ao_tamanho():
    from scripts.video.eleven_video import filtro_aparar
    # Veo devolve 1080×1920 com 4 px pretos de cada lado: corta, amplia e recorta no centro
    assert filtro_aparar("crop=1072:1920:4:0", 1080, 1920) == "crop=1068:1920:6:0,scale=1080:-2,crop=1080:1920"
    assert filtro_aparar("crop=1080:1920:0:0", 1080, 1920) is None      # sem faixa: não mexe


def test_vai_e_volta_so_quando_a_cena_e_mais_longa_que_o_video():
    from scripts.video.eleven_video import voltas_vai_e_volta
    assert voltas_vai_e_volta(4.0, 3.5) == 0      # o vídeo já cobre a cena
    assert voltas_vai_e_volta(8.0, 11.6) == 1     # ida + volta = 16 s
    assert voltas_vai_e_volta(8.0, 16.0) == 1
    assert voltas_vai_e_volta(8.0, 20.7) == 2     # 2× (ida + volta) = 32 s


def test_pedido_usa_o_desenho_como_primeiro_quadro_sem_audio(tmp_path):
    img = tmp_path / "dona.jpg"
    img.write_bytes(b"\xff\xd8fake")
    p = montar_pedido(img, "leve movimento", segundos=5.48)
    assert p["model_id"] == "veo-3.1-fast-generate-001"
    assert (p["duration_secs"], p["aspect_ratio"], p["resolution"], p["generate_audio"]) == (6, "9:16", "1080p", False)
    assert p["start_frame"] == {"type": "inline_base64", "mime_type": "image/jpeg",
                                "content_base64": base64.b64encode(b"\xff\xd8fake").decode()}
    assert "câmera parada" in p["prompt"] and "leve movimento" in p["prompt"]
