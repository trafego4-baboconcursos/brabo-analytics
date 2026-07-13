"""
src/readers/typeform_reader.py
Lê as respostas do Typeform do lançamento e cruza com CRM (Active Campaign) e vendas (Hotmart + TMB)
para avaliar taxas de conversão e perfil dos respondentes.
"""
from __future__ import annotations
import csv
import re
import unicodedata
from pathlib import Path
from dataclasses import dataclass, field
from typing import Any
import pandas as pd

from .path_helper import find_subfolder
from .vendas_reader import _detect_encoding, _to_float, _to_int, _norm_text, _find_col, _load_csv

@dataclass
class TypeformSummary:
    has_data: bool = False
    total_tf: int = 0
    tf_leads_crm: int = 0
    tf_compras: int = 0
    tf_compras_crm: int = 0
    tx_lead_pct: float = 0.0
    tx_venda_tf_pct: float = 0.0
    tx_venda_lead_pct: float = 0.0
    receita_tf: float = 0.0
    receita_total: float = 0.0
    receita_tf_pct: float = 0.0
    
    # Gênero
    genero_comp_pct: dict[str, float] = field(default_factory=dict)
    genero_ncomp_pct: dict[str, float] = field(default_factory=dict)
    genero_diff: dict[str, float] = field(default_factory=dict)
    
    # Situação Profissional
    situacao_comp_pct: dict[str, float] = field(default_factory=dict)
    situacao_ncomp_pct: dict[str, float] = field(default_factory=dict)
    situacao_diff: dict[str, float] = field(default_factory=dict)
    
    # Nível de estudo
    nivel_comp_pct: dict[str, float] = field(default_factory=dict)
    nivel_ncomp_pct: dict[str, float] = field(default_factory=dict)
    nivel_diff: dict[str, float] = field(default_factory=dict)
    
    # Faixa etária
    idade_comp_pct: dict[str, float] = field(default_factory=dict)
    idade_ncomp_pct: dict[str, float] = field(default_factory=dict)
    idade_diff: dict[str, float] = field(default_factory=dict)
    
    # Conhecimento do Graton
    graton_comp_pct: dict[str, float] = field(default_factory=dict)
    graton_ncomp_pct: dict[str, float] = field(default_factory=dict)
    graton_diff: dict[str, float] = field(default_factory=dict)
    
    # Obstáculos
    obstaculos_comp_pct: dict[str, float] = field(default_factory=dict)
    obstaculos_ncomp_pct: dict[str, float] = field(default_factory=dict)
    obstaculos_diff: dict[str, float] = field(default_factory=dict)
    
    # Estados
    top_estados_comp: list[dict] = field(default_factory=list)
    top_estados_geral: list[dict] = field(default_factory=list)
    
    # UTM de Compradores
    top_utm_sources: list[dict] = field(default_factory=list)
    
    # Informações de bases usadas
    leads_crm_total: int = 0
    vendas_hotmart_total: int = 0
    vendas_tmb_total: int = 0
    tf_file_name: str = ""
    leads_file_name: str = ""
    hotmart_file_name: str = ""
    tmb_file_name: str = ""


def _detect_separator(path: Path, enc: str) -> str:
    try:
        with path.open(encoding=enc, errors="replace") as f:
            first_line = f.readline()
        if first_line.count(";") > first_line.count(","):
            return ";"
        return ","
    except Exception:
        return ","


def _find_csv_files(folder: Path, pattern: str = "*.csv") -> list[Path]:
    if not folder or not folder.exists():
        return []
    return sorted(folder.glob(pattern))


def read_typeform(launch_folder: Path) -> TypeformSummary:
    summary = TypeformSummary()
    
    tf_folder = find_subfolder(launch_folder, "typeform")
    ac_folder = find_subfolder(launch_folder, "ac")
    vendas_folder = find_subfolder(launch_folder, "vendas")
    
    # Se não houver pasta do Typeform, retorna vazio (has_data = False)
    if not tf_folder or not tf_folder.exists():
        return summary
        
    tf_csvs = sorted(tf_folder.glob("*.csv"))
    if not tf_csvs:
        return summary
        
    # Encontra o CSV do Typeform que contém "pesquisa" ou o primeiro disponível
    tf_file = None
    for csv_path in tf_csvs:
        if "pesquisa" in csv_path.name.lower():
            tf_file = csv_path
            break
    if not tf_file:
        tf_file = tf_csvs[0]
        
    summary.tf_file_name = tf_file.name
    summary.has_data = True
    
    # ── 1. Carrega dados do Typeform ──
    try:
        tf_enc = _detect_encoding(tf_file)
        tf_sep = _detect_separator(tf_file, tf_enc)
        tf_df = pd.read_csv(tf_file, sep=tf_sep, encoding=tf_enc, low_memory=False)
    except Exception:
        summary.has_data = False
        return summary
        
    # Identifica coluna de e-mail no Typeform
    tf_email_col = None
    for col in tf_df.columns:
        col_norm = _norm_text(col)
        if "digite o seu e-mail" in col_norm or "digite seu e-mail" in col_norm or "e-mail" in col_norm or "email" in col_norm:
            tf_email_col = col
            break
    if not tf_email_col:
        # Pega a primeira coluna que contiver @ ou email nos cabeçalhos
        tf_email_col = tf_df.columns[0]
        
    tf_df["email_norm"] = tf_df[tf_email_col].astype(str).str.strip().str.lower()
    # Limpa linhas vazias de e-mail
    tf_df = tf_df[tf_df["email_norm"].str.contains("@", na=False)].copy()
    tf_df = tf_df.drop_duplicates("email_norm", keep="last")
    summary.total_tf = len(tf_df)
    
    # ── 2. Carrega leads do CRM (Active Campaign) ──
    crm_df = pd.DataFrame()
    if ac_folder and ac_folder.exists():
        ac_csvs = sorted(ac_folder.glob("*.csv"))
        if ac_csvs:
            # Pega o maior arquivo ou o modificado mais recentemente
            crm_file = max(ac_csvs, key=lambda f: f.stat().st_size)
            summary.leads_file_name = crm_file.name
            try:
                crm_enc = _detect_encoding(crm_file)
                crm_sep = _detect_separator(crm_file, crm_enc)
                crm_df = pd.read_csv(crm_file, sep=crm_sep, encoding=crm_enc, low_memory=False)
                crm_email_col = None
                for col in crm_df.columns:
                    c_norm = _norm_text(col)
                    if "email" in c_norm or "e-mail" in c_norm:
                        crm_email_col = col
                        break
                if crm_email_col:
                    crm_df["email_norm"] = crm_df[crm_email_col].astype(str).str.strip().str.lower()
                    crm_df = crm_df[crm_df["email_norm"].str.contains("@", na=False)].copy()
                    crm_df = crm_df.drop_duplicates("email_norm", keep="first")
                    summary.leads_crm_total = len(crm_df)
            except Exception:
                crm_df = pd.DataFrame()
                
    # ── 3. Carrega vendas da Hotmart e TMB ──
    hm_df = pd.DataFrame()
    tmb_df = pd.DataFrame()
    
    if vendas_folder and vendas_folder.exists():
        hm_csvs = [f for f in vendas_folder.glob("*.csv") if "hotmart" in f.name.lower()]
        tmb_csvs = [f for f in vendas_folder.glob("*.csv") if "tmb" in f.name.lower()]
        
        # Hotmart
        if hm_csvs:
            hm_file = hm_csvs[0]
            summary.hotmart_file_name = hm_file.name
            try:
                hm_enc = _detect_encoding(hm_file)
                hm_sep = _detect_separator(hm_file, hm_enc)
                hm_raw = pd.read_csv(hm_file, sep=hm_sep, encoding=hm_enc, low_memory=False)
                
                # Tratamento de Recuperador Inteligente e valores
                tipo_col = next((c for c in hm_raw.columns if "tipo" in _norm_text(c) and "cobran" in _norm_text(c)), None)
                cob_col  = next((c for c in hm_raw.columns if "quantidade de cobranca" in _norm_text(c)), "Quantidade de cobranças")
                par_col  = next((c for c in hm_raw.columns if "total de parcela" in _norm_text(c) or "total parcelas" in _norm_text(c)), "Quantidade total de parcelas")
                val_col  = next((c for c in hm_raw.columns if "faturamento liquido" in _norm_text(c) or "valor liquido" in _norm_text(c)), "Faturamento líquido do(a) Produtor(a)")
                status_col = next((c for c in hm_raw.columns if "status da transacao" in _norm_text(c) or "status" in _norm_text(c)), "Status da transação")
                email_col = next((c for c in hm_raw.columns if "email do(a) comprador" in _norm_text(c) or "email" in _norm_text(c)), "Email do(a) Comprador(a)")
                
                # Filtra vendas aprovadas/pagas
                hm_raw["status_norm"] = hm_raw[status_col].astype(str).apply(_norm_text)
                hm_paid = hm_raw[hm_raw["status_norm"].isin({"completo", "complete", "aprovado", "approved", "pago"})].copy()
                
                # Normal e RI
                if tipo_col and cob_col in hm_paid.columns and par_col in hm_paid.columns:
                    hm_normal = hm_paid[hm_paid[tipo_col].astype(str).str.strip() != "Recuperador Inteligente"].copy()
                    hm_normal["valor_liq"] = hm_normal[val_col].apply(_to_float)
                    
                    hm_ri = hm_paid[
                        (hm_paid[tipo_col].astype(str).str.strip() == "Recuperador Inteligente") &
                        (pd.to_numeric(hm_paid[cob_col], errors="coerce").fillna(0) == 1)
                    ].copy()
                    hm_ri[par_col] = pd.to_numeric(hm_ri[par_col], errors="coerce").fillna(1)
                    hm_ri["valor_liq"] = hm_ri[val_col].apply(_to_float) * hm_ri[par_col]
                    hm_df = pd.concat([hm_normal, hm_ri], ignore_index=True)
                else:
                    hm_paid["valor_liq"] = hm_paid[val_col].apply(_to_float)
                    hm_df = hm_paid
                    
                hm_df["email_norm"] = hm_df[email_col].astype(str).str.strip().str.lower()
                hm_df = hm_df[hm_df["email_norm"].str.contains("@", na=False)].copy()
                summary.vendas_hotmart_total = len(hm_df)
            except Exception:
                hm_df = pd.DataFrame()
                
        # TMB
        if tmb_csvs:
            tmb_file = tmb_csvs[0]
            summary.tmb_file_name = tmb_file.name
            try:
                tmb_enc = _detect_encoding(tmb_file)
                tmb_sep = _detect_separator(tmb_file, tmb_enc)
                tmb_raw = pd.read_csv(tmb_file, sep=tmb_sep, encoding=tmb_enc, low_memory=False)
                
                status_col = next((c for c in tmb_raw.columns if "situacao" in _norm_text(c) or "status" in _norm_text(c)), None)
                if status_col:
                    tmb_raw["status_norm"] = tmb_raw[status_col].astype(str).apply(_norm_text)
                    tmb_paid = tmb_raw[tmb_raw["status_norm"].isin({"vigente", "efetivado", "pago", "em dia", "integralizado", "aprovado", "concluido", "active"})].copy()
                else:
                    tmb_paid = tmb_raw
                    
                email_col = next((c for c in tmb_paid.columns if "email" in _norm_text(c) or "e-mail" in _norm_text(c)), None)
                val_col = next((c for c in tmb_paid.columns if "ticket do pedido" in _norm_text(c) or "valor" in _norm_text(c)), None)
                
                if email_col and val_col:
                    tmb_paid["email_norm"] = tmb_paid[email_col].astype(str).str.strip().str.lower()
                    tmb_paid = tmb_paid[tmb_paid["email_norm"].str.contains("@", na=False)].copy()
                    tmb_paid["valor_liq"] = tmb_paid[val_col].apply(_to_float)
                    tmb_df = tmb_paid
                    summary.vendas_tmb_total = len(tmb_df)
            except Exception:
                tmb_df = pd.DataFrame()

    # ── 4. Cruzamento de E-mails e faturamento ──
    tf_emails = set(tf_df["email_norm"])
    crm_emails = set(crm_df["email_norm"]) if not crm_df.empty else set()
    
    hm_emails = set(hm_df["email_norm"]) if not hm_df.empty else set()
    tmb_emails = set(tmb_df["email_norm"]) if not tmb_df.empty else set()
    vendas_emails = hm_emails | tmb_emails
    
    # Compradores e faturamento por email
    receita_por_email = {}
    vendas_por_email = {}
    
    for df in [hm_df, tmb_df]:
        if not df.empty and "email_norm" in df.columns and "valor_liq" in df.columns:
            for _, r in df.iterrows():
                email = r["email_norm"]
                val = float(r["valor_liq"])
                receita_por_email[email] = receita_por_email.get(email, 0.0) + val
                vendas_por_email[email] = vendas_por_email.get(email, 0) + 1
                
    summary.receita_total = sum(receita_por_email.values())
    
    # Cruzados
    tf_e_crm = tf_emails & crm_emails
    tf_e_vendas = tf_emails & vendas_emails
    
    summary.tf_leads_crm = len(tf_e_crm)
    summary.tf_compras = len(tf_e_vendas)
    summary.tf_compras_crm = len(tf_e_crm & vendas_emails)
    
    summary.tx_lead_pct = (summary.tf_leads_crm / summary.total_tf * 100) if summary.total_tf > 0 else 0.0
    summary.tx_venda_tf_pct = (summary.tf_compras / summary.total_tf * 100) if summary.total_tf > 0 else 0.0
    
    if not crm_df.empty:
        total_compradores_crm = len(crm_emails & vendas_emails)
        summary.tx_venda_lead_pct = (total_compradores_crm / len(crm_df) * 100) if len(crm_df) > 0 else 0.0
        
    summary.receita_tf = sum(receita_por_email.get(em, 0.0) for em in tf_e_vendas)
    summary.receita_tf_pct = (summary.receita_tf / summary.receita_total * 100) if summary.receita_total > 0 else 0.0
    
    # Dataframes de Compradores e Não-Compradores do Typeform
    tf_comp = tf_df[tf_df["email_norm"].isin(tf_e_vendas)].copy()
    tf_ncomp = tf_df[~tf_df["email_norm"].isin(tf_e_vendas)].copy()
    
    # ── 5. Análise de Distribuição Demográfica ──
    def comp_ncomp_distribution(col_name_part: str) -> tuple[dict[str, float], dict[str, float], dict[str, float]]:
        # Encontra a coluna correspondente
        col = None
        for c in tf_df.columns:
            if col_name_part.lower() in _norm_text(c):
                col = c
                break
        if not col:
            return {}, {}, {}
            
        vc_comp = tf_comp[col].value_counts(normalize=True) * 100
        vc_ncomp = tf_ncomp[col].value_counts(normalize=True) * 100
        
        all_keys = set(vc_comp.index) | set(vc_ncomp.index)
        
        comp_dist = {}
        ncomp_dist = {}
        diff_dist = {}
        
        for k in all_keys:
            if pd.isna(k) or str(k).strip() == "":
                continue
            c_val = float(vc_comp.get(k, 0.0))
            nc_val = float(vc_ncomp.get(k, 0.0))
            comp_dist[str(k)] = c_val
            ncomp_dist[str(k)] = nc_val
            diff_dist[str(k)] = c_val - nc_val
            
        # Ordena por percentual de compradores decrescente
        sorted_keys = sorted(comp_dist.keys(), key=lambda x: comp_dist[x], reverse=True)
        return (
            {k: comp_dist[k] for k in sorted_keys},
            {k: ncomp_dist[k] for k in sorted_keys},
            {k: diff_dist[k] for k in sorted_keys}
        )
        
    summary.genero_comp_pct, summary.genero_ncomp_pct, summary.genero_diff = comp_ncomp_distribution("genero")
    summary.situacao_comp_pct, summary.situacao_ncomp_pct, summary.situacao_diff = comp_ncomp_distribution("situacao profissional")
    summary.nivel_comp_pct, summary.nivel_ncomp_pct, summary.nivel_diff = comp_ncomp_distribution("voce se considera")
    summary.idade_comp_pct, summary.idade_ncomp_pct, summary.idade_diff = comp_ncomp_distribution("idade")
    summary.graton_comp_pct, summary.graton_ncomp_pct, summary.graton_diff = comp_ncomp_distribution("felipe graton")
    
    # ── 6. Análise de Obstáculos ──
    obstaculos = [
        ("Não sei estudar do jeito certo", "Não sei estudar do jeito certo (falta de técnicas de estudos)"),
        ("Não sei montar um cronograma", "Não sei montar um cronograma de estudos"),
        ("Procrastinação", "Procrastinação (não conseguir estudar)"),
        ("Estou há muito tempo sem estudar", "Estou há muito tempo sem estudar"),
        ("Pouco tempo disponível", "Pouco tempo disponível pra me dedicar aos estudos"),
        ("Medo de esquecer no dia da prova", "Medo de esquecer tudo no dia da prova"),
        ("Medo de estudar e não passar", "Medo de estudar muito e não conseguir passar"),
        ("Sem dinheiro para curso", "Não tenho dinheiro para investir in um curso"),
        ("Medo de não sair o concurso", "Medo de não sair o concurso este ano"),
    ]
    
    obst_comp = {}
    obst_ncomp = {}
    obst_diff = {}
    
    for label, pattern in obstaculos:
        col = None
        for c in tf_df.columns:
            c_norm = _norm_text(c)
            # Verifica se o texto do cabeçalho contém palavras do padrão
            if _norm_text(label) in c_norm or _norm_text(pattern)[:30] in c_norm:
                col = c
                break
        if col:
            # Conta percentual de respondentes que marcaram (não nulos)
            val_comp = (tf_comp[col].notna().sum() / len(tf_comp) * 100) if len(tf_comp) > 0 else 0.0
            val_ncomp = (tf_ncomp[col].notna().sum() / len(tf_ncomp) * 100) if len(tf_ncomp) > 0 else 0.0
            
            obst_comp[label] = val_comp
            obst_ncomp[label] = val_ncomp
            obst_diff[label] = val_comp - val_ncomp
            
    # Ordena obstáculos pela diferença ou pela taxa de compradores
    sorted_obst = sorted(obst_comp.keys(), key=lambda x: obst_comp[x], reverse=True)
    summary.obstaculos_comp_pct = {k: obst_comp[k] for k in sorted_obst}
    summary.obstaculos_ncomp_pct = {k: obst_ncomp[k] for k in sorted_obst}
    summary.obstaculos_diff = {k: obst_diff[k] for k in sorted_obst}
    
    # ── 7. Geografia ──
    estado_col = None
    for c in tf_df.columns:
        if "estado" in _norm_text(c):
            estado_col = c
            break
            
    if estado_col:
        # Geral
        vc_geral = tf_df[estado_col].value_counts()
        total_g = len(tf_df)
        summary.top_estados_geral = [
            {"estado": str(est), "qtd": int(qtd), "pct": float(qtd / total_g * 100)}
            for est, qtd in vc_geral.head(10).items() if str(est).strip() != ""
        ]
        
        # Compradores
        vc_comp = tf_comp[estado_col].value_counts()
        total_c = len(tf_comp)
        summary.top_estados_comp = [
            {"estado": str(est), "qtd": int(qtd), "pct": float(qtd / total_c * 100) if total_c > 0 else 0.0}
            for est, qtd in vc_comp.head(10).items() if str(est).strip() != ""
        ]
        
    # ── 8. UTM dos Compradores (da pesquisa Typeform) ──
    utm_col = None
    if not crm_df.empty:
        for col in crm_df.columns:
            if "utm_source" in _norm_text(col):
                utm_col = col
                break
                
    if utm_col:
        crm_comp_tf = crm_df[crm_df["email_norm"].isin(tf_e_vendas)]
        if not crm_comp_tf.empty:
            vc_utm = crm_comp_tf[utm_col].value_counts().head(10)
            summary.top_utm_sources = []
            for src, cnt in vc_utm.items():
                src_str = str(src).strip()
                if not src_str:
                    continue
                plat = "Outros"
                src_lower = src_str.lower()
                if src_lower.startswith("yt") or "youtube" in src_lower:
                    plat = "YouTube"
                elif src_lower.startswith("fb") or "facebook" in src_lower or "meta" in src_lower or "instagram" in src_lower:
                    plat = "Meta / FB"
                summary.top_utm_sources.append({
                    "source": src_str,
                    "qtd": int(cnt),
                    "canal": plat
                })
                
    return summary
