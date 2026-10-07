"""
etl/historico_utm.py — histórico de UTM por (contato, lançamento).

POR QUE EXISTE. A `leads` espelha o Active Campaign: UMA linha por contato, e o
campo de UTM do AC só guarda um valor. Quando um contato que já está na base se
cadastra num lançamento novo, o `etl_active_campaign.py` sobrescreve a linha
(`ON CONFLICT (id) DO UPDATE`) e o lançamento antigo perde a pessoa — junto com
a UTM que dizia qual anúncio a trouxe. Medido em 07/10/26: todo lançamento
fechado tinha perdido de 32% a 41% dos compradores rastreados, e 34 consultas do
frontend filtram a `leads` por lançamento. Na Black, que capta da base, quase
todo lead é contato antigo. Ver `docs/sistema/METODOLOGIA_EXTRACAO_DADOS.md` §13.

A REGRA (decidida pelo Michel em 07/10/26):
  - mesmo lançamento, várias UTMs do mesmo contato → fica a ÚLTIMA;
  - lançamento diferente → linha nova; a do lançamento antigo nunca é tocada.

Na Black a chave inclui a TRILHA (Base Forte × Black Vitalícia têm o mesmo
código, BV-26, e as páginas mostram as duas separadas). Guardar separado é a
escolha reversível: juntar depois é uma consulta; separar o que foi juntado é
impossível. Fora da Black a trilha é '' e a chave se comporta como
(contato, lançamento).

Só entra UTM que NOMEIA o lançamento — o código é tirado da própria
`utm_campaign`, nunca de fallback por pasta ou tag.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Iterable

from sqlalchemy import text

from logger import get_logger

# Logger do projeto, não o logging cru: o cru não tem handler no ETL e a
# linha "N linhas gravadas" sumia da saída (pego em 07/10/26).
logger = get_logger("etl.historico_utm")

TABELA = "lead_utm_lancamento"

TRILHA_BASE_FORTE = "Base Forte"
TRILHA_VITALICIA = "Black Vitalícia"

# Lista de comandos, NUNCA dividida por ";" — comentário com ponto e vírgula
# quebrava a divisão por texto (07/10/26, mesma armadilha do
# scripts/materializar_typeform.py).
_DDL_COMANDOS = [
    f"""
CREATE TABLE IF NOT EXISTS {TABELA} (
    contact_id        text        NOT NULL,
    lancamento_codigo text        NOT NULL,
    trilha            text        NOT NULL DEFAULT '',
    email             text        NOT NULL DEFAULT '',
    utm_source        text        NOT NULL DEFAULT '',
    utm_medium        text        NOT NULL DEFAULT '',
    utm_campaign      text        NOT NULL DEFAULT '',
    utm_content       text        NOT NULL DEFAULT '',
    utm_term          text        NOT NULL DEFAULT '',
    gclid             text,
    fbclid            text,
    ttclid            text,
    vk_source         text,
    vk_ad_id          text,
    -- Quando ESTE sistema viu a combinação pela primeira e pela última vez.
    -- Não é a data do cadastro no AC (o AC não guarda isso por lançamento).
    primeiro_visto_em timestamptz NOT NULL DEFAULT now(),
    ultimo_visto_em   timestamptz NOT NULL DEFAULT now(),
    -- etl_ac = capturado na passada horária, seed_leads = semeado da `leads`
    -- em 07/10/26, export_ac / backup = remontado de arquivo da época.
    origem            text        NOT NULL DEFAULT 'etl_ac',
    PRIMARY KEY (contact_id, lancamento_codigo, trilha)
)
""",
    f"CREATE INDEX IF NOT EXISTS idx_{TABELA}_lanc  ON {TABELA} (lancamento_codigo)",
    f"CREATE INDEX IF NOT EXISTS idx_{TABELA}_email ON {TABELA} (email)",
    # O vigia do ETL (frontend/services/vigia_etl.py) lê max(ultimo_visto_em)
    # a cada 15 min; sem índice é varredura de 1,9 mi de linhas.
    f"CREATE INDEX IF NOT EXISTS idx_{TABELA}_visto ON {TABELA} (ultimo_visto_em)",
]
# Só para o etl/schema.sql — o código executa _DDL_COMANDOS um a um.
DDL = ";\n\n".join(c.strip() for c in _DDL_COMANDOS)


_MARCAS_BASE_FORTE = ("base forte", "base-forte")  # espelha src/nomenclatura.py
_UTM = ("utm_source", "utm_medium", "utm_campaign", "utm_content", "utm_term")
_IDS = ("gclid", "fbclid", "ttclid", "vk_source", "vk_ad_id")


def criar_tabela(engine) -> None:
    with engine.begin() as conn:
        for comando in _DDL_COMANDOS:
            conn.execute(text(comando))


def _txt(v: Any) -> str:
    if v is None:
        return ""
    s = str(v).strip()
    return "" if s.lower() in ("nan", "none") else s


def trilha_de(lancamento_codigo: str, utm_campaign: str) -> str:
    """'' fora da Black; na Black, a trilha pelo nome da campanha."""
    if not str(lancamento_codigo or "").upper().startswith("BV-"):
        return ""
    camp = _txt(utm_campaign).lower()
    return TRILHA_BASE_FORTE if any(m in camp for m in _MARCAS_BASE_FORTE) else TRILHA_VITALICIA


def linhas_historico(registros: Iterable[dict], extrair_codigo,
                     agora: datetime | None = None,
                     origem: str = "etl_ac") -> list[dict]:
    """Converte os registros do ETL nas linhas do histórico.

    `extrair_codigo` é o `extract_launch_code` do ETL — passado de fora para o
    código do lançamento vir SEMPRE da própria `utm_campaign`. Registro cuja UTM
    não nomeia lançamento nenhum não entra. Duplicata da mesma chave no mesmo
    lote fica com a ÚLTIMA (o Postgres recusa duas linhas da mesma chave num só
    INSERT ... ON CONFLICT DO UPDATE).
    """
    agora = agora or datetime.now(timezone.utc)
    por_chave: dict[tuple[str, str, str], dict] = {}
    for r in registros:
        contato = _txt(r.get("id"))
        campanha = _txt(r.get("utm_campaign"))
        codigo = extrair_codigo(campanha) if campanha else None
        if not contato or not codigo:
            continue
        trilha = trilha_de(codigo, campanha)
        linha = {
            "contact_id": contato,
            "lancamento_codigo": codigo,
            "trilha": trilha,
            "email": _txt(r.get("email")).lower(),
            **{c: _txt(r.get(c)) for c in _UTM},
            **{c: (_txt(r.get(c)) or None) for c in _IDS},
            "visto_em": agora,
            "origem": origem,
        }
        por_chave[(contato, codigo, trilha)] = linha
    return list(por_chave.values())


_UPSERT = text(f"""
    INSERT INTO {TABELA} (
        contact_id, lancamento_codigo, trilha, email,
        utm_source, utm_medium, utm_campaign, utm_content, utm_term,
        gclid, fbclid, ttclid, vk_source, vk_ad_id,
        primeiro_visto_em, ultimo_visto_em, origem)
    VALUES (
        :contact_id, :lancamento_codigo, :trilha, :email,
        :utm_source, :utm_medium, :utm_campaign, :utm_content, :utm_term,
        :gclid, :fbclid, :ttclid, :vk_source, :vk_ad_id,
        :visto_em, :visto_em, :origem)
    ON CONFLICT (contact_id, lancamento_codigo, trilha) DO UPDATE SET
        email           = EXCLUDED.email,
        utm_source      = EXCLUDED.utm_source,
        utm_medium      = EXCLUDED.utm_medium,
        utm_campaign    = EXCLUDED.utm_campaign,
        utm_content     = EXCLUDED.utm_content,
        utm_term        = EXCLUDED.utm_term,
        gclid           = COALESCE(EXCLUDED.gclid,     {TABELA}.gclid),
        fbclid          = COALESCE(EXCLUDED.fbclid,    {TABELA}.fbclid),
        ttclid          = COALESCE(EXCLUDED.ttclid,    {TABELA}.ttclid),
        vk_source       = COALESCE(EXCLUDED.vk_source, {TABELA}.vk_source),
        vk_ad_id        = COALESCE(EXCLUDED.vk_ad_id,  {TABELA}.vk_ad_id),
        ultimo_visto_em = EXCLUDED.ultimo_visto_em,
        origem          = EXCLUDED.origem
""")


def gravar_historico(engine, linhas: list[dict], lote: int = 1000) -> int:
    """Upsert "a última vence" dentro da mesma (contato, lançamento, trilha).

    Lançamento diferente é chave diferente: a linha antiga não é tocada.
    """
    if not linhas:
        return 0
    criar_tabela(engine)
    with engine.begin() as conn:
        for i in range(0, len(linhas), lote):
            conn.execute(_UPSERT, linhas[i:i + lote])
    logger.info("%s: %d linhas (contato × lançamento) gravadas.", TABELA, len(linhas))
    return len(linhas)


# `:bf` e `:bv` entram como parâmetro para o texto acentuado não ficar
# embutido no SQL.
_SEMEAR = text(f"""
    INSERT INTO {TABELA} (
        contact_id, lancamento_codigo, trilha, email,
        utm_source, utm_medium, utm_campaign, utm_content, utm_term,
        gclid, fbclid, ttclid, vk_source, vk_ad_id,
        primeiro_visto_em, ultimo_visto_em, origem)
    SELECT
        id::text, lancamento_codigo,
        CASE WHEN lancamento_codigo LIKE 'BV-%%' THEN
             CASE WHEN lower(utm_campaign) LIKE '%%base forte%%'
                    OR lower(utm_campaign) LIKE '%%base-forte%%'
                  THEN :bf ELSE :bv END
             ELSE '' END,
        lower(trim(coalesce(email, ''))),
        coalesce(utm_source, ''), coalesce(utm_medium, ''), coalesce(utm_campaign, ''),
        coalesce(utm_content, ''), coalesce(utm_term, ''),
        nullif(gclid, ''), nullif(fbclid, ''), nullif(ttclid, ''),
        nullif(vk_source, ''), nullif(vk_ad_id, ''),
        coalesce(updated_at, now()), coalesce(updated_at, now()), 'seed_leads'
    FROM leads
    WHERE lancamento_codigo = :codigo
      AND upper(coalesce(utm_campaign, '')) LIKE '%%' || :codigo || '%%'
    ON CONFLICT (contact_id, lancamento_codigo, trilha) DO NOTHING
""")


def semear_da_leads(engine, codigos: list[str] | None = None) -> dict[str, int]:
    """Copia para o histórico o estado ATUAL da `leads`, lançamento a lançamento.

    Roda no servidor (INSERT ... SELECT): não traz linha nenhuma pro Python.
    `DO NOTHING` porque o que a passada horária já capturou é tão bom ou melhor.
    Re-rodar é seguro e é o jeito de cobrir o intervalo até o deploy.
    """
    criar_tabela(engine)
    if codigos is None:
        with engine.connect() as conn:
            codigos = [r[0] for r in conn.execute(text(
                "SELECT DISTINCT lancamento_codigo FROM leads "
                "WHERE lancamento_codigo IS NOT NULL")).fetchall()]
    resultado: dict[str, int] = {}
    for codigo in sorted(codigos):
        with engine.begin() as conn:
            conn.execute(text("SET LOCAL statement_timeout = '600s'"))
            r = conn.execute(_SEMEAR, {"codigo": codigo,
                                       "bf": TRILHA_BASE_FORTE, "bv": TRILHA_VITALICIA})
            resultado[codigo] = r.rowcount or 0
        logger.info("%s: semeado %s -> %d linhas novas", TABELA, codigo, resultado[codigo])
    return resultado
