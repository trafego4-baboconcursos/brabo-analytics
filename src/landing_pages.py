"""Landing page de um anúncio — extração do link do criativo e normalização da URL.

Compartilhado entre o ETL do Meta (grava `ad_landing_pages`, base da seção "Carregamento da página"
em /meta) e a auditoria de LPs (`scripts/ads/auditar_lps.py`): os dois precisam chegar na mesma URL
para o mesmo anúncio.
"""
from __future__ import annotations

from urllib.parse import urlsplit


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
