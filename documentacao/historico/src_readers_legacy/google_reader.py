"""
src/readers/google_reader.py
Leitor dos CSVs de export do Google Ads.
Estrutura dos exports Google: linhas de cabeçalho com metadados antes do header real.
Detecta automaticamente a linha do header real (procura por "Campanha" ou "Segmento").
"""
from __future__ import annotations
import csv
import re
from pathlib import Path
from dataclasses import dataclass, field


def _detect_encoding(path: Path) -> str:
    for enc in ["utf-8-sig", "utf-8", "latin-1", "cp1252"]:
        try:
            with path.open(encoding=enc) as f:
                f.read(1024)
            return enc
        except (UnicodeDecodeError, LookupError):
            continue
    return "latin-1"


def _to_float(val: str) -> float:
    if not val or val.strip() in ("", "--", "-", "N/D", "N/A"):
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


def _find_col(header: list[str], *candidates: str) -> int | None:
    for cand in candidates:
        for i, col in enumerate(header):
            if cand.strip().lower() in col.strip().lower():
                return i
    return None


def _load_google_csv(path: Path) -> tuple[list[str], list[list[str]]]:
    """Carrega CSV do Google Ads, pulando linhas de metadados iniciais."""
    enc = _detect_encoding(path)
    all_rows = []
    with path.open(encoding=enc, errors="replace") as f:
        reader = csv.reader(f)
        all_rows = list(reader)

    # Encontra a linha do header real (tem pelo menos 4 colunas e contém palavra-chave)
    header_idx = 0
    for i, row in enumerate(all_rows):
        if len(row) >= 4 and any(
            kw in " ".join(row).lower()
            for kw in ["campanha", "segmento", "grupo de anún", "anúncio", "público"]
        ):
            header_idx = i
            break

    header = all_rows[header_idx]
    # Dados são as linhas após o header, ignorando linhas de total/resumo no final
    data = []
    for row in all_rows[header_idx + 1:]:
        if not row or not row[0].strip():
            continue
        if any(kw in row[0].lower() for kw in ["total", "resumo", "período", "relatório"]):
            continue
        data.append(row)

    return header, data


# ──────────────────────────────────────────────────────────────────────────────
# Tags de nomenclatura de campanhas Google
# ──────────────────────────────────────────────────────────────────────────────
ETAPA_MAP = {
    "captação": "Captação",
    "capta": "Captação",
    "pré-qualificação": "Pré-Qualificação",
    "pre-qualificacao": "Pré-Qualificação",
    "pré-quali": "Pré-Qualificação",
    "pre-quali": "Pré-Qualificação",
    "tráfego": "RMK/Tráfego",
    "trafego": "RMK/Tráfego",
    "performance max": "Performance Max",
    "pmax": "Performance Max",
}

TEMPERATURA_MAP = {
    "quente": "Quente",
    "frio": "Frio",
    "específico": "Específico",
    "especifico": "Específico",
}


def _extract_google_tags(nome: str) -> dict:
    lower = nome.lower()
    etapa = "Outros"
    temp = "Outros"
    for k, v in ETAPA_MAP.items():
        if k in lower:
            etapa = v
            break
    for k, v in TEMPERATURA_MAP.items():
        if f"[{k}]" in lower or f"]{k}[" in lower:
            temp = v
            break
    return {"etapa": etapa, "temperatura": temp}


# ──────────────────────────────────────────────────────────────────────────────
# Estruturas de saída
# ──────────────────────────────────────────────────────────────────────────────
@dataclass
class GoogleCampanha:
    nome: str
    etapa: str
    temperatura: str
    tipo: str = ""
    cliques: int = 0
    impressoes: int = 0
    ctr: float = 0.0
    custo: float = 0.0
    cpc: float = 0.0
    conversoes: float = 0.0
    custo_conv: float = 0.0
    taxa_conv: float = 0.0
    visualizacoes: int = 0


@dataclass
class GooglePublico:
    segmento: str
    campanha: str
    grupo: str
    cliques: int = 0
    impressoes: int = 0
    custo: float = 0.0
    conversoes: float = 0.0
    ctr: float = 0.0
    cpc: float = 0.0


@dataclass
class GoogleSummary:
    total_custo: float = 0.0
    total_cliques: int = 0
    total_impressoes: int = 0
    total_conversoes: float = 0.0
    total_visualizacoes: int = 0
    custo_conv_medio: float = 0.0
    ctr_medio: float = 0.0
    # Por etapa
    por_etapa: dict = field(default_factory=dict)
    # Por temperatura (captação)
    por_temperatura: dict = field(default_factory=dict)
    # Campanhas detalhadas
    campanhas: list = field(default_factory=list)
    # Públicos top
    publicos: list = field(default_factory=list)
    anuncios_por_ad: list = field(default_factory=list)
    # Período
    data_inicio: str = ""
    data_fim: str = ""


def _find_csv_by_keyword(folder: Path, keyword: str) -> Path | None:
    for csv_path in sorted(folder.glob("*.csv")):
        if keyword.lower() in csv_path.name.lower():
            return csv_path
    return None


from .path_helper import find_subfolder


def read_google(launch_folder: Path) -> GoogleSummary | None:
    folder = find_subfolder(launch_folder, "google")
    if not folder or not folder.exists():
        return None

    # ── Campanhas ──
    camp_csv = _find_csv_by_keyword(folder, "campanha") or _find_csv_by_keyword(folder, "campaign")
    campanhas: list[GoogleCampanha] = []

    if camp_csv:
        header, rows = _load_google_csv(camp_csv)
        col_nome = _find_col(header, "campanha")
        col_tipo = _find_col(header, "tipo")
        col_cliq = _find_col(header, "clique", "clicks")
        col_impr = _find_col(header, "impr", "impressão")
        col_ctr  = _find_col(header, "ctr")
        col_custo= _find_col(header, "custo", "cost") or _find_col(header, "gasto")
        col_conv = _find_col(header, "conversão", "conv")
        col_cconv= _find_col(header, "custo / conv", "cost/conv")
        col_tconv= _find_col(header, "taxa de conv")
        col_views= _find_col(header, "visualizações", "visualizacoes", "views")

        def g(row, col, default=""):
            return row[col].strip() if col is not None and col < len(row) else default

        for row in rows:
            nome = g(row, col_nome)
            if not nome:
                continue
            tags = _extract_google_tags(nome)
            custo = _to_float(g(row, col_custo))
            conv  = _to_float(g(row, col_conv))
            cliq  = _to_int(g(row, col_cliq))
            impr  = _to_int(g(row, col_impr))
            campanhas.append(GoogleCampanha(
                nome=nome,
                etapa=tags["etapa"],
                temperatura=tags["temperatura"],
                tipo=g(row, col_tipo),
                cliques=cliq,
                impressoes=impr,
                ctr=_to_float(g(row, col_ctr)),
                custo=custo,
                cpc=custo / cliq if cliq > 0 else 0.0,
                conversoes=conv,
                custo_conv=custo / conv if conv > 0 else 0.0,
                taxa_conv=_to_float(g(row, col_tconv)),
                visualizacoes=_to_int(g(row, col_views)) if col_views is not None else 0,
            ))

    # ── Públicos ──
    pub_csv = _find_csv_by_keyword(folder, "publico") or _find_csv_by_keyword(folder, "audience")
    publicos: list[GooglePublico] = []

    if pub_csv:
        header, rows = _load_google_csv(pub_csv)
        col_seg  = _find_col(header, "segmento", "público-alvo", "segmento de público")
        col_camp = _find_col(header, "campanha")
        col_grupo= _find_col(header, "grupo")
        col_cliq = _find_col(header, "clique", "clicks")
        col_impr = _find_col(header, "impr")
        col_custo= _find_col(header, "custo", "cost")
        col_conv = _find_col(header, "conversão", "conv")
        col_ctr  = _find_col(header, "ctr")

        def g(row, col, default=""):
            return row[col].strip() if col is not None and col < len(row) else default

        for row in rows:
            seg = g(row, col_seg)
            if not seg or "não incluído" in seg.lower():
                continue
            custo = _to_float(g(row, col_custo))
            cliq  = _to_int(g(row, col_cliq))
            publicos.append(GooglePublico(
                segmento=seg,
                campanha=g(row, col_camp),
                grupo=g(row, col_grupo),
                cliques=cliq,
                impressoes=_to_int(g(row, col_impr)),
                custo=custo,
                conversoes=_to_float(g(row, col_conv)),
                ctr=_to_float(g(row, col_ctr)),
                cpc=custo / cliq if cliq > 0 else 0.0,
            ))
        publicos = sorted(publicos, key=lambda x: x.custo, reverse=True)[:20]

    if not campanhas:
        return None

    ads_csv = (
        _find_csv_by_keyword(folder, "performance-dos-anuncios")
        or _find_csv_by_keyword(folder, "dos-anuncios")
        or _find_csv_by_keyword(folder, "ads")
    )
    anuncios_por_ad: list[dict] = []
    if ads_csv:
        header, rows = _load_google_csv(ads_csv)
        col_nome = _find_col(header, "nome do anuncio", "nome do anúncio", "anuncio", "anúncio")
        col_camp = _find_col(header, "campanha")
        col_cliq = _find_col(header, "clique", "clicks")
        col_impr = _find_col(header, "impr")
        col_custo = _find_col(header, "custo", "cost")
        col_conv = _find_col(header, "convers", "conv")
        col_views = _find_col(header, "visualizações do trueview", "visualizacoes do trueview", "views")

        def g(row, col, default=""):
            return row[col].strip() if col is not None and col < len(row) else default

        by_ad: dict[str, dict] = {}
        views_por_campanha: dict[str, int] = {}
        for row in rows:
            nome = g(row, col_nome)
            campanha = g(row, col_camp)
            if not campanha:
                continue
            
            if col_views is not None and col_views < len(row):
                views_val = _to_int(row[col_views])
                views_por_campanha[campanha] = views_por_campanha.get(campanha, 0) + views_val

            if not nome or "capta" not in campanha.lower():
                continue
            match = re.search(r"\bAD\d+\b", nome, flags=re.IGNORECASE)
            if not match:
                continue
            ad_code = match.group(0).upper()
            if ad_code not in by_ad:
                by_ad[ad_code] = {
                    "ad_code": ad_code,
                    "nome": nome,
                    "gasto": 0.0,
                    "leads": 0.0,
                    "cliques": 0,
                    "impressoes": 0,
                    "origem": "Google Ads",
                }
            item = by_ad[ad_code]
            item["gasto"] += _to_float(g(row, col_custo))
            item["leads"] += _to_float(g(row, col_conv))
            item["cliques"] += _to_int(g(row, col_cliq))
            item["impressoes"] += _to_int(g(row, col_impr))
            if len(nome) > len(item["nome"]):
                item["nome"] = nome
        for item in by_ad.values():
            item["cpl"] = item["gasto"] / item["leads"] if item["leads"] > 0 else 0.0
            item["ctr"] = item["cliques"] / item["impressoes"] * 100 if item["impressoes"] > 0 else 0.0
            item["cpm"] = item["gasto"] / item["impressoes"] * 1000 if item["impressoes"] > 0 else 0.0
            item["leads"] = int(round(item["leads"]))
            anuncios_por_ad.append(item)
        anuncios_por_ad = sorted(anuncios_por_ad, key=lambda x: x["leads"], reverse=True)

        if views_por_campanha:
            for c in campanhas:
                if c.visualizacoes == 0 and c.nome in views_por_campanha:
                    c.visualizacoes = views_por_campanha[c.nome]

    # Agrega por etapa
    por_etapa: dict[str, dict] = {}
    for c in campanhas:
        e = c.etapa
        if e not in por_etapa:
            por_etapa[e] = {"etapa": e, "custo": 0.0, "conversoes": 0.0, "cliques": 0, "impressoes": 0, "visualizacoes": 0}
        por_etapa[e]["custo"] += c.custo
        por_etapa[e]["conversoes"] += c.conversoes
        por_etapa[e]["cliques"] += c.cliques
        por_etapa[e]["impressoes"] += c.impressoes
        por_etapa[e]["visualizacoes"] += c.visualizacoes

    total_custo_etapas = sum(v["custo"] for v in por_etapa.values()) or 1
    for e in por_etapa.values():
        e["custo_conv"] = e["custo"] / e["conversoes"] if e["conversoes"] > 0 else 0.0
        e["pct"] = e["custo"] / total_custo_etapas * 100

    # Agrega por temperatura (só captação)
    por_temperatura: dict[str, dict] = {}
    for c in campanhas:
        if c.etapa != "Captação":
            continue
        t = c.temperatura
        if t not in por_temperatura:
            por_temperatura[t] = {"temperatura": t, "custo": 0.0, "conversoes": 0.0}
        por_temperatura[t]["custo"] += c.custo
        por_temperatura[t]["conversoes"] += c.conversoes
    for t in por_temperatura.values():
        t["custo_conv"] = t["custo"] / t["conversoes"] if t["conversoes"] > 0 else 0.0

    total_custo = sum(c.custo for c in campanhas)
    total_cliques = sum(c.cliques for c in campanhas)
    total_impressoes = sum(c.impressoes for c in campanhas)
    total_conversoes = sum(c.conversoes for c in campanhas)
    total_visualizacoes = sum(c.visualizacoes for c in campanhas)

    return GoogleSummary(
        total_custo=total_custo,
        total_cliques=total_cliques,
        total_impressoes=total_impressoes,
        total_conversoes=total_conversoes,
        total_visualizacoes=total_visualizacoes,
        custo_conv_medio=total_custo / total_conversoes if total_conversoes > 0 else 0.0,
        ctr_medio=total_cliques / total_impressoes * 100 if total_impressoes > 0 else 0.0,
        por_etapa=por_etapa,
        por_temperatura=por_temperatura,
        campanhas=sorted(campanhas, key=lambda x: x.custo, reverse=True),
        publicos=publicos,
        anuncios_por_ad=anuncios_por_ad,
    )
