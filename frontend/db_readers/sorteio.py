"""
frontend/db_readers/sorteio.py — Leitura de sorteio_respostas (etl/etl_sorteio_forms.py)
pauta debriefing / /pesquisas.

sorteio_respostas guarda TODAS as respostas históricas de todos os formulários
de um projeto (ex: "INSS" foi de 09/2023 até hoje, formulários novos a cada
lançamento) — não existe uma coluna de lançamento. A separação por lançamento
é feita aqui, batendo `created_at` contra a janela "Aulas no Ar" de cada
launch_config: do início das aulas do lançamento até o início das aulas do
PRÓXIMO lançamento do mesmo produto (resolve a "cauda" de gente que responde
dias depois da aula). `aulas_start_date` costuma estar em branco na config
(preenchimento manual, raramente feito) — cai pra `carrinho_start_date` e,
por fim, `dim_lancamentos.data_inicio`, sempre presente.
"""
from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from sqlalchemy import text

from logger import get_logger
from frontend.db import _get_engine
from frontend.db_readers.launches import read_launch_config
from frontend.utils import _extract_launch_code
from src.constants import PRODUCT_BY_PREFIX

logger = get_logger("db")

# Ordem de exibição — mesma normalização de etl/etl_sorteio_forms.py::_normaliza_aula.
_AULAS_ORDEM = ["Aula 1", "Aula 2", "Aula 3", "Aula 4", "Resumão"]


def _janela_inicio(code: str, dim_data_inicio: Any) -> str | None:
    cfg = read_launch_config(code)
    inicio = cfg.get("aulas_start_date") or cfg.get("carrinho_start_date")
    if inicio:
        return str(inicio)
    return str(dim_data_inicio) if dim_data_inicio else None


def _resolve_janela(code: str) -> tuple[str, str] | None:
    """[início, fim) das "Aulas no Ar" deste lançamento até o início das do
    próximo do mesmo produto — ou até hoje, se este for o mais recente."""
    prefix = code.split("-")[0]
    engine = _get_engine()
    with engine.connect() as conn:
        siblings = conn.execute(text(
            "SELECT codigo, data_inicio FROM dim_lancamentos "
            "WHERE split_part(codigo, '-', 1) = :prefix ORDER BY data_inicio"
        ), {"prefix": prefix}).fetchall()

    codes = [r[0] for r in siblings]
    if code not in codes:
        return None
    idx = codes.index(code)

    inicio = _janela_inicio(code, siblings[idx][1])
    if not inicio:
        return None

    if idx + 1 < len(codes):
        fim = _janela_inicio(codes[idx + 1], siblings[idx + 1][1])
    else:
        fim = None
    if not fim:
        fim = (date.today() + timedelta(days=1)).isoformat()

    return inicio, fim


def read_sorteio(launch_folder_or_code: Any) -> dict | None:
    code = _extract_launch_code(launch_folder_or_code)
    prefix = code.split("-")[0]
    projeto = PRODUCT_BY_PREFIX.get(prefix, (None,))[0]
    if not projeto:
        return None

    try:
        janela = _resolve_janela(code)
    except Exception:
        logger.exception("read_sorteio: falha ao resolver janela de %s", code)
        janela = None
    inicio, fim = janela if janela else (None, None)

    # Atribuição: prioriza etl/etl_sorteio_form_map.py (sorteio_form_lancamento)
    # — form_id é sinal melhor que data de corte pra "Aula 1" (ela acontece
    # semanas antes de aulas_start_date, quase sempre em branco, então a
    # janela por data cai pro carrinho_start_date do lançamento e perde a
    # cauda pro lançamento anterior; form_id não tem esse viés, um form novo
    # por lançamento). Formulário sem mapeamento (lançamento novo, script
    # ainda não rodou de novo) cai pro método de data como antes.
    engine = _get_engine()
    cte = (
        "WITH mapa AS ("
        "  SELECT form_id, lancamento_codigo, aula FROM sorteio_form_lancamento WHERE projeto = :projeto"
        "), janela AS ("
        # COALESCE(m.aula, r.aula): a tabela curada pode corrigir a aula de um
        # formulário reciclado (ex.: Aula 2 que quebrou e usou o link da Aula 3,
        # ver _CORRECOES_AULA em etl/etl_sorteio_form_map.py) — sorteio_respostas
        # continua com o nome real do formulário no Drive, a correção mora só aqui.
        "  SELECT COALESCE(m.aula, r.aula) AS aula, lower(btrim(r.email)) AS email_norm, r.response_id"
        "  FROM sorteio_respostas r LEFT JOIN mapa m ON m.form_id = r.form_id"
        "  WHERE r.projeto = :projeto"
        "    AND ("
        "      m.lancamento_codigo = :code"
        "      OR (m.form_id IS NULL AND :inicio IS NOT NULL AND r.created_at >= :inicio AND r.created_at < :fim)"
        "    )"
        ") "
    )
    params = {"projeto": projeto, "code": code, "inicio": inicio, "fim": fim}
    try:
        with engine.connect() as conn:
            por_aula_rows = conn.execute(text(
                cte + "SELECT aula, count(DISTINCT COALESCE(email_norm, response_id)) FROM janela GROUP BY aula"
            ), params).fetchall()

            resumo = conn.execute(text(
                cte + ", leads_base AS ("
                "  SELECT DISTINCT lower(btrim(email)) AS email_norm FROM leads"
                "  WHERE lancamento_codigo = :code AND email IS NOT NULL AND email <> ''"
                ") "
                "SELECT (SELECT count(DISTINCT COALESCE(email_norm, response_id)) FROM janela), "
                "(SELECT count(*) FROM leads_base), "
                "(SELECT count(DISTINCT j.email_norm) FROM janela j JOIN leads_base b ON j.email_norm = b.email_norm)"
            ), params).fetchone()
    except Exception:
        logger.exception("read_sorteio: falha ao consultar sorteio_respostas para %s", code)
        return None

    total_participantes = int(resumo[0] or 0)
    if not total_participantes:
        return None
    base_leads = int(resumo[1] or 0)
    cruzados = int(resumo[2] or 0)

    contagem = {aula: int(n) for aula, n in por_aula_rows}
    por_aula = [
        {"aula": aula, "participantes": contagem[aula]}
        for aula in _AULAS_ORDEM if aula in contagem
    ]
    # Formulários fora do padrão de aula reconhecido (raro) entram no fim.
    for aula, n in contagem.items():
        if aula not in _AULAS_ORDEM:
            por_aula.append({"aula": aula, "participantes": n})

    return {
        "por_aula": por_aula,
        "total_participantes": total_participantes,
        "base_leads": base_leads,
        "cruzados_com_base": cruzados,
        "taxa_participacao": (cruzados / base_leads * 100) if base_leads else 0.0,
        "janela_inicio": inicio,
        "janela_fim": fim,
    }
