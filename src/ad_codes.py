"""Extração do código de anúncio a partir do nome do criativo.

A convenção corrente é `ADxxx - Descrição...` (AD + número), usada como chave
de atribuição entre Meta, Google, UTMs e vendas.

O BV-25 (Black Vitalícia 2025) é a exceção: rodou antes dessa padronização,
com `AD-<iniciais><n>` e variantes por etapa do lançamento —
ADC (Cadastro), ADR (Reconhecimento), ADL (Lembrete), além de UGC para
criativo de terceiro. O regex corrente pega só 7 dos 237 nomes do lançamento.

Por isso a exceção é resolvida POR LANÇAMENTO, e não estendendo o regex
global: a chave de atribuição dos lançamentos ativos (PBB/PES/PI) fica
intacta. Para um `ADxxx` clássico os dois caminhos devolvem o mesmo valor.
"""
from __future__ import annotations

import re

# Convenção corrente — não mexer sem revisar a atribuição de todos os lançamentos.
AD_CODE_RE = re.compile(r"(AD\d+)", re.IGNORECASE)

# BV-25: prefixo de etapa (AD/ADC/ADR/ADL) ou UGC, hífen e espaços opcionais,
# iniciais do responsável opcionais (FE=Felipe, IV=Ivan, MA=Mateus, TR=trio).
# Cobre os 237 nomes distintos do lançamento (Meta + Google).
LEGACY_AD_CODE_RE = re.compile(r"\b(AD[CRL]?|UGC)\s*-?\s*([A-Z]{2})?\s*(\d+)\b", re.IGNORECASE)

# Lançamentos que não seguem a convenção corrente.
_LEGACY_LAUNCHES = {"BV-25"}


def uses_legacy_ad_codes(launch_code: str | None) -> bool:
    return (launch_code or "").strip().upper() in _LEGACY_LAUNCHES


def extract_ad_code(ad_name: str | None, launch_code: str | None = None) -> str:
    """Código do anúncio, normalizado em maiúsculas. String vazia se não houver.

    Sem `launch_code`, ou para um lançamento que segue a convenção corrente,
    usa só `ADxxx`.
    """
    name = str(ad_name or "")
    if not name:
        return ""
    if uses_legacy_ad_codes(launch_code):
        match = LEGACY_AD_CODE_RE.search(name)
        if match:
            prefix = match.group(1).upper()
            initials = (match.group(2) or "").upper()
            number = match.group(3)
            # "AD- TR25" e "AD-TR25" são o mesmo criativo: normaliza o espaço.
            return f"{prefix}-{initials}{number}" if initials else f"{prefix}{number}"
        return ""
    match = AD_CODE_RE.search(name)
    return match.group(1).upper() if match else ""
