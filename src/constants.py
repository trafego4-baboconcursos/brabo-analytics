"""Constantes compartilhadas por frontend/db_readers e frontend/database_reader.py."""
from __future__ import annotations

ETAPAS_ORDEM: list[str] = [
    "Pré-Qualificação",
    "Captação",
    "Lembrete",
    "Aulas no Ar",
    "Replay",
    "Matrículas Abertas",
]

PRODUCT_BY_PREFIX: dict[str, tuple[str, str, int]] = {
    "PI":       ("INSS",           "Instituto Nacional do Seguro Social", 1),
    "PES":      ("TJ-SP",          "Tribunal de Justiça de São Paulo",    2),
    "PBB":      ("Banco do Brasil", "Banco do Brasil",                    3),
    "PERPETUO": ("PERPETUO",       "Produto Perpétuo",                    4),
}

LAUNCH_ACCENT: dict[str, str] = {
    "PES-JAN-26": "#764ba2",
    "PBB-FEV-26": "#667eea",
    "PBB-ABR-26": "#f5576c",
    "PES-MAI-26": "#0f766e",
    "PES-MAR-26": "#2f5ee3",
    "PI-ABR-26":  "#e67e22",
    "PI-JAN-26":  "#16a085",
    "PERPETUO":   "#e74c3c",
}

LAUNCH_SHORT: dict[str, str] = {
    "PES-JAN-26": "JAN",
    "PBB-FEV-26": "FEV",
    "PBB-ABR-26": "ABR",
    "PES-MAI-26": "MAI",
    "PES-MAR-26": "MAR",
    "PI-ABR-26":  "ABR",
    "PI-JAN-26":  "JAN",
    "PERPETUO":   "PERP",
}

LAUNCH_NAMES: dict[str, str] = {
    "PES-JAN-26": "TJ-SP - Janeiro 2026",
    "PBB-FEV-26": "Banco do Brasil - Fevereiro 2026",
    "PBB-ABR-26": "Banco do Brasil - Abril 2026",
    "PES-MAI-26": "TJ-SP - Maio 2026",
    "PES-MAR-26": "TJ-SP - Março 2026",
    "PI-ABR-26":  "INSS - Abril 2026",
    "PI-JAN-26":  "INSS - Janeiro 2026",
    "PERPETUO":   "Perpétuo - Geral",
}
