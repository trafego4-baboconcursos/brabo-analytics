"""Serialização estável para os testes de caracterização.

O objetivo é transformar a saída de qualquer reader (dataclass, dict, lista,
DataFrame, Decimal, date…) em JSON determinístico, para que duas execuções
sobre os mesmos dados produzam exatamente o mesmo texto. Sem isso o baseline
acusaria diferença por ordem de chave ou por ruído de ponto flutuante, e não
por mudança de comportamento — que é o que queremos detectar.
"""
from __future__ import annotations

import dataclasses
import math
from datetime import date, datetime
from decimal import Decimal
from typing import Any

# Casas decimais mantidas nos floats. Dinheiro e taxas do dashboard nunca
# precisam de mais que isso; o resto é ruído de reordenação de soma.
PRECISAO = 4


def normalizar(valor: Any, _profundidade: int = 0) -> Any:
    """Converte ``valor`` em algo serializável em JSON, de forma determinística."""
    if _profundidade > 12:
        return "<profundidade máxima>"

    if valor is None or isinstance(valor, (bool, int, str)):
        return valor

    if isinstance(valor, float):
        if math.isnan(valor):
            return "NaN"
        if math.isinf(valor):
            return "Infinity" if valor > 0 else "-Infinity"
        # -0.0 e 0.0 devem colapsar no mesmo texto.
        return round(valor, PRECISAO) + 0.0

    if isinstance(valor, Decimal):
        return normalizar(float(valor), _profundidade)

    if isinstance(valor, (datetime, date)):
        return valor.isoformat()

    if dataclasses.is_dataclass(valor) and not isinstance(valor, type):
        return {
            campo.name: normalizar(getattr(valor, campo.name), _profundidade + 1)
            for campo in dataclasses.fields(valor)
        }

    if isinstance(valor, dict):
        # Ordena por chave: dict de SQL pode vir em ordem de cursor.
        return {
            str(k): normalizar(v, _profundidade + 1)
            for k, v in sorted(valor.items(), key=lambda kv: str(kv[0]))
        }

    if isinstance(valor, (set, frozenset)):
        return sorted(normalizar(v, _profundidade + 1) for v in valor)

    if isinstance(valor, (list, tuple)):
        return [normalizar(v, _profundidade + 1) for v in valor]

    # DataFrame / Series do pandas e escalares do numpy, sem importar pandas
    # aqui (o módulo precisa carregar mesmo sem as libs de dados).
    tipo = type(valor).__name__
    if tipo == "DataFrame":
        return {
            "__tipo__": "DataFrame",
            "colunas": [str(c) for c in valor.columns],
            "linhas": normalizar(
                valor.to_dict(orient="records"), _profundidade + 1
            ),
        }
    if tipo == "Series":
        return {"__tipo__": "Series", "valores": normalizar(valor.to_dict(), _profundidade + 1)}
    if hasattr(valor, "item") and hasattr(valor, "dtype"):
        return normalizar(valor.item(), _profundidade)

    return f"<{tipo}>"


def _json_canonico(valor: Any) -> str:
    import json

    return json.dumps(valor, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _digest(valor: Any) -> str:
    import hashlib

    return hashlib.sha256(_json_canonico(valor).encode("utf-8")).hexdigest()[:16]


# Um dict com mais chaves que isso é tabela de dados (indexada por e-mail, id,
# código de anúncio…), não estrutura: vira contagem + digest.
_MAX_CHAVES_ESTRUTURAIS = 30


def _e_estrutura(d: dict) -> bool:
    """``True`` quando as chaves são nomes de campo, não dados.

    O baseline é versionado, então nada que venha de linha do banco pode entrar
    nele em texto claro — em especial e-mail, telefone e nome de comprador.
    """
    if len(d) > _MAX_CHAVES_ESTRUTURAIS:
        return False
    return not any("@" in str(k) for k in d)


def resumir(valor: Any, _profundidade: int = 0) -> Any:
    """Esqueleto compacto de ``valor``: mantém os escalares de topo (os KPIs) e
    troca qualquer coleção de dados por contagem + digest.

    Guarda o suficiente para uma falha dizer *onde* mudou, sem versionar os
    183 MB — nem os dados pessoais — que o baseline completo carregaria.
    """
    if isinstance(valor, dict):
        if _profundidade >= 3 or not _e_estrutura(valor):
            return {"__n__": len(valor), "__sha__": _digest(valor)}
        return {k: resumir(v, _profundidade + 1) for k, v in valor.items()}

    if isinstance(valor, list):
        return {"__n__": len(valor), "__sha__": _digest(valor)}

    if isinstance(valor, str) and len(valor) > 120:
        return {"__texto__": len(valor), "__sha__": _digest(valor)}

    return valor


def impressao_digital(valor: Any) -> dict:
    """Assinatura versionável da saída de um reader."""
    import hashlib

    texto = _json_canonico(valor)
    return {
        "sha256": hashlib.sha256(texto.encode("utf-8")).hexdigest(),
        "bytes": len(texto),
        "resumo": resumir(valor),
    }


# ── Falha de infraestrutura × mudança de comportamento ─────────────────────────
#
# Quando o Supabase está lento, a consulta estoura o statement_timeout e o reader
# levanta. Se o teste tratasse isso como "a saída mudou", acusaria regressão onde
# só houve rede ruim — e uma rede que grita lobo deixa de ser consultada.
# Aconteceu três vezes em 15/09/26, inclusive numa execução que levou 23 min
# contra os ~5 habituais.
#
# Estes são erros de *chegar até o dado*, nunca de *como o dado é calculado*:
# um KeyError ou um AttributeError continuam sendo falha de verdade.
_SINAIS_DE_INFRA = (
    "statement timeout",
    "canceling statement",
    "server closed the connection",
    "connection already closed",
    "could not connect",
    "connection refused",
    "connection reset",
    "ssl connection has been closed",
    "timeout expired",
    "too many connections",
    "remaining connection slots",
    "deadlock detected",
    "terminating connection",
)


def e_falha_de_infra(e: BaseException) -> str | None:
    """Devolve o motivo se ``e`` for falha de acesso ao banco, senão ``None``.

    Percorre a cadeia de causas porque o SQLAlchemy embrulha o erro do
    psycopg2, e a frase reveladora costuma estar duas camadas abaixo.
    """
    vistos = set()
    atual: BaseException | None = e
    while atual is not None and id(atual) not in vistos:
        vistos.add(id(atual))
        texto = f"{type(atual).__name__}: {atual}".lower()
        for sinal in _SINAIS_DE_INFRA:
            if sinal in texto:
                return sinal
        atual = atual.__cause__ or atual.__context__
    return None


# ── Comparação por forma, para as saídas que mudam de valor sozinhas ───────────

def _especie(valor: Any) -> str:
    """Que tipo de coisa é ``valor``, sem olhar o conteúdo."""
    if isinstance(valor, dict):
        return "<coleção>"
    if isinstance(valor, bool):
        return "<bool>"
    if isinstance(valor, (int, float)):
        return "<número>"
    if isinstance(valor, str):
        return "<texto>"
    if valor is None:
        return "<nulo>"
    return f"<{type(valor).__name__}>"


def _forma(resumo: Any) -> Any:
    """Estrutura de primeiro nível: nomes dos campos e a espécie de cada um.

    É o que se exige de um reader volátil — que continue devolvendo os mesmos
    campos, das mesmas espécies, depois da refatoração.

    Deliberadamente raso. ``resumir`` colapsa um dicionário assim que ele passa
    de 30 chaves, então uma comparação profunda trocaria de representação
    sozinha quando um dicionário aninhado cruzasse esse limiar por dado novo —
    e acusaria "mudou de forma" sem nenhuma mudança de código. Já aconteceu.
    """
    if not isinstance(resumo, dict) or "__sha__" in resumo:
        return _especie(resumo)
    return {k: _especie(v) for k, v in sorted(resumo.items())}
