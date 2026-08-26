"""
frontend/services/instagram.py — Perfis de Instagram dos experts via Graph API (business_discovery).

business_discovery permite consultar dados públicos de qualquer perfil Instagram
Business/Creator (foto, bio, seguidores, nº de posts) usando uma conta Instagram
Business nossa como "ponte" — não precisa do expert autorizar nada.
Requer:
    META_ACCESS_TOKEN        — com escopo instagram_basic (além de ads_read)
    INSTAGRAM_BUSINESS_ID    — ID da conta Instagram Business/Creator usada como ponte
Sem essas duas variáveis, ou se o perfil consultado não for Business/Creator,
a função devolve só o link do perfil (sem métricas).
"""
from __future__ import annotations
import os
import time as _time

import requests

from logger import get_logger

logger = get_logger("frontend")

API_VERSION = "v22.0"

EXPERTS = [
    {"name": "Mateus Andrade",   "username": "mateusandrade.me"},
    {"name": "Brabo Concursos",  "username": "braboconcursos"},
    {"name": "Felipe Graton",    "username": "felipegraton"},
]

_CACHE: dict[str, tuple[float, dict]] = {}
_CACHE_TTL = 3600  # 1h — dados de perfil mudam pouco


def _fetch_business_discovery(username: str) -> dict | None:
    token = os.environ.get("META_ACCESS_TOKEN")
    ig_id = os.environ.get("INSTAGRAM_BUSINESS_ID")
    if not token or not ig_id:
        return None
    url = f"https://graph.facebook.com/{API_VERSION}/{ig_id}"
    params = {
        "fields": (
            f"business_discovery.username({username})"
            "{username,name,biography,followers_count,media_count,profile_picture_url}"
        ),
        "access_token": token,
    }
    try:
        resp = requests.get(url, params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json().get("business_discovery")
        return data or None
    except Exception:
        logger.warning("Instagram business_discovery falhou para @%s", username, exc_info=True)
        return None


def get_instagram_profiles() -> list[dict]:
    """Retorna a lista de experts com o que der pra trazer da API no momento.
    Sempre inclui link do perfil; métricas (seguidores, posts, bio, foto) só
    aparecem se INSTAGRAM_BUSINESS_ID/META_ACCESS_TOKEN estiverem configurados
    e o perfil consultado for Business/Creator."""
    api_configured = bool(os.environ.get("META_ACCESS_TOKEN") and os.environ.get("INSTAGRAM_BUSINESS_ID"))
    profiles = []
    for expert in EXPERTS:
        username = expert["username"]
        cached = _CACHE.get(username)
        if cached and (_time.time() - cached[0]) < _CACHE_TTL:
            data = cached[1]
        else:
            data = _fetch_business_discovery(username) or {}
            _CACHE[username] = (_time.time(), data)
        profiles.append({
            "name": expert["name"],
            "username": username,
            "profile_url": f"https://instagram.com/{username}",
            "followers_count": data.get("followers_count"),
            "media_count": data.get("media_count"),
            "biography": data.get("biography"),
            "profile_picture_url": data.get("profile_picture_url"),
            "api_ok": bool(data),
        })
    return {"profiles": profiles, "api_configured": api_configured}
