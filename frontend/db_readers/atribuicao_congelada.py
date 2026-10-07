"""
frontend/db_readers/atribuicao_congelada.py — trava da atribuição por lançamento.

**Por que existe.** A tabela `leads` guarda UMA linha por contato, com um
`lancamento_codigo` só. Quando a pessoa se cadastra num lançamento novo, a
linha é reescrita e o lançamento antigo perde aquele comprador — junto com a
UTM que dizia qual anúncio o trouxe. Medido em 07/10/26: todo lançamento
fechado já tinha perdido de 32% a 41% dos compradores rastreados, e o ROAS do
PI-AGO-26 caiu de 2,36x para 1,97x sem venda nenhuma mudar (ver seção 13 de
`docs/sistema/METODOLOGIA_EXTRACAO_DADOS.md`).

**O que a trava faz.** Guarda, por (lançamento, comprador), a MELHOR UTM já
observada — "melhor" pelo mesmo `_utm_score` que a atribuição ao vivo usa. A
gravação é monotônica: `ON CONFLICT` só sobrescreve se o score novo for maior,
então uma linha congelada nunca piora, aconteça o que acontecer com a `leads`.

**O que ela NÃO faz.** Não recupera o que já foi sobrescrito antes do primeiro
congelamento — aquele dado não está escondido, foi perdido. Por isso o valor de
congelar cedo: cada semana sem a trava custa compradores.
"""
from __future__ import annotations

from typing import Any

from sqlalchemy import text

from logger import get_logger
from frontend.db import _get_engine

logger = get_logger("db")

_CAMPOS = ("source", "medium", "campaign", "content", "term")

DDL = """
CREATE TABLE IF NOT EXISTS atribuicao_congelada (
    lancamento_codigo text        NOT NULL,
    email             text        NOT NULL,
    score             integer     NOT NULL DEFAULT 0,
    utm_source        text        NOT NULL DEFAULT '',
    utm_medium        text        NOT NULL DEFAULT '',
    utm_campaign      text        NOT NULL DEFAULT '',
    utm_content       text        NOT NULL DEFAULT '',
    utm_term          text        NOT NULL DEFAULT '',
    congelado_em      timestamptz NOT NULL DEFAULT now(),
    atualizado_em     timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (lancamento_codigo, email)
);
"""


def criar_tabela() -> None:
    with _get_engine().begin() as conn:
        conn.execute(text(DDL))


def ler_congelada(launch_code: str) -> dict[str, dict]:
    """{email: {score, source, medium, campaign, content, term}} do lançamento.

    Dicionário vazio quando a tabela ainda não existe — a atribuição ao vivo
    segue igual, que é o comportamento de antes da trava.
    """
    if not launch_code:
        return {}
    try:
        with _get_engine().connect() as conn:
            linhas = conn.execute(
                text("""SELECT email, score, utm_source, utm_medium, utm_campaign,
                               utm_content, utm_term
                        FROM atribuicao_congelada WHERE lancamento_codigo = :c"""),
                {"c": launch_code},
            ).fetchall()
    except Exception as e:
        if "atribuicao_congelada" in str(e) and "does not exist" in str(e):
            return {}
        logger.exception("ler_congelada: falha para %s", launch_code)
        return {}
    return {
        str(r[0]): {
            "score": int(r[1] or 0), "source": r[2] or "", "medium": r[3] or "",
            "campaign": r[4] or "", "content": r[5] or "", "term": r[6] or "",
        }
        for r in linhas
    }


def gravar_congelada(launch_code: str, buyer_utms: dict[str, Any]) -> int:
    """Congela as UTMs deste lançamento. Devolve quantas linhas foram enviadas.

    Monotônico de propósito: só sobrescreve quando o score novo é MAIOR. Como a
    `leads` só degrada com o tempo, um congelamento posterior nunca pode apagar
    um anterior — no pior caso não acrescenta nada.
    """
    if not launch_code or not buyer_utms:
        return 0
    criar_tabela()
    linhas = [
        {
            "c": launch_code, "email": email, "score": int(utm.get("score") or 0),
            **{f"utm_{k}": str(utm.get(k) or "") for k in _CAMPOS},
        }
        for email, utm in buyer_utms.items()
        if email
    ]
    sql = text("""
        INSERT INTO atribuicao_congelada
            (lancamento_codigo, email, score, utm_source, utm_medium,
             utm_campaign, utm_content, utm_term)
        VALUES (:c, :email, :score, :utm_source, :utm_medium,
                :utm_campaign, :utm_content, :utm_term)
        ON CONFLICT (lancamento_codigo, email) DO UPDATE SET
            score         = EXCLUDED.score,
            utm_source    = EXCLUDED.utm_source,
            utm_medium    = EXCLUDED.utm_medium,
            utm_campaign  = EXCLUDED.utm_campaign,
            utm_content   = EXCLUDED.utm_content,
            utm_term      = EXCLUDED.utm_term,
            atualizado_em = now()
        WHERE EXCLUDED.score > atribuicao_congelada.score
    """)
    with _get_engine().begin() as conn:
        for i in range(0, len(linhas), 1000):
            conn.execute(sql, linhas[i:i + 1000])
    logger.info("atribuicao_congelada: %d linhas enviadas para %s", len(linhas), launch_code)
    return len(linhas)
