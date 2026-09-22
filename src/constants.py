"""Constantes compartilhadas pelos leitores em frontend/db_readers."""
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
    # BV = Black Vitálicia: promoção anual multiproduto (INSS + TJ-SP + BB
    # na mesma campanha), fora do ciclo normal de lançamento por produto.
    "BV":       ("Black Vitalícia", "Black Vitalícia (multiproduto)",     5),
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
    "BV-25":      "#111827",
    "BV-26":      "#f97316",
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
    "BV-25":      "BLACK",
    "BV-26":      "BLACK",
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
    "BV-25":      "Black Vitalícia 2025",
    "BV-26":      "Black Vitalícia 2026",
}

# Campanha de e-mail do AC raramente traz o código do lançamento no nome, então
# ac_campaigns.lancamento_codigo fica NULL em praticamente todas (3.325 de 3.325
# em set/26). O vínculo com o lançamento sai da data de envio + uma palavra do
# produto no nome. Usado pelo leitor (frontend) e pelo ETL de engajamento, que
# precisam enxergar exatamente o mesmo conjunto de campanhas.
AC_KEYWORDS_BY_PREFIX: dict[str, list[str]] = {
    "PBB": ["bb", "banco do brasil"],
    "PES": ["tjsp", "escrevente"],
    "PI":  ["inss"],
}
AC_KEYWORDS_TODAS: list[str] = ["inss", "tjsp", "bb", "banco do brasil"]


def ac_keywords(launch_code: str) -> list[str]:
    """Palavras que identificam o produto no nome da campanha de e-mail."""
    prefixo = (launch_code or "").split("-")[0].upper()
    return AC_KEYWORDS_BY_PREFIX.get(prefixo, AC_KEYWORDS_TODAS)
