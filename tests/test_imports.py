"""Todo módulo de etl/ e frontend/ tem que importar sem erro.

Existe por causa de um apagão real: em 17/09/26 a categorização por nome de
campanha saiu dos readers para `frontend/db_readers/nomenclatura.py`, e
`etl/budget_alert.py` continuou importando `_categorize_campaign` de
`ads_meta`. Como `etl/scheduler.py` importa `budget_alert` no topo, o container
do scheduler entrou em crash-loop no import e **o ETL ficou 5h30 sem rodar** —
sem nenhum teste falhando, porque nada importava esses módulos.

Este teste roda sem banco (marker padrão, entra no CI): importar não executa
consulta nenhuma. Se um módulo precisar de banco no import, o problema é ele.
"""
from __future__ import annotations

import importlib
import pathlib
import sys

import pytest

_RAIZ = pathlib.Path(__file__).resolve().parent.parent

# Os scripts de etl/ se importam entre si como módulos soltos (`from db import
# get_engine`), que é como rodam em produção. O pythonpath do pytest
# (pyproject.toml) tem só "." e "src" — adicionar "etl" lá dentro faria o módulo
# `db` do ETL sombrear qualquer outro `db` do projeto, então fica local aqui.
if str(_RAIZ / "etl") not in sys.path:
    sys.path.insert(0, str(_RAIZ / "etl"))

_PASTAS = ("etl", "frontend/db_readers", "frontend/services", "frontend/routes")


def _modulos() -> list[str]:
    nomes: list[str] = []
    for pasta in _PASTAS:
        for arquivo in sorted((_RAIZ / pasta).glob("*.py")):
            if arquivo.stem == "__init__":
                continue
            # etl/ roda como scripts soltos (sys.path inclui etl/), por isso o
            # módulo é o nome puro, sem o pacote.
            nomes.append(arquivo.stem if pasta == "etl" else f"{pasta.replace('/', '.')}.{arquivo.stem}")
    return nomes


@pytest.mark.parametrize("modulo", _modulos())
def test_modulo_importa(modulo: str) -> None:
    importlib.import_module(modulo)
