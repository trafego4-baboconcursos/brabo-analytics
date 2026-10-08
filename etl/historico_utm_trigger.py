"""
etl/historico_utm_trigger.py — o trigger que guarda a UTM antiga quando a leads a troca.

POR QUE UM TRIGGER. A `leads` espelha o Active Campaign: uma linha por contato, e
o AC guarda UM valor de UTM. Quando o contato se cadastra de novo, quem grava na
`leads` (nosso ETL, o upsert em tempo real do Mateus, qualquer um futuro)
sobrescreve a UTM. O trigger roda DENTRO do banco, na mesma gravação: zero
requisição a mais, em tempo real, e pega todo escritor sem ninguém mudar código.

DUAS TABELAS (estado atual + histórico das versões substituídas):
  - `lead_utm_lancamento` (já existe): UMA linha por (contato, lançamento, trilha),
    a UTM ATUAL. É o que as páginas leem. "Mesmo lançamento → a última vence."
  - `lead_utm_historico` (nova): só as UTMs que foram SUBSTITUÍDAS. Dentro do mesmo
    lançamento a UTM quase não muda (11 a 57 contatos por lançamento, <0,1%), então
    é uma tabela pequena. Uma cópia completa de todo toque seria 99,9% repetida num
    banco já com 8,9 GB.
  Lançamento diferente é OUTRA chave no estado: a linha do lançamento antigo nunca é
  tocada. Primeiro toque = o histórico mais antigo, ou o próprio estado se não houve troca.

SEGURANÇA — o trigger não pode derrubar a gravação da `leads`:
  - `EXCEPTION WHEN OTHERS` engole o erro e vira WARNING: se o histórico falhar, a
    `leads` grava do mesmo jeito (o histórico é que perde, nunca a `leads`);
  - `SECURITY DEFINER`: roda como dono da função, então um escritor sem permissão nas
    tabelas novas não faz o trigger falhar em silêncio;
  - dispara por COMANDO (não por linha), com tabelas de transição: uma inserção em
    lote por comando, não uma por contato.
  - só age quando o contato é novo ou a UTM mudou.

SÓ ENTRA UTM QUE NOMEIA UM LANÇAMENTO. `link_bio`, `{{campaign.name}}` e orgânico
nunca viram linha nem sobrescrevem uma UTM boa. A regra do código do lançamento existe
em Python (`etl_active_campaign.extract_launch_code`) e aqui em SQL; o teste
`tests/test_trigger_utm.py` compara as duas sobre nomes reais de campanha.

Os nomes das tabelas e funções são parâmetros: o teste monta tudo com prefixo `zz_`
dentro de uma transação desfeita no fim, sem tocar nas tabelas reais.
"""
from __future__ import annotations

from dataclasses import dataclass

CAMPOS_UTM = ("utm_source", "utm_medium", "utm_campaign", "utm_content", "utm_term")
CAMPOS_ID = ("gclid", "fbclid", "ttclid", "vk_source", "vk_ad_id")

# Regex do código do lançamento em SQL: `\y` é a borda de palavra do Postgres
# (o `\b` do Python). Espelha etl_active_campaign.extract_launch_code.
REGEX_CODIGO = r"\y(?:(?:PBB|PES|PI)-\w{3}|BV)-\d{2}\y"


@dataclass(frozen=True)
class Nomes:
    leads: str = "leads"
    estado: str = "lead_utm_lancamento"
    historico: str = "lead_utm_historico"
    hash_fn: str = "fn_utm_hash"
    fn_ins: str = "fn_lead_utm_ins"
    fn_upd: str = "fn_lead_utm_upd"
    trg_ins: str = "trg_lead_utm_ins"
    trg_upd: str = "trg_lead_utm_upd"

    @classmethod
    def teste(cls) -> "Nomes":
        """Prefixo zz_ em tudo: o teste roda numa transação desfeita no fim."""
        return cls(leads="zz_leads", estado="zz_estado", historico="zz_historico",
                   hash_fn="zz_utm_hash", fn_ins="zz_fn_ins", fn_upd="zz_fn_upd",
                   trg_ins="zz_trg_ins", trg_upd="zz_trg_upd")


def ddl_tabelas(n: Nomes) -> list[str]:
    """Lista de comandos — nunca dividida por ';' (comentário com ';' já quebrou isso)."""
    cols_id = ",\n        ".join(f"{c} text" for c in CAMPOS_ID)
    return [
        # Quando a UTM ATUAL do estado passou a valer. O estado já existente não tem
        # essa coluna; sem default, é só metadado (não reescreve 1,9 mi de linhas).
        f"ALTER TABLE {n.estado} ADD COLUMN IF NOT EXISTS utm_desde timestamptz",
        f"""CREATE TABLE IF NOT EXISTS {n.historico} (
        contact_id        text        NOT NULL,
        lancamento_codigo text        NOT NULL,
        trilha            text        NOT NULL DEFAULT '',
        utm_hash          text        NOT NULL,
        email             text        NOT NULL DEFAULT '',
        utm_source        text        NOT NULL DEFAULT '',
        utm_medium        text        NOT NULL DEFAULT '',
        utm_campaign      text        NOT NULL DEFAULT '',
        utm_content       text        NOT NULL DEFAULT '',
        utm_term          text        NOT NULL DEFAULT '',
        {cols_id},
        visto_desde       timestamptz,
        substituida_em    timestamptz,
        origem            text        NOT NULL DEFAULT 'trigger',
        PRIMARY KEY (contact_id, lancamento_codigo, trilha, utm_hash)
    )""",
        f"CREATE INDEX IF NOT EXISTS idx_{n.historico}_lanc  ON {n.historico} (lancamento_codigo)",
        f"CREATE INDEX IF NOT EXISTS idx_{n.historico}_email ON {n.historico} (email)",
    ]


def ddl_hash(n: Nomes) -> str:
    """A ÚNICA definição de "é a mesma UTM". Maiúscula/minúscula e espaço nas pontas
    não criam UTM nova. Backfill e trigger usam esta mesma função."""
    return f"""CREATE OR REPLACE FUNCTION public.{n.hash_fn}(s text, m text, c text, ct text, t text)
RETURNS text LANGUAGE sql IMMUTABLE PARALLEL SAFE AS $f$
  SELECT md5(lower(concat_ws('|', btrim(coalesce(s, '')), btrim(coalesce(m, '')),
                                  btrim(coalesce(c, '')), btrim(coalesce(ct, '')), btrim(coalesce(t, '')))))
$f$"""


def _comando(n: Nomes, fonte: str) -> str:
    """O comando único que o trigger executa. `fonte` é de onde vêm as linhas:
    todas as novas (INSERT) ou só as que mudaram de UTM (UPDATE)."""
    h = f"public.{n.hash_fn}"
    sel_estado = ",\n         ".join(f"e.{c}" for c in (*CAMPOS_UTM, *CAMPOS_ID))
    sel_toque = ",\n       ".join(f"t.{c}" for c in (*CAMPOS_UTM, *CAMPOS_ID))
    ins_cols = ", ".join(("contact_id", "lancamento_codigo", "trilha", "email",
                          *CAMPOS_UTM, *CAMPOS_ID))
    sets_id = ",\n      ".join(f"{c} = COALESCE(EXCLUDED.{c}, {n.estado}.{c})" for c in CAMPOS_ID)
    sets_utm = ",\n      ".join(f"{c} = EXCLUDED.{c}" for c in CAMPOS_UTM)
    return f"""WITH base AS (
  SELECT n.id AS contact_id, n.email, n.utm_source, n.utm_medium, n.utm_campaign,
         n.utm_content, n.utm_term, n.gclid, n.fbclid, n.ttclid, n.vk_source, n.vk_ad_id,
         upper((regexp_match(n.utm_campaign, '{REGEX_CODIGO}', 'i'))[1]) AS codigo
  {fonte}
),
toque AS (
  SELECT b.contact_id, b.codigo, lower(btrim(coalesce(b.email, ''))) AS email_n,
         coalesce(b.utm_source, '') AS utm_source, coalesce(b.utm_medium, '') AS utm_medium,
         coalesce(b.utm_campaign, '') AS utm_campaign, coalesce(b.utm_content, '') AS utm_content,
         coalesce(b.utm_term, '') AS utm_term,
         nullif(b.gclid, '') AS gclid, nullif(b.fbclid, '') AS fbclid, nullif(b.ttclid, '') AS ttclid,
         nullif(b.vk_source, '') AS vk_source, nullif(b.vk_ad_id, '') AS vk_ad_id,
         CASE WHEN left(b.codigo, 3) = 'BV-' THEN
                CASE WHEN strpos(lower(coalesce(b.utm_campaign, '')), 'base forte') > 0
                       OR strpos(lower(coalesce(b.utm_campaign, '')), 'base-forte') > 0
                     THEN 'Base Forte' ELSE 'Black Vitalícia' END
              ELSE '' END AS trilha,
         {h}(b.utm_source, b.utm_medium, b.utm_campaign, b.utm_content, b.utm_term) AS utm_hash
  FROM base b
  WHERE b.codigo IS NOT NULL
),
antes AS (
  SELECT e.contact_id, e.lancamento_codigo, e.trilha, e.email,
         {sel_estado},
         {h}(e.utm_source, e.utm_medium, e.utm_campaign, e.utm_content, e.utm_term) AS utm_hash,
         coalesce(e.utm_desde, e.primeiro_visto_em) AS visto_desde
  FROM {n.estado} e
  JOIN toque t ON t.contact_id = e.contact_id AND t.codigo = e.lancamento_codigo AND t.trilha = e.trilha
  WHERE {h}(e.utm_source, e.utm_medium, e.utm_campaign, e.utm_content, e.utm_term) <> t.utm_hash
),
guarda AS (
  INSERT INTO {n.historico} (contact_id, lancamento_codigo, trilha, utm_hash, email,
                             {", ".join(CAMPOS_UTM)}, {", ".join(CAMPOS_ID)},
                             visto_desde, substituida_em, origem)
  SELECT a.contact_id, a.lancamento_codigo, a.trilha, a.utm_hash, a.email,
         {", ".join("a." + c for c in (*CAMPOS_UTM, *CAMPOS_ID))},
         a.visto_desde, now(), 'trigger'
  FROM antes a
  ON CONFLICT (contact_id, lancamento_codigo, trilha, utm_hash)
  DO UPDATE SET substituida_em = EXCLUDED.substituida_em
)
INSERT INTO {n.estado} ({ins_cols}, primeiro_visto_em, ultimo_visto_em, utm_desde, origem)
SELECT t.contact_id, t.codigo, t.trilha, t.email_n,
       {sel_toque},
       now(), now(), now(), 'trigger'
FROM toque t
ON CONFLICT (contact_id, lancamento_codigo, trilha) DO UPDATE SET
      email = EXCLUDED.email,
      {sets_utm},
      {sets_id},
      utm_desde = CASE WHEN {h}({n.estado}.utm_source, {n.estado}.utm_medium, {n.estado}.utm_campaign,
                               {n.estado}.utm_content, {n.estado}.utm_term)
                            <> {h}(EXCLUDED.utm_source, EXCLUDED.utm_medium, EXCLUDED.utm_campaign,
                                   EXCLUDED.utm_content, EXCLUDED.utm_term)
                       THEN now() ELSE {n.estado}.utm_desde END,
      ultimo_visto_em = now(),
      origem = 'trigger'"""


def _funcao(n: Nomes, nome: str, fonte: str) -> str:
    return f"""CREATE OR REPLACE FUNCTION public.{nome}() RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $fn$
BEGIN
  {_comando(n, fonte)};
  RETURN NULL;
EXCEPTION WHEN OTHERS THEN
  -- O histórico é que perde; a gravação na leads NUNCA pode falhar por causa dele.
  RAISE WARNING 'lead_utm: falha ao registrar o histórico (%): %', SQLSTATE, SQLERRM;
  RETURN NULL;
END
$fn$"""


def ddl_funcoes(n: Nomes) -> list[str]:
    fonte_ins = "FROM novas n"
    fonte_upd = f"""FROM novas n
  JOIN antigas o ON o.id = n.id
  WHERE (o.utm_source, o.utm_medium, o.utm_campaign, o.utm_content, o.utm_term)
        IS DISTINCT FROM (n.utm_source, n.utm_medium, n.utm_campaign, n.utm_content, n.utm_term)"""
    return [_funcao(n, n.fn_ins, fonte_ins), _funcao(n, n.fn_upd, fonte_upd)]


def ddl_triggers(n: Nomes) -> list[str]:
    return [
        f"""CREATE TRIGGER {n.trg_ins} AFTER INSERT ON public.{n.leads}
REFERENCING NEW TABLE AS novas
FOR EACH STATEMENT EXECUTE FUNCTION public.{n.fn_ins}()""",
        f"""CREATE TRIGGER {n.trg_upd} AFTER UPDATE ON public.{n.leads}
REFERENCING OLD TABLE AS antigas NEW TABLE AS novas
FOR EACH STATEMENT EXECUTE FUNCTION public.{n.fn_upd}()""",
    ]


def ddl_completo(n: Nomes) -> list[str]:
    """Tudo, na ordem: tabelas, função de hash, funções do trigger, triggers."""
    return [*ddl_tabelas(n), ddl_hash(n), *ddl_funcoes(n), *ddl_triggers(n)]


def ddl_remover(n: Nomes) -> list[str]:
    """Desfaz o trigger (as tabelas ficam). É o botão de emergência."""
    return [
        f"DROP TRIGGER IF EXISTS {n.trg_upd} ON public.{n.leads}",
        f"DROP TRIGGER IF EXISTS {n.trg_ins} ON public.{n.leads}",
    ]
