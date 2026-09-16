"""
frontend/db_readers/_vendas_comum.py — Peças usadas por mais de um leitor de venda.

Não é um "utils" genérico: cada coisa aqui está aqui porque é consultada de dois
ou três lugares diferentes (``sales``, ``hotmart``, ``tmb``) e duplicá-la já
causaria divergência entre o número da Hotmart e o do consolidado.

O caso mais delicado é ``_parcela_unica_info``, que decide se uma linha da
Hotmart é venda à vista, parcelada ou assinatura recorrente — critério usado
tanto na contagem de vendas quanto no faturamento e no dia 1.
"""
from __future__ import annotations

import math
import re
from typing import Any

import pandas as pd

from frontend.utils import _norm_text


def _hm_data_sql(col: str) -> str:
    """Fragmento SQL que extrai a data (fuso America/Sao_Paulo) de uma coluna
    de data da Hotmart — aceita os 3 formatos que a tabela mistura (DD/MM/YYYY,
    epoch em segundos ou milissegundos, ISO timestamptz).

    ÚNICA fonte dessa lógica: usado via COALESCE(_hm_data_sql("data_da_transacao"),
    _hm_data_sql("confirmacao_do_pagamento")) em toda consulta que filtra
    vendas Hotmart por data — antes essa lógica estava duplicada em 2 lugares
    (_query_hotmart e read_hotmart_details) e só um deles tinha a conversão de
    fuso horário corrigida, então via e voltava a divergir. Não duplicar de
    novo — sempre chamar essa função.

    BUG CORRIGIDO (2026-09-11): os ramos de epoch e timestamptz faziam
    `::date` direto, que extrai a data em UTC. Uma venda às 22h39 (Brasília)
    de 24/08 é 01h39 UTC de 25/08 — caía fora da janela do carrinho
    (10-24/08) mesmo tendo acontecido dentro dela. Confirmado comparando
    contra o export oficial da Hotmart: 3 vendas de PI-AGO-26 sumiam por
    causa disso. Agora converte pro fuso de Brasília ANTES de extrair a data.
    """
    return (
        "CASE WHEN NULLIF(" + col + ",'') ~ '^\\d{2}/\\d{2}/\\d{4}' THEN to_date(" + col + ",'DD/MM/YYYY')\n"
        "     WHEN NULLIF(" + col + ",'') ~ '^\\d{10,13}$' THEN (to_timestamp(\n"
        "         CASE WHEN length(NULLIF(" + col + ",'')) = 13\n"
        "              THEN " + col + "::bigint / 1000\n"
        "              ELSE " + col + "::bigint END) AT TIME ZONE 'America/Sao_Paulo')::date\n"
        "     WHEN NULLIF(" + col + ",'') IS NOT NULL THEN (" + col + "::timestamptz AT TIME ZONE 'America/Sao_Paulo')::date END"
    )


def _parcela_unica_info(row) -> tuple[bool, bool, int, int]:
    """Identifica vendas do Hotmart gravadas com o VALOR DA PARCELA em vez do total,
    e separa isso de "é retentativa de cobrança" (que é sempre indicado por
    quantidade_de_cobrancas > 1, independente do tipo_de_cobranca).

    Duas origens gravam com o valor da PARCELA (não o total):
    - CSV do Hotmart: tipo_de_cobranca = "Recuperador Inteligente"
    - Webhook/API (tipo_de_cobranca vazio): o payload só traz recurrence_number
      (gravado em quantidade_de_cobrancas) nesse tipo de compra — a presença do
      campo é o marcador. Validado contra o PI-AGO-26 inteiro comparando cada
      valor com o preço padrão da mesma oferta: 5.436 linhas, separação exata.

    BUG CORRIGIDO (2026-09-11): quantidade_de_cobrancas > 1 sempre indica que
    não é a primeira cobrança desse contrato — isso vale mesmo quando
    tipo_de_cobranca tem um valor normal preenchido (não vazio, não
    "Recuperador Inteligente"). A versão antiga só tratava como retentativa
    quando eh_por_parcela também era verdadeiro, contando cobranças repetidas
    de outros tipos como venda nova (inflou PI-AGO-26 de 1.641 pra 1.960
    matrículas — confirmado comparando contra o export oficial da Hotmart
    filtrado por Quantidade de cobranças=1).

    Retorna (eh_por_parcela, eh_repeticao, cobrancas, parcelas).
    - eh_por_parcela: valor gravado é o da PARCELA, precisa multiplicar por
      `parcelas` pra virar faturamento real.
    - eh_repeticao: linha é retentativa/cobrança subsequente de um contrato já
      contado — nunca é venda nova, independente do tipo_de_cobranca.
    """
    tipo_raw = row.get("tipo_de_cobranca")
    tipo_vazio = (
        tipo_raw is None
        or (isinstance(tipo_raw, float) and math.isnan(tipo_raw))
        or str(tipo_raw).strip() == ""
    )
    tipo = "" if tipo_vazio else _norm_text(str(tipo_raw))

    cobr_raw = row.get("quantidade_de_cobrancas")
    tem_cobrancas = not (
        cobr_raw is None
        or (isinstance(cobr_raw, float) and math.isnan(cobr_raw))
        or str(cobr_raw).strip() == ""
    )
    try:
        cobrancas = int(float(cobr_raw)) if tem_cobrancas else 1
    except (ValueError, TypeError):
        cobrancas, tem_cobrancas = 1, False

    parc_raw = row.get("quantidade_total_de_parcelas")
    try:
        parcelas = 1 if (
            parc_raw is None
            or (isinstance(parc_raw, float) and math.isnan(parc_raw))
            or str(parc_raw).strip() == ""
        ) else int(float(parc_raw))
    except (ValueError, TypeError):
        parcelas = 1

    eh_por_parcela = tipo == "recuperador inteligente" or (tipo_vazio and tem_cobrancas)
    eh_repeticao = tem_cobrancas and cobrancas != 1
    return eh_por_parcela, eh_repeticao, cobrancas, parcelas


_UF_POR_NOME = {
    "acre": "AC", "alagoas": "AL", "amapa": "AP", "amazonas": "AM", "bahia": "BA",
    "ceara": "CE", "distrito federal": "DF", "espirito santo": "ES", "goias": "GO",
    "maranhao": "MA", "mato grosso": "MT", "mato grosso do sul": "MS", "minas gerais": "MG",
    "para": "PA", "paraiba": "PB", "parana": "PR", "pernambuco": "PE", "piaui": "PI",
    "rio de janeiro": "RJ", "rio grande do norte": "RN", "rio grande do sul": "RS",
    "rondonia": "RO", "roraima": "RR", "santa catarina": "SC", "sao paulo": "SP",
    "sergipe": "SE", "tocantins": "TO",
}
_UFS_VALIDAS = set(_UF_POR_NOME.values())


def _norm_uf(value: Any) -> str | None:
    """Normaliza estado pra sigla (UF), aceitando sigla, nome completo (com/sem
    acento) ou o formato do Meta Ads ("Acre (state)"). None se não reconhecer
    (ex: "Florida" — comprador fora do Brasil)."""
    import unicodedata
    s = str(value or "").strip()
    if not s:
        return None
    s = re.sub(r"\s*\(state\)\s*$", "", s, flags=re.IGNORECASE).strip()
    if len(s) == 2 and s.upper() in _UFS_VALIDAS:
        return s.upper()
    s_norm = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower().strip()
    return _UF_POR_NOME.get(s_norm)


def _canal_venda(sck: Any, utm_source: Any) -> str:
    """Comercial × IA × Orgânico. Hotmart marca o comercial no codigo_sck
    (ana, HOTMART_SALES_AGENT, agente_ia); TMB no utm_source (COMERCIAL, IA).
    Sem marcação conta como Orgânico."""
    s = str(sck or "").strip().lower()
    u = str(utm_source or "").strip().lower()
    if "comercial" in u or "comercial" in s or s in ("ana", "hotmart_sales_agent"):
        return "Comercial"
    if s == "agente_ia" or u in ("ia", "agente_ia") or u.startswith("ia"):
        return "IA"
    return "Orgânico"


def _hm_parse_date(v: Any):
    s = str(v or "").strip()
    try:
        if re.match(r"^\d{2}/\d{2}/\d{4}", s):
            return pd.to_datetime(s[:10], format="%d/%m/%Y")
        if re.match(r"^\d{10,13}$", s):
            return pd.Timestamp(int(s) / 1000 if len(s) == 13 else int(s), unit="s")
        x = pd.to_datetime(s, errors="coerce", utc=True)
        return x.tz_convert(None) if pd.notna(x) else pd.NaT
    except Exception:
        return pd.NaT


def _hm_metodo_label(metodo: Any, tipo_cobranca: Any = None) -> str:
    m = _norm_text(str(metodo or ""))
    t = _norm_text(str(tipo_cobranca or ""))
    recorrente = "recurr" in t or "subscri" in t or "recorr" in t
    if "boleto" in m or "billet" in m:
        return "Boleto"
    if "pix" in m:
        return "Pix"
    if "installment" in m or "parcel" in m:
        return "Recorrência"
    if "cart" in m or "credit" in m or "card" in m:
        return "Cartão Recorrente" if recorrente else "Cartão de Crédito"
    return str(metodo or "Outro").strip() or "Outro"


def _bucket_metodo_pagamento(metodo: Any) -> str:
    s = str(metodo or "").strip().lower()
    if not s:
        return "Outro"
    if "boleto" in s or s == "billet":
        return "Boleto"
    if "pix" in s:
        return "Pix"
    if "cart" in s or "credit" in s or "nupay" in s:
        return "Cartão de Crédito"
    return "Outro"



_DIA1_CHECKPOINTS = [
    ("8h30", 8 * 60 + 30), ("9h", 9 * 60), ("10h", 10 * 60), ("11h", 11 * 60),
    ("12h", 12 * 60), ("13h", 13 * 60), ("15h", 15 * 60), ("16h", 16 * 60),
    ("17h", 17 * 60), ("18h", 18 * 60), ("19h", 19 * 60), ("20h", 20 * 60),
    ("21h", 21 * 60), ("22h", 22 * 60),
]

_HOTMART_STATUS_APROVADO = (
    "Completa", "Aprovada", "Paga", "Completo", "Aprovado", "Pago",
    "approved", "complete", "APPROVED", "COMPLETED",
)
