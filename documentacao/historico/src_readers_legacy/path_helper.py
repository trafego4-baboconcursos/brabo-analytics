from __future__ import annotations
from pathlib import Path

def find_subfolder(launch_folder: Path, category: str) -> Path | None:
    """
    Busca uma subpasta dentro de launch_folder de forma tolerante a erros de
    grafia, espaços e maiúsculas/minúsculas.
    
    Categorias válidas:
      - 'meta': Meta Ads, Facebook, FB
      - 'google': Google Ads, Googole Ads, Googleads, YouTube Ads, YouTube, YT
      - 'vendas': Vendas, Sales
      - 'ac': Active Campaign, Active Campaing, AC, Active
      - 'typeform': Typeform, Pesquisa
    """
    if not launch_folder.exists() or not launch_folder.is_dir():
        return None
        
    category = category.lower()
    for child in launch_folder.iterdir():
        if not child.is_dir():
            continue
        name = child.name.lower()
        if category == "meta":
            if "meta" in name or "facebook" in name or "fb" in name:
                return child
        elif category == "google":
            if "google" in name or "googole" in name or "youtube" in name or "yt" in name or "ga" in name:
                return child
        elif category == "vendas":
            if "venda" in name or "sales" in name:
                return child
        elif category == "ac":
            if "active" in name or "ac" in name or "campaing" in name or "campaign" in name:
                return child
        elif category == "typeform":
            if "typeform" in name or "pesquisa" in name:
                return child
                
    # Fallback se não encontrar por aproximação, tenta os caminhos padrão
    fallback_map = {
        "meta": "Meta Ads",
        "google": "Google Ads",
        "vendas": "Vendas",
        "ac": "Active Campaign",
        "typeform": "Typeform"
    }
    fb_name = fallback_map.get(category)
    if fb_name:
        fallback_path = launch_folder / fb_name
        if fallback_path.exists():
            return fallback_path
            
    return None
