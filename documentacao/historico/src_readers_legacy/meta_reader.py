"""
src/readers/meta_reader.py
Leitor do CSV de export bruto do Gerenciador de Anúncios do Meta (Facebook).
Colunas esperadas (em português - export padrão):
  Nome da campanha | Dia | Nome do conjunto de anúncios | Nome do anúncio |
  Resultados | Valor usado (BRL) | Custo por resultado | Cliques no link |
  Leads | Custo por lead | ThruPlays | Custo por ThruPlay | Impressões | ...
"""
from __future__ import annotations
import csv
import re
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional


# ──────────────────────────────────────────────────────────────────────────────
# Mapeamento flexível de nomes de coluna (normalizado → alias possíveis)
# ──────────────────────────────────────────────────────────────────────────────
COL_MAP = {
    "campanha":         ["Nome da campanha"],
    "dia":              ["Dia"],
    "conjunto":         ["Nome do conjunto de anúncios"],
    "anuncio":          ["Nome do anúncio"],
    "impressoes":       ["Impressões"],
    "alcance":          ["Alcance"],
    "cliques_link":     ["Cliques no link"],
    "cliques_todos":    ["Cliques (todos)"],
    "ctr":              ["CTR (todos)"],
    "cpm":              ["CPM (custo por 1.000 impressões)"],
    "cpc_link":         ["CPC (custo por clique no link)"],
    "gasto":            ["Valor usado (BRL)"],
    "resultados":       ["Resultados"],
    "custo_resultado":  ["Custo por resultado"],
    "leads":            ["Leads"],
    "cpl":              ["Custo por lead"],
    "thruplays":        ["ThruPlays"],
    "custo_thruplay":   ["Custo por ThruPlay"],
    "tipo_resultado":   ["Tipo de resultado"],
    "nivel":            ["Nível de veiculação"],
    "inicio":           ["Início dos relatórios"],
    "fim":              ["Encerramento dos relatórios"],
}


def _find_col(header: list[str], aliases: list[str]) -> int | None:
    for alias in aliases:
        for i, col in enumerate(header):
            if col.strip().lower() == alias.strip().lower():
                return i
    return None


def _to_float(val: str) -> float:
    if not val or val.strip() in ("", "-", "N/D", "N/A"):
        return 0.0
    cleaned = re.sub(r"[^\d,.-]", "", val).strip()
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


# ──────────────────────────────────────────────────────────────────────────────
# Extrações de metadados da nomenclatura de campanha Meta
# ──────────────────────────────────────────────────────────────────────────────
# Ex: [MA][captação][quente][principal][PBB-ABR-26][03.04.26][M]
ETAPA_MAP = {
    "captação": "Captação",
    "capta": "Captação",
    "compra": "Captação",
    "compras": "Captação",
    "pré-qualificação": "Pré-Qualificação",
    "pre-qualificacao": "Pré-Qualificação",
    "pré-quali": "Pré-Qualificação",
    "pre-quali": "Pré-Qualificação",
    "engajamento": "RMK/Engajamento",
    "replay": "RMK/Engajamento",
    "trafego": "RMK/Engajamento",
    "tráfego": "RMK/Engajamento",
    "matrículas": "Pitch/ROAS",
    "matriculas": "Pitch/ROAS",
    "pitch": "Pitch/ROAS",
    "roas": "Pitch/ROAS",
}

TEMPERATURA_MAP = {
    "quente": "Quente",
    "frio": "Frio",
    "específico": "Específico",
    "especifico": "Específico",
    "lookalike": "Frio",
}

BUCKET_MAP = {
    "principal": "Principal",
    "potencial": "Potencial",
    "reels": "Reels",
    "novos-ads": "Novos Ads (teste)",
    "novos_ads": "Novos Ads (teste)",
}


def _extract_tags(nome: str) -> dict:
    """Extrai etapa, temperatura e bucket do nome da campanha."""
    lower = nome.lower()
    etapa = "Outros"
    temp = "Outros"
    bucket = "Outros"
    for k, v in ETAPA_MAP.items():
        if f"[{k}]" in lower or f"][{k}]" in lower:
            etapa = v
            break
    for k, v in TEMPERATURA_MAP.items():
        if f"[{k}]" in lower:
            temp = v
            break
    for k, v in BUCKET_MAP.items():
        if f"[{k}]" in lower:
            bucket = v
            break
    return {"etapa": etapa, "temperatura": temp, "bucket": bucket}


# ──────────────────────────────────────────────────────────────────────────────
# Estruturas de saída
# ──────────────────────────────────────────────────────────────────────────────
@dataclass
class MetaCriativo:
    nome: str
    campanha: str
    conjunto: str
    etapa: str
    temperatura: str
    bucket: str
    gasto: float = 0.0
    impressoes: int = 0
    alcance: int = 0
    cliques: int = 0
    leads: int = 0
    thruplays: int = 0
    cpl: float = 0.0
    ctr: float = 0.0
    cpc: float = 0.0
    cpm: float = 0.0
    custo_thruplay: float = 0.0


@dataclass
class MetaSummary:
    total_gasto: float = 0.0
    total_leads: int = 0
    total_cliques: int = 0
    total_impressoes: int = 0
    total_thruplays: int = 0
    cpl_medio: float = 0.0
    ctr_medio: float = 0.0
    cpm_medio: float = 0.0
    # Por etapa
    por_etapa: dict = field(default_factory=dict)
    # Por temperatura
    por_temperatura: dict = field(default_factory=dict)
    # Por bucket
    por_bucket: dict = field(default_factory=dict)
    # Por dia e etapa
    por_dia: list = field(default_factory=list)
    # Top criativos
    top_por_leads: list = field(default_factory=list)
    top_por_cpl: list = field(default_factory=list)
    piores_cpl: list = field(default_factory=list)
    # Criativos validados vs novos
    validados: list = field(default_factory=list)
    novos: list = field(default_factory=list)
    captacao_por_ad: list = field(default_factory=list)
    # Período
    data_inicio: str = ""
    data_fim: str = ""


def _find_csv(folder: Path) -> Path | None:
    """Retorna o primeiro CSV encontrado na pasta."""
    csvs = sorted(folder.glob("*.csv"))
    return csvs[0] if csvs else None


def _find_xlsx(folder: Path) -> Path | None:
    """Retorna o primeiro Excel (.xlsx ou .xls) encontrado na pasta."""
    xlsxs = sorted(folder.glob("*.xlsx"))
    if xlsxs:
        return xlsxs[0]
    xlss = sorted(folder.glob("*.xls"))
    if xlss:
        return xlss[0]
    return None


def _detect_encoding(path: Path) -> str:
    for enc in ["utf-8-sig", "utf-8", "latin-1", "cp1252"]:
        try:
            with path.open(encoding=enc) as f:
                f.read(1024)
            return enc
        except (UnicodeDecodeError, LookupError):
            continue
    return "latin-1"


from .path_helper import find_subfolder


def read_meta(launch_folder: Path) -> MetaSummary | None:
    """
    Lê o CSV ou Excel da pasta 'Meta Ads/' do lançamento e retorna um MetaSummary.
    Retorna None se a pasta/CSV/Excel não existir.
    """
    folder = find_subfolder(launch_folder, "meta")
    if not folder or not folder.exists():
        return None
    csv_path = _find_csv(folder)
    xlsx_path = None
    if not csv_path:
        xlsx_path = _find_xlsx(folder)

    if not csv_path and not xlsx_path:
        return None

    rows = []
    header = []

    if csv_path:
        enc = _detect_encoding(csv_path)
        with csv_path.open(encoding=enc, errors="replace") as f:
            reader = csv.reader(f)
            header = next(reader)
            col = {k: _find_col(header, v) for k, v in COL_MAP.items()}
            for row in reader:
                if len(row) < 3 or not row[0].strip():
                    continue
                # Só processa linhas de nível "anúncio"
                nivel_idx = col.get("nivel")
                if nivel_idx is not None and row[nivel_idx].strip() not in ("ad", ""):
                    continue
                rows.append(row)
    else:
        import pandas as pd
        import warnings
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            df = pd.read_excel(xlsx_path)
        
        header = [str(col) for col in df.columns]
        col = {k: _find_col(header, v) for k, v in COL_MAP.items()}
        for _, df_row in df.iterrows():
            row = [str(val) if pd.notna(val) else "" for val in df_row.values]
            if len(row) < 3 or not row[0].strip():
                continue
            nivel_idx = col.get("nivel")
            if nivel_idx is not None and row[nivel_idx].strip() not in ("ad", ""):
                continue
            rows.append(row)

    if not rows:
        return None

    # Agrega por nome do anúncio
    criativos: dict[str, MetaCriativo] = {}
    por_dia_map: dict[str, dict] = {}
    datas = set()

    for row in rows:
        def g(k, default=""):
            idx = col.get(k)
            return row[idx].strip() if idx is not None and idx < len(row) else default

        anuncio = g("anuncio") or g("conjunto")
        campanha = g("campanha")
        conjunto = g("conjunto")
        dia = g("dia")
        if dia:
            datas.add(dia)

        tags = _extract_tags(campanha)
        etapa = tags["etapa"]
        key = anuncio

        if dia:
            gasto = _to_float(g("gasto"))
            leads = _to_int(g("leads"))
            thruplays = _to_int(g("thruplays"))
            cliques = _to_int(g("cliques_link")) or _to_int(g("cliques_todos"))
            if dia not in por_dia_map:
                por_dia_map[dia] = {"dia": dia, "gasto": 0.0, "leads": 0, "thruplays": 0, "cliques": 0, "por_etapa": {}}
            day = por_dia_map[dia]
            day["gasto"] += gasto
            day["leads"] += leads
            day["thruplays"] += thruplays
            day["cliques"] += cliques
            if etapa not in day["por_etapa"]:
                day["por_etapa"][etapa] = {"etapa": etapa, "gasto": 0.0, "leads": 0, "thruplays": 0, "cliques": 0}
            day_etapa = day["por_etapa"][etapa]
            day_etapa["gasto"] += gasto
            day_etapa["leads"] += leads
            day_etapa["thruplays"] += thruplays
            day_etapa["cliques"] += cliques

        if key not in criativos:
            criativos[key] = MetaCriativo(
                nome=anuncio, campanha=campanha, conjunto=conjunto,
                **tags
            )

        c = criativos[key]
        c.gasto += _to_float(g("gasto"))
        c.impressoes += _to_int(g("impressoes"))
        c.alcance += _to_int(g("alcance"))
        c.cliques += _to_int(g("cliques_link")) or _to_int(g("cliques_todos"))
        c.leads += _to_int(g("leads"))
        c.thruplays += _to_int(g("thruplays"))

    # Calcula métricas derivadas
    for c in criativos.values():
        c.cpl = c.gasto / c.leads if c.leads > 0 else 0.0
        c.ctr = (c.cliques / c.impressoes * 100) if c.impressoes > 0 else 0.0
        c.cpm = (c.gasto / c.impressoes * 1000) if c.impressoes > 0 else 0.0
        c.cpc = (c.gasto / c.cliques) if c.cliques > 0 else 0.0
        c.custo_thruplay = (c.gasto / c.thruplays) if c.thruplays > 0 else 0.0

    lista = list(criativos.values())

    # Agrega por etapa
    por_etapa: dict[str, dict] = {}
    for c in lista:
        e = c.etapa
        if e not in por_etapa:
            por_etapa[e] = {"etapa": e, "gasto": 0.0, "leads": 0, "thruplays": 0, "cliques": 0}
        por_etapa[e]["gasto"] += c.gasto
        por_etapa[e]["leads"] += c.leads
        por_etapa[e]["thruplays"] += c.thruplays
        por_etapa[e]["cliques"] += c.cliques

    for e in por_etapa.values():
        e["cpl"] = e["gasto"] / e["leads"] if e["leads"] > 0 else 0.0
        e["custo_thruplay"] = e["gasto"] / e["thruplays"] if e["thruplays"] > 0 else 0.0

    # Agrega por temperatura
    por_temperatura: dict[str, dict] = {}
    captacao = [c for c in lista if c.etapa == "Captação"]
    for c in captacao:
        t = c.temperatura
        if t not in por_temperatura:
            por_temperatura[t] = {"temperatura": t, "gasto": 0.0, "leads": 0}
        por_temperatura[t]["gasto"] += c.gasto
        por_temperatura[t]["leads"] += c.leads
    for t in por_temperatura.values():
        t["cpl"] = t["gasto"] / t["leads"] if t["leads"] > 0 else 0.0

    # Agrega por bucket (captação)
    por_bucket: dict[str, dict] = {}
    for c in captacao:
        b = c.bucket
        if b not in por_bucket:
            por_bucket[b] = {"bucket": b, "gasto": 0.0, "leads": 0}
        por_bucket[b]["gasto"] += c.gasto
        por_bucket[b]["leads"] += c.leads
    total_gasto_cap = sum(v["gasto"] for v in por_bucket.values()) or 1
    for b in por_bucket.values():
        b["cpl"] = b["gasto"] / b["leads"] if b["leads"] > 0 else 0.0
        b["pct"] = b["gasto"] / total_gasto_cap * 100

    # Totais
    total_gasto = sum(c.gasto for c in lista)
    total_leads = sum(c.leads for c in lista)
    total_cliques = sum(c.cliques for c in lista)
    total_impressoes = sum(c.impressoes for c in lista)
    total_thruplays = sum(c.thruplays for c in lista)

    # Top criativos (captação com leads)
    com_leads = [c for c in captacao if c.leads > 0]
    top_leads = sorted(com_leads, key=lambda x: x.leads, reverse=True)[:10]
    top_cpl = sorted(com_leads, key=lambda x: x.cpl)[:5]
    piores_cpl = sorted(com_leads, key=lambda x: x.cpl, reverse=True)[:5]

    captacao_por_ad_map: dict[str, dict] = {}
    for c in captacao:
        match = re.search(r"\bAD\d+\b", c.nome or "", flags=re.IGNORECASE)
        if not match:
            continue
        ad_code = match.group(0).upper()
        if ad_code not in captacao_por_ad_map:
            captacao_por_ad_map[ad_code] = {
                "ad_code": ad_code,
                "nome": c.nome,
                "gasto": 0.0,
                "leads": 0,
                "cliques": 0,
                "impressoes": 0,
                "origem": "Meta Ads",
            }
        item = captacao_por_ad_map[ad_code]
        item["gasto"] += c.gasto
        item["leads"] += c.leads
        item["cliques"] += c.cliques
        item["impressoes"] += c.impressoes
        if len(c.nome) > len(item["nome"]):
            item["nome"] = c.nome
    captacao_por_ad = []
    for item in captacao_por_ad_map.values():
        item["cpl"] = item["gasto"] / item["leads"] if item["leads"] > 0 else 0.0
        item["ctr"] = item["cliques"] / item["impressoes"] * 100 if item["impressoes"] > 0 else 0.0
        item["cpm"] = item["gasto"] / item["impressoes"] * 1000 if item["impressoes"] > 0 else 0.0
        captacao_por_ad.append(item)
    captacao_por_ad = sorted(captacao_por_ad, key=lambda x: x["leads"], reverse=True)

    # Validados vs Novos
    validados = [c for c in captacao if c.bucket != "Novos Ads (teste)" and c.leads > 0]
    novos = [c for c in captacao if c.bucket == "Novos Ads (teste)" and c.leads > 0]
    validados_top = sorted(validados, key=lambda x: x.leads, reverse=True)[:6]
    novos_top = sorted(novos, key=lambda x: x.leads, reverse=True)[:6]

    datas_sorted = sorted(datas)
    por_dia = []
    for dia in datas_sorted:
        day = por_dia_map.get(dia)
        if not day:
            continue
        day["cpl"] = day["gasto"] / day["leads"] if day["leads"] > 0 else 0.0
        for etapa_data in day["por_etapa"].values():
            etapa_data["cpl"] = etapa_data["gasto"] / etapa_data["leads"] if etapa_data["leads"] > 0 else 0.0
        por_dia.append(day)

    return MetaSummary(
        total_gasto=total_gasto,
        total_leads=total_leads,
        total_cliques=total_cliques,
        total_impressoes=total_impressoes,
        total_thruplays=total_thruplays,
        cpl_medio=total_gasto / total_leads if total_leads > 0 else 0.0,
        ctr_medio=total_cliques / total_impressoes * 100 if total_impressoes > 0 else 0.0,
        cpm_medio=total_gasto / total_impressoes * 1000 if total_impressoes > 0 else 0.0,
        por_etapa=por_etapa,
        por_temperatura=por_temperatura,
        por_bucket=por_bucket,
        por_dia=por_dia,
        top_por_leads=top_leads,
        top_por_cpl=top_cpl,
        piores_cpl=piores_cpl,
        validados=validados_top,
        novos=novos_top,
        captacao_por_ad=captacao_por_ad,
        data_inicio=datas_sorted[0] if datas_sorted else "",
        data_fim=datas_sorted[-1] if datas_sorted else "",
    )
