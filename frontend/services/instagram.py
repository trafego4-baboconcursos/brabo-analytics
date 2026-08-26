"""
frontend/services/instagram.py — Perfis de Instagram dos experts via Graph API.

As 3 contas Instagram dos experts são Business/Creator vinculadas a Páginas do
Facebook que administramos — dá pra ler os dados delas direto pelo próprio
ID da conta (sem precisar de business_discovery nem de autorização extra).
Requer:
    META_ACCESS_TOKEN — com escopo instagram_basic (além de ads_read)
Sem essa variável, ou se a chamada falhar, a função devolve só o link do perfil.
"""
from __future__ import annotations
import os
import time as _time

import requests

from logger import get_logger

logger = get_logger("frontend")

API_VERSION = "v22.0"

EXPERTS = [
    {"name": "Mateus Andrade",   "username": "mateusandrade.me", "ig_id": "17841402341156659"},
    {"name": "Brabo Concursos",  "username": "braboconcursos",   "ig_id": "17841456180884668"},
    {"name": "Felipe Graton",    "username": "felipegraton",     "ig_id": "17841460679248187"},
]

_CACHE: dict[str, tuple[float, dict]] = {}
_CACHE_TTL = 3600  # 1h — dados de perfil mudam pouco


def _fetch_profile(ig_id: str) -> dict | None:
    token = os.environ.get("META_ACCESS_TOKEN")
    if not token:
        return None
    url = f"https://graph.facebook.com/{API_VERSION}/{ig_id}"
    params = {
        "fields": "username,name,biography,followers_count,media_count,profile_picture_url",
        "access_token": token,
    }
    try:
        resp = requests.get(url, params=params, timeout=15)
        resp.raise_for_status()
        return resp.json() or None
    except Exception:
        logger.warning("Instagram: falha ao buscar perfil %s", ig_id, exc_info=True)
        return None


def get_instagram_profiles() -> dict:
    """Retorna a lista de experts com o que der pra trazer da API no momento.
    Sempre inclui link do perfil; métricas (seguidores, posts, bio, foto) só
    aparecem se META_ACCESS_TOKEN estiver configurado com instagram_basic."""
    api_configured = bool(os.environ.get("META_ACCESS_TOKEN"))
    profiles = []
    for expert in EXPERTS:
        ig_id = expert["ig_id"]
        cached = _CACHE.get(ig_id)
        if cached and (_time.time() - cached[0]) < _CACHE_TTL:
            data = cached[1]
        else:
            data = _fetch_profile(ig_id) or {}
            _CACHE[ig_id] = (_time.time(), data)
        profiles.append({
            "name": expert["name"],
            "username": expert["username"],
            "profile_url": f"https://instagram.com/{expert['username']}",
            "followers_count": data.get("followers_count"),
            "media_count": data.get("media_count"),
            "biography": data.get("biography"),
            "profile_picture_url": data.get("profile_picture_url"),
            "api_ok": bool(data),
        })
    return {"profiles": profiles, "api_configured": api_configured}
