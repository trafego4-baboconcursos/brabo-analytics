"""ETL de públicos em uso — Facebook (Meta) e Google (YouTube) → banco analytics. Alimenta a página /publicos.

Lê das plataformas (só leitura), reaproveitando `scripts/ads` (a mesma leitura da conferência SEG-4):
  - `publicos_snapshot`        cada público usado: tipo, tamanho, status, retenção, última atualização
  - `publicos_uso`             lançamento → campanha → conjunto/grupo → público, inclui/exclui
  - `publicos_tamanho_diario`  um tamanho por público por dia

Os alertas (SEG-4, lista pequena, lista velha) NÃO são gravados: o reader os calcula a partir destas tabelas, para uma
mudança de regra valer sem recoletar.

Uso:
    python etl/etl_publicos.py --ativos                  # o que o scheduler roda (pula coleta com < 6 h)
    python etl/etl_publicos.py --launch PES-NOV-26
    python etl/etl_publicos.py --launch PES-NOV-26 --dry-run   # lê e relata, não grava
"""
from __future__ import annotations

import argparse
import hashlib
import re
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import text

_RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_RAIZ / "src"))
sys.path.insert(0, str(_RAIZ / "etl"))
sys.path.insert(0, str(_RAIZ))
from db import get_engine  # noqa: E402
from logger import get_logger  # noqa: E402

load_dotenv(_RAIZ / ".env")
logger = get_logger("etl.publicos")

# Só coleta de novo um lançamento cuja última coleta tenha mais que isto (o scheduler passa de hora em hora).
HORAS_ENTRE_COLETAS = 6
# Lançamento "ativo" para este ETL: já criou campanha (começa em até N dias) e ainda não acabou há mais de N dias.
DIAS_ANTES_DO_INICIO = 14
DIAS_APOS_FIM = 3

CAMPOS_PUBLICO_META = ("id,name,subtype,account_id,approximate_count_lower_bound,approximate_count_upper_bound,"
                       "delivery_status,operation_status,retention_days,time_content_updated")

DDL = """
CREATE TABLE IF NOT EXISTS publicos_snapshot (
    plataforma TEXT NOT NULL, conta TEXT NOT NULL DEFAULT '', publico_id TEXT NOT NULL, nome TEXT, tipo TEXT,
    conta_dona TEXT, tamanho_inferior BIGINT, tamanho_superior BIGINT, tamanho_display BIGINT, tamanho_busca BIGINT,
    tamanho_efetivo BIGINT, status TEXT, status_detalhe TEXT, elegivel BOOLEAN, retencao_dias INTEGER,
    match_rate NUMERIC(6,2), atualizado_em TIMESTAMPTZ, coletado_em TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (plataforma, conta, publico_id));
CREATE TABLE IF NOT EXISTS publicos_uso (
    lancamento_codigo TEXT NOT NULL, plataforma TEXT NOT NULL, conta TEXT NOT NULL, campanha_id TEXT NOT NULL,
    campanha_nome TEXT, campanha_status TEXT, grupo_id TEXT NOT NULL, grupo_nome TEXT, grupo_status TEXT,
    publico_id TEXT NOT NULL, publico_nome TEXT, publico_tipo TEXT, papel TEXT NOT NULL,
    coletado_em TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (lancamento_codigo, plataforma, grupo_id, publico_id, papel));
CREATE INDEX IF NOT EXISTS idx_publicos_uso_publico ON publicos_uso (plataforma, publico_id);
CREATE TABLE IF NOT EXISTS publicos_tamanho_diario (
    plataforma TEXT NOT NULL, conta TEXT NOT NULL DEFAULT '', publico_id TEXT NOT NULL, data DATE NOT NULL,
    tamanho BIGINT, PRIMARY KEY (plataforma, conta, publico_id, data));
"""


# ---------------------------------------------------------------------------- funções puras (testadas)
def _int(v) -> int | None:
    try:
        return int(v) if v is not None and v != "" else None
    except (TypeError, ValueError):
        return None


def _data(v) -> datetime | None:
    """Meta devolve epoch (segundos) ou ISO; Google, nada aqui."""
    if v in (None, "", 0):
        return None
    try:
        if isinstance(v, (int, float)) or str(v).isdigit():
            return datetime.fromtimestamp(int(v), tz=timezone.utc)
        return datetime.fromisoformat(str(v).replace("Z", "+00:00"))
    except (ValueError, OSError):
        return None


def tipo_uso_meta(subtype: str | None, nome: str = "") -> str:
    """Rótulo curto do público para a tela (a coluna `tipo` do snapshot guarda o subtype cru)."""
    s = (subtype or "").upper()
    if s == "LOOKALIKE":
        return "SEMELHANTE"
    if s == "WEBSITE":
        return "SITE"
    if s in ("ENGAGEMENT", "VIDEO", "IG_BUSINESS", "FACEBOOK_PAGE", "ON_SITE_LEAD"):
        return "ENGAJAMENTO"
    if s in ("CUSTOM", "CRM", "DATA_SET", "OFFLINE_CONVERSION"):
        return "LISTA"
    if not s and "semelhante" in nome.lower():
        return "SEMELHANTE"
    return "OUTRO"


def tipo_uso_google(tipo: str | None) -> str:
    t = (tipo or "").upper()
    return {"CRM_BASED": "LISTA", "RULE_BASED": "SITE", "LOGICAL": "COMBINADO", "SIMILAR": "SEMELHANTE",
            "LOOKALIKE": "SEMELHANTE"}.get(t, "OUTRO")


def normalizar_publico_meta(raw: dict) -> dict:
    """`approximate_count_*`: o Meta devolve -1 quando não sabe, e faixa a partir de 1.000 (não distingue 0 de 300)."""
    inf, sup = _int(raw.get("approximate_count_lower_bound")), _int(raw.get("approximate_count_upper_bound"))
    inf = inf if inf is not None and inf >= 0 else None
    sup = sup if sup is not None and sup >= 0 else None
    ds = raw.get("delivery_status") or {}
    op = raw.get("operation_status") or {}
    return {
        "plataforma": "meta", "conta": "", "publico_id": str(raw["id"]), "nome": raw.get("name"),
        "tipo": raw.get("subtype"), "conta_dona": str(raw["account_id"]) if raw.get("account_id") else None,
        "tamanho_inferior": inf, "tamanho_superior": sup, "tamanho_display": None, "tamanho_busca": None,
        "tamanho_efetivo": inf,
        "status": ds.get("code") if isinstance(ds, dict) else None,
        "status_detalhe": (op.get("description") or str(op.get("code") or "")) if isinstance(op, dict) else None,
        "elegivel": None, "retencao_dias": _int(raw.get("retention_days")), "match_rate": None,
        "atualizado_em": _data(raw.get("time_content_updated")),
    }


def normalizar_lista_google(raw: dict, conta: str) -> dict:
    """`raw`: o objeto `userList` da resposta da GAQL (camelCase)."""
    disp, busca = _int(raw.get("sizeForDisplay")), _int(raw.get("sizeForSearch"))
    el_d, el_s = raw.get("eligibleForDisplay"), raw.get("eligibleForSearch")
    elegivel = None if el_d is None and el_s is None else bool(el_d or el_s)
    detalhe = ", ".join(f"{k}={'sim' if v else 'não'}" for k, v in (("display", el_d), ("busca", el_s)) if v is not None)
    mr = raw.get("matchRatePercentage")
    return {
        "plataforma": "google", "conta": conta, "publico_id": str(raw["id"]), "nome": raw.get("name"),
        "tipo": raw.get("type"), "conta_dona": conta, "tamanho_inferior": None, "tamanho_superior": None,
        "tamanho_display": disp, "tamanho_busca": busca,
        "tamanho_efetivo": max(disp or 0, busca or 0) if (disp is not None or busca is not None) else None,
        "status": raw.get("membershipStatus"), "status_detalhe": detalhe or None, "elegivel": elegivel,
        "retencao_dias": _int(raw.get("membershipLifeSpan")), "match_rate": float(mr) if mr not in (None, "") else None,
        "atualizado_em": None,
    }


def id_segmento_google(nome: str) -> str:
    """Segmento personalizado/interesse chega sem ID legível pelo caminho de leitura da conferência: ID estável pelo nome."""
    return "seg:" + hashlib.md5(nome.encode("utf-8")).hexdigest()[:12]


def _linha_uso(base: dict, publico_id: str, nome: str, tipo: str, papel: str) -> dict:
    return {**base, "publico_id": str(publico_id), "publico_nome": nome, "publico_tipo": tipo, "papel": papel}


def _sem_publico(base: dict) -> dict:
    """Conjunto/grupo sem nenhum público: sem esta linha ele sumiria da tela, e é justamente o que merece alerta."""
    return _linha_uso(base, "-", "(sem público)", "OUTRO", "nenhum")


def usos_adset_meta(base_campanha: dict, adset: dict, publicos: dict[str, dict]) -> list[dict]:
    """Uma linha por público/interesse do conjunto. `publicos`: {id: snapshot normalizado}, para tipo e nome."""
    t = adset.get("targeting") or {}
    base = {**base_campanha, "grupo_id": str(adset["id"]), "grupo_nome": adset.get("name"),
            "grupo_status": adset.get("effective_status") or adset.get("status")}
    out = []
    for campo, papel in (("custom_audiences", "inclui"), ("excluded_custom_audiences", "exclui")):
        for a in t.get(campo) or []:
            snap = publicos.get(str(a["id"])) or {}
            nome = a.get("name") or snap.get("nome") or str(a["id"])
            out.append(_linha_uso(base, a["id"], nome, tipo_uso_meta(snap.get("tipo"), nome), papel))
    exc = t.get("exclusions") or {}
    for blocos, papel in ((t.get("flexible_spec") or [], "inclui"), ([exc] if exc else [], "exclui")):
        for b in blocos:
            for v in b.values():
                for x in (v if isinstance(v, list) else []):
                    if isinstance(x, dict) and x.get("id"):
                        out.append(_linha_uso(base, x["id"], x.get("name") or str(x["id"]), "INTERESSE", papel))
    return out or [_sem_publico(base)]


def usos_grupo_google(base_campanha: dict, grupo: dict, listas: dict[str, dict]) -> list[dict]:
    """`grupo`: item de `scripts.ads.publicos.publicos_grupos_google` (com `id`). `listas`: {id: snapshot normalizado}."""
    base = {**base_campanha, "grupo_id": str(grupo["id"]), "grupo_nome": grupo.get("nome"),
            "grupo_status": grupo.get("status")}
    out = []
    for papel, campo in (("inclui", "incluidos"), ("exclui", "excluidos")):
        for pid, nome in (grupo.get(campo) or {}).items():
            out.append(_linha_uso(base, pid, nome or str(pid), tipo_uso_google((listas.get(str(pid)) or {}).get("tipo")),
                                  papel))
    for nome in grupo.get("segmentos") or []:
        tipo = "INTERESSE" if nome.startswith("Interesse:") else "SEGMENTO"
        out.append(_linha_uso(base, id_segmento_google(nome), nome, tipo, "inclui"))
    return out or [_sem_publico(base)]


# ---------------------------------------------------------------------------- leitura das plataformas
def _publicos_meta_por_id(m, ids: list[str]) -> dict[str, dict]:
    """Detalhe de cada público referenciado, em lotes (`?ids=`): pega também o compartilhado de outra conta."""
    out: dict[str, dict] = {}
    ids = sorted(set(ids))
    for i in range(0, len(ids), 50):
        r = m.get("", ids=",".join(ids[i:i + 50]), fields=CAMPOS_PUBLICO_META)
        for pid, raw in r.items():
            if isinstance(raw, dict) and raw.get("id"):
                out[str(pid)] = normalizar_publico_meta(raw)
    return out


def coletar_meta(lancamento: str) -> tuple[list[dict], list[dict]]:
    """(usos, snapshots) do Facebook (Meta) para o lançamento, em todas as contas de campanha."""
    from scripts.ads.conferir import CONTAS_META
    from scripts.ads.meta import Meta

    m = Meta()
    usos: list[dict] = []
    adsets_por_campanha: list[tuple[dict, dict]] = []
    ids_publicos: list[str] = []
    for conta in CONTAS_META:
        for c in m.campanhas(conta, lancamento):
            if c.get("effective_status") in ("DELETED", "ARCHIVED"):
                continue
            base = {"lancamento_codigo": lancamento, "plataforma": "meta", "conta": conta, "campanha_id": str(c["id"]),
                    "campanha_nome": c.get("name"), "campanha_status": c.get("effective_status")}
            for s in m.adsets(c["id"]):
                if s.get("effective_status") in ("DELETED", "ARCHIVED"):
                    continue
                adsets_por_campanha.append((base, s))
                t = s.get("targeting") or {}
                ids_publicos += [str(a["id"]) for k in ("custom_audiences", "excluded_custom_audiences")
                                 for a in t.get(k) or []]
    snaps = _publicos_meta_por_id(m, ids_publicos) if ids_publicos else {}
    for base, s in adsets_por_campanha:
        usos += usos_adset_meta(base, s, snaps)
    usadas = {u["publico_id"] for u in usos if u["papel"] != "nenhum"}
    return usos, [v for k, v in snaps.items() if k in usadas]


def _listas_google_completas(g, conta: str) -> dict[str, dict]:
    r = g.buscar(conta, """SELECT user_list.id, user_list.name, user_list.type, user_list.membership_status,
        user_list.size_for_display, user_list.size_for_search, user_list.membership_life_span,
        user_list.eligible_for_display, user_list.eligible_for_search, user_list.match_rate_percentage
        FROM user_list""")
    return {str(x["userList"]["id"]): normalizar_lista_google(x["userList"], conta) for x in r}


def coletar_google(lancamento: str) -> tuple[list[dict], list[dict]]:
    from scripts.ads import padroes as P
    from scripts.ads.google import Google
    from scripts.ads.publicos import publicos_grupos_google

    g = Google()
    usos: list[dict] = []
    snaps: dict[tuple[str, str], dict] = {}
    for conta in P.GOOGLE_CONTAS.values():
        campanhas = [c for c in g.campanhas(conta, lancamento) if c.get("status") in ("ENABLED", "PAUSED")]
        if not campanhas:
            continue
        listas = _listas_google_completas(g, conta)
        for c in campanhas:
            base = {"lancamento_codigo": lancamento, "plataforma": "google", "conta": conta,
                    "campanha_id": str(c["id"]), "campanha_nome": c.get("name"), "campanha_status": c.get("status")}
            for gr in publicos_grupos_google(g, conta, c["id"], todos=True):
                if gr.get("status") == "REMOVED":
                    continue
                for u in usos_grupo_google(base, gr, listas):
                    usos.append(u)
                    if u["papel"] != "nenhum" and not u["publico_id"].startswith("seg:") and u["publico_id"] in listas:
                        snaps[(conta, u["publico_id"])] = listas[u["publico_id"]]
    return usos, list(snaps.values())


# ---------------------------------------------------------------------------- banco
def garantir_tabelas(conn) -> None:
    for stmt in [s.strip() for s in DDL.split(";") if s.strip()]:
        conn.execute(text(stmt))


def gravar(lancamento: str, plataforma: str, usos: list[dict], snaps: list[dict]) -> None:
    """Troca os usos da (lançamento, plataforma) e atualiza snapshot + tamanho do dia numa transação só.
    Só chega aqui com a coleta inteira em memória: falha de API antes disso não apaga o que já estava gravado."""
    hoje = datetime.now(timezone(timedelta(hours=-3))).date()
    with get_engine().begin() as conn:
        garantir_tabelas(conn)
        conn.execute(text("DELETE FROM publicos_uso WHERE lancamento_codigo = :l AND plataforma = :p"),
                     {"l": lancamento, "p": plataforma})
        if usos:
            conn.execute(text("""INSERT INTO publicos_uso (lancamento_codigo, plataforma, conta, campanha_id,
                campanha_nome, campanha_status, grupo_id, grupo_nome, grupo_status, publico_id, publico_nome,
                publico_tipo, papel) VALUES (:lancamento_codigo, :plataforma, :conta, :campanha_id, :campanha_nome,
                :campanha_status, :grupo_id, :grupo_nome, :grupo_status, :publico_id, :publico_nome, :publico_tipo,
                :papel) ON CONFLICT DO NOTHING"""), usos)
        if snaps:
            conn.execute(text("""INSERT INTO publicos_snapshot (plataforma, conta, publico_id, nome, tipo, conta_dona,
                tamanho_inferior, tamanho_superior, tamanho_display, tamanho_busca, tamanho_efetivo, status,
                status_detalhe, elegivel, retencao_dias, match_rate, atualizado_em, coletado_em)
                VALUES (:plataforma, :conta, :publico_id, :nome, :tipo, :conta_dona, :tamanho_inferior,
                :tamanho_superior, :tamanho_display, :tamanho_busca, :tamanho_efetivo, :status, :status_detalhe,
                :elegivel, :retencao_dias, :match_rate, :atualizado_em, NOW())
                ON CONFLICT (plataforma, conta, publico_id) DO UPDATE SET nome = EXCLUDED.nome, tipo = EXCLUDED.tipo,
                conta_dona = EXCLUDED.conta_dona, tamanho_inferior = EXCLUDED.tamanho_inferior,
                tamanho_superior = EXCLUDED.tamanho_superior, tamanho_display = EXCLUDED.tamanho_display,
                tamanho_busca = EXCLUDED.tamanho_busca, tamanho_efetivo = EXCLUDED.tamanho_efetivo,
                status = EXCLUDED.status, status_detalhe = EXCLUDED.status_detalhe, elegivel = EXCLUDED.elegivel,
                retencao_dias = EXCLUDED.retencao_dias, match_rate = EXCLUDED.match_rate,
                atualizado_em = EXCLUDED.atualizado_em, coletado_em = NOW()"""), snaps)
            conn.execute(text("""INSERT INTO publicos_tamanho_diario (plataforma, conta, publico_id, data, tamanho)
                VALUES (:plataforma, :conta, :publico_id, :data, :tamanho)
                ON CONFLICT (plataforma, conta, publico_id, data) DO UPDATE SET tamanho = EXCLUDED.tamanho"""),
                         [{"plataforma": s["plataforma"], "conta": s["conta"], "publico_id": s["publico_id"],
                           "data": hoje, "tamanho": s["tamanho_efetivo"]} for s in snaps])


def coletado_recentemente(lancamento: str) -> bool:
    try:
        with get_engine().connect() as conn:
            r = conn.execute(text("""SELECT MAX(coletado_em) > NOW() - make_interval(hours => :h)
                FROM publicos_uso WHERE lancamento_codigo = :l"""), {"h": HORAS_ENTRE_COLETAS, "l": lancamento}).scalar()
        return bool(r)
    except Exception:  # tabela ainda não existe na primeira vez
        return False


def lancamentos_ativos(hoje: date | None = None) -> list[str]:
    hoje = hoje or date.today()
    with get_engine().connect() as conn:
        rows = conn.execute(text("""SELECT codigo FROM dim_lancamentos
            WHERE data_fim >= :ini AND data_inicio <= :fim ORDER BY data_inicio"""),
                            {"ini": hoje - timedelta(days=DIAS_APOS_FIM),
                             "fim": hoje + timedelta(days=DIAS_ANTES_DO_INICIO)}).fetchall()
    return [r[0] for r in rows if re.match(r"^(PBB|PES|PI)-[A-Z]{3}-\d{2}$", str(r[0] or ""), re.IGNORECASE)]


def resumo(lancamento: str, plataforma: str, usos: list[dict], snaps: list[dict]) -> str:
    pequenos = [s for s in snaps if s["tamanho_efetivo"] is not None and s["tamanho_efetivo"] < 500]
    sem_tam = [s for s in snaps if s["tamanho_efetivo"] is None]
    return (f"{lancamento} {plataforma}: {len({u['grupo_id'] for u in usos})} conjuntos/grupos, "
            f"{len([u for u in usos if u['papel'] != 'nenhum'])} usos, "
            f"{len(snaps)} públicos ({len(pequenos)} < 500, {len(sem_tam)} sem tamanho)")


def rodar(lancamento: str, dry_run: bool = False) -> bool:
    ok = True
    for plataforma, coletor in (("meta", coletar_meta), ("google", coletar_google)):
        try:
            usos, snaps = coletor(lancamento)
        except Exception as e:  # uma plataforma fora não pode apagar nem travar a outra
            logger.error("%s %s: coleta falhou: %s", lancamento, plataforma, e)
            ok = False
            continue
        logger.info(resumo(lancamento, plataforma, usos, snaps))
        if dry_run:
            for s in sorted(snaps, key=lambda x: (x["tamanho_efetivo"] is None, x["tamanho_efetivo"] or 0))[:8]:
                logger.info("   menor: %s | %s | %s | status=%s", s["publico_id"], s["nome"], s["tamanho_efetivo"],
                            s["status"])
        else:
            gravar(lancamento, plataforma, usos, snaps)
    return ok


def main() -> int:
    ap = argparse.ArgumentParser(description="ETL de públicos em uso (Meta + Google) → banco analytics")
    ap.add_argument("--launch", help="ex.: PES-NOV-26")
    ap.add_argument("--ativos", action="store_true", help="lançamentos ativos (modo do scheduler)")
    ap.add_argument("--dry-run", action="store_true", help="lê e relata, não grava")
    ap.add_argument("--forcar", action="store_true", help=f"ignora a trava de {HORAS_ENTRE_COLETAS} h do --ativos")
    a = ap.parse_args()
    if not (a.launch or a.ativos):
        ap.error("--launch ou --ativos")
    lancamentos = [a.launch.upper()] if a.launch else lancamentos_ativos()
    if not lancamentos:
        logger.info("Nenhum lançamento ativo para coletar públicos.")
        return 0
    falhas = []
    for l in lancamentos:
        if a.ativos and not a.forcar and not a.dry_run and coletado_recentemente(l):
            logger.info("%s: coletado há menos de %d h, pulando.", l, HORAS_ENTRE_COLETAS)
            continue
        if not rodar(l, a.dry_run):
            falhas.append(l)
    return 1 if falhas else 0


if __name__ == "__main__":
    sys.exit(main())
