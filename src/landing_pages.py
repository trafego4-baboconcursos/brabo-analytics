"""Landing page de um anúncio — extração do link do criativo e normalização da URL.

Compartilhado entre o ETL do Meta (grava `ad_landing_pages`), a auditoria de LPs
(`scripts/ads/auditar_lps.py`) e a página /landing-pages: os três precisam chegar na mesma URL para o
mesmo anúncio e ler as métricas com as mesmas faixas.
"""
from __future__ import annotations

from urllib.parse import urlsplit

# Faixas de leitura no celular — (limite do "bom", limite do "ruim"), pelo corte do Google
# (web.dev/vitals para LCP/INP/CLS/FCP/TTFB; Lighthouse para TBT e nota). Entre os dois = "precisa
# melhorar". Usadas pela auditoria (alerta no "ruim") e pela página /landing-pages (cores).
FAIXAS_CWV = {
    "lcp": (2.5, 4.0),        # s — maior elemento visível carregado
    "fcp": (1.8, 3.0),        # s — primeiro conteúdo na tela
    "cls": (0.1, 0.25),       # layout pulando
    "tbt_ms": (200, 600),     # ms — tempo travado por script (proxy do INP no laboratório)
    "inp_ms": (200, 500),     # ms — resposta ao toque (só usuários reais, CrUX)
    "ttfb_ms": (800, 1800),   # ms — resposta do servidor
    "si": (3.4, 5.8),         # s — Speed Index
}
NOTA_BOA, NOTA_RUIM = 90, 50  # nota de performance do Lighthouse (maior é melhor)


def faixa(metrica: str, valor) -> str:
    """'bom' | 'medio' | 'ruim' | '' (sem valor) — para colorir a métrica."""
    if valor is None:
        return ""
    if metrica == "nota":
        return "bom" if valor >= NOTA_BOA else ("ruim" if valor < NOTA_RUIM else "medio")
    bom, ruim = FAIXAS_CWV[metrica]
    return "bom" if valor <= bom else ("ruim" if valor > ruim else "medio")


def links_do_criativo(creative: dict) -> list[str]:
    """Links de um creative do Meta: asset_feed_spec (dinâmico/feed+story), link_data (imagem e
    carrossel) e o CTA de video_data."""
    oss, afs = creative.get("object_story_spec") or {}, creative.get("asset_feed_spec") or {}
    links = [u.get("website_url", "") for u in afs.get("link_urls", [])]
    ld, vd = oss.get("link_data") or {}, oss.get("video_data") or {}
    links += [ld.get("link", "")] + [c.get("link", "") for c in ld.get("child_attachments", [])]
    links.append(((vd.get("call_to_action") or {}).get("value") or {}).get("link", ""))
    return [l for l in links if l]


def normalizar_url(url: str) -> str:
    """Sem query/fragmento, host minúsculo, com barra no fim — a UTM e o {lpurl} não mudam a página."""
    p = urlsplit(url.strip())
    caminho = p.path if p.path.endswith("/") else p.path + "/"
    return f"{p.scheme.lower() or 'https'}://{p.netloc.lower()}{caminho}"


def lp_do_criativo(creative: dict) -> str | None:
    """A LP do anúncio: o primeiro link normalizado. Anúncio com mais de uma LP (raro: carrossel com
    destinos diferentes) fica com a primeira."""
    links = links_do_criativo(creative)
    return normalizar_url(links[0]) if links else None
