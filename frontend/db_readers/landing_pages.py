"""
frontend/db_readers/landing_pages.py — Versão da landing page por anúncio.

A versão da LP não cabe em nenhuma UTM: os cinco campos já carregam
lançamento/público/ADxxx e sobrescrever qualquer um quebra uma view existente
(`view_atribuicao`, `view_atribuicao_publicos`). Mas o link de destino de cada
anúncio já é ingerido em `ad_copy_textos` (`campo='link'`, por
`etl_copy_meta.py`/`etl_copy_google.py`) e a versão está no próprio slug da
URL — então o mapa ADxxx → versão sai de graça do que já está no banco.

**Limite conhecido:** um anúncio pode apontar para várias LPs ao mesmo tempo
(Google com vários `final_urls`, carrossel Meta com link por card). Nesses o
ADxxx não determina a página, e o anúncio entra como ambíguo em vez de ser
chutado numa versão — no PES-SET-26 são 26 anúncios / R$ 158 mil. Fechar os
100% exige marcação nascida na própria LP (campo oculto `lp_versao`) — ver
`docs/projetos/PLANO_VERSAO_LANDING_PAGE.md`.

Outro limite: `ad_copy_textos` guarda o link **atual** do anúncio, sem
histórico. Se a LP de um anúncio foi trocada no meio do voo, o período
anterior aparece com a página nova.
"""
from __future__ import annotations

from typing import Any
from urllib.parse import urlsplit

from sqlalchemy import text

from frontend.db import _get_engine
from frontend.db_readers.ga4 import _versao_da_pagina
from frontend.utils import _extract_launch_code


def read_versao_lp_por_ad(launch_folder_or_code: Any) -> dict[str, dict]:
    """ADxxx -> {"versao": "v5"|None, "path": "/projeto-...-v5", "ambiguo": bool}.

    `versao` usa o mesmo parser do GA4 (`_versao_da_pagina`), então o rótulo
    bate com o da seção "Páginas de Captura" e o sufixo de Pré-Quali
    (`v5-pq-fb`) não é fundido com a `v5` de Captação — fundir os dois fazia a
    v5 aparecer com CPA de R$ 2.703 em vez de R$ 885 (achado 19/09/26)."""
    code = _extract_launch_code(launch_folder_or_code)
    if not code:
        return {}

    with _get_engine().connect() as conn:
        rows = conn.execute(
            text("SELECT ad_code, texto FROM ad_copy_textos "
                 "WHERE campo = 'link' AND lancamento_codigo = :code"),
            {"code": code},
        ).fetchall()

    por_ad: dict[str, dict[str, str]] = {}
    for ad_code, url in rows:
        ad = str(ad_code or "").upper()
        if not ad:
            continue
        # o link pode vir com query string (UTM colada na URL por engano, por
        # exemplo) — a versão está no path, não no resto
        path = urlsplit(str(url or "")).path or str(url or "")
        versao = _versao_da_pagina(path)
        if versao:
            por_ad.setdefault(ad, {})[versao] = path.rstrip("/")

    resultado: dict[str, dict] = {}
    for ad, versoes in por_ad.items():
        if len(versoes) == 1:
            versao, path = next(iter(versoes.items()))
            resultado[ad] = {"versao": versao, "path": path, "ambiguo": False}
        else:
            resultado[ad] = {"versao": None, "path": None, "ambiguo": True}
    return resultado
