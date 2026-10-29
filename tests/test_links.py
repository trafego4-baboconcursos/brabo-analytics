"""Encurtador de links (/links) — regras que dá pra testar sem banco.

A leitura e a gravação dependem do schema `encurtador` no banco comercial e
ficam no smoke (``tests/test_frontend_smoke.py``).
"""
import os

import pytest

os.environ["PRE_WARM_CACHE"] = "false"
os.environ.setdefault("SECRET_KEY", "smoke-secret-key-para-testes")
os.environ.setdefault("SUPABASE_DB_URL", "postgresql://smoke:smoke@127.0.0.1:1/smoke")
os.environ.setdefault("SUPABASE_USERS_URL", "postgresql://smoke:smoke@127.0.0.1:1/smoke")

from frontend.services import links as lk  # noqa: E402


def test_slug_reservado_e_formato():
    assert lk.valida_slug("ebook-tjsp") is None
    assert "reservado" in lk.valida_slug("api")       # caminho do próprio app Brabo Links
    assert lk.valida_slug("Com Espaço") is not None
    assert lk.valida_slug("") is not None
    assert lk.slugify("Aula 1 — Semana do INSS!") == "aula-1-semana-do-inss"


def test_destino_precisa_de_dominio():
    assert lk.normaliza_destino("braboconcursos.com.br/x") == "https://braboconcursos.com.br/x"
    assert lk.valida_destino("https://nada") is not None
    assert lk.valida_destino("https://youtu.be/abc") is None


def test_categoria_detectada_pelo_destino():
    assert lk.detecta_categoria("https://www.youtube.com/watch?v=1") == "youtube"
    assert lk.detecta_categoria("https://pay.hotmart.com/X123") == "checkout"
    assert lk.detecta_categoria("https://wa.me/5511999999999") == "whatsapp"
    assert lk.detecta_categoria("https://drive.google.com/file/d/1") == "ebook"
    assert lk.detecta_categoria("https://exemplo.org") == "pagina"


def test_formulario_exige_medium_junto_com_source():
    base = {"destino": "https://braboconcursos.com.br", "slug": "home"}
    with pytest.raises(lk.LinkInvalido, match="utm_medium"):
        lk.campos_do_formulario({**base, "utm_source": "ig"})
    c = lk.campos_do_formulario({**base, "utm_source": "ig", "utm_medium": "social", "campanha": "pes-nov-26"})
    assert c["campanha"] == "PES-NOV-26"
    assert c["titulo"] == "home"                      # sem título, usa o nome
    assert c["categoria"] == "vendas"


def test_destino_final_utm_fixa_substitui_a_do_destino():
    link = {"destino": "https://site.com/p?utm_source=velho&x=1", "utm_source": "ig", "utm_medium": "social",
            "utm_campaign": "[MA][cadastro]", "utm_content": "", "utm_term": ""}
    final = lk.destino_final(link)
    assert final.startswith("https://site.com/p?x=1&")
    assert "utm_source=ig" in final and "velho" not in final
    assert "utm_campaign=%5BMA%5D%5Bcadastro%5D" in final


def test_rotas_do_encurtador_registradas():
    from frontend.app import app
    from frontend.routes import links

    caminhos = {r.path for r in links.router.routes}
    assert {"/links", "/links/{link_id}", "/api/links", "/api/links/{link_id}"} <= caminhos
    incluidos = [getattr(r, "original_router", None) for r in app.routes]
    assert links.router in incluidos, "router de links não incluído no app"
