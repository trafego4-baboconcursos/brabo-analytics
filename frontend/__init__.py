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

# Carrega o .env pelo mesmo motivo do sys.path acima: vários submódulos leem
# variáveis de ambiente NO IMPORT (auth.py lê as credenciais, db.py a string de
# conexão), então o arquivo precisa estar lido antes de qualquer um deles.
#
# Sem isto o app rodava sem o .env: `SUPABASE_USERS_URL` faltava, toda
# autenticação por banco estourava KeyError e caía no fallback legado, que
# ainda por cima assumia as credenciais default do código (achado em 18/09/26).
#
# `override=False` de propósito: em produção o .env não existe (o
# .dockerignore o exclui da imagem) e quem manda são as variáveis injetadas
# pela plataforma — elas continuam tendo precedência.
try:
    from dotenv import load_dotenv as _load_dotenv

    _load_dotenv(dotenv_path=WORKSPACE_ROOT / ".env", override=False)
except ImportError:  # python-dotenv ausente: o ambiente já deve trazer as vars
    pass
