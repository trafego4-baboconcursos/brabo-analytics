"""
src/readers/launch_discovery.py
Auto-descoberta de lancamentos na pasta analises/.
Detecta pastas no padrao [XXX-YYY-YY] e retorna metadados de cada um.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from .path_helper import find_subfolder
from ..constants import PRODUCT_BY_PREFIX, LAUNCH_ACCENT, LAUNCH_SHORT, LAUNCH_NAMES

FOLDER_PATTERN = re.compile(r"^\[([A-Z0-9_-]+)\]$")


@dataclass
class Launch:
    code: str
    folder: Path
    accent: str
    short: str
    name: str
    product: str = ""
    product_name: str = ""
    product_order: int = 99
    has_meta: bool = False
    has_google: bool = False
    has_vendas: bool = False
    has_hotmart: bool = False
    has_tmb: bool = False
    has_ac: bool = False
    has_typeform: bool = False


def discover_launches(analises_dir: Path) -> list[Launch]:
    """Varre analises/ e retorna lancamentos descobertos."""
    launches: list[Launch] = []

    if not analises_dir.exists():
        return launches

    for child in sorted(analises_dir.iterdir()):
        if not child.is_dir():
            continue
        match = FOLDER_PATTERN.match(child.name)
        if not match:
            continue

        code = match.group(1)
        prefix = code.split("-")[0]
        product, product_name, product_order = PRODUCT_BY_PREFIX.get(prefix, (prefix, prefix, 99))

        meta_folder = find_subfolder(child, "meta")
        google_folder = find_subfolder(child, "google")
        vendas_folder = find_subfolder(child, "vendas")
        ac_folder = find_subfolder(child, "ac")
        typeform_folder = find_subfolder(child, "typeform")
        vendas_files = list(vendas_folder.glob("*.csv")) + list(vendas_folder.glob("*.xlsx")) if vendas_folder else []

        launch = Launch(
            code=code,
            folder=child,
            accent=LAUNCH_ACCENT.get(code, "#2f5ee3"),
            short=LAUNCH_SHORT.get(code, code.split("-")[1] if "-" in code else code),
            name=LAUNCH_NAMES.get(code, code),
            product=product,
            product_name=product_name,
            product_order=product_order,
            has_meta=meta_folder is not None and (any(meta_folder.glob("*.csv")) or any(meta_folder.glob("*.xlsx"))),
            has_google=google_folder is not None and (any(google_folder.glob("*.csv")) or any(google_folder.glob("*.xlsx"))),
            has_vendas=bool(vendas_files),
            has_hotmart=any("hotmart" in file.name.lower() for file in vendas_files),
            has_tmb=any("tmb" in file.name.lower() for file in vendas_files),
            has_ac=ac_folder is not None and any(ac_folder.glob("*.csv")),
            has_typeform=typeform_folder is not None and any(typeform_folder.glob("*.csv")),
        )
        launches.append(launch)

    return launches


def get_launch(launches: list[Launch], code: str) -> Launch | None:
    for launch in launches:
        if launch.code == code:
            return launch
    return None
