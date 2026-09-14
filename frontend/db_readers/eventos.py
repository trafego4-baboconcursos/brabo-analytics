"""
frontend/db_readers/eventos.py — leitura da tabela `eventos_trafego`.

É o índice legível por máquina dos diários de mudança
(`docs/performance/lancamentos/[CODIGO]/MUDANCAS_*.md`), escrito por
`scripts/eventos.py`. Serve pra anotar os gráficos: o que foi FEITO num dia,
ao lado do que ACONTECEU naquele dia nas métricas.

Tabela pequena (centenas de linhas por lançamento) — não é fonte de egress
relevante, mas mesmo assim só devolve o período pedido e as colunas usadas.
"""
from __future__ import annotations

from datetime import date

from sqlalchemy import text

from frontend.db import _get_engine
from logger import get_logger

logger = get_logger("db")

# Cor por tipo de ação — usada pra colorir o ponto no gráfico. Mantida aqui
# (e não no template) pra que qualquer página que mostre eventos use a mesma.
CORES_TIPO = {
    "orcamento": "#f59e0b",
    "cpa":       "#8b5cf6",
    "criativo":  "#3b82f6",
    "publico":   "#14b8a6",
    "estrutura": "#6b7280",
    "pausa":     "#ef4444",
    "ativacao":  "#22c55e",
    "analise":   "#0ea5e9",
    "outro":     "#9ca3af",
}


def read_eventos(codigo: str, inicio: date | None = None, fim: date | None = None) -> list[dict]:
    """Eventos de um escopo (lançamento, perpétuo ou distribuição), em ordem."""
    if not codigo:
        return []
    where = ["codigo = :c"]
    params: dict = {"c": codigo}
    if inicio:
        where.append("data >= :i")
        params["i"] = inicio
    if fim:
        where.append("data <= :f")
        params["f"] = fim
    sql = text(
        "SELECT data, tipo, plataforma, titulo, regra, resultado "
        "FROM eventos_trafego WHERE " + " AND ".join(where) + " ORDER BY data, id"
    )
    try:
        with _get_engine().connect() as conn:
            linhas = conn.execute(sql, params).mappings().all()
    except Exception:
        # Tabela pode não existir ainda num ambiente que não rodou o schema novo.
        # Gráfico sem anotação é degradação aceitável; página quebrada não é.
        logger.exception("read_eventos: falha para %s", codigo)
        return []
    return [
        {
            "data_str": r["data"].strftime("%d/%m"),
            "data_iso": r["data"].isoformat(),
            "tipo": r["tipo"] or "outro",
            "cor": CORES_TIPO.get(r["tipo"] or "outro", CORES_TIPO["outro"]),
            "plataforma": r["plataforma"],
            "titulo": r["titulo"],
            "regra": r["regra"],
            "resultado": r["resultado"],
        }
        for r in linhas
    ]


def eventos_por_dia(eventos: list[dict]) -> dict[str, list[dict]]:
    """Agrupa por `data_str` (dd/mm) — é a chave que os gráficos usam no eixo X."""
    por_dia: dict[str, list[dict]] = {}
    for e in eventos:
        por_dia.setdefault(e["data_str"], []).append(e)
    return por_dia
