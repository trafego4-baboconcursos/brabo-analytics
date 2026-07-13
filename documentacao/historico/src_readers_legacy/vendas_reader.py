"""
src/readers/vendas_reader.py
Lê os CSVs de Hotmart e TMB da pasta Vendas/ do lançamento.
Cruza com Active Campaign para calcular atribuição por UTM.
"""
from __future__ import annotations
import csv
import re
import unicodedata
from pathlib import Path
from dataclasses import dataclass, field
from typing import Any
import pandas as pd


def _detect_encoding(path: Path) -> str:
    for enc in ["utf-8-sig", "utf-8", "latin-1", "cp1252"]:
        try:
            with path.open(encoding=enc) as f:
                f.read(1024)
            return enc
        except (UnicodeDecodeError, LookupError):
            continue
    return "latin-1"


def _to_float(val: Any) -> float:
    if val is None:
        return 0.0
    if isinstance(val, (int, float)):
        import math
        if math.isnan(val):
            return 0.0
        return float(val)
    val_str = str(val).strip()
    if not val_str or val_str in ("", "--", "-", "N/D", "N/A"):
        return 0.0
    cleaned = re.sub(r"[^\d,.-]", "", val_str).strip()
    if "," in cleaned and "." in cleaned:
        if cleaned.rfind(",") > cleaned.rfind("."):
            cleaned = cleaned.replace(".", "").replace(",", ".")
        else:
            cleaned = cleaned.replace(",", "")
    elif "," in cleaned:
        cleaned = cleaned.replace(".", "").replace(",", ".")
    elif "." in cleaned:
        parts = cleaned.split(".")
        if len(parts) > 1 and all(len(part) == 3 for part in parts[1:]):
            cleaned = cleaned.replace(".", "")
    try:
        return float(cleaned)
    except ValueError:
        return 0.0


def _to_int(val: str) -> int:
    return int(_to_float(val))


def _norm_text(value: str) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    return text.encode("ascii", "ignore").decode("ascii").strip().lower()


def _find_col(header: list[str], *candidates: str) -> int | None:
    normalized_header = [_norm_text(col) for col in header]
    for cand in candidates:
        cand_norm = _norm_text(cand)
        for i, col in enumerate(normalized_header):
            if cand_norm in col:
                return i
    return None


def _detect_separator(path: Path, enc: str) -> str:
    with path.open(encoding=enc, errors="replace") as f:
        first_line = f.readline()
    if first_line.count(";") > first_line.count(","):
        return ";"
    return ","


def _load_csv(path: Path) -> tuple[list[str], list[list[str]]]:
    enc = _detect_encoding(path)
    sep = _detect_separator(path, enc)
    rows = []
    with path.open(encoding=enc, errors="replace") as f:
        reader = csv.reader(f, delimiter=sep)
        header = next(reader, [])
        for row in reader:
            if row and any(c.strip() for c in row):
                rows.append(row)
    return header, rows


# ──────────────────────────────────────────────────────────────────────────────
@dataclass
class VendasSummary:
    # Hotmart
    hotmart_vendas: int = 0
    hotmart_receita: float = 0.0
    hotmart_ticket_medio: float = 0.0
    # TMB
    tmb_vendas: int = 0
    tmb_receita: float = 0.0
    tmb_ticket_medio: float = 0.0
    # Total
    total_vendas: int = 0
    total_receita: float = 0.0
    total_ticket_medio: float = 0.0
    # Métodos de pagamento (Hotmart)
    pagamento_cartao: int = 0
    pagamento_boleto: int = 0
    pagamento_pix: int = 0
    pagamento_outros: int = 0
    # Status breakdown
    por_status: dict = field(default_factory=dict)
    # Emails dos compradores (para cruzamento AC)
    emails_hotmart: set = field(default_factory=set)
    emails_tmb: set = field(default_factory=set)
    receita_por_email: dict = field(default_factory=dict)
    vendas_por_email: dict = field(default_factory=dict)


def _find_csv_by_keyword(folder: Path, *keywords: str) -> Path | None:
    for kw in keywords:
        for csv_path in sorted(folder.glob("*.csv")):
            if kw.lower() in csv_path.name.lower():
                return csv_path
    return None


from .path_helper import find_subfolder

def read_vendas(launch_folder: Path) -> VendasSummary | None:
    folder = find_subfolder(launch_folder, "vendas")
    if not folder or not folder.exists():
        return None

    summary = VendasSummary()

    # ── Hotmart ──────────────────────────────────────────────────────────────
    hotmart_csv = _find_csv_by_keyword(folder, "hotmart")
    if hotmart_csv:
        header, rows = _load_csv(hotmart_csv)

        col_status   = _find_col(header, "status da transacao", "status")
        col_email    = _find_col(header, "email do(a) comprador", "e-mail do(a) comprador", "email")
        col_valor    = _find_col(header, "faturamento liquido do(a) produtor", "faturamento liquido", "faturamento bruto", "valor de compra")
        col_pagto    = _find_col(header, "metodo de pagamento", "pagamento")
        col_tipo     = _find_col(header, "tipo de cobranca")
        col_parcelas = _find_col(header, "quantidade total de parcelas")
        col_cobrancas = _find_col(header, "quantidade de cobrancas")

        def g(row, col, default=""):
            return row[col].strip() if col is not None and col < len(row) else default

        for row in rows:
            status = _norm_text(g(row, col_status))
            if status not in ("completo", "complete", "aprovado", "approved", "pago"):
                continue
            valor = _to_float(g(row, col_valor))
            tipo_cobranca = _norm_text(g(row, col_tipo))
            cobrancas = _to_int(g(row, col_cobrancas))
            if tipo_cobranca == "recuperador inteligente":
                if cobrancas != 1:
                    continue
                valor *= max(1, _to_int(g(row, col_parcelas)))
            email = g(row, col_email).lower()
            pagto = _norm_text(g(row, col_pagto))

            summary.hotmart_vendas += 1
            summary.hotmart_receita += valor
            if email:
                summary.emails_hotmart.add(email)
                summary.receita_por_email[email] = summary.receita_por_email.get(email, 0.0) + valor
                summary.vendas_por_email[email] = summary.vendas_por_email.get(email, 0) + 1

            # Método de pagamento
            if "cartao" in pagto or "card" in pagto or "credit" in pagto:
                summary.pagamento_cartao += 1
            elif "boleto" in pagto:
                summary.pagamento_boleto += 1
            elif "pix" in pagto:
                summary.pagamento_pix += 1
            else:
                summary.pagamento_outros += 1

    # ── TMB ──────────────────────────────────────────────────────────────────
    tmb_csv = _find_csv_by_keyword(folder, "tmb")
    if tmb_csv:
        header, rows = _load_csv(tmb_csv)

        col_status = _find_col(header, "situacao", "status")
        col_email  = _find_col(header, "e-mail", "email", "e_mail")
        col_valor  = _find_col(header, "ticket do pedido", "valor", "receita", "faturamento", "preco")

        def g(row, col, default=""):
            return row[col].strip() if col is not None and col < len(row) else default

        for row in rows:
            valor = _to_float(g(row, col_valor))
            if valor <= 0:
                continue
            email = g(row, col_email).lower()

            summary.tmb_vendas += 1
            summary.tmb_receita += valor
            if email:
                summary.emails_tmb.add(email)
                summary.receita_por_email[email] = summary.receita_por_email.get(email, 0.0) + valor
                summary.vendas_por_email[email] = summary.vendas_por_email.get(email, 0) + 1

    # Totais
    summary.total_vendas = summary.hotmart_vendas + summary.tmb_vendas
    summary.total_receita = summary.hotmart_receita + summary.tmb_receita
    summary.hotmart_ticket_medio = (
        summary.hotmart_receita / summary.hotmart_vendas if summary.hotmart_vendas > 0 else 0.0
    )
    summary.tmb_ticket_medio = (
        summary.tmb_receita / summary.tmb_vendas if summary.tmb_vendas > 0 else 0.0
    )
    summary.total_ticket_medio = (
        summary.total_receita / summary.total_vendas if summary.total_vendas > 0 else 0.0
    )

    if summary.total_vendas == 0:
        return None

    return summary


# ──────────────────────────────────────────────────────────────────────────────
# Cruzamento com Active Campaign
# ──────────────────────────────────────────────────────────────────────────────
@dataclass
class LeadsSummary:
    total_leads: int = 0
    compradores_rastreados: int = 0
    compradores_sem_utm: int = 0
    total_compradores: int = 0
    cpl: float = 0.0
    # Distribuição por fonte UTM
    por_utm_source: dict = field(default_factory=dict)
    por_utm_medium: dict = field(default_factory=dict)
    # Emails cruzados
    emails_rastreados: set = field(default_factory=set)


def read_leads(launch_folder: Path, vendas: VendasSummary | None = None) -> LeadsSummary | None:
    folder = find_subfolder(launch_folder, "ac")
    if not folder or not folder.exists():
        return None

    csvs = sorted(folder.glob("*.csv"))
    if not csvs:
        return None

    summary = LeadsSummary()
    emails_com_utm: set[str] = set()
    por_source: dict[str, int] = {}
    por_medium: dict[str, int] = {}

    for csv_path in csvs:
        enc = _detect_encoding(csv_path)
        try:
            with csv_path.open(encoding=enc, errors="replace") as f:
                first = f.readline()
                sep = ";" if first.count(";") > first.count(",") else ","
        except Exception:
            sep = ";"

        try:
            with csv_path.open(encoding=enc, errors="replace") as f:
                reader = csv.reader(f, delimiter=sep)
                header = next(reader, [])

                col_email  = _find_col(header, "email", "e-mail", "e_mail")
                col_source = _find_col(header, "utm_source", "utm source", "source")
                col_medium = _find_col(header, "utm_medium", "utm medium", "medium")

                if col_email is None:
                    continue

                def g(row, col, default=""):
                    return row[col].strip() if col is not None and col < len(row) else default

                for row in reader:
                    if len(row) <= col_email:
                        continue
                    email = g(row, col_email).lower()
                    if not email:
                        continue
                    source = g(row, col_source)
                    medium = g(row, col_medium)

                    summary.total_leads += 1

                    if source or medium:
                        emails_com_utm.add(email)
                        if source:
                            por_source[source] = por_source.get(source, 0) + 1
                        if medium:
                            por_medium[medium] = por_medium.get(medium, 0) + 1
        except Exception:
            pass

    # Cruzamento
    if vendas:
        all_buyers = vendas.emails_hotmart | vendas.emails_tmb
        summary.total_compradores = vendas.total_vendas
        rastreados = all_buyers & emails_com_utm
        summary.compradores_rastreados = len(rastreados)
        summary.emails_rastreados = rastreados
        summary.compradores_sem_utm = max(0, summary.total_compradores - summary.compradores_rastreados)
    else:
        summary.total_compradores = 0

    summary.por_utm_source = dict(sorted(por_source.items(), key=lambda x: x[1], reverse=True)[:10])
    summary.por_utm_medium = dict(sorted(por_medium.items(), key=lambda x: x[1], reverse=True)[:10])

    return summary


# ──────────────────────────────────────────────────────────────────────────────
# DETALHES DE HOTMART E TMB PARA AS PÁGINAS DO V2
# ──────────────────────────────────────────────────────────────────────────────

@dataclass
class HotmartDetails:
    has_data: bool = False
    total_vendas: int = 0
    receita_bruta: float = 0.0
    receita_liquida: float = 0.0
    taxas: float = 0.0
    taxas_pct: float = 0.0
    ticket_medio: float = 0.0
    pix_ticket: float = 0.0
    card_ticket: float = 0.0
    pix_premium: float = 0.0
    vendas_12x_pct: float = 0.0
    timeline: list[dict[str, Any]] = field(default_factory=list)
    pagamentos: list[dict[str, Any]] = field(default_factory=list)
    parcelas: list[dict[str, Any]] = field(default_factory=list)
    fluxo_caixa: dict[str, float] = field(default_factory=dict)
    ofertas: list[dict[str, Any]] = field(default_factory=list)
    estados: list[dict[str, Any]] = field(default_factory=list)
    cidades: list[dict[str, Any]] = field(default_factory=list)
    file_name: str = ""

@dataclass
class TmbDetails:
    has_data: bool = False
    total_vendas: int = 0
    faturamento: float = 0.0
    ticket_medio: float = 0.0
    total_emitidos: int = 0
    total_cancelados: int = 0
    taxa_cancelamento: float = 0.0
    vendas_d1: int = 0
    vendas_d1_pct: float = 0.0
    com_utm_qtd: int = 0
    com_utm_pct: float = 0.0
    timeline: list[dict[str, Any]] = field(default_factory=list)
    status_emitidos: list[dict[str, Any]] = field(default_factory=list)
    ofertas: list[dict[str, Any]] = field(default_factory=list)
    utm_sources: list[dict[str, Any]] = field(default_factory=list)
    estados: list[dict[str, Any]] = field(default_factory=list)
    cidades: list[dict[str, Any]] = field(default_factory=list)
    file_name: str = ""

@dataclass
class ConsolidadoVendasSummary:
    has_data: bool = False
    total_receita: float = 0.0
    total_transacoes: int = 0
    compradores_unicos: int = 0
    ticket_medio: float = 0.0
    leads_crm: int = 0
    conversao_lead_venda: float = 0.0
    compradores_crm: int = 0
    compradores_typeform: int = 0
    
    # Tabelas
    fechamento: list[dict[str, Any]] = field(default_factory=list)
    top_canais: list[dict[str, Any]] = field(default_factory=list)
    top_campanhas: list[dict[str, Any]] = field(default_factory=list)
    top_estados: list[dict[str, Any]] = field(default_factory=list)
    top_cidades: list[dict[str, Any]] = field(default_factory=list)
    propensao: list[dict[str, Any]] = field(default_factory=list)
    
    # Demografia
    genero: list[dict[str, Any]] = field(default_factory=list)
    idade: list[dict[str, Any]] = field(default_factory=list)
    situacao_prof: list[dict[str, Any]] = field(default_factory=list)
    escolaridade: list[dict[str, Any]] = field(default_factory=list)
    
    # Insights
    top_origem_nome: str = ""
    top_origem_faturamento: float = 0.0
    top_origem_compradores: int = 0
    top_origem_ticket: float = 0.0
    
    top_estado_nome: str = ""
    top_estado_faturamento: float = 0.0
    top_estado_compradores: int = 0
    
    volume_insight: dict[str, Any] = field(default_factory=dict)
    conv_insight: dict[str, Any] = field(default_factory=dict)
    ticket_insight: dict[str, Any] = field(default_factory=dict)


def read_hotmart_details(launch_folder: Path) -> HotmartDetails:
    details = HotmartDetails()
    folder = find_subfolder(launch_folder, "vendas")
    if not folder or not folder.exists():
        return details
        
    hotmart_csv = _find_csv_by_keyword(folder, "hotmart")
    if not hotmart_csv:
        return details
        
    details.file_name = hotmart_csv.name
    details.has_data = True
    
    try:
        enc = _detect_encoding(hotmart_csv)
        sep = _detect_separator(hotmart_csv, enc)
        df = pd.read_csv(hotmart_csv, sep=sep, encoding=enc, low_memory=False)
        
        # Mapeamento de colunas
        tipo_col = next((c for c in df.columns if "tipo" in _norm_text(c) and "cobran" in _norm_text(c)), None)
        cob_col  = next((c for c in df.columns if "quantidade de cobranca" in _norm_text(c)), "Quantidade de cobranças")
        par_col  = next((c for c in df.columns if "total de parcela" in _norm_text(c) or "total parcelas" in _norm_text(c)), "Quantidade total de parcelas")
        val_col  = next((c for c in df.columns if "faturamento liquido" in _norm_text(c) or "valor liquido" in _norm_text(c)), "Faturamento líquido do(a) Produtor(a)")
        val_bruto_col = next((c for c in df.columns if "faturamento bruto" in _norm_text(c) or "valor bruto" in _norm_text(c)), "Faturamento bruto (sem impostos)")
        status_col = next((c for c in df.columns if "status da transacao" in _norm_text(c) or "status" in _norm_text(c)), "Status da transação")
        email_col = next((c for c in df.columns if "email do(a) comprador" in _norm_text(c) or "email" in _norm_text(c)), "Email do(a) Comprador(a)")
        pagto_col = next((c for c in df.columns if "metodo de pagamento" in _norm_text(c) or "forma de pagamento" in _norm_text(c)), "Método de pagamento")
        data_col = next((c for c in df.columns if "data da transacao" in _norm_text(c) or "data" in _norm_text(c)), "Data da transação")
        estado_col = next((c for c in df.columns if "estado" in _norm_text(c) or "provincia" in _norm_text(c)), "Estado / Província")
        cidade_col = next((c for c in df.columns if "cidade" in _norm_text(c)), "Cidade")
        preco_col = next((c for c in df.columns if "nome deste preco" in _norm_text(c) or "nome do preco" in _norm_text(c)), "Nome deste preço")
        
        # Filtra vendas válidas
        df["status_norm"] = df[status_col].astype(str).apply(_norm_text)
        df_paid = df[df["status_norm"].isin({"completo", "complete", "aprovado", "approved", "pago"})].copy()
        
        if df_paid.empty:
            return details
            
        # Processa valores normais e Recuperador Inteligente
        if tipo_col and cob_col in df_paid.columns and par_col in df_paid.columns:
            hm_normal = df_paid[df_paid[tipo_col].astype(str).str.strip() != "Recuperador Inteligente"].copy()
            hm_normal["valor_liq"] = hm_normal[val_col].apply(_to_float)
            hm_normal["valor_bruto"] = hm_normal[val_bruto_col].apply(_to_float)
            
            hm_ri = df_paid[
                (df_paid[tipo_col].astype(str).str.strip() == "Recuperador Inteligente") &
                (pd.to_numeric(df_paid[cob_col], errors="coerce").fillna(0) == 1)
            ].copy()
            hm_ri[par_col] = pd.to_numeric(hm_ri[par_col], errors="coerce").fillna(1)
            hm_ri["valor_liq"] = hm_ri[val_col].apply(_to_float) * hm_ri[par_col]
            hm_ri["valor_bruto"] = hm_ri[val_bruto_col].apply(_to_float) * hm_ri[par_col]
            
            hm_df = pd.concat([hm_normal, hm_ri], ignore_index=True)
        else:
            df_paid["valor_liq"] = df_paid[val_col].apply(_to_float)
            df_paid["valor_bruto"] = df_paid[val_bruto_col].apply(_to_float)
            hm_df = df_paid
            
        hm_df["parcelas_int"] = pd.to_numeric(hm_df[par_col], errors="coerce").fillna(1).astype(int)
        
        # KPIs básicos
        details.total_vendas = len(hm_df)
        details.receita_bruta = float(hm_df["valor_bruto"].sum())
        details.receita_liquida = float(hm_df["valor_liq"].sum())
        details.taxas = details.receita_bruta - details.receita_liquida
        details.taxas_pct = (details.taxas / details.receita_bruta * 100) if details.receita_bruta > 0 else 0.0
        details.ticket_medio = (details.receita_liquida / details.total_vendas) if details.total_vendas > 0 else 0.0
        
        # Métodos de pagamento
        mp_groups = hm_df.groupby(pagto_col)
        for name, group in mp_groups:
            qtd = len(group)
            faturamento = float(group["valor_liq"].sum())
            details.pagamentos.append({
                "metodo": str(name),
                "qtd": qtd,
                "pct_vendas": (qtd / details.total_vendas * 100),
                "faturamento": faturamento,
                "pct_faturamento": (faturamento / details.receita_liquida * 100) if details.receita_liquida > 0 else 0.0,
                "ticket_medio": (faturamento / qtd) if qtd > 0 else 0.0
            })
        details.pagamentos = sorted(details.pagamentos, key=lambda x: x["faturamento"], reverse=True)
        
        # Pix vs Cartão
        pix_group = hm_df[hm_df[pagto_col].astype(str).str.lower().str.contains("pix", na=False)]
        card_group = hm_df[hm_df[pagto_col].astype(str).str.lower().str.contains("cart", na=False)]
        
        details.pix_ticket = float(pix_group["valor_liq"].mean()) if not pix_group.empty else 0.0
        details.card_ticket = float(card_group["valor_liq"].mean()) if not card_group.empty else 0.0
        
        if details.card_ticket > 0:
            details.pix_premium = (details.pix_ticket - details.card_ticket) / details.card_ticket * 100
            
        # Parcelamento
        if not card_group.empty:
            details.vendas_12x_pct = (len(card_group[card_group["parcelas_int"] == 12]) / len(card_group) * 100)
            
            p_dist = card_group["parcelas_int"].value_counts().sort_index()
            for p_val, cnt in p_dist.items():
                details.parcelas.append({
                    "label": "À vista" if p_val == 1 else f"{p_val}x",
                    "qtd": int(cnt),
                    "pct_vendas": float(cnt / len(card_group) * 100)
                })
                
        # Fluxo de caixa
        av_df = hm_df[hm_df[pagto_col].astype(str).str.lower().str.contains("pix|boleto", na=False) | (hm_df["parcelas_int"] == 1)]
        parc_df = hm_df[(hm_df["parcelas_int"] > 1) & hm_df[pagto_col].astype(str).str.lower().str.contains("cart", na=False)]
        
        details.fluxo_caixa = {
            "a_vista": float(av_df["valor_liq"].sum()),
            "parcelado": float(parc_df["valor_liq"].sum())
        }
        
        # Timeline diária
        hm_df["data_parsed"] = pd.to_datetime(hm_df[data_col], dayfirst=True, errors="coerce")
        # Encontra o D1 dinamicamente
        d1_date = hm_df["data_parsed"].min()
        timeline_grouped = hm_df.groupby(hm_df["data_parsed"].dt.date).agg(
            vendas=("valor_liq", "count"),
            faturamento=("valor_liq", "sum")
        ).reset_index()
        timeline_grouped = timeline_grouped.sort_values("data_parsed")
        
        for _, row in timeline_grouped.iterrows():
            dt = row["data_parsed"]
            details.timeline.append({
                "data": dt.strftime("%Y-%m-%d"),
                "data_str": dt.strftime("%d/%b"),
                "vendas": int(row["vendas"]),
                "faturamento": float(row["faturamento"]),
                "is_d1": dt == d1_date.date()
            })
            
        # Estrutura de ofertas
        preco_col_val = preco_col if preco_col in hm_df.columns else None
        if preco_col_val:
            ofertas_grouped = hm_df.groupby(preco_col_val)
            for name, group in ofertas_grouped:
                name_str = str(name).strip()
                tipo = "Base" if name_str == "(none)" or name_str.lower() == "none" else ("Cross" if "cross" in name_str.lower() else ("Upsell" if "upsell" in name_str.lower() else "Lead"))
                details.ofertas.append({
                    "nome": name_str,
                    "tipo": tipo,
                    "qtd": len(group),
                    "faturamento": float(group["valor_liq"].sum()),
                    "ticket_medio": float(group["valor_liq"].mean())
                })
            details.ofertas = sorted(details.ofertas, key=lambda x: x["qtd"], reverse=True)
            
        # Estados
        if estado_col in hm_df.columns:
            est_grouped = hm_df.groupby(estado_col).agg(qtd=("valor_liq", "count"), fat=("valor_liq", "sum")).sort_values("qtd", ascending=False).head(10)
            for est, r in est_grouped.iterrows():
                details.estados.append({
                    "estado": str(est),
                    "qtd": int(r["qtd"]),
                    "faturamento": float(r["fat"])
                })
                
        # Cidades
        if cidade_col in hm_df.columns:
            cid_grouped = hm_df.groupby(cidade_col).agg(qtd=("valor_liq", "count"), fat=("valor_liq", "sum")).sort_values("qtd", ascending=False).head(10)
            for cid, r in cid_grouped.iterrows():
                details.cidades.append({
                    "cidade": str(cid),
                    "qtd": int(r["qtd"]),
                    "faturamento": float(r["fat"])
                })
    except Exception:
        details.has_data = False
        
    return details


def read_tmb_details(launch_folder: Path) -> TmbDetails:
    details = TmbDetails()
    folder = find_subfolder(launch_folder, "vendas")
    if not folder or not folder.exists():
        return details
        
    tmb_csv = _find_csv_by_keyword(folder, "tmb")
    if not tmb_csv:
        return details
        
    details.file_name = tmb_csv.name
    details.has_data = True
    
    try:
        enc = _detect_encoding(tmb_csv)
        sep = _detect_separator(tmb_csv, enc)
        df_all = pd.read_csv(tmb_csv, sep=sep, encoding=enc, low_memory=False)
        
        status_col = next((c for c in df_all.columns if "situacao" in _norm_text(c) or "status" in _norm_text(c)), None)
        email_col = next((c for c in df_all.columns if "email" in _norm_text(c) or "e-mail" in _norm_text(c)), None)
        val_col = next((c for c in df_all.columns if "ticket do pedido" in _norm_text(c) or "valor" in _norm_text(c)), None)
        data_col = next((c for c in df_all.columns if "criado em" in _norm_text(c) or "data" in _norm_text(c)), None)
        oferta_col = next((c for c in df_all.columns if "oferta" in _norm_text(c) or "produto" in _norm_text(c)), None)
        utm_col = next((c for c in df_all.columns if "utm_source" in _norm_text(c)), None)
        estado_col = next((c for c in df_all.columns if "estado" in _norm_text(c) or "uf" in _norm_text(c)), None)
        cidade_col = next((c for c in df_all.columns if "cidade" in _norm_text(c)), None)
        
        # Total emitidos
        details.total_emitidos = len(df_all)
        
        # Filtra cancelados
        if status_col:
            df_all["status_norm"] = df_all[status_col].astype(str).apply(_norm_text)
            details.total_cancelados = int(df_all["status_norm"].isin({"cancelado", "cancelled"}).sum())
            df_paid = df_all[df_all["status_norm"].isin({"vigente", "efetivado", "pago", "em dia", "integralizado", "aprovado", "concluido", "active"})].copy()
            
            # Status distribuição
            status_vc = df_all["status_norm"].value_counts()
            for stat, cnt in status_vc.items():
                details.status_emitidos.append({
                    "status": str(stat).capitalize(),
                    "qtd": int(cnt),
                    "pct": float(cnt / details.total_emitidos * 100)
                })
        else:
            df_paid = df_all.copy()
            details.total_cancelados = 0
            
        details.taxa_cancelamento = (details.total_cancelados / details.total_emitidos * 100) if details.total_emitidos > 0 else 0.0
        
        if val_col:
            df_paid["valor_liq"] = df_paid[val_col].apply(_to_float)
        else:
            df_paid["valor_liq"] = 0.0
            
        details.total_vendas = len(df_paid)
        details.faturamento = float(df_paid["valor_liq"].sum())
        details.ticket_medio = (details.faturamento / details.total_vendas) if details.total_vendas > 0 else 0.0
        
        # Timeline diária
        if data_col:
            df_paid["data_parsed"] = pd.to_datetime(df_paid[data_col], dayfirst=True, errors="coerce")
            d1_date = df_paid["data_parsed"].min()
            
            timeline_grouped = df_paid.groupby(df_paid["data_parsed"].dt.date).agg(
                vendas=("valor_liq", "count"),
                faturamento=("valor_liq", "sum")
            ).reset_index()
            timeline_grouped = timeline_grouped.sort_values("data_parsed")
            
            for _, row in timeline_grouped.iterrows():
                dt = row["data_parsed"]
                is_d1 = dt == d1_date.date() if pd.notna(d1_date) else False
                details.timeline.append({
                    "data": dt.strftime("%Y-%m-%d") if pd.notna(dt) else "Sem data",
                    "data_str": dt.strftime("%d/%b") if pd.notna(dt) else "Sem data",
                    "vendas": int(row["vendas"]),
                    "faturamento": float(row["faturamento"]),
                    "is_d1": is_d1
                })
                
                if is_d1:
                    details.vendas_d1 = int(row["vendas"])
                    details.vendas_d1_pct = (details.vendas_d1 / details.total_vendas * 100) if details.total_vendas > 0 else 0.0
                    
        # Estrutura de ofertas
        if oferta_col and oferta_col in df_paid.columns:
            oferta_grouped = df_paid.groupby(oferta_col)
            for name, group in oferta_grouped:
                name_str = str(name).strip()
                tipo = "Lead" if "lead" in name_str.lower() else ("Upsell" if "upsell" in name_str.lower() else "Crossell")
                details.ofertas.append({
                    "nome": name_str,
                    "tipo": tipo,
                    "qtd": len(group),
                    "faturamento": float(group["valor_liq"].sum()),
                    "ticket_medio": float(group["valor_liq"].mean())
                })
            details.ofertas = sorted(details.ofertas, key=lambda x: x["qtd"], reverse=True)
            
        # UTM Sources
        if utm_col and utm_col in df_paid.columns:
            df_paid["utm_norm"] = df_paid[utm_col].fillna("").astype(str).str.strip()
            details.com_utm_qtd = int((df_paid["utm_norm"] != "").sum())
            details.com_utm_pct = (details.com_utm_qtd / details.total_vendas * 100) if details.total_vendas > 0 else 0.0
            
            utm_vc = df_paid["utm_norm"].value_counts()
            for src, cnt in utm_vc.items():
                src_str = str(src)
                if not src_str:
                    src_str = "Sem rastreio"
                details.utm_sources.append({
                    "source": src_str,
                    "qtd": int(cnt),
                    "pct": float(cnt / details.total_vendas * 100)
                })
                
        # Estados
        if estado_col and estado_col in df_paid.columns:
            est_grouped = df_paid.groupby(estado_col).agg(qtd=("valor_liq", "count"), fat=("valor_liq", "sum")).sort_values("qtd", ascending=False).head(10)
            for est, r in est_grouped.iterrows():
                details.estados.append({
                    "estado": str(est),
                    "qtd": int(r["qtd"]),
                    "faturamento": float(r["fat"])
                })
                
        # Cidades
        if cidade_col and cidade_col in df_paid.columns:
            cid_grouped = df_paid.groupby(cidade_col).agg(qtd=("valor_liq", "count"), fat=("valor_liq", "sum")).sort_values("qtd", ascending=False).head(10)
            for cid, r in cid_grouped.iterrows():
                details.cidades.append({
                    "cidade": str(cid),
                    "qtd": int(r["qtd"]),
                    "faturamento": float(r["fat"])
                })
    except Exception:
        details.has_data = False
        
    return details


def read_vendas_consolidado(launch_folder: Path) -> ConsolidadoVendasSummary:
    summary = ConsolidadoVendasSummary()
    
    # ── 1. Carrega Leitores Individuais de Vendas ──
    v_sum = read_vendas(launch_folder)
    if not v_sum:
        return summary
        
    summary.has_data = True
    summary.total_receita = v_sum.total_receita
    summary.total_transacoes = v_sum.total_vendas
    summary.compradores_unicos = v_sum.total_vendas  # aproximação de compradores únicos
    summary.ticket_medio = v_sum.total_ticket_medio
    
    # ── 2. Fechamento Comercial ──
    if v_sum.hotmart_vendas > 0:
        summary.fechamento.append({
            "plataforma": "Hotmart",
            "compradores": v_sum.hotmart_vendas,
            "transacoes": v_sum.hotmart_vendas,
            "faturamento": v_sum.hotmart_receita,
            "ticket": v_sum.hotmart_ticket_medio
        })
    if v_sum.tmb_vendas > 0:
        summary.fechamento.append({
            "plataforma": "TMB",
            "compradores": v_sum.tmb_vendas,
            "transacoes": v_sum.tmb_vendas,
            "faturamento": v_sum.tmb_receita,
            "ticket": v_sum.tmb_ticket_medio
        })
        
    # ── 3. Cruzamento completo com CRM e Typeform ──
    # Para obter origens, demografia e propensão, vamos carregar os CSVs
    ac_folder = find_subfolder(launch_folder, "ac")
    tf_folder = find_subfolder(launch_folder, "typeform")
    vendas_folder = find_subfolder(launch_folder, "vendas")
    
    # Carregar CRM
    crm_df = pd.DataFrame()
    if ac_folder and ac_folder.exists():
        ac_csvs = sorted(ac_folder.glob("*.csv"))
        if ac_csvs:
            crm_file = max(ac_csvs, key=lambda f: f.stat().st_size)
            try:
                crm_enc = _detect_encoding(crm_file)
                crm_sep = _detect_separator(crm_file, crm_enc)
                crm_df = pd.read_csv(crm_file, sep=crm_sep, encoding=crm_enc, low_memory=False)
                crm_email_col = next((c for c in crm_df.columns if "email" in _norm_text(c) or "e-mail" in _norm_text(c)), None)
                if crm_email_col:
                    crm_df["email_norm"] = crm_df[crm_email_col].astype(str).str.strip().str.lower()
                    crm_df = crm_df[crm_df["email_norm"].str.contains("@", na=False)].copy()
                    crm_df = crm_df.drop_duplicates("email_norm", keep="first")
                    summary.leads_crm = len(crm_df)
            except Exception:
                crm_df = pd.DataFrame()
                
    # Carregar Typeform
    tf_df = pd.DataFrame()
    if tf_folder and tf_folder.exists():
        tf_csvs = sorted(tf_folder.glob("*.csv"))
        if tf_csvs:
            tf_file = next((f for f in tf_csvs if "pesquisa" in f.name.lower()), tf_csvs[0])
            try:
                tf_enc = _detect_encoding(tf_file)
                tf_sep = _detect_separator(tf_file, tf_enc)
                tf_df = pd.read_csv(tf_file, sep=tf_sep, encoding=tf_enc, low_memory=False)
                tf_email_col = next((c for c in tf_df.columns if "digite seu e-mail" in _norm_text(c) or "e-mail" in _norm_text(c) or "email" in _norm_text(c)), None)
                if tf_email_col:
                    tf_df["email_norm"] = tf_df[tf_email_col].astype(str).str.strip().str.lower()
                    tf_df = tf_df[tf_df["email_norm"].str.contains("@", na=False)].copy()
                    tf_df = tf_df.drop_duplicates("email_norm", keep="last")
            except Exception:
                tf_df = pd.DataFrame()
                
    # Carrega Vendas detalhadas em Dataframes para cruzamento
    sales_df = pd.DataFrame()
    if vendas_folder and vendas_folder.exists():
        hm_csvs = [f for f in vendas_folder.glob("*.csv") if "hotmart" in f.name.lower()]
        tmb_csvs = [f for f in vendas_folder.glob("*.csv") if "tmb" in f.name.lower()]
        
        frames = []
        if hm_csvs:
            try:
                hm_enc = _detect_encoding(hm_csvs[0])
                hm_sep = _detect_separator(hm_csvs[0], hm_enc)
                hm_raw = pd.read_csv(hm_csvs[0], sep=hm_sep, encoding=hm_enc, low_memory=False)
                
                # RI e Normal
                tipo_col = next((c for c in hm_raw.columns if "tipo" in _norm_text(c) and "cobran" in _norm_text(c)), None)
                cob_col  = next((c for c in hm_raw.columns if "quantidade de cobranca" in _norm_text(c)), "Quantidade de cobranças")
                par_col  = next((c for c in hm_raw.columns if "total de parcela" in _norm_text(c) or "total parcelas" in _norm_text(c)), "Quantidade total de parcelas")
                val_col  = next((c for c in hm_raw.columns if "faturamento liquido" in _norm_text(c) or "valor liquido" in _norm_text(c)), "Faturamento líquido do(a) Produtor(a)")
                status_col = next((c for c in hm_raw.columns if "status da transacao" in _norm_text(c) or "status" in _norm_text(c)), "Status da transação")
                email_col = next((c for c in hm_raw.columns if "email do(a) comprador" in _norm_text(c) or "email" in _norm_text(c)), "Email do(a) Comprador(a)")
                estado_col = next((c for c in hm_raw.columns if "estado" in _norm_text(c) or "provincia" in _norm_text(c)), "Estado / Província")
                cidade_col = next((c for c in hm_raw.columns if "cidade" in _norm_text(c)), "Cidade")
                
                hm_raw["status_norm"] = hm_raw[status_col].astype(str).apply(_norm_text)
                hm_paid = hm_raw[hm_raw["status_norm"].isin({"completo", "complete", "aprovado", "approved", "pago"})].copy()
                
                if tipo_col and cob_col in hm_paid.columns and par_col in hm_paid.columns:
                    hm_normal = hm_paid[hm_paid[tipo_col].astype(str).str.strip() != "Recuperador Inteligente"].copy()
                    hm_normal["valor_liq"] = hm_normal[val_col].apply(_to_float)
                    hm_ri = hm_paid[
                        (hm_paid[tipo_col].astype(str).str.strip() == "Recuperador Inteligente") &
                        (pd.to_numeric(hm_paid[cob_col], errors="coerce").fillna(0) == 1)
                    ].copy()
                    hm_ri[par_col] = pd.to_numeric(hm_ri[par_col], errors="coerce").fillna(1)
                    hm_ri["valor_liq"] = hm_ri[val_col].apply(_to_float) * hm_ri[par_col]
                    hm_final = pd.concat([hm_normal, hm_ri], ignore_index=True)
                else:
                    hm_paid["valor_liq"] = hm_paid[val_col].apply(_to_float)
                    hm_final = hm_paid
                    
                hm_final["email_norm"] = hm_final[email_col].astype(str).str.strip().str.lower()
                hm_final = hm_final[hm_final["email_norm"].str.contains("@", na=False)].copy()
                
                hm_sub = pd.DataFrame({
                    "email_norm": hm_final["email_norm"],
                    "valor": hm_final["valor_liq"],
                    "plataforma": "Hotmart",
                    "estado": hm_final[estado_col].fillna("").astype(str) if estado_col in hm_final.columns else "",
                    "cidade": hm_final[cidade_col].fillna("").astype(str) if cidade_col in hm_final.columns else "",
                    "utm_source": "",
                    "utm_campaign": ""
                })
                frames.append(hm_sub)
            except Exception:
                pass
                
        if tmb_csvs:
            try:
                tmb_enc = _detect_encoding(tmb_csvs[0])
                tmb_sep = _detect_separator(tmb_csvs[0], tmb_enc)
                tmb_raw = pd.read_csv(tmb_csvs[0], sep=tmb_sep, encoding=tmb_enc, low_memory=False)
                
                status_col = next((c for c in tmb_raw.columns if "situacao" in _norm_text(c) or "status" in _norm_text(c)), None)
                email_col = next((c for c in tmb_raw.columns if "email" in _norm_text(c) or "e-mail" in _norm_text(c)), None)
                val_col = next((c for c in tmb_raw.columns if "ticket do pedido" in _norm_text(c) or "valor" in _norm_text(c)), None)
                estado_col = next((c for c in tmb_raw.columns if "estado" in _norm_text(c) or "uf" in _norm_text(c)), None)
                cidade_col = next((c for c in tmb_raw.columns if "cidade" in _norm_text(c)), None)
                utm_col = next((c for c in tmb_raw.columns if "utm_source" in _norm_text(c)), None)
                utm_camp_col = next((c for c in tmb_raw.columns if "utm_campaign" in _norm_text(c)), None)
                
                if status_col:
                    tmb_raw["status_norm"] = tmb_raw[status_col].astype(str).apply(_norm_text)
                    tmb_paid = tmb_raw[tmb_raw["status_norm"].isin({"vigente", "efetivado", "pago", "em dia", "integralizado", "aprovado", "concluido", "active"})].copy()
                else:
                    tmb_paid = tmb_raw
                    
                if email_col and val_col:
                    tmb_paid["email_norm"] = tmb_paid[email_col].astype(str).str.strip().str.lower()
                    tmb_paid = tmb_paid[tmb_paid["email_norm"].str.contains("@", na=False)].copy()
                    tmb_paid["valor_liq"] = tmb_paid[val_col].apply(_to_float)
                    
                    tmb_sub = pd.DataFrame({
                        "email_norm": tmb_paid["email_norm"],
                        "valor": tmb_paid["valor_liq"],
                        "plataforma": "TMB",
                        "estado": tmb_paid[estado_col].fillna("").astype(str) if estado_col in tmb_paid.columns else "",
                        "cidade": tmb_paid[cidade_col].fillna("").astype(str) if cidade_col in tmb_paid.columns else "",
                        "utm_source": tmb_paid[utm_col].fillna("").astype(str) if utm_col in tmb_paid.columns else "",
                        "utm_campaign": tmb_paid[utm_camp_col].fillna("").astype(str) if utm_camp_col in tmb_paid.columns else ""
                    })
                    frames.append(tmb_sub)
            except Exception:
                pass
                
        if frames:
            sales_df = pd.concat(frames, ignore_index=True)
            
    # Junta UTMs e dados do CRM
    if not sales_df.empty:
        # Se crm está preenchido, cruza para preencher utms faltantes e informações demográficas
        if not crm_df.empty:
            crm_utm_s = next((c for c in crm_df.columns if "utm_source" in _norm_text(c)), None)
            crm_utm_c = next((c for c in crm_df.columns if "utm_campaign" in _norm_text(c)), None)
            
            crm_sub = crm_df[["email_norm"]].copy()
            if crm_utm_s:
                crm_sub["crm_source"] = crm_df[crm_utm_s].fillna("").astype(str)
            if crm_utm_c:
                crm_sub["crm_campaign"] = crm_df[crm_utm_c].fillna("").astype(str)
                
            sales_df = sales_df.merge(crm_sub, on="email_norm", how="left")
            
            if "crm_source" in sales_df.columns:
                sales_df["utm_source"] = sales_df.apply(lambda r: r["crm_source"] if str(r["utm_source"]).strip() == "" else r["utm_source"], axis=1)
            if "crm_campaign" in sales_df.columns:
                sales_df["utm_campaign"] = sales_df.apply(lambda r: r["crm_campaign"] if str(r["utm_campaign"]).strip() == "" else r["utm_campaign"], axis=1)
                
            summary.compradores_crm = int(sales_df["email_norm"].isin(set(crm_df["email_norm"])).sum())
            
        if not tf_df.empty:
            summary.compradores_typeform = int(sales_df["email_norm"].isin(set(tf_df["email_norm"])).sum())
            
        summary.conversao_lead_venda = (summary.compradores_unicos / summary.leads_crm * 100) if summary.leads_crm > 0 else 0.0
        
        # ── 4. Origem das Vendas (Canais e Campanhas) ──
        # Identifica canais
        def get_channel(src):
            s = _norm_text(src)
            if not s:
                return "Sem rastreio"
            if s.startswith("fb") or "facebook" in s or "meta" in s or "instagram" in s:
                return "Meta / Facebook"
            if s.startswith("yt") or "youtube" in s:
                return "YouTube"
            if "google" in s or s.startswith("g-") or s.startswith("gg"):
                return "Google"
            if "whatsapp" in s or "comercial" in s:
                return "Comercial / WhatsApp"
            return "Outros"
            
        sales_df["canal"] = sales_df["utm_source"].apply(get_channel)
        
        # Top canais
        canal_grouped = sales_df.groupby("canal").agg(
            compradores=("email_norm", "nunique"),
            transacoes=("email_norm", "size"),
            faturamento=("valor", "sum")
        ).reset_index().sort_values("faturamento", ascending=False)
        
        for _, r in canal_grouped.iterrows():
            trans = int(r["transacoes"])
            fat = float(r["faturamento"])
            summary.top_canais.append({
                "label": str(r["canal"]),
                "compradores": int(r["compradores"]),
                "transacoes": trans,
                "faturamento": fat,
                "ticket": (fat / trans) if trans > 0 else 0.0
            })
            
        # Set top canais para leitura executiva
        if summary.top_canais:
            top_o = summary.top_canais[0]
            summary.top_origem_nome = top_o["label"]
            summary.top_origem_faturamento = top_o["faturamento"]
            summary.top_origem_compradores = top_o["compradores"]
            summary.top_origem_ticket = top_o["ticket"]
            
        # Top campanhas
        sales_df["utm_campaign_norm"] = sales_df["utm_campaign"].fillna("").astype(str).str.strip()
        camp_grouped = sales_df[sales_df["utm_campaign_norm"] != ""].groupby("utm_campaign_norm").agg(
            compradores=("email_norm", "nunique"),
            transacoes=("email_norm", "size"),
            faturamento=("valor", "sum")
        ).reset_index().sort_values("faturamento", ascending=False).head(10)
        
        for _, r in camp_grouped.iterrows():
            trans = int(r["transacoes"])
            fat = float(r["faturamento"])
            summary.top_campanhas.append({
                "label": str(r["utm_campaign_norm"]),
                "compradores": int(r["compradores"]),
                "transacoes": trans,
                "faturamento": fat,
                "ticket": (fat / trans) if trans > 0 else 0.0
            })
            
        # ── 5. Geografia das Vendas ──
        # Estados
        sales_df["estado_norm"] = sales_df["estado"].fillna("").astype(str).str.strip().str.upper()
        # Se estado_norm é vazio e temos Typeform, tenta pegar do Typeform
        if not tf_df.empty:
            tf_estado_col = next((c for c in tf_df.columns if "estado" in _norm_text(c)), None)
            if tf_estado_col:
                tf_est_sub = tf_df[["email_norm", tf_estado_col]].copy()
                tf_est_sub.columns = ["email_norm", "tf_estado"]
                sales_df = sales_df.merge(tf_est_sub, on="email_norm", how="left")
                if "tf_estado" in sales_df.columns:
                    sales_df["estado_norm"] = sales_df.apply(lambda r: str(r["tf_estado"]).strip().upper() if r["estado_norm"] == "" and pd.notna(r["tf_estado"]) else r["estado_norm"], axis=1)
                    
        est_grouped = sales_df[sales_df["estado_norm"] != ""].groupby("estado_norm").agg(
            compradores=("email_norm", "nunique"),
            transacoes=("email_norm", "size"),
            faturamento=("valor", "sum")
        ).reset_index().sort_values("faturamento", ascending=False).head(10)
        
        for _, r in est_grouped.iterrows():
            trans = int(r["transacoes"])
            fat = float(r["faturamento"])
            summary.top_estados.append({
                "label": str(r["estado_norm"]),
                "compradores": int(r["compradores"]),
                "transacoes": trans,
                "faturamento": fat,
                "ticket": (fat / trans) if trans > 0 else 0.0
            })
        if summary.top_estados:
            summary.top_estado_nome = summary.top_estados[0]["label"]
            summary.top_estado_faturamento = summary.top_estados[0]["faturamento"]
            summary.top_estado_compradores = summary.top_estados[0]["compradores"]
            
        # Cidades
        sales_df["cidade_norm"] = sales_df["cidade"].fillna("").astype(str).str.strip()
        cid_grouped = sales_df[sales_df["cidade_norm"] != ""].groupby("cidade_norm").agg(
            compradores=("email_norm", "nunique"),
            transacoes=("email_norm", "size"),
            faturamento=("valor", "sum")
        ).reset_index().sort_values("faturamento", ascending=False).head(10)
        
        for _, r in cid_grouped.iterrows():
            trans = int(r["transacoes"])
            fat = float(r["faturamento"])
            summary.top_cidades.append({
                "label": str(r["cidade_norm"]),
                "compradores": int(r["compradores"]),
                "transacoes": trans,
                "faturamento": fat,
                "ticket": (fat / trans) if trans > 0 else 0.0
            })
            
        # ── 6. Perfil Demográfico Compradores ──
        if not tf_df.empty:
            sales_tf = sales_df.merge(tf_df, on="email_norm", how="inner")
            
            def demografia_tabela(col_name_part: str) -> list[dict[str, Any]]:
                col = next((c for c in tf_df.columns if col_name_part.lower() in _norm_text(c)), None)
                if not col or sales_tf.empty:
                    return []
                grouped = sales_tf.groupby(col).agg(
                    compradores=("email_norm", "nunique"),
                    transacoes=("email_norm", "size"),
                    faturamento=("valor", "sum")
                ).reset_index().sort_values("faturamento", ascending=False)
                
                rows = []
                for _, r in grouped.iterrows():
                    lbl = str(r[col]).strip()
                    if not lbl or lbl.lower() == "nan":
                        continue
                    trans = int(r["transacoes"])
                    fat = float(r["faturamento"])
                    rows.append({
                        "label": lbl,
                        "compradores": int(r["compradores"]),
                        "transacoes": trans,
                        "faturamento": fat,
                        "ticket": (fat / trans) if trans > 0 else 0.0
                    })
                return rows
                
            summary.genero = demografia_tabela("genero")
            summary.idade = demografia_tabela("idade")
            summary.situacao_prof = demografia_tabela("situacao profissional")
            summary.escolaridade = demografia_tabela("escolaridade")
            
        # ── 7. Propensão por Resposta ──
        if not crm_df.empty and not tf_df.empty:
            lead_base = crm_df[["email_norm"]].copy()
            lead_base["comprador"] = lead_base["email_norm"].isin(set(sales_df["email_norm"]))
            lead_base["valor_comprado"] = lead_base["email_norm"].map(sales_df.groupby("email_norm")["valor"].sum()).fillna(0.0)
            
            # Cruzamento com Typeform
            lead_base = lead_base.merge(tf_df, on="email_norm", how="inner")
            
            questoes = {
                "Compromisso de 2h/dia": next((c for c in tf_df.columns if "se compromete" in _norm_text(c)), None),
                "Já assistiu conteúdo do Graton": next((c for c in tf_df.columns if "felipe graton" in _norm_text(c)), None),
                "Perfil de estudo": next((c for c in tf_df.columns if "voce se considera" in _norm_text(c)), None),
                "Faixa etária": next((c for c in tf_df.columns if "idade" in _norm_text(c)), None),
                "Situação profissional": next((c for c in tf_df.columns if "situacao profissional" in _norm_text(c)), None),
                "Escolaridade": next((c for c in tf_df.columns if "escolaridade" in _norm_text(c)), None),
            }
            
            propensao_candidatos = []
            for label, column in questoes.items():
                if not column or lead_base.empty:
                    continue
                    
                grouped = lead_base.groupby(column).agg(
                    leads=("email_norm", "count"),
                    compradores=("comprador", "sum"),
                    faturamento=("valor_comprado", "sum")
                ).reset_index()
                
                # Corta grupos pequenos (ex: menos de 80 leads)
                grouped = grouped[grouped["leads"] >= 80].copy()
                
                for _, r in grouped.iterrows():
                    resp = str(r[column]).strip()
                    if not resp or resp.lower() == "nan":
                        continue
                    leads_cnt = int(r["leads"])
                    comp_cnt = int(r["compradores"])
                    fat_val = float(r["faturamento"])
                    conv = (comp_cnt / leads_cnt * 100) if leads_cnt > 0 else 0.0
                    tkt = (fat_val / comp_cnt) if comp_cnt > 0 else 0.0
                    
                    item = {
                        "dimensao": label,
                        "resposta": resp,
                        "leads": leads_cnt,
                        "compradores": comp_cnt,
                        "tx_conv": conv,
                        "faturamento": fat_val,
                        "ticket": tkt
                    }
                    summary.propensao.append(item)
                    propensao_candidatos.append(item)
                    
            # Ordena propensão por taxa de conversão decrescente
            summary.propensao = sorted(summary.propensao, key=lambda x: x["tx_conv"], reverse=True)
            
            # Extrai insights demográficos de propensão (volume, conversão, ticket)
            if propensao_candidatos:
                summary.volume_insight = sorted(propensao_candidatos, key=lambda x: (x["compradores"], x["faturamento"]), reverse=True)[0]
                summary.conv_insight = sorted(propensao_candidatos, key=lambda x: (x["tx_conv"], x["compradores"]), reverse=True)[0]
                ticket_candidates = [x for x in propensao_candidatos if x["compradores"] >= 8]
                summary.ticket_insight = sorted(ticket_candidates or propensao_candidatos, key=lambda x: (x["ticket"], x["compradores"]), reverse=True)[0]
                
    return summary

