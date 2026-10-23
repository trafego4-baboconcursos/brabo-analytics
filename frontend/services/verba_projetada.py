"""
frontend/services/verba_projetada.py — verba PROJETADA de uma etapa, por plataforma.

A fonte é `launch_config.etapas` (a mesma que alimenta o alerta de orçamento do Slack): cada etapa tem um `total`
em reais e uma lista de `buckets` (público + plataforma + % do total da etapa). A verba projetada de uma
plataforma na etapa é o total da etapa × a soma dos % dos buckets daquela plataforma:

    Pré-Qualificação R$ 150.000 · buckets Meta somam 53% · Google 47%  →  Meta R$ 79.500 · Google R$ 70.500

Etapa sem buckets (Lembrete, Aulas, WhatsApp...) não tem divisão por plataforma: devolve só o total.
"""
from __future__ import annotations

import unicodedata


def _norm(t) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", str(t or "")) if unicodedata.category(c) != "Mn").strip().lower()


def verba_projetada_da_etapa(cfg: dict | None, nome_etapa: str) -> dict | None:
    """{'total', 'meta', 'google'} em reais (plataforma sem bucket = None), ou None se a etapa não existe/está zerada."""
    for et in (cfg or {}).get("etapas") or []:
        if _norm(et.get("nome")) != _norm(nome_etapa):
            continue
        try:
            total = float(et.get("total") or 0)
        except (TypeError, ValueError):
            return None
        if total <= 0:
            return None
        pct = {"meta": 0.0, "google": 0.0}
        for b in et.get("buckets") or []:
            plat = _norm(b.get("plataforma"))
            if plat in pct:
                try:
                    pct[plat] += float(b.get("pct") or 0)
                except (TypeError, ValueError):
                    pass
        return {
            "total": total,
            "meta": total * pct["meta"] / 100 if pct["meta"] > 0 else None,
            "google": total * pct["google"] / 100 if pct["google"] > 0 else None,
        }
    return None
