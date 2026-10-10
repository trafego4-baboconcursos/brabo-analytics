"""
frontend/db_readers/whatsapp_alunos.py — quem é aluno entre os membros dos grupos.

Responde, na página /whatsapp da Black, a pergunta que até 08/10/26 era feita à
mão (itens 141 e 180 do MUDANCAS_BV-26): dos números que entraram nos grupos,
quantos são aluno ativo, ex-aluno e não aluno — no total, por expert, por grupo
e entre quem entrou nos últimos dias.

REGRA (a mesma da análise manual; conferida contra ela em 08/10/26 — 11
diferenças em 16.614 números, todas de e-mail do CRM que mudou desde então):
  1. Quem decide se é ALUNO é a plataforma (`aluno_regua`, origem
     'api_plataforma'), nunca o Active Campaign. Casa primeiro por telefone
     (DDD + 8 últimos dígitos); sem casamento por telefone, telefone → e-mail
     no CRM (`leads`) → e-mail na plataforma.
  2. "vitalício" = compra 2025–26; "ativo (prazo)" = turma antiga com acesso
     prorrogado. Os dois são aluno ativo.
  3. As listas de ex-aluno do Active (origem 'ac_ex_aluno') só marcam EX-ALUNO,
     e só de quem não é ativo. Elas não podem encerrar a busca: na primeira
     versão o telefone numa lista de ex-aluno parava a cascata e 35 alunos
     ativos viravam ex-aluno.
  4. Sem casamento nenhum → não aluno. É TETO: 21% dos cadastros da plataforma
     não têm telefone.

A régua é uma foto (data em `referencia`): quem comprou depois dela aparece como
não aluno até a régua ser recarregada (`scripts/carregar_regua_alunos.py`).

Só para lançamento Black: a pergunta "quem é aluno" é dela, que trabalha com a
base. Num lançamento normal já encerrado, a régua de hoje classificaria como
aluno quem comprou NAQUELE lançamento — outra pergunta, e enganosa.
"""
from __future__ import annotations

import re
from typing import Any

import pandas as pd
from sqlalchemy import text

from logger import get_logger
from frontend.db import _get_engine
from frontend.utils import _extract_launch_code
from src.constants import apelidos_armazenamento

logger = get_logger("db")

ATIVO_COMPRA = "Aluno ativo (compra 2025-26)"
ATIVO_PRORROGADO = "Aluno ativo (acesso prorrogado, turma antiga)"
EX_ALUNO = "Ex-aluno"
NAO_ALUNO = "Não aluno"
ATIVOS = (ATIVO_COMPRA, ATIVO_PRORROGADO)

EXPERT_ROTULO = {"INSS": "Mateus (INSS)", "TJSP": "Ivan (TJ-SP)", "BB": "Felipe (BB)"}
DIAS_RECENTES = 3

_CLASSIFICAR = """
WITH membros AS ({membros}),
plat AS (SELECT * FROM aluno_regua WHERE origem = 'api_plataforma'),
acx  AS (SELECT * FROM aluno_regua WHERE origem = 'ac_ex_aluno'),
plat_tel AS (
  SELECT m.tel, p.expert, p.situacao, 'telefone' AS via
  FROM membros m JOIN plat p ON p.telefone_norm = m.tel),
sem_plat_tel AS (SELECT tel FROM membros EXCEPT SELECT tel FROM plat_tel),
email_crm AS (
  SELECT DISTINCT s.tel, lower(trim(l.email)) AS email
  FROM sem_plat_tel s JOIN leads l ON left(l.phone, 2) || right(l.phone, 8) = s.tel
  WHERE l.phone IS NOT NULL AND length(l.phone) BETWEEN 10 AND 11 AND l.email IS NOT NULL),
plat_email AS (
  SELECT e.tel, p.expert, p.situacao, 'e-mail do CRM' AS via
  FROM email_crm e JOIN plat p ON p.email = e.email),
ac_ex AS (
  SELECT m.tel, a.expert, 'ex-aluno' AS situacao, 'telefone' AS via
  FROM membros m JOIN acx a ON a.telefone_norm = m.tel
  UNION ALL
  SELECT e.tel, a.expert, 'ex-aluno', 'e-mail do CRM'
  FROM email_crm e JOIN acx a ON a.email = e.email),
casados AS (SELECT * FROM plat_tel UNION ALL SELECT * FROM plat_email UNION ALL SELECT * FROM ac_ex)
SELECT m.tel, m.grupo, m.entrada, m.no_grupo,
  CASE WHEN bool_or(c.situacao = 'vitalício')     THEN '{compra}'
       WHEN bool_or(c.situacao = 'ativo (prazo)') THEN '{prorrogado}'
       WHEN bool_or(c.situacao = 'ex-aluno')      THEN '{ex}'
       ELSE '{nao}' END AS classificacao,
  string_agg(DISTINCT c.expert, '+') FILTER (WHERE c.situacao IN ('vitalício', 'ativo (prazo)')) AS ativo_de,
  max(c.via) AS via
FROM membros m LEFT JOIN casados c ON c.tel = m.tel
GROUP BY m.tel, m.grupo, m.entrada, m.no_grupo
"""


def _sql_membros(tabela: str) -> str:
    """Um número por pessoa (DDD + 8): a tabela antiga guarda uma linha por
    (pessoa, grupo). Fica o grupo e a data da PRIMEIRA entrada; `no_grupo` é
    se ainda está em algum."""
    return f"""
      SELECT DISTINCT ON (tel) tel, grupo, entrada,
             bool_or(ativo) OVER (PARTITION BY tel) AS no_grupo
      FROM (
        SELECT norm_phone_brasil("NÚMERO"::text) AS tel,
               "GRUPO DA CAMPANHA" AS grupo,
               to_date("DATA1", 'DD/MM/YYYY') AS entrada,
               COALESCE("LEAD ÚNICO", 0) = 1 AS ativo
        FROM "{tabela}"
      ) t
      WHERE tel IS NOT NULL
      ORDER BY tel, entrada"""


def resumir(membros: pd.DataFrame, hoje: pd.Timestamp | None = None) -> dict:
    """Agrega a classificação por membro. Sem banco — é o que os testes cobrem."""
    total = len(membros)
    if not total:
        return {"total": 0}
    cont = membros["classificacao"].value_counts()

    def _linha(rotulo: str, n: int, nivel: int = 0) -> dict:
        return {"rotulo": rotulo, "n": int(n), "pct": n / total * 100, "nivel": nivel}

    n_ativo = int(cont.get(ATIVO_COMPRA, 0) + cont.get(ATIVO_PRORROGADO, 0))
    classes = [
        _linha("Aluno ativo", n_ativo),
        _linha("comprou em 2025–26", cont.get(ATIVO_COMPRA, 0), 1),
        _linha("turma antiga com acesso prorrogado", cont.get(ATIVO_PRORROGADO, 0), 1),
        _linha("Ex-aluno", cont.get(EX_ALUNO, 0)),
        _linha("Não aluno", cont.get(NAO_ALUNO, 0)),
    ]

    ativos = membros[membros["classificacao"].isin(ATIVOS)]
    por_expert: dict[str, int] = {}
    for de in ativos["ativo_de"].dropna():
        for exp in str(de).split("+"):
            rot = EXPERT_ROTULO.get(exp.strip(), exp.strip())
            por_expert[rot] = por_expert.get(rot, 0) + 1
    por_expert = dict(sorted(por_expert.items(), key=lambda kv: -kv[1]))

    def _numero_grupo(g: str) -> int:
        # O número fica depois do "#" e não no começo do nome: "#7 Desafio Base Forte",
        # "Desconto Black Vitalícia #7", "Black Vitalícia 2026 #16". A numeração é contínua
        # entre as duas famílias da Vitalícia (#1–#15 e #16–#25), então ordena só por ela.
        m = re.search(r"#\s*(\d+)", str(g))
        return int(m.group(1)) if m else 10**6

    por_grupo = []
    for grupo, bloco in membros.groupby("grupo"):
        n = len(bloco)
        por_grupo.append({
            "grupo": grupo, "n": n,
            "ativo_pct": bloco["classificacao"].isin(ATIVOS).sum() / n * 100,
            "nao_pct": (bloco["classificacao"] == NAO_ALUNO).sum() / n * 100,
        })
    por_grupo.sort(key=lambda g: (_numero_grupo(g["grupo"]), g["grupo"]))

    hoje = hoje if hoje is not None else pd.Timestamp.now().normalize()
    entradas = pd.to_datetime(membros["entrada"], errors="coerce")
    recentes = membros[entradas >= hoje - pd.Timedelta(days=DIAS_RECENTES - 1)]
    n_rec = len(recentes)

    return {
        "total": total,
        "no_grupo": int(membros["no_grupo"].fillna(False).sum()),
        "classes": classes,
        "pct_ativo": n_ativo / total * 100,
        "pct_nao": cont.get(NAO_ALUNO, 0) / total * 100,
        "por_expert": por_expert,
        "por_grupo": por_grupo,
        "recentes": {
            "dias": DIAS_RECENTES, "n": n_rec,
            "ativo_pct": float(recentes["classificacao"].isin(ATIVOS).sum() / n_rec * 100) if n_rec else 0.0,
            "nao_pct": float((recentes["classificacao"] == NAO_ALUNO).sum() / n_rec * 100) if n_rec else 0.0,
        },
        "casou_por": membros["via"].fillna("sem casamento").value_counts().to_dict(),
    }


BLOCOS = {"vitalicia": "Black Vitalícia", "base_forte": "Base Forte"}


def _candidatos_tabela(code: str, bloco: str) -> list[str]:
    """Vitalícia = `BV_26` (grupos "Desconto Black Vitalícia" e "Black Vitalícia 2026");
    Base Forte = `base_forte`, gravada com o nome da trilha. Ver APELIDOS_ARMAZENAMENTO."""
    base = code.replace("-", "_")
    return list(apelidos_armazenamento(code)) if bloco == "base_forte" else [f"{base}_API", base]


def _ler_sem_cache(code: str, bloco: str = "vitalicia") -> dict | None:
    from frontend.db_readers.whatsapp_groups import (  # noqa: PLC0415
        _ensure_norm_phone_fn, _escolhe_tabela,
    )

    engine = _get_engine()
    with engine.connect() as conn:
        if conn.execute(text("SELECT to_regclass('public.aluno_regua')")).scalar() is None:
            return None
        referencia = conn.execute(text("SELECT max(referencia) FROM aluno_regua")).scalar()
        base = code.replace("-", "_")
        tabela = _escolhe_tabela(conn, _candidatos_tabela(code, bloco))
    if not tabela or referencia is None:
        return None

    _ensure_norm_phone_fn()
    sql = _CLASSIFICAR.format(membros=_sql_membros(tabela), compra=ATIVO_COMPRA,
                              prorrogado=ATIVO_PRORROGADO, ex=EX_ALUNO, nao=NAO_ALUNO)
    with engine.connect() as conn:
        # ~15 s: o casamento por e-mail varre a `leads`. O cache abaixo devolve
        # o valor antigo enquanto recalcula, então só o 1º acesso pós-boot paga.
        conn.execute(text("SET LOCAL statement_timeout = '120s'"))
        linhas = conn.execute(text(sql)).fetchall()
    membros = pd.DataFrame(linhas, columns=["tel", "grupo", "entrada", "no_grupo",
                                            "classificacao", "ativo_de", "via"])
    resumo = resumir(membros)
    resumo["referencia"] = referencia
    resumo["tabela"] = tabela
    resumo["bloco"] = bloco
    return resumo


def read_whatsapp_alunos(launch_folder_or_code: Any, bloco: str = "vitalicia") -> dict | None:
    """Aluno × não aluno dos membros dos grupos de UM bloco da Black: "vitalicia" ou
    "base_forte". None fora da Black, sem régua carregada ou sem tabela de grupo."""
    from frontend.cache import _get_or_compute  # noqa: PLC0415

    code = _extract_launch_code(launch_folder_or_code)
    if not str(code or "").upper().startswith("BV"):
        return None
    try:
        return _get_or_compute(code, f"whatsapp_alunos_{bloco}", lambda: _ler_sem_cache(code, bloco), ttl=3600)
    except Exception:
        logger.exception("read_whatsapp_alunos: falha para %s", code)
        return None
