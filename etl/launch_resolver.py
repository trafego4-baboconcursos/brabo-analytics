"""Resolve o lançamento correto pra uma linha de dado (campanha + data),
protegendo contra reatribuição retroativa quando uma campanha é renomeada.

Motivação: campanhas Meta/Google às vezes são renomeadas pra reaproveitar
estrutura/aprendizado do próximo lançamento (ex.: campanha criada durante o
PBB-JUN-26, depois renomeada pra "[old][PBB-AGO-26]"). Classificar só pelo
nome ATUAL faria todo o histórico de gasto — inclusive os dias em que a
campanha ainda rodava pelo lançamento anterior — migrar retroativamente pro
lançamento novo. Aqui, o lançamento é resolvido pela DATA do gasto: qual
lançamento do mesmo produto (prefixo PBB/PES/PI) tinha a janela
[data_inicio, data_fim] ativa naquele dia — não o nome que a campanha carrega
hoje.
"""
from __future__ import annotations

import re
import unicodedata
from datetime import date, datetime
from functools import lru_cache
from pathlib import Path

import yaml
from sqlalchemy import text

CODE_RE = re.compile(r"\b(PBB|PES|PI)-\w{3}-\d{2}\b", re.IGNORECASE)
PREFIX_RE = re.compile(r"\b(PBB|PES|PI)-", re.IGNORECASE)

_INSTAGRAM_ACCOUNTS_YAML = Path(__file__).resolve().parents[1] / "config" / "instagram_accounts.yaml"

# ── Perpétuo / Distribuição de Conteúdo ──────────────────────────────────
# Campanhas always-on (sem janela de datas) não seguem PBB/PES/PI. São
# identificadas por tag no nome + palavra-chave, e mapeadas pra um
# pseudo-lançamento (linha em dim_lancamentos com data_fim bem no futuro),
# permitindo reaproveitar 100% das tabelas/views já existentes.
#
# ATENÇÃO: as campanhas reais ainda não foram auditadas/padronizadas com
# essas tags (levantamento em performance-manager/LEVANTAMENTO_PERPETUO_DISTRIBUICAO.md,
# pendências #1 e #2) — este matching é best-effort e deve ser revisado
# assim que a nomenclatura real for confirmada.
PERPETUO_TAG_RE = re.compile(r"\[perp[ée]tuo\]", re.IGNORECASE)
DISTRIBUICAO_TAG_RE = re.compile(r"\[distribui[çc][ãa]o\]", re.IGNORECASE)

# vertical → (código do pseudo-lançamento, palavras-chave que podem aparecer
# no nome da campanha, já sem acento e em minúsculo)
PERPETUO_VERTICALS: list[tuple[str, tuple[str, ...]]] = [
    ("PERPETUO-PMQ-TJSP", ("tj-sp", "tjsp", "tj sp", "[tj]")),
    ("PERPETUO-PMQ-INSS", ("inss",)),
    ("PERPETUO-PMQ-PBB",  ("banco do brasil", "[bb]", " bb ", "-bb-")),
    ("PERPETUO-PLANNER",  ("planner",)),
]

# Fallback: campanhas de tráfego pago always-on que já rodam hoje SEM a tag
# [perpétuo] — convenção real confirmada em 2026-09-01: "[compra][frio]" +
# tag curta de produto ([BB]/[INSS]/[TJ]/[TJSP]), sem código de lançamento
# (PBB-MES-AA etc.) no nome. Só entra aqui se não achar um código de
# lançamento de verdade — nunca sobrepõe uma campanha de lançamento real.
COMPRA_FRIO_RE = re.compile(r"\[compra\]", re.IGNORECASE)
FRIO_RE = re.compile(r"\[frio\]", re.IGNORECASE)


def _strip_accents(text_value: str) -> str:
    normalized = unicodedata.normalize("NFKD", text_value)
    return "".join(ch for ch in normalized if not unicodedata.combining(ch))


@lru_cache(maxsize=1)
def _load_distribuicao_experts() -> list[tuple[str, str]]:
    """Devolve [(código do pseudo-lançamento, chave de busca sem acento)]
    a partir de config/instagram_accounts.yaml — mesmos experts já usados
    na aba Instagram (leitura orgânica)."""
    if not _INSTAGRAM_ACCOUNTS_YAML.exists():
        return []
    cfg = yaml.safe_load(_INSTAGRAM_ACCOUNTS_YAML.read_text(encoding="utf-8")) or {}
    experts = []
    for account in cfg.get("accounts", []):
        name = account.get("name") or ""
        if not name:
            continue
        slug = _strip_accents(name).upper().replace(" ", "-")
        codigo = f"DISTRIBUICAO-{slug}"
        experts.append((codigo, _strip_accents(name).lower()))
        # Aliases: expert sem Instagram próprio, posta pelo perfil de outro
        # (ex: Ivan Neto → @braboconcursos) — mesma tag [distribuição], nome
        # diferente no meio da campanha, mesmo pseudo-lançamento de destino.
        for alias in account.get("aliases") or []:
            experts.append((codigo, _strip_accents(alias).lower()))
    return experts


def resolve_perpetuo_or_distribuicao_code(campaign_name: str | None) -> str | None:
    """Código do pseudo-lançamento pra campanhas always-on de Perpétuo
    (tráfego pago contínuo) ou Distribuição de Conteúdo (mídia paga que
    impulsiona o orgânico de um expert). None se a campanha não tiver
    nenhuma das duas tags no nome."""
    if not campaign_name:
        return None
    name_sem_acento = _strip_accents(campaign_name).lower()

    if PERPETUO_TAG_RE.search(campaign_name):
        for codigo, keywords in PERPETUO_VERTICALS:
            if any(kw in name_sem_acento for kw in keywords):
                return codigo
        return None

    if DISTRIBUICAO_TAG_RE.search(campaign_name):
        for codigo, keyword in _load_distribuicao_experts():
            if keyword in name_sem_acento:
                return codigo
        return None

    if (
        COMPRA_FRIO_RE.search(campaign_name)
        and FRIO_RE.search(campaign_name)
        and not extract_code_from_text(campaign_name)
    ):
        for codigo, keywords in PERPETUO_VERTICALS:
            if any(kw in name_sem_acento for kw in keywords):
                return codigo

    return None


def extract_code_from_text(campaign_name: str | None) -> str | None:
    if not campaign_name:
        return None
    match = CODE_RE.search(str(campaign_name))
    return match.group(0).upper() if match else None


def extract_prefix(campaign_name: str | None) -> str | None:
    if not campaign_name:
        return None
    match = PREFIX_RE.search(str(campaign_name))
    return match.group(1).upper() if match else None


@lru_cache(maxsize=1)
def _load_launch_windows() -> dict[str, list[tuple]]:
    from db import get_engine  # etl/db.py; import local pra evitar ciclo de import

    engine = get_engine()
    with engine.connect() as conn:
        rows = conn.execute(
            text("SELECT codigo, data_inicio, data_fim FROM dim_lancamentos ORDER BY data_inicio")
        ).fetchall()
    by_prefix: dict[str, list[tuple]] = {}
    for codigo, inicio, fim in rows:
        prefix = codigo.split("-")[0].upper()
        by_prefix.setdefault(prefix, []).append((inicio, fim, codigo))
    return by_prefix


def _to_date(value) -> date | None:
    if value is None:
        return None
    if isinstance(value, date):
        return value
    if isinstance(value, datetime):
        return value.date()
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def resolve_launch_code(campaign_name: str | None, row_date) -> str | None:
    """Código do lançamento pra uma linha de dado (campanha + data).

    Prioridade: janela [data_inicio, data_fim] do mesmo produto que contém
    row_date. Sem match (spend fora de qualquer janela cadastrada — ex.:
    lançamento futuro ainda sem linha em dim_lancamentos, ou campanha
    always-on fora de qualquer período), cai pro código extraído do nome
    (comportamento anterior).

    Campanhas de Perpétuo/Distribuição de Conteúdo (tag `[perpétuo]` ou
    `[distribuição]` no nome, sem janela de datas) são resolvidas antes de
    qualquer coisa — não passam pela lógica de prefixo/janela de lançamento.
    """
    perpetuo_ou_distribuicao = resolve_perpetuo_or_distribuicao_code(campaign_name)
    if perpetuo_ou_distribuicao:
        return perpetuo_ou_distribuicao

    prefix = extract_prefix(campaign_name)
    if not prefix:
        return None
    parsed_date = _to_date(row_date)
    if parsed_date is not None:
        for inicio, fim, codigo in _load_launch_windows().get(prefix, []):
            if inicio <= parsed_date <= fim:
                return codigo
    return extract_code_from_text(campaign_name)
