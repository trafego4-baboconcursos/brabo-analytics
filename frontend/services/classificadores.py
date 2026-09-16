"""
frontend/services/classificadores.py — Leitura do nome e das UTMs de uma venda.

Funções puras: recebem texto (nome de campanha, utm_source/medium/content/term)
e devolvem rótulo. Sem banco, sem estado, sem I/O — é o que permite que
``test_core.py`` as exercite sem subir nada.

Não confundir com ``frontend/db_readers/nomenclatura.py``: aquele lê o padrão de
colchetes do nome da campanha na plataforma (``[MA][CAPTAÇÃO][QUENTE]…``); estes
aqui trabalham em cima das UTMs que chegam junto com a venda, onde o texto vem
solto e a decisão é por palavra encontrada.
"""
from __future__ import annotations

import re

from frontend.utils import _norm_text


def _find_header_col(header: list[str], *parts: str) -> int | None:
    for i, col in enumerate(header):
        norm = _norm_text(col)
        if all(part in norm for part in parts):
            return i
    return None


def _classify_campaign(campaign: str, source: str = "", medium: str = "") -> dict:
    text = _norm_text(f"{source} {medium} {campaign}")
    data = {"channel": "Outros", "etapa": "Outros", "temperatura": "Outros", "bucket": "Outros"}
    if any(token in text for token in ["[ma]", "facebook", "fb", "meta", "instagram"]):
        data["channel"] = "Meta Ads"
    elif any(token in text for token in ["[ga]", "google", "youtube", "yt", "gads", "adwords"]):
        data["channel"] = "Google Ads"
    for tokens, label in [
        (["captacao", "capta", "cadastro", "compra", "compras"], "Captação"),
        (["pre-qualificacao", "pre-quali", "pre quali"], "Pré-Qualificação"),
        (["engajamento", "replay", "trafego"], "RMK/Engajamento"),
        (["matriculas", "pitch", "roas"], "Pitch/ROAS"),
    ]:
        if any(token in text for token in tokens):
            data["etapa"] = label
            break
    for token, label in [("quente", "Quente"), ("frio", "Frio"), ("especifico", "Específico"), ("lookalike", "Frio")]:
        if token in text:
            data["temperatura"] = label
            break
    for token, label in [("principal", "Principal"), ("potencial", "Potencial"), ("reels", "Reels"), ("novos-ads", "Novos Ads (teste)"), ("novos_ads", "Novos Ads (teste)")]:
        if token in text:
            data["bucket"] = label
            break
    return data


def _extract_ad_code(value: str) -> str:
    match = re.search(r"\bAD\d+\b", str(value or ""), flags=re.IGNORECASE)
    return match.group(0).upper() if match else ""


def _match_google_type_tokens(text: str) -> str:
    if any(token in text for token in ["pmax", "p-max", "performance max", "performance-max"]):
        return "PMax"
    if any(token in text for token in ["display", "gdn"]):
        return "Display"
    if any(token in text for token in ["search", "pesquisa", "rede de pesquisa"]):
        return "Search"
    if any(token in text for token in ["youtube", "yt-", "video", "vídeo"]):
        return "YouTube"
    if "geracao de demanda" in text or "geração de demanda" in text:
        return "Geração de demanda"
    return ""


def _classify_google_campaign_type(campaign: str = "", source: str = "", medium: str = "", content: str = "", term: str = "", campaign_type: str = "") -> str:
    # O tipo vem do NOME da campanha (convenção [search]/[p-max]/[display]).
    # content/term carregam nomes de público ("...afinidade-personalizada-...-pesquisa-google")
    # que NÃO indicam o tipo — só entram como fallback quando a UTM não trouxe
    # o nome da campanha (ex.: PI-AGO-26, onde apenas o utm_term tinha a informação).
    campaign_text = _norm_text(f"{source} {medium} {campaign} {campaign_type}")
    tipo = _match_google_type_tokens(campaign_text)
    if tipo:
        return tipo
    if "[ga]" in campaign_text and any(token in campaign_text for token in ["cadastro", "capta", "pre-qualifica"]):
        # Campanha nomeada na convenção mas sem tag de tipo = geração de demanda.
        return "Geração de demanda"
    full_text = _norm_text(f"{source} {medium} {campaign} {content} {term} {campaign_type}")
    tipo = _match_google_type_tokens(full_text)
    if tipo:
        return tipo
    if "[ga]" in full_text and any(token in full_text for token in ["cadastro", "capta", "pre-qualifica"]):
        return "Geração de demanda"
    return "Google sem AD"


_GOOGLE_TIPO_MERGE = {
    "YouTube": "YouTube + Geração de Demanda",
    "Geração de demanda": "YouTube + Geração de Demanda",
}
_GOOGLE_TIPO_ORDER = ["PMax", "Search", "YouTube + Geração de Demanda"]


def _merge_google_tipo_sales(tipo_sales: dict | None) -> dict:
    """Agrupa YouTube + Geração de Demanda em uma única categoria."""
    merged: dict[str, dict] = {}
    for tipo, s in (tipo_sales or {}).items():
        key = _GOOGLE_TIPO_MERGE.get(tipo, tipo)
        bucket = merged.setdefault(key, {"vendas": 0, "faturamento": 0.0})
        bucket["vendas"] += int(s.get("vendas") or 0)
        bucket["faturamento"] += float(s.get("faturamento") or 0.0)
    ordered = {k: merged[k] for k in _GOOGLE_TIPO_ORDER if k in merged}
    for k, v in merged.items():
        if k not in ordered:
            ordered[k] = v
    return ordered


def _inc_sales(target: dict, key: str, receita: float = 0.0, vendas: int = 1) -> None:
    if key not in target:
        target[key] = {"vendas": 0, "faturamento": 0.0}
    target[key]["vendas"] += vendas
    target[key]["faturamento"] += receita


def _utm_score(launch_code: str, source: str, medium: str, campaign: str, content: str, term: str = "") -> int:
    text = _norm_text(f"{source} {medium} {campaign} {content} {term}")
    score = 0
    if _norm_text(launch_code) in text:
        score += 100
    cls = _classify_campaign(campaign, source, medium)
    if cls["channel"] in ("Meta Ads", "Google Ads"):
        score += 20
    if cls["etapa"] == "Captação":
        score += 15
    if _extract_ad_code(f"{source} {medium} {campaign} {content} {term}"):
        score += 40
    if cls["channel"] == "Google Ads" and _classify_google_campaign_type(campaign, source, medium, content, term) in ("Search", "PMax", "Display"):
        score += 35
    if source or medium or campaign:
        score += 1
    return score
