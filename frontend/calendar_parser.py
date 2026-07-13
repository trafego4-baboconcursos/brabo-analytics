import re
import unicodedata
from pathlib import Path
from datetime import datetime, date
from typing import Any

def norm_text(value: str) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    return text.encode("ascii", "ignore").decode("ascii").strip().lower()

def parse_date(date_str: str) -> date:
    return datetime.strptime(date_str.strip(), "%d/%m/%Y").date()

def parse_calendar(workspace_root: Path) -> dict[str, dict[str, Any]]:
    """
    Varre analises/ procurando por SISTEMA_CALENDARIO_2026.html
    e extrai os limites de datas para cada lancamento.
    """
    # Procura na pasta analises/[PBB-ABR-26]/SISTEMA_CALENDARIO_2026.html
    html_path = workspace_root / "analises" / "[PBB-ABR-26]" / "SISTEMA_CALENDARIO_2026.html"
    
    # Se nao achar, procura em qualquer subpasta de analises
    if not html_path.exists():
        analises_dir = workspace_root / "analises"
        if analises_dir.exists():
            for p in analises_dir.glob("**/SISTEMA_CALENDARIO_2026.html"):
                html_path = p
                break

    if not html_path.exists():
        # Fallback para dados estáticos caso o arquivo não seja encontrado
        return get_static_fallback_bounds()

    try:
        content = html_path.read_text(encoding="utf-8")
    except Exception:
        try:
            content = html_path.read_text(encoding="latin-1")
        except Exception:
            return get_static_fallback_bounds()

    # Regex para obter as linhas da tabela da agenda
    pattern = re.compile(
        r'<tr[^>]*data-launch=["\']([^"\']+)["\'][^>]*>.*?<span[^>]*class=["\']stage [^"\']*["\'][^>]*>([^<]+)</span>.*?<td>(\d{2}/\d{2}/\d{4})</td>\s*<td>(\d{2}/\d{2}/\d{4})</td>',
        re.DOTALL
    )
    
    matches = pattern.findall(content)
    if not matches:
        return get_static_fallback_bounds()
        
    launches = {}
    for launch_code, stage_raw, start_str, end_str in matches:
        launch_code = launch_code.strip().upper()
        stage_norm = norm_text(stage_raw)
        
        # Normaliza o nome da etapa
        if "pre" in stage_norm:
            stage = "pre_quali"
        elif "capta" in stage_norm:
            stage = "captacao"
        elif "depo" in stage_norm:
            stage = "depoimento"
        elif "aula" in stage_norm:
            stage = "aulas"
        elif "carrinho" in stage_norm:
            stage = "carrinho"
        else:
            stage = stage_norm.replace(" ", "_")
            
        try:
            start_dt = parse_date(start_str)
            end_dt = parse_date(end_str)
        except Exception:
            continue
        
        launches.setdefault(launch_code, {})[stage] = {
            "start": start_dt,
            "end": end_dt
        }
        
    # Calcula os limites de datas para cada lancamento
    launch_bounds = {}
    for code, stages in launches.items():
        all_dates = []
        for stage_data in stages.values():
            all_dates.extend([stage_data["start"], stage_data["end"]])
        if all_dates:
            launch_bounds[code] = {
                "start": min(all_dates),
                "end": max(all_dates),
                "stages": stages
            }
            
    # Adiciona o Perpétuo com None para buscar sem limites de datas
    launch_bounds["PERPETUO"] = {
        "start": None,
        "end": None,
        "stages": {}
    }
            
    return launch_bounds

def get_static_fallback_bounds() -> dict[str, dict[str, Any]]:
    """
    Retorna limites de datas estaticos caso nao consiga ler o HTML
    """
    # Mapeamento estático baseado no que extraímos do HTML original
    fallback = {
        "PI-JAN-26": ("2025-11-17", "2026-01-26"),
        "PES-JAN-26": ("2026-01-01", "2026-02-02"),
        "PBB-FEV-26": ("2026-01-05", "2026-02-16"),
        "PES-MAR-26": ("2026-02-16", "2026-03-30"),
        "PI-ABR-26": ("2026-03-09", "2026-04-19"),
        "PBB-ABR-26": ("2026-03-16", "2026-04-27"),
        "PES-MAI-26": ("2026-04-13", "2026-05-25"),
        "PBB-JUN-26": ("2026-05-11", "2026-06-22"),
        "PI-AGO-26": ("2026-07-13", "2026-08-24"),
        "PES-SET-26": ("2026-08-17", "2026-09-28"),
        "PBB-OUT-26": ("2026-09-07", "2026-10-19"),
        "PI-NOV-26": ("2026-10-12", "2026-11-23"),
    }
    bounds = {}
    for code, (start_str, end_str) in fallback.items():
        start_dt = datetime.strptime(start_str, "%Y-%m-%d").date()
        end_dt = datetime.strptime(end_str, "%Y-%m-%d").date()
        bounds[code] = {
            "start": start_dt,
            "end": end_dt,
            "stages": {}
        }
    bounds["PERPETUO"] = {
        "start": None,
        "end": None,
        "stages": {}
    }
    return bounds
