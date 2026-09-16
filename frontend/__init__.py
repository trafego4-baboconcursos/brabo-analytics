"""
Pacote do frontend do Brabo Analytics.

Coloca ``src/`` no ``sys.path`` no momento em que o pacote é importado. Os
módulos compartilhados em ``src/`` (``logger``, ``db_engine``, ``constants``)
são importados pelo nome de topo (``from logger import get_logger``), então
precisam estar visíveis antes de qualquer submódulo de ``frontend`` carregar —
inclusive quando o ponto de entrada não é ``frontend.app`` (testes, scripts,
``python -c``).
"""
from __future__ import annotations

import sys
from pathlib import Path

WORKSPACE_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = WORKSPACE_ROOT / "src"

for _p in (WORKSPACE_ROOT, SRC_DIR):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))
